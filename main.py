import os
import random
import time
import json
import hmac
import hashlib
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

ADMIN_SECRET_TOKEN = os.environ.get("ADMIN_SECRET_TOKEN", "super_secret_token_123")
ADMIN_GROUP_ID = -1003943321922 # የአድሚን ግሩፕ አይዲህን አስተካክል
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
def report_error_to_admin(error_msg):
    try: bot.send_message(MY_PRIVATE_CHAT_ID, f"🚨 <b>ALERT:</b> <code>{error_msg}</code>")
    except: pass

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

def log_history(user_id, tx_type, amount, status):
    # ታሪኮችን ወደ ሬዲስ መዝግብ (Maximum 10 ሪከርድ ብቻ እንይዛለን ሜሞሪ እንዳይሞላ)
    history_data = json.dumps({"type": tx_type, "amount": amount, "status": status})
    redis.lpush(f"users:history:{user_id}", history_data)
    redis.ltrim(f"users:history:{user_id}", 0, 9) 

# --- 3. Telegram Bot Handlers ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    web_app_info = WebAppInfo(url=WEB_APP_URL)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 Play / ተጫወት", web_app=web_app_info))
    
    try:
        bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonWebApp(type="web_app", text="🎮 Play", web_app=web_app_info))
    except: pass
    
    bot.reply_to(message, f"ሰላም <b>{message.from_user.first_name}</b>! 👋\n\n👇 የሰፈር ጨዋታዎችን ለመጀመር ከታች ያለውን ቁልፍ ይጫኑ!", reply_markup=markup)

# --- 4. Flask Web & Webhook Routes ---
@server.route('/')
def index():
    # ጌሙ የሚከፈትበት ዋናው የ HTML ፋይል
    return render_template('index.html')

@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    # ቴሌግራም አዲስ ሜሴጅ ሲልክ የሚቀበልበት መንገድ (Webhook)
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
    records_raw = redis.lrange(f"users:history:{user_id}", 0, 9)
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
    log_history(user_id, config['name'], -config["fee"], "ተቀንሷል (መግቢያ)")
    return jsonify({"status": "success"})

@server.route('/api/coin_flip', methods=['POST'])
def coin_flip():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user_id = str(data.get('user_id'))
    bet_amount = float(data.get('bet_amount', 0))
    choice = data.get('choice')

    balance = float(redis.hget("users:balance", user_id) or 0)
    if balance < bet_amount:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

    redis.hincrbyfloat("users:balance", user_id, -bet_amount)
    
    result = random.choice(['ዘውድ', 'ጎፈር'])
    
    if choice == result:
        winnings = bet_amount * 2
        redis.hincrbyfloat("users:balance", user_id, winnings)
        log_history(user_id, "🪙 ዘውድና ጎፈር", winnings, "አሸነፉ 🏆")
        return jsonify({"status": "win", "message": f"አሸንፈዋል! 🎉 ውጤቱ {result} ነበር። {winnings} ብር ወደ ባላንስዎ ተጨምሯል!"})
    else:
        log_history(user_id, "🪙 ዘውድና ጎፈር", -bet_amount, "ተሸነፉ 😢")
        return jsonify({"status": "lose", "message": f"ተሸንፈዋል! 😢 ውጤቱ {result} ነበር።"})

