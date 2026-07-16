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
# 🛡️ Atomic Helper Functions (ለStability የተጨመሩ)
# ==========================================

def deduct_balance_safely(user_id: str, amount: float, game_mode: str = "real") -> str:
    """
    ይህ Lua Script በባላንስ ላይ Race condition እንዳይፈጠር በአቶሚክ ደረጃ 
    ቼክ አድርጎ ሂሳቡን ይቀንሳል። 
    - Real Mode ከሆነ ከ 'users:balance' ይቀንሳል
    - Demo Mode ከሆነ ከ 'users:demo_balance' ይቀንሳል
    """
    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    
    lua_script = """
    local balance = tonumber(redis.call('HGET', KEYS[1], KEYS[2]) or "0")
    local amount = tonumber(ARGV[1])
    if balance < amount then
        return "INSUFFICIENT"
    end
    redis.call('HINCRBYFLOAT', KEYS[1], KEYS[2], -amount)
    return "SUCCESS"
    """
    try:
        # KEYS[1] = balance_key, KEYS[2] = user_id
        result = redis.eval(lua_script, [balance_key, user_id], [amount])
        return result
    except Exception as e:
        print(f"LUA Execution Error: {e}")
        return "ERROR"

# ==========================================
# Frontend Routes
# ==========================================
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/dino')
def dino_game():
    return render_template('dino.html')

@server.route('/coin_flip_game')
def coin_flip_page():
    return render_template('coin_flip.html')


# ==========================================
# 🦖 የዲኖ ራን (Dino Run) ጨዋታ ሎጂክ ከWallet ጋር
# ==========================================
@server.route('/api/dino/bet', methods=['POST'])
def dino_bet_api():
    data = request.json or {}
    user_id = data.get("user_id")
    bet_amount = float(data.get("bet_amount", 0))
    game_mode = data.get("game_mode", "real") # "real" ወይም "demo"

    if not user_id or bet_amount <= 0:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    # በአቶሚክ መንገድ ካሰበው Mode ላይ ባላንሱን እንቀንሳለን
    deduct_status = deduct_balance_safely(user_id, bet_amount, game_mode)
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
    elif deduct_status == "ERROR":
        return jsonify({"status": "error", "message": "የሲስተም ስህተት ተከስቷል"}), 500

    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    new_balance = float(redis.hget(balance_key, user_id) or 0.0)
    return jsonify({"status": "success", "new_balance": new_balance})

@server.route('/api/dino/cashout', methods=['POST'])
def dino_cashout_api():
    data = request.json or {}
    user_id = data.get("user_id")
    bet_amount = float(data.get("bet_amount", 0))
    multiplier = float(data.get("multiplier", 1.0))
    game_mode = data.get("game_mode", "real") # "real" ወይም "demo"

    if not user_id or bet_amount <= 0 or multiplier < 1.0:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    win_amount = bet_amount * multiplier

    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    redis.hincrbyfloat(balance_key, user_id, win_amount)
    new_balance = float(redis.hget(balance_key, user_id) or 0.0)

    return jsonify({
        "status": "success", 
        "win_amount": round(win_amount, 2), 
        "new_balance": new_balance
    })

