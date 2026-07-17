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





# ==========================================
# 🚀 የተጠቃሚ መግቢያ (Start & PIN Setup)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # ተጠቃሚው ፒን አለው ወይ ብለን ቼክ እናደርጋለን
    existing_pin = get_user_pin(user_id)
    
    if not existing_pin:
        # ፒን ከሌለው State ወደ 'waiting_for_pin_1' እንቀይራለን
        set_user_state(user_id, "waiting_for_pin_1")
        
        bot.send_message(
            message.chat.id, 
            "👋 እንኳን በደህና መጡ!\n\n🔒 ለገንዘብ ደህንነትዎ እባክዎ አዲስ ባለ 4 ዲጂት ፒን ይፍጠሩ (ቁጥር ብቻ ይላኩ):"
        )
    else:
        # ፒን ካለው ቀጥታ ወደ ጌም ወይም ዋናው ሜኑ ይገባል
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🎮 ጌም ጀምር (Play)", web_app=WebAppInfo(url=WEB_APP_URL)))
        
        bot.send_message(
            message.chat.id,
            "👋 እንኳን ወደ የኛ ቤት በድጋሚ መጡ!\nከታች ያለውን በተን ተጭነው መጫወት ይችላሉ።",
            reply_markup=markup
        )




# ==========================================
# 🛡️ አጠቃላይ የሜሴጅ እና የፒን መቆጣጠሪያ (Message Handler)
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_all_text_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    chat_id = message.chat.id
    message_id = message.message_id
    
    # ተጠቃሚው በአሁን ሰዓት ምን እየጠበቀ እንደሆነ ቼክ እናደርጋለን
    state = get_user_state(user_id)
    
    # -----------------------------------------
    # 1. አዲስ ፒን እየፈጠረ ከሆነ (ደረጃ 1)
    # -----------------------------------------
    if state == "waiting_for_pin_1":
        # 🔒 ደህንነት: ተጠቃሚው የላከውን ፒን የያዘ ሜሴጅ ወዲያውኑ እናጠፋለን
        try: bot.delete_message(chat_id, message_id)
        except: pass
        
        # ፒኑ ባለ 4 ዲጂት ቁጥር መሆኑን ማረጋገጥ
        if not text.isdigit() or len(text) != 4:
            bot.send_message(chat_id, "⚠️ ስህተት! እባክዎ ትክክለኛ ባለ 4 ዲጂት ቁጥር ብቻ ያስገቡ (ለምሳሌ: 1234):")
            return
            
        # ቁጥሩ ትክክል ከሆነ በጊዜያዊነት (Temp) እናስቀምጠዋለን
        redis.setex(f"temp_pin:{user_id}", 900, text)
        
        # State ወደ ማረጋገጫ (ደረጃ 2) እንቀይራለን
        set_user_state(user_id, "waiting_for_pin_2")
        bot.send_message(chat_id, "✅ ጥሩ! ለማረጋገጥ እባክዎ ፒንዎን እንደገና ይጻፉት:")
        
        # -----------------------------------------
    # 2. ፒኑን እያረጋገጠ ከሆነ (ደረጃ 2)
    # -----------------------------------------
    elif state == "waiting_for_pin_2":
        # 🔒 ደህንነት: ይሄኛውንም ሜሴጅ ወዲያውኑ እናጠፋለን
        try: bot.delete_message(chat_id, message_id)
        except: pass
        
        # መጀመሪያ ያስገባውን ጊዜያዊ ፒን ከዳታቤዝ እናመጣለን
        temp_pin_raw = redis.get(f"temp_pin:{user_id}")
        
        # ስህተቱን ያስወገደው ትክክለኛ ኮድ
        temp_pin = str(temp_pin_raw) if temp_pin_raw else None
        
        if text == temp_pin:
            # ፒኖቹ ከተመሳሰሉ በቋሚነት ሴቭ እናደርጋለን
            save_user_pin(user_id, text)
            
            # ስራ ስለጨረሰ State እና ጊዜያዊ ፒኑን እናጸዳለን
            clear_user_state(user_id)
            redis.delete(f"temp_pin:{user_id}")
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🎮 ጌም ጀምር (Play)", web_app=WebAppInfo(url=WEB_APP_URL)))
            bot.send_message(
                chat_id, 
                "🎉 ፒንዎ በተሳካ ሁኔታ ተፈጥሯል!\n\n(ፒንዎ የሚጠየቁት ገንዘብ ወጪ ሲያደርጉ ብቻ ነው)\nከታች ያለውን በተን በመጫን መጫወት መጀመር ይችላሉ።", 
                reply_markup=markup
            )
        else:
            # ካልተመሳሰሉ ወደ መጀመሪያው እንመልሰዋለን
            set_user_state(user_id, "waiting_for_pin_1")
            bot.send_message(chat_id, "❌ ፒኑ አልተመሳሰለም! እባክዎ አዲስ ባለ 4 ዲጂት ፒን ከመጀመሪያው ይፍጠሩ:")


    # -----------------------------------------
    # 3. የገንዘብ ማውጣት ፒን እያረጋገጠ ከሆነ
    # -----------------------------------------
    elif state == "waiting_for_withdraw_pin":
        # 🔒 ደህንነት: የፒን ሜሴጁን ወዲያው እናጠፋዋለን
        try: bot.delete_message(chat_id, message_id)
        except: pass
        
        # ትክክለኛውን ፒን ከዳታቤዝ እናመጣለን
        saved_pin = get_user_pin(user_id)
        
        if text == saved_pin:
            # ፒኑ ትክክል ነው! የክፍያ መረጃውን ከጊዜያዊ ዳታቤዙ እናወጣለን
            wd_data_raw = redis.get(f"temp_withdraw:{user_id}")
            if not wd_data_raw:
                bot.send_message(chat_id, "⚠️ የጥያቄው ጊዜ (5 ደቂቃ) አልፏል ወይም ተሰርዟል። እባክዎ እንደገና ከ WebApp ላይ ይሞክሩ።")
                clear_user_state(user_id)
                return
                
            wd_data = json.loads(wd_data_raw)
            amount = wd_data["amount"]
            
            # አሁን ባላንሱን እንቀንሳለን (Deduct እናደርጋለን)
            deduct_status = deduct_balance_safely(user_id, amount, "real")
            if deduct_status == "INSUFFICIENT":
                bot.send_message(chat_id, "❌ በቂ ባላንስ የለዎትም!")
                clear_user_state(user_id)
                return
                
            # ትራንዛክሽን ሪከርድ እንፈጥራለን
            tx_id = str(uuid.uuid4())[:8]
            redis.set(f"tx:{tx_id}", json.dumps({"user_id": user_id, "amount": amount, "type": "withdraw", "status": "pending"}))
            add_to_history(user_id, {"tx_id": tx_id, "type": "ወጪ", "amount": amount, "status": "pending", "date": time.strftime("%Y-%m-%d %H:%M")})
            
            # ለአድሚን ጥያቄውን እንልካለን
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("✅ ተከፍሏል", callback_data=f"ok|withdraw|{tx_id}|{user_id}|{amount}"),
                InlineKeyboardButton("❌ ሰርዝ", callback_data=f"no|withdraw|{tx_id}|{user_id}|{amount}")
            )
            msg = f"💸 <b>አዲስ Withdraw ጥያቄ (ፒን የተረጋገጠ)</b>\n\n👤 ስም: {wd_data['user_name']}\n🏦 ባንክ: {wd_data['bank_name']}\n👤 የአካውንት ስም: {wd_data['account_name']}\n💳 ስልክ/አካውንት: <code>{wd_data['phone']}</code>\n💰 መጠን: <b>{amount} ብር</b>"
            bot.send_message(ADMIN_ID, msg, reply_markup=markup, parse_mode="HTML")
            
            # ለተጠቃሚው ማረጋገጫ እንልካለን
            bot.send_message(chat_id, f"✅ የ <b>{amount} ብር</b> ወጪ ጥያቄዎ በተሳካ ሁኔታ ተረጋግጧል! ክፍያው ሲፈጸም መልእክት ይደርሶታል።", parse_mode="HTML")
            
            # ስራ ስለጨረስን State እና ጊዜያዊ ዳታውን እናጠፋለን
            clear_user_state(user_id)
            redis.delete(f"temp_withdraw:{user_id}")
            
        else:
            # ፒኑ ከተሳሳተ
            bot.send_message(chat_id, "❌ የተሳሳተ ፒን! እባክዎ ትክክለኛውን ፒን እንደገና ያስገቡ:")
            # State አንቀይርም፣ ተጠቃሚው እንደገና እንዲሞክር እንጠብቀዋለን



