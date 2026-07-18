import gevent.monkey
gevent.monkey.patch_all()
import os
import time
import json
import uuid
import threading
import re
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import telebot

# 👇 አሮጌውን አጥፍተህ ይሄንን አዲሱን እዚህ ጋ ታስገባዋለህ 👇
from telebot.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ከ config.py የጋራ ማዋቀሪያዎችንና ረዳቶችን ማስገባት
from config import (
    bot, redis, TOKEN, ADMIN_ID, WEB_APP_URL,
    telegram_auth_required, deduct_balance_safely, add_to_history, update_history_tx_status,
    set_user_state, get_user_state, clear_user_state, save_user_pin, get_user_pin # 👈 እነዚህን አዳዲሶቹን ጨምር
)


# 🎮 6ቱንም የጌሞች ብሉፕሪንቶች ማስገባት
from games.gofere_zewd import gofere_zewd_bp
from games.aviator import aviator_bp
from games.chicken import chicken_bp
from games.keno import keno_bp
from games.virtual_sports import virtual_sports_bp
from games.real_sports import real_sports_bp

server = Flask(__name__)
server.secret_key = os.environ.get("SECRET_KEY", "gashabet_secret_super_key_123")

# የ Football API ቁልፍ ከ Render Environment ያነባል
FOOTBALL_API_KEY = os.environ.get("API_FOOTBALL_KEY")

# የ SocketIO ማስተካከያ (async_mode='gevent' መሆኑን አረጋግጥ)
socketio = SocketIO(server, cors_allowed_origins="*", async_mode='gevent')

server.register_blueprint(gofere_zewd_bp)
server.register_blueprint(aviator_bp)
server.register_blueprint(chicken_bp)
server.register_blueprint(keno_bp)
server.register_blueprint(virtual_sports_bp)
server.register_blueprint(real_sports_bp)

# --- VALIDATION HELPERS ---
def is_text_only(text):
    return bool(re.match(r'^[a-zA-Z\u1200-\u137F\s\.]+$', text))

def is_number_only(text):
    return bool(re.match(r'^\+?[0-9]+$', text))

ALLOWED_BANKS = ["CBE", "Telebirr", "Awash", "Abyssinia"]





# 🚀 የተጠቃሚ መግቢያ (Start - የሪፈራል ሲስተም የተጨመረበት)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.chat.id)
    
    # 🌟 1. የሪፈራል (የጋባዥ) ID መኖሩን ማረጋገጥ 🌟
    # ቴሌግራም ላይ ሊንኩ t.me/botname?start=ref_123456 ስለሚሆን text_parts እናወጣለን
    text_parts = message.text.split()
    if len(text_parts) > 1 and text_parts[1].startswith("ref_"):
        referrer_id = text_parts[1].replace("ref_", "")
        
        # ተጠቃሚው አዲስ መሆኑን እና ራሱን እየጋበዘ አለመሆኑን ማረጋገጥ
        if referrer_id != user_id and not redis.sismember("all_users", user_id):
            # ጋባዡን መመዝገብ (ቦነሱን ዴፖዚት ሲያደርግ እንዲያገኝ)
            redis.set(f"referrer:{user_id}", referrer_id)

    # 🌟 2. ተጠቃሚውን ወደ ዳታቤዝ (all_users) መመዝገቢያ 🌟
    redis.sadd("all_users", user_id)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 ጌም ጀምር (Play)", web_app=WebAppInfo(url=WEB_APP_URL)))

    # 🌟 3. የመጋበዣ ሊንካቸውን መስሪያ 🌟
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    welcome_msg = (
        "👋 እንኳን ወደ የኛ ቤት በሰላም መጡ!\n\n"
        "ከታች ያለውን በተን ተጭነው መጫወት እና ማሸነፍ ይችላሉ።\n\n"
        "🎁 <b>ጓደኛዎን ይጋብዙ እና ቦነስ ያግኙ!</b>\n"
        "የጋበዙት ሰው ለመጀመሪያ ጊዜ ዴፖዚት ሲያደርግ የ 5% ቦነስ ያገኛሉ!\n\n"
        f"🔗 የእርስዎ መጋበዣ ሊንክ:\n<code>{ref_link}</code>"
    )

    bot.send_message(
        message.chat.id,
        welcome_msg,
        reply_markup=markup,
        parse_mode="HTML"
    )


