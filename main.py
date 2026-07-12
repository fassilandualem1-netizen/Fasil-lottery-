import os
import random
import time
import json
import hmac
import hashlib
import uuid
from urllib.parse import parse_qsl

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from flask import Flask, render_template, jsonify, request
from upstash_redis import Redis

# --- 1. Configuration ---
TOKEN = os.environ.get("BOT_TOKEN", "8663228906:AAHSTP37xmp7z4cQF8AvSX1vP2UPbqVtssQ") 
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com" 

ADMIN_GROUP_ID = -1003943321922
MY_PRIVATE_CHAT_ID = 8488592165

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

GAME_CONFIG = {
    "beg_rucha": {"name": "🐑 የበግ ሩጫ", "fee": 2, "multiplier": 0.02, "max_score": 1000},
    "ayit_game": {"name": "🧀 የአይጧ ጨዋታ", "fee": 5, "multiplier": 0.50, "max_score": 500},
    "anbessa_aden": {"name": "🦁 የአንበሳ አደን", "fee": 10, "multiplier": 1.50, "max_score": 200}
}

# --- 2. Security & Helpers ---
def verify_telegram_data(init_data: str, bot_token: str) -> bool:
    if not init_data: return False
    try:
        parsed_data = dict(parse_qsl(init_data))
        if 'hash' not in parsed_data: return False
        received_hash = parsed_data.pop('hash')
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return calculated_hash == received_hash
    except: return False

def check_auth(req):
    init_data = req.headers.get("Authorization") or req.form.get("init_data")
    return verify_telegram_data(init_data, TOKEN)

# ታሪክ መመዝገቢያ
def log_history(user_id, tx_id, tx_type, amount, status):
    record = {"tx_id": tx_id, "type": tx_type, "amount": amount, "status": status, "time": int(time.time())}
    redis.lpush(f"users:history:{user_id}", json.dumps(record))
    redis.ltrim(f"users:history:{user_id}", 0, 19)

# የ Pending የነበረውን ታሪክ ወደ Completed ወይም Refund የሚቀይር
def update_history_status(user_id, tx_id, new_status):
    records = redis.lrange(f"users:history:{user_id}", 0, 19)
    new_records = []
    for r in records:
        rec = json.loads(r)
        if rec.get("tx_id") == tx_id:
            rec["status"] = new_status
        new_records.append(json.dumps(rec))
    
    if new_records:
        redis.delete(f"users:history:{user_id}")
        for r in reversed(new_records): 
            redis.lpush(f"users:history:{user_id}", r)

# --- 3. Telegram Bot Handlers (Including Admin Buttons) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    web_app_info = WebAppInfo(url=WEB_APP_URL)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 Play / ተጫወት", web_app=web_app_info))
    try: bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonWebApp(type="web_app", text="🎮 Play", web_app=web_app_info))
    except: pass
    bot.reply_to(message, f"ሰላም <b>{message.from_user.first_name}</b>! 👋\n\n👇 የሰፈር ጨዋታዎችን ለመጀመር ከታች ያለውን ቁልፍ ይጫኑ!", reply_markup=markup)