# -----------------------------------------
# 4. የፒን መጥፋት (Forgot PIN) - ስልክ ቁጥር ሲያጋራ
# -----------------------------------------
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    user_id = message.from_user.id
    state = get_user_state(user_id)
    
    # ተጠቃሚው "ፒን ረሳሁ" ብሎ በሂደት ላይ ከሆነ
    if state == "waiting_for_contact":
        contact_phone = message.contact.phone_number
        # እዚህ ጋር የተላከውን ስልክ ቁጥር ከዳታቤዝ ጋር ማነፃፀር ትችላለህ
        # ለምሳሌ: የተጠቃሚው ስልክ ዳታቤዝ ላይ ካለ
        # (አንተ ጋር የተጠቃሚው ስልክ Redis ላይ ካለ እዚህ ያንን ቼክ ታደርጋለህ)
        
        # ስኬታማ ከሆነ ወደ አዲስ ፒን መፍጠሪያ እንወስደዋለን
        set_user_state(user_id, "waiting_for_pin_1")
        bot.send_message(message.chat.id, "✅ ማንነትዎ ተረጋግጧል! አሁን አዲስ ባለ 4 ዲጂት ፒን ይፍጠሩ:")
    else:
        bot.send_message(message.chat.id, "⚠️ አሁን ይህንን ማድረግ አይጠበቅብዎትም።")


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

