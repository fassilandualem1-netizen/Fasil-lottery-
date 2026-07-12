import os
import random
import threading
import telebot
from telebot import types
import requests
from flask import Flask, render_template, jsonify, request
from upstash_redis import Redis

# --- 1. Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com" 

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

ADMIN_IDS = [8488592165]  
PRIMARY_ADMIN = ADMIN_IDS[0]

# 📢 ቦቱ ሲሰበር ለአድሚኑ በቀጥታ እንዲልክ የሚያደርግ ፈንክሽን
def report_error_to_admin(error_msg):
    try:
        bot.send_message(PRIMARY_ADMIN, f"🚨 <b>ALERT: ቦቱ ላይ ስህተት ተፈጥሯል!</b>\n\n<code>{error_msg}</code>")
    except Exception as e:
        print(f"Error reporting failed: {e}")

GAME_CONFIG = {
    "beg_rucha": {"name": "🐑 የበግ ሩጫ", "fee": 2, "multiplier": 0.02},
    "ayi_game": {"name": "🧀 የአይጧ ጨዋታ", "fee": 5, "multiplier": 0.50},
    "anbessa_aden": {"name": "🦁 የአንበሳ አደን", "fee": 10, "multiplier": 1.50},
    "coin_flip": {"name": "🪙 እጥፍ ወይስ ባዶ", "fee": 0, "multiplier": 2.0}
}

# --- 2. Flask API Routes ---

@server.route('/')
def index():
    return render_template('index.html')

