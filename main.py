import os
import time
import json
import uuid
from flask import Flask, render_template, request, jsonify
import telebot
from telebot.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from upstash_redis import Redis

# ==========================================
# Configuration
# ==========================================
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com"
ADMIN_ID = 8488592165  # የአድሚን ID

bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

# ==========================================
# Webhook Setup
# ==========================================
try:
    bot.remove_webhook()
    time.sleep(0.5)
    bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
except Exception as e:
    print(f"Webhook Error: {e}")

# ==========================================
# API Routes (Core Functionality)
# ==========================================

@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.json or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400
    
    current_balance = float(redis.hget("users:balance", user_id) or 0.0)
    return jsonify({"status": "success", "balance": current_balance})

@server.route('/api/get_history', methods=['POST'])
def get_history():
    data = request.json or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400
    
    # ከሬዲስ ውስጥ የሂስትሪ ሊስት እናመጣለን
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    return jsonify({"status": "success", "history": history_list})

@server.route('/api/deposit', methods=['POST'])
def handle_deposit():
    # ፎርም ዳታ እና ፋይል ለመቀበል request.form እና request.files እንጠቀማለን
    user_id = request.form.get("user_id")
    user_name = request.form.get("user_name", "የሰፈር ልጅ")
    amount = float(request.form.get("amount", 0))
    receipt_file = request.files.get("receipt")
    
    if not user_id or amount <= 0 or not receipt_file:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    tx_id = str(uuid.uuid4())[:8]
    
    # የላኩትን መረጃ ለጊዜው ማስቀመጥ
    tx_data = {"user_id": user_id, "amount": amount, "type": "deposit", "status": "pending"}
    redis.set(f"tx:{tx_id}", json.dumps(tx_data))
    
    # ታሪክ ላይ መመዝገብ (pending ሁኔታ)
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {"type": "ገቢ", "amount": amount, "status": "pending"})
    redis.set(f"history:{user_id}", json.dumps(history_list))
    
    # ለአድሚኑ ማረጋገጫ ቁልፍ ማዘጋጀት
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ አጽድቅ", callback_data=f"ok|deposit|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no|deposit|{tx_id}|{user_id}|{amount}")
    )
    
    # ደረሰኙን (ፎቶውን) ለአድሚኑ መላክ
    caption = f"🔔 <b>አዲስ Deposit ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: {user_id}\n💰 መጠን: {amount} ብር\n🔑 TxID: {tx_id}"
    try:
        bot.send_photo(ADMIN_ID, receipt_file.read(), caption=caption, reply_markup=markup)
    except Exception as e:
        print(f"Error sending photo to admin: {e}")
        # ፎቶው ካልሰራል በፅሁፍ ብቻ ይልካል
        bot.send_message(ADMIN_ID, caption, reply_markup=markup)
        
    return jsonify({"status": "success"})

@server.route('/api/withdraw', methods=['POST'])
def handle_withdraw():
    data = request.json or {}
    user_id = data.get("user_id")
    user_name = data.get("user_name", "የሰፈር ልጅ")
    amount = float(data.get("amount", 0))
    phone = data.get("phone")
    bank_name = data.get("bank_name")
    account_name = data.get("account_name")
    
    if not user_id or amount <= 0 or not phone or not bank_name or not account_name:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400
        
    current_balance = float(redis.hget("users:balance", user_id) or 0.0)
    if current_balance < amount:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"})
    
    tx_id = str(uuid.uuid4())[:8]
    tx_data = {"user_id": user_id, "amount": amount, "type": "withdraw", "status": "pending"}
    redis.set(f"tx:{tx_id}", json.dumps(tx_data))
    
    # ታሪክ ላይ መመዝገብ (pending ሁኔታ)
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {"type": "ወጪ", "amount": amount, "status": "pending"})
    redis.set(f"history:{user_id}", json.dumps(history_list))
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ ተከፍሏል", callback_data=f"ok|withdraw|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ሰርዝ", callback_data=f"no|withdraw|{tx_id}|{user_id}|{amount}")
    )
    
    msg = f"💸 <b>አዲስ Withdraw ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: {user_id}\n🏦 ባንክ: {bank_name}\n👤 የአካውንት ስም: {account_name}\n💳 አካውንት/ስልክ: {phone}\n💰 መጠን: {amount} ብር\n🔑 TxID: {tx_id}"
    bot.send_message(ADMIN_ID, msg, reply_markup=markup)
    return jsonify({"status": "success"})

# ==========================================
# Callback Handler (Admin Actions)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("ok") or call.data.startswith("no"))
def process_admin_action(call):
    action, tx_type, tx_id, user_id, amount = call.data.split('|')
    amount = float(amount)
    
    tx_status = "completed" if action == "ok" else "refund"
    
    # ታሪኩን ማዘመን
    history_data = redis.get(f"history:{user_id}")
    if history_data:
        history_list = json.loads(history_data)
        # በታሪክ ውስጥ ያለውን የዚህን አይነት የመጨረሻ pending ማስተካከል
        type_str = "ገቢ" if tx_type == "deposit" else "ወጪ"
        for item in history_list:
            if item["type"] == type_str and item["status"] == "pending" and float(item["amount"]) == amount:
                item["status"] = tx_status
                break
        redis.set(f"history:{user_id}", json.dumps(history_list))

    if tx_type == "deposit":
        if action == "ok":
            redis.hincrbyfloat("users:balance", user_id, amount)
            bot.send_message(user_id, f"✅ የእርስዎ {amount} ብር ገቢ ጸድቋል!")
        else:
            bot.send_message(user_id, f"❌ የእርስዎ {amount} ብር የገቢ ጥያቄ ውድቅ ተደርጓል።")
            
    elif tx_type == "withdraw":
        if action == "ok":
            redis.hincrbyfloat("users:balance", user_id, -amount)
            bot.send_message(user_id, f"💰 የእርስዎ {amount} ብር ወጪ ተከፍሏል!")
        else:
            bot.send_message(user_id, f"❌ የእርስዎ {amount} ብር የወጪ ጥያቄ ውድቅ ተደርጓል።")
            
    status_text = "✅ ተጠናቋል" if action == "ok" else "❌ ውድቅ ተደርጓል"
    
    # የመልዕክቱን ፅሁፍ ማስተካከል (ፎቶ ወይም ቴክስት ከሆነ እንዳይበላሽ)
    if call.message.caption:
        bot.edit_message_caption(f"{call.message.caption}\n\n{status_text}", chat_id=call.message.chat.id, message_id=call.message.message_id)
    else:
        bot.edit_message_text(f"{call.message.text}\n\n{status_text}", chat_id=call.message.chat.id, message_id=call.message.message_id)

@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

# ==========================================
# Telegram Commands
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    web_app_info = WebAppInfo(url=WEB_APP_URL)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 Play", web_app=web_app_info))
    bot.reply_to(message, "እንኳን ደህና መጡ! ጨዋታዎችን ለመጀመር Play ን ይጫኑ።", reply_markup=markup)

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
