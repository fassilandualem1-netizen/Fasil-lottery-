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

# ==========================================
# 1. Configuration (ማስተካከያዎች)
# ==========================================
TOKEN = os.environ.get("BOT_TOKEN") 
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
    "ayi_game": {"name": "🧀 የአይጧ ጨዋታ", "fee": 5, "multiplier": 0.50, "max_score": 500},
    "anbessa_aden": {"name": "🦁 የአንበሳ አደን", "fee": 10, "multiplier": 1.50, "max_score": 200}
}

# ==========================================
# 2. Webhook Setup (ቴሌግራምን ከ Render ጋር ማገናኘት)
# ==========================================
try:
    bot.remove_webhook()
    time.sleep(0.5)
    bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
    print("✅ Webhook successfully registered on Render!")
except Exception as e:
    print(f"❌ Webhook Registration Error: {e}")

# ==========================================
# 3. Security & Helpers (ረዳት ፈንክሽኖች)
# ==========================================
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

def log_history(user_id, tx_id, tx_type, amount, status):
    record = {"tx_id": tx_id, "type": tx_type, "amount": amount, "status": status, "time": int(time.time())}
    redis.lpush(f"users:history:{user_id}", json.dumps(record))
    redis.ltrim(f"users:history:{user_id}", 0, 19)

def update_history_status(user_id, tx_id, new_status):
    try:
        records = redis.lrange(f"users:history:{user_id}", 0, 19)
        new_records = []
        for r in records:
            if isinstance(r, bytes):
                r = r.decode('utf-8')
            rec = json.loads(r)
            if rec.get("tx_id") == tx_id:
                rec["status"] = new_status
            new_records.append(json.dumps(rec))

        if new_records:
            redis.delete(f"users:history:{user_id}")
            for r in reversed(new_records): 
                redis.lpush(f"users:history:{user_id}", r)
    except Exception as e:
        print(f"History update failed: {e}")

# ==========================================
# 4. Flask Web Routes (የዌብ ገፅ እና ዌብሁክ)
# ==========================================
@server.route('/')
def index():
    # ይህ የጌም ገጽህን (index.html) እንዲከፈት የሚያደርገው ዋና ኮድ ነው
    return render_template('index.html')

@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    if request.is_json: 
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'abort', 403

# ==========================================
# 5. Telegram Bot Handlers (ቦት ትዕዛዞች)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    web_app_info = WebAppInfo(url=WEB_APP_URL)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 Play / ተጫወት", web_app=web_app_info))
    try: bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonWebApp(type="web_app", text="🎮 Play", web_app=web_app_info))
    except: pass
    bot.reply_to(message, f"ሰላም <b>{message.from_user.first_name}</b>! 👋\n\n👇 የሰፈር ጨዋታዎችን ለመጀመር ከታች ያለውን ቁልፍ ይጫኑ!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_admin_callback(call):
    try:
        bot.answer_callback_query(call.id)

        data = call.data.split('|')
        action = data[0] # ok ወይም no ይሆናል
        tx_id = data[1]

        # ዳታውን ከ Redis ላይ ማምጣት
        tx_raw = redis.get(f"tx:{tx_id}")
        if not tx_raw:
            bot.send_message(call.message.chat.id, "⚠️ ይህ ጥያቄ አይገኝም ወይም ቀድሞ ተሰርዟል።")
            return

        if isinstance(tx_raw, bytes): tx_raw = tx_raw.decode('utf-8')
        tx_data = json.loads(tx_raw)

        if tx_data["status"] != "pending":
            bot.send_message(call.message.chat.id, "⚠️ ይህ ጥያቄ ቀድሞ ምላሽ አግኝቷል!")
            return

        user_id = tx_data["user_id"]
        amount = tx_data["amount"]
        tx_type = tx_data["type"] 

        new_status_text = ""

        if action == "ok":
            tx_data["status"] = "completed"
            redis.set(f"tx:{tx_id}", json.dumps(tx_data))
            update_history_status(user_id, tx_id, "completed")

            if tx_type == "deposit":
                redis.hincrbyfloat("users:balance", user_id, amount)
                try: bot.send_message(user_id, f"🎉 የ <b>{amount} ብር</b> ገቢ ጥያቄዎ ጸድቋል!")
                except: pass
                new_status_text = "✅ <b>ጸድቋል (Approved)</b>"

            elif tx_type == "withdraw":
                try: bot.send_message(user_id, f"✅ የ <b>{amount} ብር</b> ወጪ ጥያቄዎ ተከፍሏል!")
                except: pass
                new_status_text = "💰 <b>ክፍያ ተፈጽሟል (Paid)</b>"

        elif action == "no":
            tx_data["status"] = "refund"
            redis.set(f"tx:{tx_id}", json.dumps(tx_data))
            update_history_status(user_id, tx_id, "refund")

            if tx_type == "deposit":
                try: bot.send_message(user_id, f"⚠️ የ <b>{amount} ብር</b> ገቢ ጥያቄዎ ውድቅ ሆኗል።")
                except: pass
                new_status_text = "❌ <b>ውድቅ ሆኗል (Rejected)</b>"

            elif tx_type == "withdraw":
                redis.hincrbyfloat("users:balance", user_id, amount) # ብሩን መመለስ
                try: bot.send_message(user_id, f"❌ የ <b>{amount} ብር</b> የወጪ ጥያቄዎ ውድቅ ተደርጎ ብሩ ወደ ዋሌትዎ ተመልሷል።")
                except: pass
                new_status_text = "❌ <b>ውድቅ ሆኗል (ብሩ ተመልሷል)</b>"

        # አዝራሩን አጥፍተን ጽሁፉን ማደስ
        msg_text = call.message.caption if call.message.photo else call.message.text
        if call.message.photo:
            bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=f"{msg_text}\n\n{new_status_text}", parse_mode="HTML")
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"{msg_text}\n\n{new_status_text}", parse_mode="HTML")

    except Exception as e:
        bot.send_message(call.message.chat.id, f"🚨 <b>ስህተት ተፈጥሯል:</b> <code>{str(e)}</code>")

