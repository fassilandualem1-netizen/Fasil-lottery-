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
from telebot.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# ከ config.py የጋራ ማዋቀሪያዎችንና ረዳቶችን ማስገባት
import config
from config import (
    bot, redis, TOKEN, ADMIN_ID, WEB_APP_URL,
    telegram_auth_required, deduct_balance_safely, add_to_history, update_history_tx_status
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
    # እንግሊዘኛ፣ አማርኛ፣ ስፔስ እና ነጥብ(.) ይፈቅዳል
    return bool(re.match(r'^[a-zA-Z\u1200-\u137F\s\.]+$', text))

def is_number_only(text):
    # የ + ምልክት እና ቁጥሮችን ብቻ ይፈቅዳል
    return bool(re.match(r'^\+?[0-9]+$', text))

ALLOWED_BANKS = ["CBE", "Telebirr", "Awash", "Abyssinia"]

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

# --- 🚫 ተጠቃሚው የታገደ መሆኑን መፈተሻ ረዳት ፈንክሽን ---
def is_user_banned(user_id):
    if not user_id:
        return False
    return redis.sismember("banned_users", str(user_id))

# --- DEPOSIT LOGIC ---
@server.route('/api/deposit', methods=['POST'])
@telegram_auth_required
def handle_deposit():
    user_id = request.form.get("user_id")
    
    # 🚨 የታገደ መሆኑን መፈተሻ (ከሁሉም በፊት ይፈትሻል)
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

# --- WITHDRAW LOGIC ---
@server.route('/api/withdraw', methods=['POST'])
@telegram_auth_required
def handle_withdraw():
    data = request.json or {}
    user_id = data.get("user_id")
    
    # 🚨 የታገደ መሆኑን መፈተሻ (ከሁሉም በፊት ይፈትሻል)
    if is_user_banned(user_id):
        return jsonify({"status": "error", "message": "አካውንትዎ ታግዷል! መገልገያዎችን መጠቀም አይችሉም።"}), 403

    user_name = data.get("user_name", "የሰፈር ልጅ")
    amount = float(data.get("amount", 0))
    phone = str(data.get("phone", ""))
    bank_name = data.get("bank_name", "")
    account_name = data.get("account_name", "")

    if not user_id or amount <= 0: return jsonify({"status": "error", "message": "የጎደለ መረጃ"}), 400
    if bank_name not in ALLOWED_BANKS: return jsonify({"status": "error", "message": "እባክዎ ትክክለኛ ባንክ ይምረጡ"}), 400
    if not is_number_only(phone): return jsonify({"status": "error", "message": "ስልክ ቁጥር ቁጥር ብቻ መሆን አለበት"}), 400
    if not is_text_only(account_name): return jsonify({"status": "error", "message": "የአካውንት ስም ፊደል ብቻ መሆን አለበት"}), 400

    deduct_status = deduct_balance_safely(user_id, amount, "real")
    if deduct_status == "INSUFFICIENT": return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400

    tx_id = str(uuid.uuid4())[:8]
    redis.set(f"tx:{tx_id}", json.dumps({"user_id": user_id, "amount": amount, "type": "withdraw", "status": "pending"}))
    add_to_history(user_id, {"tx_id": tx_id, "type": "ወጪ", "amount": amount, "status": "pending", "date": time.strftime("%Y-%m-%d %H:%M")})

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ ተከፍሏል", callback_data=f"ok|withdraw|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ሰርዝ", callback_data=f"no|withdraw|{tx_id}|{user_id}|{amount}")
    )
    msg = f"💸 <b>አዲስ Withdraw ጥያቄ</b>\n\n👤 ስም: {user_name}\n🏦 ባንክ: {bank_name}\n👤 የአካውንት ስም: {account_name}\n💳 ስልክ/አካውንት: <code>{phone}</code>\n💰 መጠን: <b>{amount} ብር</b>"
    bot.send_message(ADMIN_ID, msg, reply_markup=markup)
    return jsonify({"status": "success"})

# --- 🔥 ሙሉ በሙሉ የሚሰራ የCALLBACK ሲስተም ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("ok") or call.data.startswith("no"))
def process_admin_action(call):
    try:
        parts = call.data.split("|")
        action = parts[0]       # ok ወይም no
        tx_type = parts[1]      # deposit ወይም withdraw
        tx_id = parts[2]
        user_id = parts[3]
        amount = float(parts[4])

        # ድጋሚ ክሊክ እንዳይደረግ ከሬዲስ ላይ ቼክ ማድረግ
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
                
                # 📊 አዲሱ የትርፍ መመዝገቢያ (የአድሚን ዳሽቦርድ ላይ የሚታየው)
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
                # 📊 አዲሱ የትርፍ መመዝገቢያ (የአድሚን ዳሽቦርድ ላይ የሚታየው)
                redis.incrbyfloat("stats:total_withdrawals", amount)
                
                tx_data["status"] = "approved"
                update_history_tx_status(user_id, tx_id, "approved")
                bot.send_message(user_id, f"✅ የ <b>{amount} ብር</b> ወጪ (Withdraw) ጥያቄዎ ተከፍሏል!")
                bot.answer_callback_query(call.id, "✅ ክፍያ መፈጸሙ ተረጋግጧል!")
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n🟢 <b>[ክፍያ የተፈጸመለት]</b>")
            else:
                # ዊዝድሮው ውድቅ ከተደረገ የተቆረጠውን ባላንስ መመለስ (Refund)
                redis.hincrbyfloat("users:balance", user_id, amount)

                # 🔥 ከዚህ በታች ያሉት ስታተሶች ወደ "refunded" ተቀይረዋል!
                tx_data["status"] = "refunded" 
                update_history_tx_status(user_id, tx_id, "refunded") 

                bot.send_message(user_id, f"❌ የ <b>{amount} ብር</b> ወጪ ጥያቄዎ ተሰርዟል! ገንዘቡ ወደ ባላንስዎ ተመልሷል (Refunded)።")
                bot.answer_callback_query(call.id, "❌ ወጪው ተሰርዟል፣ ገንዘቡ ተመልሷል!")
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n🔴 <b>[የተሰረዘ እና የተመለሰ (Refunded)]</b>")

        # የትራንዛክሽኑን ስታተስ ማደስ
        redis.set(f"tx:{tx_id}", json.dumps(tx_data))
    except Exception as e:
        bot.answer_callback_query(call.id, f"⚠️ ስህተት፡ {str(e)}")