# ==========================================
# 🦖 ቋሚ የዲኖ ጨዋታ ታሪክ (Dino Game History) በRedis
# ==========================================
@server.route('/api/get_history', methods=['GET'])
def get_dino_history_api():
    try:
        history_data = redis.get("dino:crash_history")
        history_list = json.loads(history_data) if history_data else []
        
        if not history_list:
            history_list = [1.28, 2.68, 1.44, 4.36, 2.02, 1.91, 31.23]
            redis.set("dino:crash_history", json.dumps(history_list))
            
        return jsonify({"status": "success", "history_data": history_list})
    except Exception as e:
        print(f"Error fetching dino history: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@server.route('/api/save_history', methods=['POST'])
def save_dino_history_api():
    data = request.json or {}
    multiplier = data.get("multiplier")

    if multiplier is None:
        return jsonify({"status": "error", "message": "Multiplier is missing"}), 400

    try:
        history_data = redis.get("dino:crash_history")
        history_list = json.loads(history_data) if history_data else []
        history_list.insert(0, float(multiplier))

        if len(history_list) > 20:
            history_list.pop()

        redis.set("dino:crash_history", json.dumps(history_list))
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Error saving dino history: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# API Routes (Core Functionality)
# ==========================================

@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.json or {}
    user_id = data.get("user_id")
    game_mode = data.get("game_mode", "real") # "real" ወይም "demo" (ዲፎልት 'real' ነው)
    
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400
    
    if game_mode == "demo":
        # አዲስ ተጫዋች በሙከራ ሞድ ሲገባ 1000 ETB በነጻ ይሰጠዋል
        balance_raw = redis.hget("users:demo_balance", user_id)
        if balance_raw is None:
            redis.hset("users:demo_balance", user_id, 1000.0)
            current_balance = 1000.0
        else:
            current_balance = float(balance_raw)
    else:
        # እውነተኛው ባላንስ (በተሌብር/በባንክ የሚሞላው)
        balance_raw = redis.hget("users:balance", user_id)
        if balance_raw is None:
            redis.hset("users:balance", user_id, 0.0)
            current_balance = 0.0
        else:
            current_balance = float(balance_raw)
        
    return jsonify({"status": "success", "balance": current_balance, "mode": game_mode})

@server.route('/api/get_user_history', methods=['POST'])
def get_user_history():
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
        
    # ወጪ ጥያቄ የሚሰራው ከእውነተኛው ባላንስ ('real') ላይ ብቻ ነው
    deduct_status = deduct_balance_safely(user_id, amount, "real")
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ እውነተኛ ባላንስ የለዎትም"}), 400
    elif deduct_status == "ERROR":
        return jsonify({"status": "error", "message": "የሲስተም ስህተት ተፈጥሯል፣ እባክዎ እንደገና ይሞክሩ"}), 500
    
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
        InlineKeyboardButton("❌ ሰርዝ (ተመላሽ አድርግ)", callback_data=f"no|withdraw|{tx_id}|{user_id}|{amount}")
    )
    
    msg = f"💸 <b>አዲስ Withdraw ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: {user_id}\n🏦 ባንክ: {bank_name}\n👤 የአካውንት ስም: {account_name}\n💳 አካውንት/ስልክ: {phone}\n💰 መጠን: {amount} ብር\n🔑 TxID: {tx_id}"
    bot.send_message(ADMIN_ID, msg, reply_markup=markup)
    return jsonify({"status": "success"})

# ==========================================
# የዘውድና ጎፈር ጨዋታ ሎጂክ (በሁለቱም Mode ይሰራል)
# ==========================================
@server.route('/api/coin_flip', methods=['POST'])
def coin_flip_game():
    data = request.json or {}
    user_id = data.get("user_id")
    choice = data.get("choice")  # 'ዘውድ' ወይም 'ጎፈር'
    bet_amount = float(data.get("bet_amount", 0))
    game_mode = data.get("game_mode", "real") # "real" ወይም "demo"

    if not user_id or bet_amount <= 0 or not choice:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    deduct_status = deduct_balance_safely(user_id, bet_amount, game_mode)
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
    elif deduct_status == "ERROR":
        return jsonify({"status": "error", "message": "የሲስተም ስህተት ተከስቷል"}), 500

    sides = ["ዘውድ", "ጎፈር"]
    winning_side = random.choice(sides)
    did_win = (choice == winning_side)
    
    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    
    if did_win:
        redis.hincrbyfloat(balance_key, user_id, bet_amount * 2)
        status_str = "completed"
        game_status = "win"
    else:
        status_str = "failed"
        game_status = "lose"

    new_balance = float(redis.hget(balance_key, user_id) or 0.0)

    # የታሪክ ምዝገባ (የተጫወተበትን Mode ይጨምራል)
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {
        "type": f"ዘውድና ጎፈር ({choice}) [{game_mode.upper()}]", 
        "amount": bet_amount, 
        "status": status_str,
        "date": time.strftime("%Y-%m-%d")
    })
    redis.set(f"history:{user_id}", json.dumps(history_list))

    return jsonify({
        "status": game_status, 
        "result": winning_side, 
        "new_balance": new_balance
    })