# Admin Button Clicks (No Browser, Handled Directly in Telegram)
@bot.callback_query_handler(func=lambda call: True)
def handle_admin_callback(call):
    # የሚነካው አድሚኑ መሆኑን ማረጋገጫ
    if call.message.chat.id not in [ADMIN_GROUP_ID, MY_PRIVATE_CHAT_ID]:
        bot.answer_callback_query(call.id, "Unauthorized!")
        return

    data = call.data.split('|')
    action = data[0]

    # --- 1. Deposit Approve ---
    if action == "dep_app":
        _, user_id, amount, tx_id = data
        amount = float(amount)
        if redis.get(f"tx:{tx_id}") != b"pending" and redis.get(f"tx:{tx_id}") != "pending":
            return bot.answer_callback_query(call.id, "❌ ይህ ጥያቄ ቀደም ብሎ ተስተናግዷል!", show_alert=True)
        
        redis.set(f"tx:{tx_id}", "completed")
        redis.hincrbyfloat("users:balance", user_id, amount)
        update_history_status(user_id, tx_id, "completed")
        try: bot.send_message(user_id, f"✅ የ {amount} ብር ገቢ (Deposit) ጸድቋል! ባላንስዎ ተሞልቷል።")
        except: pass
        
        bot.edit_message_caption(f"{call.message.caption}\n\n<b>✅ APPROVED (ጸድቋል)</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        bot.answer_callback_query(call.id, "✅ Successfully Approved!")

    # --- 2. Deposit Reject ---
    elif action == "dep_rej":
        _, user_id, tx_id = data
        if redis.get(f"tx:{tx_id}") != b"pending" and redis.get(f"tx:{tx_id}") != "pending":
            return bot.answer_callback_query(call.id, "❌ ይህ ጥያቄ ቀደም ብሎ ተስተናግዷል!", show_alert=True)
        
        redis.set(f"tx:{tx_id}", "refund")
        update_history_status(user_id, tx_id, "refund")
        try: bot.send_message(user_id, "❌ የላኩት የክፍያ ማረጋገጫ (Deposit) ውድቅ ተደርጓል። እባክዎ ትክክለኛ ደረሰኝ ይላኩ።")
        except: pass
        
        bot.edit_message_caption(f"{call.message.caption}\n\n<b>❌ REJECTED (ውድቅ ተደርጓል)</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        bot.answer_callback_query(call.id, "❌ Successfully Rejected!")

    # --- 3. Withdraw Paid ---
    elif action == "wit_paid":
        _, user_id, amount, tx_id = data
        amount = float(amount)
        if redis.get(f"tx:{tx_id}") != b"pending" and redis.get(f"tx:{tx_id}") != "pending":
            return bot.answer_callback_query(call.id, "❌ ይህ ጥያቄ ቀደም ብሎ ተስተናግዷል!", show_alert=True)
        
        redis.set(f"tx:{tx_id}", "completed")
        update_history_status(user_id, tx_id, "completed")
        try: bot.send_message(user_id, f"✅ የ {amount} ብር ወጪ ጥያቄዎ በቴሌብር ተልኮልዎታል!")
        except: pass
        
        bot.edit_message_text(f"{call.message.text}\n\n<b>✅ PAID (ተከፍሏል)</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        bot.answer_callback_query(call.id, "✅ Marked as Paid!")

    # --- 4. Withdraw Reject ---
    elif action == "wit_rej":
        _, user_id, amount, tx_id = data
        amount = float(amount)
        if redis.get(f"tx:{tx_id}") != b"pending" and redis.get(f"tx:{tx_id}") != "pending":
            return bot.answer_callback_query(call.id, "❌ ይህ ጥያቄ ቀደም ብሎ ተስተናግዷል!", show_alert=True)
        
        redis.set(f"tx:{tx_id}", "refund")
        redis.hincrbyfloat("users:balance", user_id, amount) # የተቆረጠውን እንመልስለታለን
        update_history_status(user_id, tx_id, "refund")
        try: bot.send_message(user_id, f"❌ የ {amount} ብር ወጪ ጥያቄዎ ውድቅ ተደርጓል። ብሩ ወደ ባላንስዎ ተመልሷል።")
        except: pass
        
        bot.edit_message_text(f"{call.message.text}\n\n<b>❌ REJECTED & REFUNDED (ውድቅ ተደርጓል)</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        bot.answer_callback_query(call.id, "❌ Withdrawal Rejected & Refunded!")


# --- 4. Flask Web Routes ---
@server.route('/')
def index():
    return render_template('index.html')

@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'abort', 403

# --- 5. Game & Wallet API Routes ---
@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    user_id = str(request.json.get('user_id'))
    return jsonify({"status": "success", "balance": float(redis.hget("users:balance", user_id) or 0)})

@server.route('/api/get_history', methods=['POST'])
def get_history():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    user_id = str(request.json.get('user_id'))
    records_raw = redis.lrange(f"users:history:{user_id}", 0, 19)
    history = [json.loads(r) for r in records_raw] if records_raw else []
    return jsonify({"status": "success", "history": history})

@server.route('/api/start_game', methods=['POST'])
def start_game():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    user_id, game_type = str(request.json.get('user_id')), request.json.get('game_type')
    config = GAME_CONFIG.get(game_type)
    
    if float(redis.hget("users:balance", user_id) or 0) < config["fee"]: 
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
        
    redis.hincrbyfloat("users:balance", user_id, -config["fee"])
    log_history(user_id, str(uuid.uuid4())[:8], f"ጨዋታ ({config['name']})", -config["fee"], "completed")
    return jsonify({"status": "success"})

@server.route('/api/coin_flip', methods=['POST'])
def coin_flip():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user_id, bet_amount, choice = str(data.get('user_id')), float(data.get('bet_amount', 0)), data.get('choice')

    if float(redis.hget("users:balance", user_id) or 0) < bet_amount:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

    redis.hincrbyfloat("users:balance", user_id, -bet_amount)
    result = random.choice(['ዘውድ', 'ጎፈር'])
    
    if choice == result:
        winnings = bet_amount * 2
        redis.hincrbyfloat("users:balance", user_id, winnings)
        log_history(user_id, str(uuid.uuid4())[:8], "🪙 ዘውድና ጎፈር አሸነፉ", winnings, "completed")
        return jsonify({"status": "win", "message": f"አሸንፈዋል! 🎉 ውጤቱ {result} ነበር። {winnings} ብር ወደ ባላንስዎ ተጨምሯል!"})
    else:
        log_history(user_id, str(uuid.uuid4())[:8], "🪙 ዘውድና ጎፈር ተሸነፉ", -bet_amount, "completed")
        return jsonify({"status": "lose", "message": f"ተሸንፈዋል! 😢 ውጤቱ {result} ነበር።"})

@server.route('/api/deposit', methods=['POST'])
def handle_deposit():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    try:
        user_id = request.form.get("user_id")
        user_name = request.form.get("user_name", "ተጫዋች")
        amount = float(request.form.get("amount", 0))
        receipt = request.files.get("receipt")
        
        # tx_id ወደ 8 ፊደል አሳጥሬዋለሁ (Callback data ቦታ እንዲበቃ)
        tx_id = str(uuid.uuid4())[:8]
        redis.set(f"tx:{tx_id}", "pending")

        caption = f"🔔 <b>አዲስ Deposit ጥያቄ</b>\n👤 ስም: {user_name}\n🆔 <code>{user_id}</code>\n💰 <b>{amount} ብር</b>"
        
        # URL ወደ Callback Data ተቀይሯል
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ አጽድቅ (Approve)", callback_data=f"dep_app|{user_id}|{amount}|{tx_id}"),
            InlineKeyboardButton("❌ ውድቅ (Reject)", callback_data=f"dep_rej|{user_id}|{tx_id}")
        )
        
        bot.send_photo(ADMIN_GROUP_ID, photo=receipt.stream.read(), caption=caption, reply_markup=markup, parse_mode="HTML")
        log_history(user_id, tx_id, "ገቢ", amount, "pending")
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@server.route('/api/withdraw', methods=['POST'])
def handle_withdraw():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user_id, user_name = str(data.get("user_id")), data.get("user_name", "ተጫዋች")
    amount, phone = float(data.get("amount", 0)), data.get("phone")
    
    if float(redis.hget("users:balance", user_id) or 0) < amount: 
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
    
    tx_id = str(uuid.uuid4())[:8]
    redis.set(f"tx:{tx_id}", "pending")
    redis.hincrbyfloat("users:balance", user_id, -amount)
    
    msg = f"💸 <b>Withdraw ጥያቄ!</b>\n👤 ስም: {user_name}\n🆔 <code>{user_id}</code>\n📱 ስልክ: <code>{phone}</code>\n💰 <b>{amount} ብር</b>"
    
    # URL ወደ Callback Data ተቀይሯል
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ ተከፍሏል", callback_data=f"wit_paid|{user_id}|{amount}|{tx_id}"),
        InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"wit_rej|{user_id}|{amount}|{tx_id}")
    )
    
    bot.send_message(ADMIN_GROUP_ID, text=msg, reply_markup=markup, parse_mode="HTML")
    log_history(user_id, tx_id, "ወጪ", amount, "pending")
    return jsonify({"status": "success"})


if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
