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
# ⚙️ Configuration (ማዋቀሪያዎች)
# ==========================================
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com"
ADMIN_ID = 8488592165  # የአድሚን ቴሌግራም ID

bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

# ==========================================
# 🌐 Webhook Setup
# ==========================================
try:
    bot.remove_webhook()
    time.sleep(0.5)
    bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
except Exception as e:
    print(f"Webhook Error: {e}")

# ==========================================
# 🛡️ Atomic Wallet Helpers (ደህንነቱ የተጠበቀ ዋሌት)
# ==========================================

def deduct_balance_safely(user_id: str, amount: float, game_mode: str = "real") -> str:
    """
    ይህ የ Lua ስክሪፕት በባላንስ ላይ Race Condition (የሳይበር ስርቆት/ድርብ ክፍያ) 
    እንዳይፈጠር በአቶሚክ ደረጃ ቼክ አድርጎ ሂሳብ ይቀንሳል።
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
        result = redis.eval(lua_script, [balance_key, user_id], [amount])
        return result
    except Exception as e:
        print(f"LUA Wallet Error: {e}")
        return "ERROR"

# ==========================================
# 📄 Frontend Routes (የገጽ ማሳያ መንገዶች)
# ==========================================
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/aviator')
def aviator_game():
    return render_template('aviator.html')

@server.route('/coin_flip_game')
def coin_flip_page():
    return render_template('coin_flip.html')


# ==========================================
# ✈️ Aviator Game APIs
# ==========================================
@server.route('/api/aviator/bet', methods=['POST'])
def aviator_bet_api():
    data = request.json or {}
    user_id = data.get("user_id")
    bet_amount = float(data.get("bet_amount", 0))
    game_mode = data.get("game_mode", "real") 

    if not user_id or bet_amount <= 0:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    deduct_status = deduct_balance_safely(user_id, bet_amount, game_mode)
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
    elif deduct_status == "ERROR":
        return jsonify({"status": "error", "message": "የሲስተም ስህተት ተከስቷል"}), 500

    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    new_balance = float(redis.hget(balance_key, user_id) or 0.0)
    return jsonify({"status": "success", "new_balance": new_balance})

@server.route('/api/aviator/cashout', methods=['POST'])
def aviator_cashout_api():
    data = request.json or {}
    user_id = data.get("user_id")
    bet_amount = float(data.get("bet_amount", 0))
    multiplier = float(data.get("multiplier", 1.0))
    game_mode = data.get("game_mode", "real")

    if not user_id or bet_amount <= 0 or multiplier < 1.0:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    win_amount = bet_amount * multiplier
    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    
    redis.hincrbyfloat(balance_key, user_id, win_amount)
    new_balance = float(redis.hget(balance_key, user_id) or 0.0)

    # የታሪክ ምዝገባ
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {
        "type": f"Aviator Win (x{multiplier}) [{game_mode.upper()}]", 
        "amount": win_amount, 
        "status": "completed",
        "date": time.strftime("%Y-%m-%d %H:%M")
    })
    redis.set(f"history:{user_id}", json.dumps(history_list))

    return jsonify({
        "status": "success", 
        "win_amount": round(win_amount, 2), 
        "new_balance": new_balance
    })




// የታሪክ ታብን ለመቀያየር
function switchWalletTab(tabName) {
    // ነባር ታቦችን ደብቅ
    document.getElementById("deposit-tab").classList.add("hidden");
    document.getElementById("withdraw-tab").classList.add("hidden");
    document.getElementById("history-tab").classList.add("hidden");

    // የተመረጠውን አሳይ
    document.getElementById(tabName).classList.remove("hidden");
    
    // ታሪክ ከሆነ ዳታውን Fetch አድርግ
    if(tabName === 'history-tab') {
        fetchHistory();
    }
}

// ታሪክን ከሰርቨር ማምጣት
function fetchHistory() {
    fetch(`/api/get_history?user_id=${userId}`)
    .then(res => res.json())
    .then(data => {
        const list = document.getElementById("history-list");
        list.innerHTML = ""; // ያረጀውን አጽዳ
        data.transactions.forEach(tx => {
            list.innerHTML += `
            <div class="flex justify-between items-center bg-gray-900 p-2 rounded text-[11px]">
                <div>
                    <div class="font-bold">${tx.type}</div>
                    <div class="text-gray-500">${tx.date}</div>
                </div>
                <div class="font-black ${tx.status === 'pending' ? 'text-yellow-500' : tx.status === 'completed' ? 'text-green-500' : 'text-red-500'}">
                    ${tx.amount} ETB (${tx.status})
                </div>
            </div>`;
        });
    });
}



# ==========================================
# 💰 Core Wallet APIs (የዋሌት ዋና ተግባራት)
# ==========================================

@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.json or {}
    user_id = data.get("user_id")
    game_mode = data.get("game_mode", "real")
    
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400
    
    if game_mode == "demo":
        balance_raw = redis.hget("users:demo_balance", user_id)
        if balance_raw is None:
            redis.hset("users:demo_balance", user_id, 10000.0)  # የሙከራ ብር ወደ 10,000 ከፍ ተደርጓል
            current_balance = 10000.0
        else:
            current_balance = float(balance_raw)
    else:
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
    
    # የታሪክ ምዝገባ በልዩ tx_id
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {
        "tx_id": tx_id,
        "type": "ገቢ", 
        "amount": amount, 
        "status": "pending", 
        "date": time.strftime("%Y-%m-%d %H:%M")
    })
    redis.set(f"history:{user_id}", json.dumps(history_list))
    
    # ለአድሚን የሚላክ Inline Button
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ አጽድቅ", callback_data=f"ok|deposit|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no|deposit|{tx_id}|{user_id}|{amount}")
    )
    
    caption = f"🔔 <b>አዲስ Deposit ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: <code>{user_id}</code>\n💰 መጠን: <b>{amount} ብር</b>\n🔑 TxID: <code>{tx_id}</code>"
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
        
    # ወጪ የሚደረገው ከእውነተኛ ባላንስ ላይ ብቻ ነው (በጊዜያዊነት Hold ይደረጋል)
    deduct_status = deduct_balance_safely(user_id, amount, "real")
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ እውነተኛ ባላንስ የለዎትም"}), 400
    elif deduct_status == "ERROR":
        return jsonify({"status": "error", "message": "የሲስተም ስህተት ተፈጥሯል"}), 500
    
    tx_id = str(uuid.uuid4())[:8]
    tx_data = {"user_id": user_id, "amount": amount, "type": "withdraw", "status": "pending"}
    redis.set(f"tx:{tx_id}", json.dumps(tx_data))
    
    # የታሪክ ምዝገባ በልዩ tx_id
    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {
        "tx_id": tx_id,
        "type": "ወጪ", 
        "amount": amount, 
        "status": "pending", 
        "date": time.strftime("%Y-%m-%d %H:%M")
    })
    redis.set(f"history:{user_id}", json.dumps(history_list))
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ ተከፍሏል", callback_data=f"ok|withdraw|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ሰርዝ (ተመላሽ አድርግ)", callback_data=f"no|withdraw|{tx_id}|{user_id}|{amount}")
    )
    
    msg = f"💸 <b>አዲስ Withdraw ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: <code>{user_id}</code>\n🏦 ባንክ: {bank_name}\n👤 የአካውንት ስም: {account_name}\n💳 አካውንት/ስልክ: <code>{phone}</code>\n💰 መጠን: <b>{amount} ብር</b>\n🔑 TxID: <code>{tx_id}</code>"
    bot.send_message(ADMIN_ID, msg, reply_markup=markup)
    return jsonify({"status": "success"})


# ==========================================
# 🪙 Coin Flip Game Logic (ዘውድና ጎፈር ጨዋታ)
# ==========================================
@server.route('/api/coin_flip', methods=['POST'])
def coin_flip_game():
    data = request.json or {}
    user_id = data.get("user_id")
    choice = data.get("choice")  # 'ዘውድ' ወይም 'ጎፈር'
    bet_amount = float(data.get("bet_amount", 0))
    game_mode = data.get("game_mode", "real")

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

    # የታሪክ ምዝገባ
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
# 🎁 Daily Bonus & 🏆 Leaderboard
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

    gift_amount = random.choice([1, 2, 3, 4, 5])
    redis.hincrbyfloat("users:balance", user_id, gift_amount)

    history_data = redis.get(f"history:{user_id}")
    history_list = json.loads(history_data) if history_data else []
    history_list.insert(0, {"type": "ነጻ ዕድል ሩሌት", "amount": gift_amount, "status": "completed", "date": time.strftime("%Y-%m-%d")})
    redis.set(f"history:{user_id}", json.dumps(history_list))

    return jsonify({"status": "success", "gift_amount": float(gift_amount)})

@server.route('/api/get_leaderboard', methods=['POST'])
def get_leaderboard():
    try:
        all_balances = redis.hgetall("users:balance")
        if not all_balances:
            return jsonify({"status": "success", "leaders": []})

        leaders = []
        for u_id, bal in all_balances.items():
            if u_id == str(ADMIN_ID):
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
# 🤖 Telegram Admin Callback Handler (የእጅ ማጽደቂያ)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("ok") or call.data.startswith("no"))
def process_admin_action(call):
    try:
        action, tx_type, tx_id, user_id, amount = call.data.split('|')
        amount = float(amount)
    except Exception as e:
        bot.answer_callback_query(call.id, "⚠️ የዳታ ስህተት ተከስቷል!")
        return

    tx_key = f"tx:{tx_id}"
    tx_data_raw = redis.get(tx_key)
    
    if not tx_data_raw:
        bot.answer_callback_query(call.id, "❌ ይህ ትራንዛክሽን አልተገኘም!")
        return
        
    tx_data = json.loads(tx_data_raw)
    if tx_data.get("status") != "pending":
        bot.answer_callback_query(call.id, "⚠️ ይህ ጥያቄ ቀደም ብሎ ምላሽ አግኝቷል!")
        return

    # በትክክለኛው ሁኔታ መሰረት ስሞችን መምረጥ
    if tx_type == "deposit":
        tx_status = "completed" if action == "ok" else "failed"
        status_text = "🟢 ጸድቋል (Completed)" if action == "ok" else "🔴 ውድቅ ተደርጓል (Failed)"
    else:
        tx_status = "completed" if action == "ok" else "refunded"
        status_text = "🟢 ተከፍሏል (Completed)" if action == "ok" else "🔴 ተሰርዟል/ተመልሷል (Refunded)"

    # የትራንዛክሽን ሁኔታን ማዘመን
    tx_data["status"] = tx_status
    redis.set(tx_key, json.dumps(tx_data))
    
    # 1. የተጠቃሚውን የትራንዛክሽን ታሪክ በ tx_id አረጋግጦ ማዘመን
    history_data = redis.get(f"history:{user_id}")
    if history_data:
        history_list = json.loads(history_data)
        for item in history_list:
            if item.get("tx_id") == tx_id:
                item["status"] = tx_status
                break
        redis.set(f"history:{user_id}", json.dumps(history_list))

    # 2. የገንዘብ መጠንን ማስተካከልና ለተጠቃሚው በቴሌግራም መልዕክት መላክ
    if tx_type == "deposit":
        if action == "ok":
            redis.hincrbyfloat("users:balance", user_id, amount)
            try:
                bot.send_message(user_id, f"🎉 <b>የገቢ (Deposit) ጥያቄዎ ጸድቋል!</b>\n\n💰 የገንዘብ መጠን: <b>{amount} ETB</b> ዋሌትዎ ላይ ተጨምሯል።")
            except Exception as e:
                print(f"Failed to notify user {user_id}: {e}")
        else:
            try:
                bot.send_message(user_id, f"❌ <b>የገቢ (Deposit) ጥያቄዎ ውድቅ ተደርጓል!</b>\n\n💰 የገንዘብ መጠን: <b>{amount} ETB</b>\n🔍 እባክዎ የላኩት የክፍያ ደረሰኝ ትክክለኛ መሆኑን ያረጋግጡ።")
            except Exception as e:
                print(f"Failed to notify user {user_id}: {e}")
            
    elif tx_type == "withdraw":
        if action == "ok":
            try:
                bot.send_message(user_id, f"🎉 <b>የወጪ (Withdraw) ጥያቄዎ ተከፍሏል!</b>\n\n💰 የገንዘብ መጠን: <b>{amount} ETB</b> ወደ ባንክ አካውንትዎ በተሳካ ሁኔታ ተልኳል።")
            except Exception as e:
                print(f"Failed to notify user {user_id}: {e}")
        else:
            # ጥያቄው ውድቅ ከተደረገ በ Hold ላይ የነበረውን ብር መመለስ (Refund)
            redis.hincrbyfloat("users:balance", user_id, amount)
            try:
                bot.send_message(user_id, f"❌ <b>የወጪ (Withdraw) ጥያቄዎ ተሰርዟል!</b>\n\n💰 የገንዘብ መጠን: <b>{amount} ETB</b> ወደ ዋሌትዎ ተመልሷል።")
            except Exception as e:
                print(f"Failed to notify user {user_id}: {e}")
            
    # ለአድሚን በቴሌግራም ላይ ምላሽ መስጠት
    bot.answer_callback_query(call.id, f"ጥያቄው: {status_text}")
    
    # ቁልፎቹን በማጥፋት (reply_markup=None) መልዕክቱን ማደስ
    if call.message.caption:
        new_caption = f"{call.message.caption}\n\n🏷️ <b>ሁኔታ:</b> {status_text}"
        bot.edit_message_caption(caption=new_caption, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
    else:
        new_text = f"{call.message.text}\n\n🏷️ <b>ሁኔታ:</b> {status_text}"
        bot.edit_message_text(text=new_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)

@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

# ==========================================
# 🚀 Telegram Start Command
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    web_app_info = WebAppInfo(url=WEB_APP_URL)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 Play Games", web_app=web_app_info))
    bot.reply_to(message, "👋 እንኳን ወደ ሰፈር ቦት በደህና መጡ! ለመጫወት እና ዋሌትዎን ለመጠቀም ከታች ያለውን ቁልፍ ይጫኑ።", reply_markup=markup)

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