# ==========================================
# 🛡️ የአድሚን መቆጣጠሪያ API ROUTES (አዲስ የተጨመሩ)
# ==========================================

@server.route('/admin-panel')
def admin_panel():
    return render_template('admin.html')

@server.route('/api/admin/stats', methods=['POST'])
def get_admin_stats():
    data = request.json or {}
    admin_id = str(data.get("admin_id"))
    
    # የገባው ሰው አድሚን መሆኑን ማረጋገጫ
    if admin_id != str(ADMIN_ID): 
        return jsonify({"status": "error", "message": "ያልተፈቀደ የደህንነት ጥሰት ሙከራ!"}), 403
    
    total_users = redis.hlen("users:balance")
    banned_users_count = redis.scard("banned_users")
    
    # ገቢ፣ ወጪ እና ትርፍ ማስላት
    total_dep = float(redis.get("stats:total_deposits") or 0.0)
    total_wd = float(redis.get("stats:total_withdrawals") or 0.0)
    net_profit = total_dep - total_wd
    
    return jsonify({
        "status": "success",
        "total_users": total_users,
        "banned_users": banned_users_count,
        "total_deposits": total_dep,
        "total_withdrawals": total_wd,
        "net_profit": net_profit
    })

@server.route('/api/admin/user_action', methods=['POST'])
def admin_user_action():
    data = request.json or {}
    admin_id = str(data.get("admin_id"))
    target_user_id = str(data.get("target_user_id"))
    action = data.get("action") # ban, unban, adjust_balance
    
    if admin_id != str(ADMIN_ID): 
        return jsonify({"status": "error", "message": "ያልተፈቀደ ሙከራ!"}), 403
        
    if not target_user_id:
        return jsonify({"status": "error", "message": "የተጠቃሚ ID አልተገኘም!"}), 400

    if action == "ban":
        redis.sadd("banned_users", target_user_id)
        # ተጠቃሚው ላይ እገዳ መጣሉን በቦት ማሳወቅ
        try:
            bot.send_message(target_user_id, "⚠️ <b>መለያዎ (Account) በህግ ጥሰት ምክንያት በሲስተም አድሚን ታግዷል!</b>\nቅሬታ ካለዎት አድሚኑን ያነጋግሩ።", parse_mode="HTML")
        except: pass
        return jsonify({"status": "success", "message": "ተጠቃሚው በተሳካ ሁኔታ ታግዷል!"})
        
    elif action == "unban":
        redis.srem("banned_users", target_user_id)
        try:
            bot.send_message(target_user_id, "🎉 <b>የመለያዎ እገዳ በተሳካ ሁኔታ ተነስቷል!</b>\nአሁን መጫወት እና መጠቀም ይችላሉ።", parse_mode="HTML")
        except: pass
        return jsonify({"status": "success", "message": "የተጠቃሚው እገዳ ተነስቷል!"})
        
    elif action == "adjust_balance":
        amount = float(data.get("amount", 0))
        # ባላንስ መጨመር ወይም መቀነስ (አሉታዊ ቁጥር ከተላከ ይቀንሳል)
        redis.hincrbyfloat("users:balance", target_user_id, amount)
        try:
            sign = "+" if amount > 0 else ""
            bot.send_message(target_user_id, f"🔔 <b>የሂሳብ ማስተካከያ ተደርጓል!</b>\nባላንስዎ ላይ <b>{sign}{amount} ብር</b> ተጨምሯል/ተቀንሷል።", parse_mode="HTML")
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
        bot.send_message(message.chat.id, "🤖 <b>እንኳን ወደ 'የኛ ቤት' መቆጣጠሪያ ፓነል በሰላም መጡ!</b>\n\nእዚህ ገጽ ላይ የቦቱን ጠቅላላ ትርፍ ማየት፣ አጭበርባሪዎችን ማገድ እና የተጠቃሚዎችን ባላንስ በእጅ ማስተካከል ይችላሉ።", parse_mode="HTML", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "❌ ይህ ትዕዛዝ ለአድሚን ብቻ የተፈቀደ ነው!")


# ==========================================
# 🔌 WEBHOOK & SERVER START (ያለህበት የድሮው ክፍል)
# ==========================================
@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

# --- WEBHOOK SETUP ---
try:
    bot.remove_webhook()
    time.sleep(0.1)
    bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
except: pass

if __name__ == "__main__":
    socketio.run(server, host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