@server.route('/api/get_user_history', methods=['POST'])
@telegram_auth_required
def get_user_history():
    data = request.json or {}
    user_id = data.get("user_id")
    if not user_id: return jsonify({"status": "error", "message": "Missing user_id"}), 400
    try:
        raw_history = redis.lrange(f"history:{user_id}", 0, -1) or []
    except Exception as e:
        if "WRONGTYPE" in str(e):
            redis.delete(f"history:{user_id}")
            raw_history = []
        else: return jsonify({"status": "error", "message": "የዳታቤዝ ስህተት"}), 500
    return jsonify({"status": "success", "history": [json.loads(item) for item in raw_history]})

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

# --- WITHDRAW LOGIC (በፒን የተሻሻለ) ---
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

    # የዳታ ማረጋገጫዎች
    if not user_id or amount <= 0: return jsonify({"status": "error", "message": "የጎደለ መረጃ"}), 400
    if bank_name not in ALLOWED_BANKS: return jsonify({"status": "error", "message": "እባክዎ ትክክለኛ ባንክ ይምረጡ"}), 400
    if not is_number_only(phone): return jsonify({"status": "error", "message": "ስልክ ቁጥር ቁጥር ብቻ መሆን አለበት"}), 400
    if not is_text_only(account_name): return jsonify({"status": "error", "message": "የአካውንት ስም ፊደል ብቻ መሆን አለበት"}), 400

    # ተጠቃሚው በቂ ባላንስ እንዳለው ቼክ እናደርጋለን እንጂ አንቀንሰውም (deduct አናደርግም)
    balance_raw = redis.hget("users:balance", user_id)
    current_balance = float(balance_raw) if balance_raw else 0.0
    
    if amount > current_balance:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400

    # 1. መረጃውን ለ 5 ደቂቃ በጊዜያዊነት Redis ላይ እናስቀምጣለን
    withdraw_data = {
        "user_name": user_name, "amount": amount, "phone": phone, 
        "bank_name": bank_name, "account_name": account_name
    }
    redis.setex(f"temp_withdraw:{user_id}", 300, json.dumps(withdraw_data))
    
    # 2. የተጠቃሚውን State ወደ ፒን መጠየቂያ እንቀይራለን
    set_user_state(user_id, "waiting_for_withdraw_pin")
    
    # 3. ለተጠቃሚው ፒን እንዲያስገባ ሜሴጅ እንልካለን
    try:
        bot.send_message(user_id, f"💸 የ <b>{amount} ብር</b> ወጪ ጥያቄ ቀርቧል።\n\n🔒 ለማረጋገጥ እባክዎ የ 4 ዲጂት ፒንዎን ያስገቡ:", parse_mode="HTML")
    except:
        pass
        
    # 4. ለ WebApp ስኬታማ መሆኑን እንነግረዋለን
    return jsonify({"status": "success", "message": "እባክዎ ቴሌግራም ላይ ፒንዎን በማስገባት ያረጋግጡ!"})

