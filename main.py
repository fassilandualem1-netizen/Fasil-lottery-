import os
import time
import json
import uuid
import random
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
# Frontend Routes (Multi-page Template Routes)
# ==========================================
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/horse_race')
def horse_race_page():
    return render_template('horse_race.html')

@server.route('/coin_flip_game')
def coin_flip_page():
    return render_template('coin_flip.html')

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
    
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    return jsonify({"status": "success", "history": history_list})

@server.route('/api/deposit', methods=['POST'])
def handle_deposit():
    user_id = request.form.get("user_id")
    user_name = request.form.get("user_name", "የሰፈር ልጅ")
    amount = float(request.form.get("amount", 0))
    receipt_file = request.files.get("receipt")
    
    if not user_id or amount <= 0 or not receipt_file:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    tx_id = str(uuid.uuid4())[:8]
    tx_data = {"user_id": user_id, "amount": amount, "type": "deposit", "status": "pending"}
    redis.set(f"tx:{tx_id}", json.dumps(tx_data))
    
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {"type": "ገቢ", "amount": amount, "status": "pending"})
    redis.set(f"history:{user_id}", json.dumps(history_list))
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ አጽድቅ", callback_data=f"ok|deposit|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no|deposit|{tx_id}|{user_id}|{amount}")
    )
    
    caption = f"🔔 <b>አዲስ Deposit ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: {user_id}\n💰 መጠን: {amount} ብር\n🔑 TxID: {tx_id}"
    try:
        bot.send_photo(ADMIN_ID, receipt_file.read(), caption=caption, reply_markup=markup)
    except Exception as e:
        print(f"Error sending photo to admin: {e}")
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
# ዩኒቨርሳል የጨዋታ ውጤት ማዕከል
# ==========================================
@server.route('/api/race_result', methods=['POST'])
def race_result():
    data = request.json or {}
    user_id = data.get("user_id")
    bet_amount = float(data.get("bet_amount", 0))
    did_win = data.get("did_win", False)
    win_amount = float(data.get("win_amount", 0))
    details = data.get("details", "የሰፈር ጨዋታ")

    if not user_id or bet_amount <= 0:
        return jsonify({"status": "error", "message": "ትክክለኛ ያልሆነ መረጃ"}), 400

    current_balance = float(redis.hget("users:balance", user_id) or 0.0)
    
    # ተጫዋቹ ከተሸነፈ ባላንሱ ካስያዘው ያነሰ መሆን የለበትም (የሴኩሪቲ ቼክ)
    if not did_win and current_balance < bet_amount:
         return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

    if did_win:
        # ያሸነፈው ጠቅላላ ብር (Win Amount) ሲቀነስ ያስያዘው (Bet) የተጣራ ትርፍ ይሰጠናል
        net_change = win_amount - bet_amount
        redis.hincrbyfloat("users:balance", user_id, net_change)
    else:
        redis.hincrbyfloat("users:balance", user_id, -bet_amount)

    # ታሪክ መመዝገቢያ
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    status_str = "አሸንፏል 🎉" if did_win else "ተሸንፏል 😞"
    history_list.insert(0, {"type": f"{details}", "amount": bet_amount, "status": status_str})
    redis.set(f"history:{user_id}", json.dumps(history_list))

    return jsonify({"status": "success"})

# ==========================================
# የጨዋታ ማስጀመሪያ ፈቃድ ኤፒአይ
# ==========================================
@server.route('/api/start_game', methods=['POST'])
def start_game():
    data = request.json or {}
    user_id = data.get("user_id")
    bet_amount = float(data.get("bet_amount", 0))
    
    if not user_id or bet_amount <= 0:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400
        
    current_balance = float(redis.hget("users:balance", user_id) or 0.0)
    if current_balance < bet_amount:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

    return jsonify({"status": "ready"})

# ==========================================
# የዘውድና ጎፈር ጨዋታ ሎጂክ (የተስተካከለ)
# ==========================================
@server.route('/api/coin_flip', methods=['POST'])
def coin_flip_game():
    data = request.json or {}
    user_id = data.get("user_id")
    choice = data.get("choice")  # 'ዘውድ' ወይም 'ጎፈር'
    bet_amount = float(data.get("bet_amount", 0))

    if not user_id or bet_amount <= 0 or not choice:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    current_balance = float(redis.hget("users:balance", user_id) or 0.0)
    if current_balance < bet_amount:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

    sides = ["ዘውድ", "ጎፈር"]
    winning_side = random.choice(sides)
    did_win = (choice == winning_side)
    
    # ማስታወሻ፡ ፍሮንትአንዱ ውጤቱን በቀጥታ ወደ /api/race_result የማይልክ ከሆነ 
    # ሂሳቡ እዚህ ላይ ብቻ እንዲቀነስ/እንዲደመር ማድረግ ይቻላል። 
    # ነገር ግን ሁለቱንም ኤፒአይ የሚጠቀም ከሆነ እዚህ ጋር ባላንስ መቀየር የለብንም።
    # ለደህንነት ሲባል እዚህ ጋር ብቻ ቀጥታ እናሰላውና ታሪክ ላይ እንመዝግበው፡
    if did_win:
        net_change = bet_amount
        redis.hincrbyfloat("users:balance", user_id, net_change)
        message = f"🎉 እንኳን ደስ አለዎት! ሳንቲሙ {winning_side} ወጥቷል። {bet_amount * 2} ብር አሸንፈዋል!"
        status_str = "አሸንፏል 🎉"
    else:
        redis.hincrbyfloat("users:balance", user_id, -bet_amount)
        message = f"😞 መጥፎ እድል! ሳንቲሙ {winning_side} ወጥቷል። {bet_amount} ብር ተበልተዋል!"
        status_str = "ተሸንፏል 😞"

    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {"type": f"ዘውድና ጎፈር ({choice})", "amount": bet_amount, "status": status_str})
    redis.set(f"history:{user_id}", json.dumps(history_list))

    return jsonify({"status": "success", "message": message, "did_win": did_win, "winning_side": winning_side})

# ==========================================
# Callback Handler (Admin Actions)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("ok") or call.data.startswith("no"))
def process_admin_action(call):
    action, tx_type, tx_id, user_id, amount = call.data.split('|')
    amount = float(amount)
    
    tx_status = "completed" if action == "ok" else "refund"
    
    history_data = redis.get(f"history:{user_id}")
    if history_data:
        history_list = json.loads(history_data)
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