# ==========================================
# 6. Game & Wallet API Routes
# ==========================================
@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.json
        user_id = str(data.get("user_id"))
        
        # ባላንሱን ከ Redis ላይ መፈለግ
        balance = float(redis.hget("users:balance", user_id) or 0.0)
        return jsonify({"status": "success", "balance": balance})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@server.route('/api/deposit', methods=['POST'])
def handle_deposit():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    try:
        user_id = request.form.get("user_id")
        user_name = request.form.get("user_name", "ተጫዋች")
        amount = float(request.form.get("amount", 0))
        receipt = request.files.get("receipt")

        tx_id = str(uuid.uuid4())[:8]
        tx_data = {"user_id": user_id, "amount": amount, "type": "deposit", "status": "pending"}
        redis.set(f"tx:{tx_id}", json.dumps(tx_data))

        caption = f"🔔 <b>አዲስ Deposit ጥያቄ</b>\n👤 ስም: {user_name}\n🆔 <code>{user_id}</code>\n💰 <b>{amount} ብር</b>"

        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ አጽድቅ", callback_data=f"ok|{tx_id}"),
            InlineKeyboardButton("❌ ውድቅ", callback_data=f"no|{tx_id}")
        )

        photo_bytes = receipt.read()
        try: bot.send_photo(ADMIN_GROUP_ID, photo=photo_bytes, caption=caption, reply_markup=markup, parse_mode="HTML")
        except: pass
        try: bot.send_photo(MY_PRIVATE_CHAT_ID, photo=photo_bytes, caption=caption, reply_markup=markup, parse_mode="HTML")
        except: pass

        log_history(user_id, tx_id, "ገቢ", amount, "pending")
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@server.route('/api/withdraw', methods=['POST'])
def handle_withdraw():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user_id = str(data.get("user_id"))
    user_name = data.get("user_name", "ተጫዋች")
    amount = float(data.get("amount", 0))
    phone = data.get("phone", "ያልተሞላ")
    account_name = data.get("account_name", "ያልተሞላ")
    bank_name = data.get("bank_name", "ያልተሞላ")

    if float(redis.hget("users:balance", user_id) or 0) < amount: 
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

    tx_id = str(uuid.uuid4())[:8]
    tx_data = {"user_id": user_id, "amount": amount, "type": "withdraw", "status": "pending"}
    redis.set(f"tx:{tx_id}", json.dumps(tx_data))
    redis.hincrbyfloat("users:balance", user_id, -amount)

    msg = (
        f"💸 <b>አዲስ Withdraw ጥያቄ!</b>\n"
        f"👤 TG ስም: {user_name}\n"
        f"🆔 <code>{user_id}</code>\n"
        f"🏦 የባንክ አይነት: <b>{bank_name}</b>\n"
        f"💳 የአካውንት ስም: <b>{account_name}</b>\n"
        f"📱 አካውንት ቁጥር/ስልክ: <code>{phone}</code>\n"
        f"💰 የጠየቀው መጠን: <b>{amount} ብር</b>"
    )

    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ ተከፍሏል", callback_data=f"ok|{tx_id}"),
        InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no|{tx_id}")
    )

    try: bot.send_message(ADMIN_GROUP_ID, text=msg, reply_markup=markup, parse_mode="HTML")
    except: pass
    try: bot.send_message(MY_PRIVATE_CHAT_ID, text=msg, reply_markup=markup, parse_mode="HTML")
    except: pass

    log_history(user_id, tx_id, "ወጪ", amount, "pending")
    return jsonify({"status": "success"})


# ==========================================
# 7. Application Runner (For Local Env)
# ==========================================
if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