# ==========================================
# 🛡️ አጠቃላይ የሜሴጅ መቆጣጠሪያ 
# ==========================================
@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/'))
def handle_all_text_messages(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 ጌም ጀምር (Play)", web_app=WebAppInfo(url=WEB_APP_URL)))
    
    # ፒን ሲስተም ስለጠፋ፣ ተጠቃሚው ሌላ ጽሁፍ ከጻፈ ወደ ጌሙ እንመልሰዋለን
    bot.send_message(
        message.chat.id, 
        "⚠️ እባክዎ ጌሙን ለመጫወት እና ገንዘብ ወጪ ለማድረግ ከታች ያለውን በተን ይጠቀሙ።",
        reply_markup=markup
    )

# --- ROUTES ---
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.json or {}
    user_id = data.get("user_id")
    game_mode = data.get("game_mode", "real")
    if not user_id: return jsonify({"status": "error", "message": "Missing user_id"}), 400

    if game_mode == "demo":
        balance_raw = redis.hget("users:demo_balance", user_id)
        current_balance = float(balance_raw) if balance_raw else 10000.0
    else:
        balance_raw = redis.hget("users:balance", user_id)
        current_balance = float(balance_raw) if balance_raw else 0.0
    return jsonify({"status": "success", "balance": current_balance, "mode": game_mode})

# 🚀 አዲስ የተጨመረ፡ የተቆለፈ ስልክ ካለ ወደ WebApp የሚልክ API
@server.route('/api/get_locked_phone', methods=['POST'])
@telegram_auth_required
def get_locked_phone():
    data = request.json or {}
    user_id = data.get("user_id")
    if not user_id: 
        return jsonify({"status": "error", "message": "Missing user_id"}), 400
    
    locked_phone_raw = redis.get(f"users:locked_phone:{user_id}")
    locked_phone = locked_phone_raw.decode('utf-8') if isinstance(locked_phone_raw, bytes) else str(locked_phone_raw) if locked_phone_raw else None
    
    return jsonify({"status": "success", "locked_phone": locked_phone})

# --- DEPOSIT LOGIC (Background Thread) ---
def send_photo_background(user_name, user_id, amount, tx_id, photo_data):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ አጽድቅ", callback_data=f"ok|deposit|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no|deposit|{tx_id}|{user_id}|{amount}")
    )
    caption = f"🔔 <b>አዲስ Deposit ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: <code>{user_id}</code>\n💰 መጠን: <b>{amount} ብር</b>\n🔑 TxID: <code>{tx_id}</code>"
    try:
        bot.send_photo(ADMIN_ID, photo_data, caption=caption, reply_markup=markup)
    except:
        bot.send_message(ADMIN_ID, caption, reply_markup=markup)

def is_user_banned(user_id):
    if not user_id:
        return False
    return redis.sismember("banned_users", str(user_id))

# --- DEPOSIT LOGIC ---
@server.route('/api/deposit', methods=['POST'])
@telegram_auth_required
def handle_deposit():
    user_id = request.form.get("user_id")
    
    if is_user_banned(user_id):
        return jsonify({"status": "error", "message": "አካውንትዎ ታግዷል! መገልገያዎችን መጠቀም አይችሉም።"}), 403

    user_name = request.form.get("user_name", "የሰፈር ልጅ")
    amount = float(request.form.get("amount", 0))
    receipt_file = request.files.get("receipt")
    if not user_id or amount <= 0 or not receipt_file: 
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    photo_data = receipt_file.read()
    tx_id = str(uuid.uuid4())[:8]
    redis.set(f"tx:{tx_id}", json.dumps({"user_id": user_id, "amount": amount, "type": "deposit", "status": "pending"}))
    add_to_history(user_id, {"tx_id": tx_id, "type": "ገቢ", "amount": amount, "status": "pending", "date": time.strftime("%Y-%m-%d %H:%M")})

    thread = threading.Thread(target=send_photo_background, args=(user_name, user_id, amount, tx_id, photo_data))
    thread.start()
    return jsonify({"status": "success"})