# ==========================================
# 🎁 የዕለቱ ነጻ ዕድል (Claim Daily Bonus) - ወደ Real Balance ብቻ ይገባል
# ==========================================
@server.route('/api/claim_daily', methods=['POST'])
def claim_daily():
    data = request.json or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    cooldown_key = f"daily_bonus:cooldown:{user_id}"
    
    is_claimed_today = redis.set(cooldown_key, "claimed", ex=86400, nx=True)
    if not is_claimed_today:
        return jsonify({"status": "error", "message": "የዛሬውን ነጻ ዕድል ወስደዋል! እባክዎ ከ24 ሰዓት በኋላ ይመለሱ።"})

    gifts = [1, 2, 3, 4, 5]
    gift_amount = random.choice(gifts)

    # ነጻ ዕድል ሁልጊዜ ወደ እውነተኛው ዋሌት (Real Balance) ይገባል
    redis.hincrbyfloat("users:balance", user_id, gift_amount)

    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {
        "type": "ነጻ ዕድል ሩሌት", 
        "amount": gift_amount, 
        "status": "completed",
        "date": time.strftime("%Y-%m-%d")
    })
    redis.set(f"history:{user_id}", json.dumps(history_list))

    return jsonify({"status": "success", "gift_amount": float(gift_amount)})

# ==========================================
# 🏆 የሳምንቱ መሪዎች ሰሌዳ (Leaderboard) - በእውነተኛ ባላንስ ብቻ
# ==========================================
@server.route('/api/get_leaderboard', methods=['POST'])
def get_leaderboard():
    try:
        all_balances = redis.hgetall("users:balance")
        if not all_balances:
            return jsonify({"status": "success", "leaders": []})

        leaders = []
        for u_id, bal in all_balances.items():
            if u_id == str(ADMIN_ID) or u_id == "2165":
                continue
            leaders.append({
                "user_id": u_id,
                "user_name": f"ተጫዋች_{u_id[-4:]}",
                "balance": float(bal)
            })

        leaders.sort(key=lambda x: x["balance"], reverse=True)
        return jsonify({"status": "success", "leaders": leaders[:5]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# Callback Handler (Admin Actions)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("ok") or call.data.startswith("no"))
def process_admin_action(call):
    action, tx_type, tx_id, user_id, amount = call.data.split('|')
    amount = float(amount)
    
    tx_key = f"tx:{tx_id}"
    tx_data_raw = redis.get(tx_key)
    
    if not tx_data_raw:
        bot.answer_callback_query(call.id, "❌ ይህ ትራንዛክሽን በሲስተሙ ውስጥ አልተገኘም!")
        return
        
    tx_data = json.loads(tx_data_raw)
    if tx_data.get("status") != "pending":
        bot.answer_callback_query(call.id, "⚠️ ይህ ጥያቄ ቀደም ብሎ ምላሽ አግኝቷል!")
        return

    tx_status = "completed" if action == "ok" else "refund"
    tx_data["status"] = tx_status
    redis.set(tx_key, json.dumps(tx_data))
    
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
            # እውነተኛው ዋሌት ላይ ይደመራል
            redis.hincrbyfloat("users:balance", user_id, amount)
            bot.send_message(user_id, f"✅ የእርስዎ {amount} ብር ገቢ ጸድቋል!")
        else:
            bot.send_message(user_id, f"❌ የእርስዎ {amount} ብር የገቢ ጥያቄ ውድቅ ተደርጓል።")
            
    elif tx_type == "withdraw":
        if action == "ok":
            bot.send_message(user_id, f"💰 የእርስዎ {amount} ብር ወጪ ተከፍሏል!")
        else:
            # ውድቅ ከተደረገ እውነተኛው ዋሌት ላይ ይመለሳል
            redis.hincrbyfloat("users:balance", user_id, amount)
            bot.send_message(user_id, f"❌ የእርስዎ {amount} ብር የወጪ ጥያቄ ውድቅ ስለተደረገ ወደ አካውንትዎ ተመልሷል።")
            
    status_text = "✅ ተጠናቋል" if action == "ok" else "❌ ውድቅ ተደርጓል"
    bot.answer_callback_query(call.id, f"ጥያቄው {status_text} ሆኗል")
    
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