@server.route('/api/deposit', methods=['POST'])
def handle_deposit():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    try:
        user_id = request.form.get("user_id")
        user_name = request.form.get("user_name", "ተጫዋች")
        amount = float(request.form.get("amount", 0))
        receipt = request.files.get("receipt")
        
        caption = f"🔔 <b>አዲስ Deposit ጥያቄ</b>\n👤 ስም: {user_name}\n🆔 <code>{user_id}</code>\n💰 <b>{amount} ብር</b>"
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ አጽድቅ (Approve)", url=f"{WEB_APP_URL}/quick-approve?user_id={user_id}&amount={amount}&token={ADMIN_SECRET_TOKEN}"),
            InlineKeyboardButton("❌ ውድቅ (Reject)", url=f"{WEB_APP_URL}/quick-reject?user_id={user_id}&token={ADMIN_SECRET_TOKEN}")
        )
        bot.send_photo(ADMIN_GROUP_ID, photo=receipt.stream.read(), caption=caption, reply_markup=markup, parse_mode="HTML")
        log_history(user_id, "Deposit", amount, "በሂደት ላይ ⏳")
        return jsonify({"status": "success"})
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@server.route('/api/withdraw', methods=['POST'])
def handle_withdraw():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user_id = str(data.get("user_id"))
    user_name = data.get("user_name", "ተጫዋች")
    amount = float(data.get("amount", 0))
    phone = data.get("phone")
    
    if float(redis.hget("users:balance", user_id) or 0) < amount: 
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
    
    # ብሩን ወዲያውኑ እንቀንሰዋለን (ከአቅም በላይ እንዳያወጣ)
    redis.hincrbyfloat("users:balance", user_id, -amount)
    
    msg = f"💸 <b>Withdraw ጥያቄ!</b>\n👤 ስም: {user_name}\n🆔 <code>{user_id}</code>\n📱 ስልክ: <code>{phone}</code>\n💰 <b>{amount} ብር</b>"
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ ተከፍሏል", url=f"{WEB_APP_URL}/mark-paid?user_id={user_id}&amount={amount}&token={ADMIN_SECRET_TOKEN}"),
        InlineKeyboardButton("❌ ውድቅ አድርግ", url=f"{WEB_APP_URL}/reject-withdraw?user_id={user_id}&amount={amount}&token={ADMIN_SECRET_TOKEN}")
    )
    bot.send_message(ADMIN_GROUP_ID, text=msg, reply_markup=markup, parse_mode="HTML")
    log_history(user_id, "Withdraw", amount, "በሂደት ላይ ⏳")
    return jsonify({"status": "success"})

# --- 6. Admin Action Routes ---
@server.route('/quick-approve', methods=['GET'])
def quick_approve():
    if request.args.get("token") != ADMIN_SECRET_TOKEN: return "Unauthorized", 403
    user_id = request.args.get("user_id")
    amount = float(request.args.get("amount"))
    redis.hincrbyfloat("users:balance", user_id, amount)
    log_history(user_id, "Deposit", amount, "ጸድቋል ✅")
    try: bot.send_message(user_id, f"✅ የ {amount} ብር ዲፖዚትዎ ጸድቋል! ባላንስዎ ተሞልቷል።")
    except: pass
    return "Successfully Approved! You can close this page."

@server.route('/quick-reject', methods=['GET'])
def quick_reject():
    if request.args.get("token") != ADMIN_SECRET_TOKEN: return "Unauthorized", 403
    user_id = request.args.get("user_id")
    log_history(user_id, "Deposit", 0, "ውድቅ ተደርጓል ❌")
    try: bot.send_message(user_id, "❌ የላኩት የክፍያ ማረጋገጫ (Deposit) ውድቅ ተደርጓል። እባክዎ ትክክለኛ ደረሰኝ ይላኩ።")
    except: pass
    return "Successfully Rejected! You can close this page."

@server.route('/mark-paid', methods=['GET'])
def mark_paid():
    if request.args.get("token") != ADMIN_SECRET_TOKEN: return "Unauthorized", 403
    user_id = request.args.get("user_id")
    amount = request.args.get("amount")
    log_history(user_id, "Withdraw", amount, "ተከፍሏል ✅")
    try: bot.send_message(user_id, f"✅ የ {amount} ብር ወጪ ጥያቄዎ በቴሌብር ተልኮልዎታል!")
    except: pass
    return "Marked as Paid! You can close this page."

@server.route('/reject-withdraw', methods=['GET'])
def reject_withdraw():
    if request.args.get("token") != ADMIN_SECRET_TOKEN: return "Unauthorized", 403
    user_id = request.args.get("user_id")
    amount = float(request.args.get("amount"))
    # የተቆረጠበትን ብር እንመልስለታለን
    redis.hincrbyfloat("users:balance", user_id, amount)
    log_history(user_id, "Withdraw", amount, "ውድቅ ተደርጓል (ብርዎ ተመልሷል) ❌")
    try: bot.send_message(user_id, f"❌ የ {amount} ብር ወጪ ጥያቄዎ ውድቅ ተደርጓል። ብሩ ወደ ባላንስዎ ተመልሷል።")
    except: pass
    return "Withdrawal Rejected & Refunded! You can close this page."

if __name__ == "__main__":
    # Webhook Setup
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
    
    # Server Run
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