# --- WITHDRAW LOGIC (ከአድሚን ማጽደቂያ እና ከሂስትሪ ጋር የተገናኘው) ---
@server.route('/api/withdraw', methods=['POST'])
@telegram_auth_required
def handle_withdraw():
    data = request.json or {}
    user_id = data.get("user_id")
    
    if is_user_banned(user_id):
        return jsonify({"status": "error", "message": "አካውንትዎ ታግዷል! መገልገያዎችን መጠቀም አይችሉም።"}), 403

    user_name = data.get("user_name", "የሰፈር ልጅ")
    amount = float(data.get("amount", 0))
    phone = str(data.get("phone", ""))
    bank_name = data.get("bank_name", "")
    account_name = data.get("account_name", "")

    # 1. የዳታ ማረጋገጫዎች
    if not user_id or amount <= 0: return jsonify({"status": "error", "message": "የጎደለ መረጃ"}), 400
    if bank_name not in ALLOWED_BANKS: return jsonify({"status": "error", "message": "እባክዎ ትክክለኛ ባንክ ይምረጡ"}), 400
    if not is_number_only(phone): return jsonify({"status": "error", "message": "ስልክ ቁጥር ቁጥር ብቻ መሆን አለበት"}), 400
    if not is_text_only(account_name): return jsonify({"status": "error", "message": "የአካውንት ስም ፊደል ብቻ መሆን አለበት"}), 400

    # 🚀 2. የ Closed-Loop (Address Whitelisting) ሎጂክ
    locked_phone_raw = redis.get(f"users:locked_phone:{user_id}")
    locked_phone = locked_phone_raw.decode('utf-8') if isinstance(locked_phone_raw, bytes) else str(locked_phone_raw) if locked_phone_raw else None
    
    if locked_phone:
        if phone != locked_phone:
            return jsonify({"status": "error", "message": f"🔒 የደህንነት ጥበቃ! ማውጣት የሚችሉት ወደ ተመዘገበው ስልክ ({locked_phone}) ብቻ ነው።"}), 403
    else:
        redis.set(f"users:locked_phone:{user_id}", phone)

    # 3. ባላንስ ቼክ ማድረግ
    balance_raw = redis.hget("users:balance", user_id)
    current_balance = float(balance_raw) if balance_raw else 0.0
    
    if amount > current_balance:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400

    # 💸 4. ብሩን ከባላንሱ ላይ በጊዜያዊነት መቀነስ (የአድሚን ማጽደቂያ ስለሚጠብቅ)
    redis.hincrbyfloat("users:balance", user_id, -amount)

    # 🔑 5. ልዩ TxID መፍጠር እና በ Redis መመዝገብ (ለአድሚን ሲስተሙ በጣም ወሳኝ ነው!)
    tx_id = str(uuid.uuid4())[:8]
    redis.set(f"tx:{tx_id}", json.dumps({"user_id": user_id, "amount": amount, "type": "withdraw", "status": "pending"}))

    # 📝 6. ሂስትሪ ላይ በጋራ ረዳት (add_to_history) መመዝገብ 
    # (ይህ ካልሆነ update_history_tx_status() በትክክል ሊያገኘው አይችልም!)
    add_to_history(user_id, {
        "tx_id": tx_id,
        "type": "ወጪ", # 👈 ፍሮንትኤንዱ በምስሉ ላይ እንዲያነበው "ወጪ" መሆን አለበት
        "amount": amount,
        "status": "pending",
        "date": time.strftime("%Y-%m-%d %H:%M")
    })

        # 📩 7. ለአድሚን የማጽደቂያ መልዕክት ከነ በተኑ መላክ 🚀
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ ክፍያ ፈጽሜያለሁ (አጽድቅ)", callback_data=f"ok|withdraw|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ሰርዝ (ገንዘቡን መልስ)", callback_data=f"no|withdraw|{tx_id}|{user_id}|{amount}")
    )
    
    admin_msg = (
        f"🚨 <b>አዲስ የውጪ (Withdraw) ጥያቄ</b>\n\n"
        f"👤 ስም: {user_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"🏦 ባንክ: <b>{bank_name}</b>\n"
        f"👤 አካውንት ስም: <b>{account_name}</b>\n"
        f"📱 ስልክ: <code>{phone}</code>\n"
        f"💰 መጠን: <b>{amount} ብር</b>\n"
        f"🔑 TxID: <code>{tx_id}</code>"
    )
    
    # እዚህ ጋር try-except አውጥተነዋል ስህተት ካለ በግልጽ ተርሚናል ላይ እንዲያሳይህ!
    bot.send_message(int(ADMIN_ID), admin_msg, reply_markup=markup, parse_mode="HTML")

    # 📩 8. ለተጠቃሚው ማሳወቂያ መላክ
    try:
        success_msg = f"✅ የ <b>{amount} ብር</b> ወጪ ጥያቄዎ በተሳካ ሁኔታ ተቀብለናል!\n\n🏦 ባንክ: {bank_name}\n👤 አካውንት: {account_name}\n📱 ስልክ: {phone}\n\n⏳ በአድሚን ተረጋግጦ ክፍያው በቅርቡ ይላክሎታል።"
        bot.send_message(user_id, success_msg, parse_mode="HTML")
    except:
        pass

    return jsonify({"status": "success", "message": "ጥያቄዎ በተሳካ ሁኔታ ተልኳል!"})