# --- CALLBACK SYSTEM ---
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
                redis.hincrbyfloat("users:balance", user_id, amount)
                redis.incrbyfloat("stats:total_deposits", amount)
                tx_data["status"] = "approved"
                update_history_tx_status(user_id, tx_id, "approved")
                bot.send_message(user_id, f"✅ <b>ዴፖዚትዎ ጸድቋል!</b>\n💰 መጠን: <b>{amount} ብር</b> ወደ አካውንትዎ ገብቷል።")
                bot.answer_callback_query(call.id, "✅ በተሳካ ሁኔታ ጸድቋል!")
                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=call.message.caption + "\n\n🟢 <b>[የጸደቀ ገቢ]</b>")
            else:
                tx_data["status"] = "rejected"
                update_history_tx_status(user_id, tx_id, "rejected")
                bot.send_message(user_id, f"❌ የ <b>{amount} ብር</b> ገቢ ጥያቄዎ በባለሙያ ውድቅ ተደርጓል።")
                bot.answer_callback_query(call.id, "❌ ውድቅ ተደርጓል!")
                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=call.message.caption + "\n\n🔴 <b>[ውድቅ የተደረገ ገቢ]</b>")

        elif tx_type == "withdraw":
            if action == "ok":
                redis.incrbyfloat("stats:total_withdrawals", amount)
                tx_data["status"] = "approved"
                update_history_tx_status(user_id, tx_id, "approved")
                bot.send_message(user_id, f"✅ የ <b>{amount} ብር</b> ወጪ (Withdraw) ጥያቄዎ ተከፍሏል!")
                bot.answer_callback_query(call.id, "✅ ክፍያ መፈጸሙ ተረጋግጧል!")
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n🟢 <b>[ክፍያ የተፈጸመለት]</b>")
            else:
                redis.hincrbyfloat("users:balance", user_id, amount)
                tx_data["status"] = "refunded" 
                update_history_tx_status(user_id, tx_id, "refunded") 
                bot.send_message(user_id, f"❌ የ <b>{amount} ብር</b> ወጪ ጥያቄዎ ተሰርዟል! ገንዘቡ ወደ ባላንስዎ ተመልሷል (Refunded)።")
                bot.answer_callback_query(call.id, "❌ ወጪው ተሰርዟል፣ ገንዘቡ ተመልሷል!")
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n🔴 <b>[የተሰረዘ እና የተመለሰ (Refunded)]</b>")

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

    # የገባው ሰው አድሚን መሆኑን ማረጋገጫ
    if admin_id != str(ADMIN_ID): 
        return jsonify({"status": "error", "message": "ያልተፈቀደ የደህንነት ጥሰት ሙከራ!"}), 403

    # የሁሉንም ተጠቃሚዎች ባላንስ በአንዴ ማምጣት
    balances_raw = redis.hgetall("users:balance")

    users_list = []
    total_system_balance = 0.0

    # 👇 እዚህ ጋ ያለው ስፔስ ተስተካክሏል (ከላይኛው መስመር ጋር እኩል ሆኗል)
    for uid_raw, bal_raw in balances_raw.items():
        # ዳታው በ string ከመጣ ቀጥታ ይጠቀማል፣ በ bytes ከመጣ ደግሞ decode ያደርጋል
        uid = uid_raw.decode('utf-8') if isinstance(uid_raw, bytes) else str(uid_raw)
        bal = float(bal_raw.decode('utf-8') if isinstance(bal_raw, bytes) else bal_raw)

        users_list.append({"user_id": uid, "balance": bal})
        total_system_balance += bal


    total_users = len(users_list)
    banned_users_count = redis.scard("banned_users")

    # ገቢ፣ ወጪ እና የተጣራ ትርፍ
    total_dep = float(redis.get("stats:total_deposits") or 0.0)
    total_wd = float(redis.get("stats:total_withdrawals") or 0.0)
    net_profit = total_dep - total_wd
    
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

