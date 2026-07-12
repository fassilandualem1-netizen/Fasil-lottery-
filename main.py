import os
import random
import time
import json
import threading
import hmac
import hashlib
from urllib.parse import parse_qsl

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, render_template, jsonify, request
from upstash_redis import Redis

# --- 1. Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com" 

ADMIN_SECRET_TOKEN = os.environ.get("ADMIN_SECRET_TOKEN", "super_secret_token_123")
ADMIN_GROUP_ID = -1003943321922
MY_PRIVATE_CHAT_ID = 8488592165

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

GAME_CONFIG = {
    "beg_rucha": {"name": "🐑 የበግ ሩጫ", "fee": 2, "multiplier": 0.02, "max_score": 1000},
    "ayi_game": {"name": "🧀 የአይጧ ጨዋታ", "fee": 5, "multiplier": 0.50, "max_score": 500},
    "anbessa_aden": {"name": "🦁 የአንበሳ አደን", "fee": 10, "multiplier": 1.50, "max_score": 200},
    "coin_flip": {"name": "🪙 እጥፍ ወይስ ባዶ", "fee": 0, "multiplier": 2.0}
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

# --- 3. Telegram Bot Handlers ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    web_app_info = telebot.types.WebAppInfo(url=WEB_APP_URL)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 Play / ተጫወት", web_app=web_app_info))
    
    try:
        bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=telebot.types.MenuButtonWebApp(type="web_app", text="🎮 Play", web_app=web_app_info))
    except: pass
    
    bot.reply_to(message, f"ሰላም <b>{message.from_user.first_name}</b>! 👋\n\n👇 ለመጀመር ከታች ያለውን ቁልፍ ይጫኑ!", reply_markup=markup)

# --- 4. Flask API Routes ---
@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    user_id = str(request.json.get('user_id'))
    return jsonify({"balance": float(redis.hget("users:balance", user_id) or 0)})

@server.route('/api/deposit', methods=['POST'])
def handle_deposit():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    try:
        user_id, amount = request.form.get("user_id"), float(request.form.get("amount", 0))
        receipt = request.files.get("receipt")
        caption = f"🔔 <b>አዲስ Deposit</b>\n🆔 <code>{user_id}</code>\n💰 <b>{amount} ብር</b>"
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ አጽድቅ", url=f"{WEB_APP_URL}/quick-approve?user_id={user_id}&amount={amount}&token={ADMIN_SECRET_TOKEN}"),
            InlineKeyboardButton("❌ አትም", url=f"{WEB_APP_URL}/quick-reject?user_id={user_id}&token={ADMIN_SECRET_TOKEN}")
        )
        bot.send_photo(ADMIN_GROUP_ID, photo=receipt.stream.read(), caption=caption, reply_markup=markup, parse_mode="HTML")
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@server.route('/api/withdraw', methods=['POST'])
def handle_withdraw():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user_id, amount = str(data.get("user_id")), float(data.get("amount", 0))
    if float(redis.hget("users:balance", user_id) or 0) < amount: return jsonify({"error": "በቂ ባላንስ የለዎትም!"}), 400
    
    redis.hincrbyfloat("users:balance", user_id, -amount)
    msg = f"💸 <b>Withdraw ጥያቄ!</b>\n🆔 <code>{user_id}</code>\n💰 <b>{amount} ብር</b>"
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ ተከፍሏል", url=f"{WEB_APP_URL}/mark-paid?user_id={user_id}&amount={amount}&token={ADMIN_SECRET_TOKEN}"),
        InlineKeyboardButton("❌ ውድቅ", url=f"{WEB_APP_URL}/reject-withdraw?user_id={user_id}&amount={amount}&token={ADMIN_SECRET_TOKEN}")
    )
    bot.send_message(ADMIN_GROUP_ID, text=msg, reply_markup=markup, parse_mode="HTML")
    return jsonify({"status": "success"})

@server.route('/api/start_game', methods=['POST'])
def start_game():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    user_id, game_type = str(request.json.get('user_id')), request.json.get('game_type')
    config = GAME_CONFIG.get(game_type)
    if float(redis.hget("users:balance", user_id) or 0) < config["fee"]: return jsonify({"error": "no_money"}), 400
    redis.hincrbyfloat("users:balance", user_id, -config["fee"])
    return jsonify({"status": "ready"})

@server.route('/api/save_score', methods=['POST'])
def save_score():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user_id, score, config = str(data.get('user_id')), int(data.get('score', 0)), GAME_CONFIG.get(data.get('game_type'))
    if score > config["max_score"]: return jsonify({"error": "Cheat"}), 400
    winnings = round(score * config["multiplier"], 2)
    redis.hincrbyfloat("users:balance", user_id, winnings)
    return jsonify({"winnings": winnings})

# Admin Routes (approve/reject/secret-panel logic...)
@server.route('/secret-admin-panel', methods=['GET', 'POST'])
def admin_panel():
    if request.args.get("token") != ADMIN_SECRET_TOKEN: return "Unauthorized", 403
    # ... (የቀድሞው የአድሚን ሎጂክ እዚህ ይግባ)
    return "Admin Panel"

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