# --- CALLBACK SYSTEM (ከሂስትሪ ማስተካከያ ጋር የተጣጣመው) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("ok") or call.data.startswith("no"))
def process_admin_action(call):
    try:
        parts = call.data.split("|")
        action = parts[0]
        tx_type = parts[1]
        tx_id = parts[2]
        user_id = parts[3]
        amount = float(parts[4])

        tx_data_raw = redis.get(f"tx:{tx_id}")
        if not tx_data_raw:
            bot.answer_callback_query(call.id, "⚠️ ይህ ትራንዛክሽን ቀደም ብሎ ተሰርዟል ወይም አልተገኘም!")
            return

        tx_data = json.loads(tx_data_raw)
        if tx_data.get("status") != "pending":
            bot.answer_callback_query(call.id, f"⚠️ ይህ ጥያቄ ቀደም ብሎ {tx_data.get('status')} ሆኗል!")
            return

        if tx_type == "deposit":
            if action == "ok":
                # 1. ዴፖዚቱን ወደ "Total Deposits" እንጨምራለን (ትክክለኛ ብር ብቻ)
                redis.incrbyfloat("stats:total_deposits", amount)
                
                # 2. የመጀመሪያ ዴፖዚት መሆኑን ማረጋገጥ
                is_first_deposit = redis.setnx(f"has_deposited:{user_id}", "1")
                
                if is_first_deposit in (1, True):
                    # 🎁 የ 10% የመጀመሪያ ጊዜ ቦነስ
                    user_bonus = amount * 0.10
                    total_to_add = amount + user_bonus
                    redis.hincrbyfloat("users:balance", user_id, total_to_add)
                    
                    success_msg = f"✅ <b>ዴፖዚትዎ ጸድቋል!</b>\n\n💰 ገቢ መጠን: <b>{amount} ብር</b>\n🎁 የ 10% የመጀመሪያ ጊዜ ቦነስ: <b>{user_bonus} ብር</b>\n\n💵 በአጠቃላይ <b>{total_to_add} ብር</b> ወደ አካውንትዎ ገብቷል።"
                    bot.send_message(user_id, success_msg, parse_mode="HTML")
                    
                    # 🎁 የጋባዥ (Referrer) የ 5% ቦነስ
                    referrer_id_raw = redis.get(f"referrer:{user_id}")
                    if referrer_id_raw:
                        referrer_id = referrer_id_raw.decode('utf-8') if isinstance(referrer_id_raw, bytes) else str(referrer_id_raw)
                        referrer_bonus = amount * 0.05
                        redis.hincrbyfloat("users:balance", referrer_id, referrer_bonus)
                        try:
                            ref_msg = f"🎉 <b>እንኳን ደስ አለዎት!</b>\n\nበእርስዎ ሊንክ የመጣ ሰው ለመጀመሪያ ጊዜ ዴፖዚት ስላደረገ የ 5% (<b>{referrer_bonus} ብር</b>) ቦነስ አግኝተዋል! ብሩ ወደ ባላንስዎ ተደምሯል።"
                            bot.send_message(referrer_id, ref_msg, parse_mode="HTML")
                        except:
                            pass
                            
                else:
                    # 🔄 መደበኛ ዴፖዚት (ቦነስ የለውም)
                    redis.hincrbyfloat("users:balance", user_id, amount)
                    bot.send_message(user_id, f"✅ <b>ዴፖዚትዎ ጸድቋል!</b>\n💰 መጠን: <b>{amount} ብር</b> ወደ አካውንትዎ ገብቷ።", parse_mode="HTML")
                
                # 3. የትራንዛክሽን ሁኔታን ማደስ
                tx_data["status"] = "approved"
                update_history_tx_status(user_id, tx_id, "approved")
                bot.answer_callback_query(call.id, "✅ በተሳካ ሁኔታ ጸድቋል!")
                try:
                    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=call.message.caption + "\n\n🟢 <b>[የጸደቀ ገቢ]</b>", parse_mode="HTML")
                except:
                    pass
                
            else:
                # ❌ ውድቅ ሲደረግ
                tx_data["status"] = "rejected"
                update_history_tx_status(user_id, tx_id, "rejected")
                bot.send_message(user_id, f"❌ የ <b>{amount} ብር</b> ገቢ ጥያቄዎ በባለሙያ ውድቅ ተደርጓል።", parse_mode="HTML")
                bot.answer_callback_query(call.id, "❌ ውድቅ ተደርጓል!")
                try:
                    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=call.message.caption + "\n\n🔴 <b>[ውድቅ የተደረገ ገቢ]</b>", parse_mode="HTML")
                except:
                    pass

        elif tx_type == "withdraw":
            if action == "ok":
                # 🟢 ወጪ ጥያቄው ሲጸድቅ
                redis.incrbyfloat("stats:total_withdrawals", amount)
                tx_data["status"] = "approved"
                
                # በሂስትሪው ውስጥ ያለውን ሁኔታ ወደ "approved" መቀየር
                update_history_tx_status(user_id, tx_id, "approved")
                
                bot.send_message(user_id, f"✅ የ <b>{amount} ብር</b> ወጪ (Withdraw) ጥያቄዎ ተከፍሏል!", parse_mode="HTML")
                bot.answer_callback_query(call.id, "✅ ክፍያ መፈጸሙ ተረጋግጧል!")
                try:
                    # መልዕክቱ Text ስለሆነ edit_message_text እንጠቀማለን
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n🟢 <b>[ክፍያ የተፈጸመለት]</b>", parse_mode="HTML")
                except:
                    pass
            else:
                # 🔴 ወጪ ጥያቄው ውድቅ ሲደረግ (ገንዘቡ ይመለሳል)
                redis.hincrbyfloat("users:balance", user_id, amount)
                tx_data["status"] = "refunded"
                
                # በሂስትሪው ውስጥ ያለውን ሁኔታ ወደ "refunded" መቀየር
                update_history_tx_status(user_id, tx_id, "refunded")
                
                bot.send_message(user_id, f"❌ የ <b>{amount} ብር</b> ወጪ ጥያቄዎ ተሰርዟል! ገንዘቡ ወደ ባላንስዎ ተመልሷል (Refunded)።", parse_mode="HTML")
                bot.answer_callback_query(call.id, "❌ ወጪው ተሰርዟል፣ ገንዘቡ ተመልሷል!")
                try:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n🔴 <b>[የተሰረዘ እና የተመለሰ (Refunded)]</b>", parse_mode="HTML")
                except:
                    pass

        # የዋናውን ትራንዛክሽን ዳታ በ JSON መልክ መልሶ ማስቀመጥ
        redis.set(f"tx:{tx_id}", json.dumps(tx_data))
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"⚠️ ስህተት፡ {str(e)}")