@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    try:
        data = request.json
        user_id = str(data.get('user_id'))
        balance = float(redis.hget("users:balance", user_id) or 0)
        return jsonify({"status": "success", "balance": balance})
    except Exception as e:
        report_error_to_admin(f"API get_balance Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@server.route('/api/start_game', methods=['POST'])
def start_game():
    try:
        data = request.json
        user_id = str(data.get('user_id'))
        game_type = data.get('game_type')
        config = GAME_CONFIG.get(game_type)
        
        if not config:
            return jsonify({"status": "error", "message": "ያልታወቀ ጨዋታ!"}), 400

        current_balance = float(redis.hget("users:balance", user_id) or 0)
        if current_balance < config["fee"]:
            return jsonify({"status": "no_money", "message": "በቂ የቦት ብር የለዎትም!"}), 400

        if config["fee"] > 0:
            redis.hincrbyfloat("users:balance", user_id, -config["fee"])
        return jsonify({"status": "ready", "new_balance": current_balance - config["fee"]})
    except Exception as e:
        report_error_to_admin(f"API start_game Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@server.route('/api/save_score', methods=['POST'])
def save_score():
    try:
        data = request.json
        user_id = str(data.get('user_id'))
        game_type = data.get('game_type')
        score = int(data.get('score', 0))

        config = GAME_CONFIG.get(game_type)
        winnings = round(score * config["multiplier"], 2)
        if winnings > 0:
            redis.hincrbyfloat("users:balance", user_id, winnings)
        return jsonify({"status": "success", "winnings": winnings})
    except Exception as e:
        report_error_to_admin(f"API save_score Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@server.route('/api/deposit', methods=['POST'])
def handle_web_deposit():
    try:
        user_id = request.form.get("user_id")
        amount = request.form.get("amount")
        receipt_file = request.files.get("receipt")
        
        caption_text = (
            f"🔔 <b>አዲስ የ Deposit ጥያቄ ከዌብአፕ!</b>\n\n"
            f"👤 <b>ተጫዋች ID:</b> <code>{user_id}</code>\n"
            f"💰 <b>የጠየቀው መጠን:</b> <b>{amount} ብር</b>\n\n"
            f"📝 <b>ለማጽደቅ፦</b>\n<code>/add {user_id} {amount}</code>\n"
            f"❌ <b>ውድቅ ለማድረግ፡</b>\n<code>/reject {user_id}</code>"
        )
        bot.send_photo(chat_id=PRIMARY_ADMIN, photo=receipt_file.stream.read(), caption=caption_text)
        return jsonify({"status": "success", "message": "የክፍያ ማረጋገጫዎ ለአስተዳዳሪው ተልኳል!"})
    except Exception as e:
        report_error_to_admin(f"Web Deposit Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@server.route('/api/withdraw', methods=['POST'])
def handle_web_withdraw():
    try:
        data = request.json
        user_id = str(data.get("user_id"))
        amount = float(data.get("amount", 0))
        phone = data.get("phone", "").strip()
        
        current_balance = float(redis.hget("users:balance", user_id) or 0)
        if current_balance < amount:
            return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

        redis.hincrbyfloat("users:balance", user_id, -amount)
        message_text = (
            f"💸 <b>አዲስ የ Withdraw ጥያቄ ከዌብአፕ!</b>\n\n"
            f"👤 <b>ተጫዋች ID:</b> <code>{user_id}</code>\n"
            f"📱 <b>ስልክ:</b> <code>{phone}</code>\n"
            f"💰 <b>መጠን:</b> <b>{amount} ብር</b>\n\n"
            f"📝 <b>ለማጽደቅ፡</b>\n<code>/paid {user_id} {amount}</code>"
        )
        bot.send_message(chat_id=PRIMARY_ADMIN, text=message_text)
        return jsonify({"status": "success", "message": "የማውጫ ጥያቄዎ ደርሷል!"})
    except Exception as e:
        report_error_to_admin(f"Web Withdraw Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- 🔗 3. የዌብሁክ መቀበያ እና ስህተት መያዣ ---

@server.route('/webhook/' + TOKEN, methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    except Exception as e:
        # 🚨 እዚህ ላይ በዌብሁክ የመጣውን ስህተት በቀጥታ ቴሌግራም ላይ ይልካል
        report_error_to_admin(f"Webhook Execution Error: {str(e)}")
    return "!", 200

@server.route("/set_webhook")
def set_webhook():
    try:
        render_url = os.environ.get("RENDER_EXTERNAL_URL") or WEB_APP_URL
        bot.remove_webhook()
        webhook_url = f"{render_url}/webhook/{TOKEN}"
        status = bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        return f"🟢 Webhook Successfully Set! Status: {status}", 200
    except Exception as e:
        report_error_to_admin(f"Webhook Setup Error: {str(e)}")
        return f"❌ Webhook Setup Failed: {e}", 500


# --- 4. የቴሌግራም ቦት መልዕክቶች (Telegram Handlers) ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        user_id = str(message.from_user.id)
        username = message.from_user.username or "የሰፈር ልጅ"

        if not redis.hexists("users:balance", user_id):
            redis.hset("users:balance", user_id, "0")
            redis.hset("users:username", user_id, username)

        balance = redis.hget("users:balance", user_id) or "0"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn_games = types.KeyboardButton("🕹️ 3D ጨዋታዎችን ይምረጡ", web_app=types.WebAppInfo(url=WEB_APP_URL))
        btn_wallet = types.KeyboardButton("💰 የኪስ ቦርሳ (Balance)")
        btn_deposit = types.KeyboardButton("📥 ብር አስገባ (Deposit)")
        btn_withdraw = types.KeyboardButton("📤 ብር አውጣ (Withdraw)")
        markup.add(btn_games)
        markup.add(btn_wallet, btn_deposit, btn_withdraw)

        bot.send_message(message.chat.id, f"<b>እንኳን ወደ ሰፈር 3D ጌሚንግ ቦት በሰላም መጡ! 👋</b>\n\n💰 ባላንስዎ፦ <b>{balance} ብር</b>", reply_markup=markup)
    except Exception as e:
        report_error_to_admin(f"Start Command Error: {str(e)}")

@bot.message_handler(func=lambda m: m.text == "💰 የኪስ ቦርሳ (Balance)")
def check_balance(message):
    try:
        user_id = str(message.from_user.id)
        balance = redis.hget("users:balance", user_id) or "0"
        bot.send_message(message.chat.id, f"💰 ወቅታዊ የኪስ ቦርሳዎ፦ <b>{balance} ብር</b> ነው።")
    except Exception as e:
        report_error_to_admin(f"Balance Command Error: {str(e)}")

# --- 📥 በቦት ቴክስት Deposit/Withdraw ---
@bot.message_handler(func=lambda m: m.text == "📥 ብር አስገባ (Deposit)")
def deposit_instruction(message):
    bot.send_message(message.chat.id, " ወደ <code>0951381356</code> በቴሌብር ልከው <b>የደረሰኝ ቁጥሩን (Transaction ID)</b> ብቻ ይጻፉ።")
    bot.register_next_step_handler(message, process_deposit_request)

def process_deposit_request(message):
    try:
        tx_id = message.text.strip()
        user_id = message.from_user.id
        username = message.from_user.username or "የሰፈር ልጅ"

        admin_msg = f"🔔 <b>አዲስ የጽሑፍ ማጫኛ!</b>\n👤 @{username} (ID: <code>{user_id}</code>)\n🧾 Tx ID: <code>{tx_id}</code>\n\n<code>/add {user_id} 50</code>"
        bot.send_message(PRIMARY_ADMIN, admin_msg)
        bot.send_message(message.chat.id, "⏳ ጥያቄዎ ለአስተዳዳሪው ቀርቧል።")
    except Exception as e:
        report_error_to_admin(f"Process Deposit Error: {str(e)}")

@bot.message_handler(func=lambda m: m.text == "📤 ብር አውጣ (Withdraw)")
def withdraw_request(message):
    bot.send_message(message.chat.id, "📤 <code>መጠን - ስልክ</code> (ምሳሌ፦ 100 - 0912345678)")
    bot.register_next_step_handler(message, process_withdraw_request)

def process_withdraw_request(message):
    try:
        text = message.text
        amount, phone = text.split("-")
        amount = float(amount.strip())
        phone = phone.strip()
        user_id = str(message.from_user.id)

        current_balance = float(redis.hget("users:balance", user_id) or 0)
        if current_balance < amount:
            bot.send_message(message.chat.id, "❌ በቂ የቦት ብር የለም!")
            return

        redis.hincrbyfloat("users:balance", user_id, -amount)
        admin_msg = f"🚨 <b>የጽሑፍ ማውጫ!</b>\n👤 ID: <code>{user_id}</code>\n💰 መጠን: {amount}\n📱 ስልክ: <code>{phone}</code>\n\n<code>/paid {user_id} {amount}</code>"
        bot.send_message(PRIMARY_ADMIN, admin_msg)
        bot.send_message(message.chat.id, "⏳ ጥያቄዎ ተመዝግቧል።")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ የተሳሳተ አጻጻፍ!")
        report_error_to_admin(f"Process Withdraw Error: {str(e)}")


# --- 🎛️ 5. የአድሚን የጽሑፍ ትዕዛዞች (Admin Commands) ---

@bot.message_handler(commands=['add'])
def admin_add_balance(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        parts = message.text.split()
        user_id = parts[1]
        amount = float(parts[2])
        redis.hincrbyfloat("users:balance", user_id, amount)
        bot.reply_to(message, f"✅ ለተጠቃሚ <code>{user_id}</code> {amount} ብር ተጭኗል።")
        bot.send_message(user_id, f"🎉 የ <b>{amount} ብር</b> ማጫኛ ጥያቄዎ ጸድቋል!")
    except Exception as e:
        report_error_to_admin(f"Cmd /add Error: {str(e)}")

@bot.message_handler(commands=['paid'])
def admin_confirm_withdraw(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        parts = message.text.split()
        user_id = parts[1]
        amount = float(parts[2])
        bot.reply_to(message, f"✅ ለተጠቃሚ <code>{user_id}</code> {amount} ብር መከፈሉ ተመዝግቧል።")
        bot.send_message(user_id, f"💸 የጠየቁት <b>{amount} ብር</b> በቴሌብር ተልኮልዎታል።")
    except Exception as e:
        report_error_to_admin(f"Cmd /paid Error: {str(e)}")

@bot.message_handler(commands=['reject'])
def admin_reject_request(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        parts = message.text.split()
        user_id = parts[1]
        bot.reply_to(message, f"❌ የባላንስ ጥያቄው ውድቅ ተደርጓል።")
        bot.send_message(user_id, "❌ የላኩት ጥያቄ በአስተዳዳሪው ውድቅ ተደርጓል።")
    except Exception as e:
        report_error_to_admin(f"Cmd /reject Error: {str(e)}")

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