@server.route('/api/admin/user_action', methods=['POST'])
def admin_user_action():
    data = request.json or {}
    admin_id = str(data.get("admin_id"))
    target_user_id = str(data.get("target_user_id"))
    action = data.get("action") 
    
    if admin_id != str(ADMIN_ID): 
        return jsonify({"status": "error", "message": "ያልተፈቀደ ሙከራ!"}), 403
        
    if not target_user_id:
        return jsonify({"status": "error", "message": "የተጠቃሚ ID አልተገኘም!"}), 400

    if action == "ban":
        redis.sadd("banned_users", target_user_id)
        try: bot.send_message(target_user_id, "⚠️ <b>መለያዎ (Account) በህግ ጥሰት ምክንያት ታግዷል!</b>", parse_mode="HTML")
        except: pass
        return jsonify({"status": "success", "message": "ተጠቃሚው በተሳካ ሁኔታ ታግዷል!"})
        
    elif action == "unban":
        redis.srem("banned_users", target_user_id)
        try: bot.send_message(target_user_id, "🎉 <b>የመለያዎ እገዳ ተነስቷል!</b>\nአሁን መጫወት ይችላሉ።", parse_mode="HTML")
        except: pass
        return jsonify({"status": "success", "message": "የተጠቃሚው እገዳ ተነስቷል!"})
        
    elif action == "adjust_balance":
        amount = float(data.get("amount", 0))
        # ⚠️ ዋናው ጥበቃ፦ አሁን ያለውን ብር ቼክ ማድረግ
        current_balance = float(redis.hget("users:balance", target_user_id) or 0.0)
        new_balance = current_balance + amount
        
        if new_balance < 0:
            return jsonify({"status": "error", "message": f"ስህተት! የተጠቃሚው ባላንስ {current_balance} ብር ብቻ ነው። ወደ ኔጌቲቭ ማውረድ አይቻልም!"}), 400
            
        redis.hset("users:balance", target_user_id, new_balance)
        
        # 👇 ይሄ አዲሱ ወደ ሂስቶሪ (History) መጨመሪያ ኮድ ነው 👇
        import time
        import uuid
        tx_type = "ገቢ" if amount > 0 else "ወጪ"
        abs_amount = abs(amount)
        tx_id = "ADM-" + str(uuid.uuid4())[:5] # አድሚን መሆኑን ለመለየት ADM- ይጨመራል
        
        history_data = {
            "tx_id": tx_id,
            "type": tx_type,
            "amount": abs_amount,
            "status": "APPROVED", # በአድሚን ስለተደረገ ቀጥታ ጸድቋል (APPROVED)
            "date": time.strftime("%Y-%m-%d %H:%M")
        }
        add_to_history(target_user_id, history_data)
        # 👆 የሂስቶሪ ኮድ እዚህ ያልቃል 👆

        try:
            sign = "+" if amount > 0 else ""
            bot.send_message(target_user_id, f"🔔 <b>የሂሳብ ማስተካከያ!</b>\nባላንስዎ ላይ <b>{sign}{amount} ብር</b> በአድሚን ተስተካክሏል።", parse_mode="HTML")
        except: pass
        return jsonify({"status": "success", "message": "ባላንስ በተሳካ ሁኔታ ተስተካክሏል!"})

    return jsonify({"status": "error", "message": "የማይታወቅ ትዕዛዝ!"}), 400


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



@bot.message_handler(commands=['settings'])
def settings_menu(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔑 ፒን ረሳሁ", callback_data="forgot_pin"))
    bot.send_message(message.chat.id, "⚙️ የሴቲንግ ምርጫዎች:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "forgot_pin")
def handle_forgot_pin(call):
    user_id = call.from_user.id
    set_user_state(user_id, "waiting_for_contact")
    
    # Inline የነበረውን ወደ Reply Keyboard ቀይረነዋል
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📞 ስልክ ቁጥር አጋራ", request_contact=True))
    
    bot.send_message(call.message.chat.id, "ማንነትዎን ለማረጋገጥ እባክዎ ከታች ያለውን በተን ተጭነው ስልክ ቁጥርዎን ያጋሩ:", reply_markup=markup)

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
