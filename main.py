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
# Frontend Routes
# ==========================================
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/coin_flip_game')
def coin_flip_page():
    return render_template('coin_flip.html')

# ==========================================
# API Routes (Core Wallet & History)
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
# G1. Coin Flip Core Logic (With Streak Tracking)
# ==========================================
@server.route('/api/coin_flip', methods=['POST'])
def coin_flip():
    data = request.json or {}
    user_id = data.get("user_id")
    bet_amount = float(data.get("bet_amount", 0))
    choice = data.get("choice")
    
    if not user_id or bet_amount <= 0 or not choice:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ!"})
        
    current_balance = float(redis.hget("users:balance", user_id) or 0.0)
    if current_balance < bet_amount:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"})
        
    sides = ["ዘውድ", "ጎፈር"]
    result = random.choice(sides)
    
    # የተጠቃሚውን ስም ለLeaderboard ለማዘጋጀት ከቴሌግራም ዳታቤዝ ወይም በነባሪ መውሰድ
    user_name = redis.hget("users:username", user_id) or f"ተጫዋች_{str(user_id)[-4:]}"
    
    if choice == result:
        # አሸናፊ ሲሆን የStreak ቁጥር በ 1 ይጨምራል
        current_streak = int(redis.hincrby("users:current_streak", user_id, 1))
        
        # 3ኛ ተከታታይ ድል ላይ ሲደርስ 1.5x የStreak ቦነስ ማበረታቻ መስጠት
        if current_streak == 3:
            bonus_amount = bet_amount * 1.5
            redis.hincrbyfloat("users:balance", user_id, bonus_amount)
            msg = f"🪙 ውጤቱ {result} ሆኗል! 🔥 የ 3x STREAK ቦነስ ጨምሮ {bet_amount + bonus_amount} ብር አሸንፈዋል! 🎉"
        else:
            redis.hincrbyfloat("users:balance", user_id, bet_amount)
            msg = f"🪙 ውጤቱ {result} ሆኗል! እንኳን ደስ አለዎት {bet_amount * 2} ብር አሸንፈዋል! 🎉"
            
        status = "win"
        status_history = "አሸንፏል 🎉"
        
        # ከፍተኛውን Streak (Best Streak) ካሸነፈ በሊደርቦርዱ Sorted Set ላይ ማዘመን
        best_streak = int(redis.hget("users:best_streak", user_id) or 0)
        if current_streak > best_streak:
            redis.hset("users:best_streak", user_id, current_streak)
            # Redis Sorted Set (ZADD) በመጠቀም ለሊደርቦርድ ማስቀመጥ
            redis.zadd("leaderboard:streaks", {f"{user_name}": current_streak})
            
    else:
        # ከተሸነፈ የStreak ዜሮ (0) ይሆናል
        redis.hset("users:current_streak", user_id, 0)
        redis.hincrbyfloat("users:balance", user_id, -bet_amount)
        status = "lose"
        msg = f"🪙 ውጤቱ {result} ሆኗል! ይቅርታ፣ {bet_amount} ብር ተሸንፈዋል።"
        status_history = "ተሸንፏል 😞"
        
    new_balance = float(redis.hget("users:balance", user_id) or 0.0)
    
    # ታሪክ መዝገብ
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {"type": f"ዘውድና ጎፈር ({choice})", "amount": bet_amount, "status": status_history})
    redis.set(f"history:{user_id}", json.dumps(history_list))
    
    return jsonify({
        "status": status, 
        "result": result, 
        "message": msg,
        "new_balance": new_balance
    })

# ==========================================
# G2. Fortune Wheel API (Daily Cooldown System)
# ==========================================
@server.route('/api/claim_daily', methods=['POST'])
def claim_daily():
    data = request.json or {}
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400
        
    # በየ 24 ሰዓቱ (86400 ሰከንድ) አንድ ጊዜ ብቻ እንዲሽከረከር መቆጣጠሪያ ኪይ (Key)
    cooldown_key = f"daily_cooldown:{user_id}"
    is_claimed = redis.get(cooldown_key)
    
    if is_claimed:
        return jsonify({"status": "error", "message": "የዕለቱን ነጻ ዕድል አስቀድመው ወስደዋል! ከ24 ሰዓት በኋላ ይሞክሩ።"})
        
    # በነባሪነት የሩሌቱ ዕድሎች (1, 2, 3, 4, 5 ብር)
    wheel_options = [1, 2, 3, 4, 5]
    gift_amount = random.choice(wheel_options)
    
    # ባላንስ ላይ መጨመር
    redis.hincrbyfloat("users:balance", user_id, float(gift_amount))
    
    # የ 24 ሰዓት ገደብ ማስቀመጥ (TTL = 86400)
    redis.setex(cooldown_key, 86400, "claimed")
    
    # ወደ ታሪክ መዝገብ ማስገባት
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {"type": "ነጻ ሩሌት ስጦታ 🎁", "amount": float(gift_amount), "status": "ተጠናቋል"})
    redis.set(f"history:{user_id}", json.dumps(history_list))
    
    return jsonify({
        "status": "success",
        "gift_amount": gift_amount,
        "message": f"እንኳን ደስ አለዎት! {gift_amount} ብር ወደ አካውንትዎ ተጨምሯል።"
    })

# ==========================================
# G3. Leaderboard API (Top 5 Active Streak Heroes)
# ==========================================
@server.route('/api/get_leaderboard', methods=['POST'])
def get_leaderboard():
    try:
        # ከRedis Sorted Set ላይ ከፍተኛ የ-Streak ውጤት ያላቸውን ምርጥ 5 ተጫዋቾች በቅደም ተከተል መውሰድ
        # ZREVRANGEBYSCORE ወይም zrevrange በ upstash-redis አጠቃቀም መሠረት
        top_leaders = redis.zrevrange("leaderboard:streaks", 0, 4, withscores=True)
        
        leaders_list = []
        # top_leaders ፎርማት [['ዮናስ', 8], ['ሳሚ', 6]...] ሊሆን ይችላል
        for leader in top_leaders:
            name = leader[0]
            streak_score = int(leader[1])
            leaders_list.append({
                "user_name": name,
                "streak": streak_score
            })
            
        return jsonify({
            "status": "success",
            "leaders": leaders_list
        })
    except Exception as e:
        print(f"Leaderboard Error: {e}")
        return jsonify({"status": "error", "message": "ሊደርቦርዱን ማምጣት አልተቻለም"}), 500

# ==========================================
# Callback & Webhook Handlers
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

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "የሰፈር ልጅ"
    
    # የተጠቃሚውን ስም ለሊደርቦርድ እንዲያገለግል በRedis ማስቀመጥ
    redis.hset("users:username", user_id, first_name)
    
    web_app_info = WebAppInfo(url=WEB_APP_URL)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 Play", web_app=web_app_info))
    bot.reply_to(message, f"እንኳን ደህና መጡ {first_name}! ጨዋታዎችን ለመጀመር Play ን ይጫኑ።", reply_markup=markup)

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