# ==========================================
# 🛡️ አዲሱ የአድሚን መቆጣጠሪያ API ROUTES (ተሻሽሏል)
# ==========================================

@server.route('/admin-panel')
def admin_panel():
    return render_template('admin.html')

@server.route('/api/admin/get_dashboard_data', methods=['POST'])
def get_dashboard_data():
    data = request.json or {}
    admin_id = str(data.get("admin_id"))

    # 1. ጥብቅ የደህንነት ማረጋገጫ (አድሚን ካልሆነ በፍጹም አያስገባም)
    if admin_id != str(ADMIN_ID): 
        return jsonify({"status": "error", "message": "ያልተፈቀደ የደህንነት ጥሰት ሙከራ!"}), 403

    # 2. የተጠቃሚዎችን ባላንስ ከ Redis ማምጣት
    balances_raw = redis.hgetall("users:balance")

    users_list = []
    total_system_balance = 0.0

    for uid_raw, bal_raw in balances_raw.items():
        uid = uid_raw.decode('utf-8') if isinstance(uid_raw, bytes) else str(uid_raw)
        bal = float(bal_raw.decode('utf-8') if isinstance(bal_raw, bytes) else bal_raw)
        
        users_list.append({"user_id": uid, "balance": bal})
        total_system_balance += bal

    # 3. 🌟 ትክክለኛው የጠቅላላ ተጠቃሚዎች ቆጠራ 🌟
    # (ይህ ቦቱን start ያደረገውን ሁሉ ይቆጥራል)
    total_users = redis.scard("all_users") 
    
    # ምናልባት ማንም start አላደረገም ብሎ 0 ካመጣ፣ ባላንስ ያላቸውን ሰዎች ብዛት እንዲወስድ 
    if total_users == 0:
        total_users = len(users_list)

    banned_users_count = redis.scard("banned_users")

    # 4. ጠቅላላ ገቢ፣ ወጪ እና የተጣራ ትርፍ ስሌት
    total_dep = float(redis.get("stats:total_deposits") or 0.0)
    total_wd = float(redis.get("stats:total_withdrawals") or 0.0)
    
    # 🌟 የተጣራ ትርፍ = አጠቃላይ ገቢ - አጠቃላይ ወጪ - በደንበኞች እጅ ያለ ቀሪ ሂሳብ
    net_profit = total_dep - total_wd - total_system_balance

    # 5. ዳታውን ወደ ዳሽቦርዱ (Frontend) መላክ
    return jsonify({
        "status": "success",
        "stats": {
            "total_users": total_users,
            "banned_users": banned_users_count,
            "total_deposits": total_dep,
            "total_withdrawals": total_wd,
            "net_profit": net_profit,
            "total_user_balances": total_system_balance
        },
        "users": users_list
    })


# ==========================================
# 🤖 የቴሌግራም አድሚን ቦት ትዕዛዝ
# ==========================================
@bot.message_handler(commands=['admin'])
def send_admin_panel(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📊 የአድሚን ፓነል ክፈት", web_app=WebAppInfo(url=f"{WEB_APP_URL}/admin-panel")))
        bot.send_message(message.chat.id, "🤖 <b>እንኳን ወደ 'የኛ ቤት' መቆጣጠሪያ ፓነል መጡ!</b>", parse_mode="HTML", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "❌ ይህ ትዕዛዝ ለአድሚን ብቻ የተፈቀደ ነው!")


# ==========================================
# 🔌 WEBHOOK & SERVER START
# ==========================================
@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

try:
    bot.remove_webhook()
    time.sleep(0.1)
    bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
except: pass

if __name__ == "__main__":
    socketio.run(server, host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
