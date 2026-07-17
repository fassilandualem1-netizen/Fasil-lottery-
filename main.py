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

server.secret_key = os.environ.get("SECRET_KEY")


# የ Football API ቁልፍ ከ Render Environment ያነባል
FOOTBALL_API_KEY = os.environ.get("API_FOOTBALL_KEY")

# የ SocketIO ማስተካከያ (ኤረር ሲያመጣ የነበረው 'eventlet' ወደ 'gevent' ተቀይሯል)
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

@server.route('/api/deposit', methods=['POST'])
@telegram_auth_required
def handle_deposit():
    user_id = request.form.get("user_id")
    user_name = request.form.get("user_name", "የሰፈር ልጅ")
    amount = float(request.form.get("amount", 0))
    receipt_file = request.files.get("receipt")
    if not user_id or amount <= 0 or not receipt_file: return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    photo_data = receipt_file.read()
    tx_id = str(uuid.uuid4())[:8]
    redis.set(f"tx:{tx_id}", json.dumps({"user_id": user_id, "amount": amount, "type": "deposit", "status": "pending"}))
    add_to_history(user_id, {"tx_id": tx_id, "type": "ገቢ", "amount": amount, "status": "pending", "date": time.strftime("%Y-%m-%d %H:%M")})

    thread = threading.Thread(target=send_photo_background, args=(user_name, user_id, amount, tx_id, photo_data))
    thread.start()
    return jsonify({"status": "success"})

# --- WITHDRAW LOGIC (With Validation) ---
@server.route('/api/withdraw', methods=['POST'])
@telegram_auth_required
def handle_withdraw():
    data = request.json or {}
    user_id = data.get("user_id")
    user_name = data.get("user_name", "የሰፈር ልጅ")
    amount = float(data.get("amount", 0))
    phone = str(data.get("phone", ""))
    bank_name = data.get("bank_name", "")
    account_name = data.get("account_name", "")

    # Validation
    if not user_id or amount <= 0: return jsonify({"status": "error", "message": "የጎደለ መረጃ"}), 400
    if not is_number_only(phone): return jsonify({"status": "error", "message": "ስልክ ቁጥር ቁጥር ብቻ መሆን አለበት"}), 400
    if not is_text_only(bank_name) or not is_text_only(account_name): 
        return jsonify({"status": "error", "message": "ባንክ እና ስም ፊደል ብቻ መሆን አለባቸው"}), 400

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

# --- CALLBACKS & WEBHOOK ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("ok") or call.data.startswith("no"))
def process_admin_action(call):
    # ... (ቀድሞ የነበረው የcallback ኮድህ እዚህ ይቀጥላል) ...
    pass 

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
socketio = SocketIO(server, cors_allowed_origins="*", async_mode='gevent')

server.register_blueprint(gofere_zewd_bp)
server.register_blueprint(aviator_bp)
server.register_blueprint(chicken_bp)
server.register_blueprint(keno_bp)
server.register_blueprint(virtual_sports_bp)
server.register_blueprint(real_sports_bp)

# --- VALIDATION HELPERS ---
def is_text_only(text):
    return bool(re.match(r'^[a-zA-Z\u1200-\u137F\s]+$', text))

def is_number_only(text):
    return text.isdigit()

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

@server.route('/api/deposit', methods=['POST'])
@telegram_auth_required
def handle_deposit():
    user_id = request.form.get("user_id")
    user_name = request.form.get("user_name", "የሰፈር ልጅ")
    amount = float(request.form.get("amount", 0))
    receipt_file = request.files.get("receipt")
    if not user_id or amount <= 0 or not receipt_file: return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    photo_data = receipt_file.read()
    tx_id = str(uuid.uuid4())[:8]
    redis.set(f"tx:{tx_id}", json.dumps({"user_id": user_id, "amount": amount, "type": "deposit", "status": "pending"}))
    add_to_history(user_id, {"tx_id": tx_id, "type": "ገቢ", "amount": amount, "status": "pending", "date": time.strftime("%Y-%m-%d %H:%M")})

    thread = threading.Thread(target=send_photo_background, args=(user_name, user_id, amount, tx_id, photo_data))
    thread.start()
    return jsonify({"status": "success"})

# --- WITHDRAW LOGIC (With Validation) ---
@server.route('/api/withdraw', methods=['POST'])
@telegram_auth_required
def handle_withdraw():
    data = request.json or {}
    user_id = data.get("user_id")
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

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("ok") or call.data.startswith("no"))
def process_admin_action(call):
    # ... (የቀድሞው የCallback ኮድህ) ...
    pass 

@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

# --- WEBHOOK SETUP (Outside if name == main) ---
try:
    bot.remove_webhook()
    time.sleep(0.1)
    bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
except: pass

if __name__ == "__main__":
    socketio.run(server, host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))