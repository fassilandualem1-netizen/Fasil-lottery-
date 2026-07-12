import os
import random
import telebot
from flask import Flask, render_template, jsonify, request
from upstash_redis import Redis

# --- 1. Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com" 

# ቦቱ መልዕክት መላኪያ ብቻ ይሆናል (ዌብሁክ እና ፖሊንግ ሙሉ በሙሉ ይቆማሉ)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

# ያንተ የግል ቴሌግራም ID (መልዕክቶች ቀጥታ ወደ አንተ እንዲመጡ)
MY_PRIVATE_CHAT_ID =[8488592165]  

GAME_CONFIG = {
    "beg_rucha": {"name": "🐑 የበግ ሩጫ", "fee": 2, "multiplier": 0.02},
    "ayi_game": {"name": "🧀 የአይጧ ጨዋታ", "fee": 5, "multiplier": 0.50},
    "anbessa_aden": {"name": "🦁 የአንበሳ አደን", "fee": 10, "multiplier": 1.50},
    "coin_flip": {"name": "🪙 እጥፍ ወይስ ባዶ", "fee": 0, "multiplier": 2.0}
}

# 📢 በስተጀርባ ችግር ከተፈጠረ ላንተ በግል ሪፖርት ማድረጊያ
def report_error_to_admin(error_msg):
    try:
        bot.send_message(MY_PRIVATE_CHAT_ID, f"🚨 <b>ALERT: ሰርቨር ላይ ስህተት ተፈጥሯል!</b>\n\n<code>{error_msg}</code>")
    except Exception as e:
        print(f"Error reporting failed: {e}")

# --- 2. Flask API Routes (ለጨዋታው እና ለባላንስ) ---

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
            return jsonify({"status": "no_money", "message": "በቂ ብር የለዎትም!"}), 400

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

# --- 🪙 🪙 እጥፍ ወይስ ባዶ (ዘውድና ጎፈር) API መስመር ---
@server.route('/api/coin_flip', methods=['POST'])
def api_coin_flip():
    try:
        data = request.json
        user_id = str(data.get('user_id'))
        bet_amount = float(data.get('bet_amount', 0))
        user_choice = data.get('choice') # 'ዘውድ' ወይም 'ጎፈር'

        if bet_amount <= 0:
            return jsonify({"status": "error", "message": "ትክክለኛ የውርርድ መጠን ያስገቡ!"}), 400

        current_balance = float(redis.hget("users:balance", user_id) or 0)
        if current_balance < bet_amount:
            return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

        # 🎰 እጣ ማውጣት
        sides = ['ዘውድ', 'ጎፈር']
        winning_side = random.choice(sides)
        
        if user_choice == winning_side:
            # አሸነፈ (እጥፍ)
            redis.hincrbyfloat("users:balance", user_id, bet_amount)
            new_balance = current_balance + bet_amount
            return jsonify({
                "status": "win",
                "message": f"🪙 ውጤቱ: {winning_side} ሆኗል!\n🎉 እንኳን ደስ አለዎት! የ {bet_amount * 2} ብር አሸንፈዋል!",
                "new_balance": new_balance
            })
        else:
            # ተሸነፈ (ባዶ)
            redis.hincrbyfloat("users:balance", user_id, -bet_amount)
            new_balance = current_balance - bet_amount
            return jsonify({
                "status": "lose",
                "message": f"🪙 ውጤቱ: {winning_side} ሆኗል!\n😢 ይቅርታ፣ ተሸንፈዋል! {bet_amount} ብር ከባላንስዎ ላይ ቀንሷል።",
                "new_balance": new_balance
            })
    except Exception as e:
        report_error_to_admin(f"API coin_flip Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 📥 ከዌብአፕ ቀጥታ ወደ አንተ የግል ቴሌግራም የሚመጣ DEPOSIT ---
@server.route('/api/deposit', methods=['POST'])
def handle_web_deposit():
    try:
        user_id = request.form.get("user_id")
        user_name = request.form.get("user_name", "የሰፈር ልጅ")
        amount = request.form.get("amount")
        receipt_file = request.files.get("receipt")
        
        caption_text = (
            f"🔔 <b>አዲስ የ Deposit ጥያቄ ከዌብአፕ!</b>\n\n"
            f"👤 <b>ተጫዋች፦</b> {user_name}\n"
            f"🆔 <b>የላኪው ID:</b> <code>{user_id}</code>\n"
            f"💰 <b>የብር መጠን:</b> <b>{amount} ብር</b>\n\n"
            f"💡 ብሩ መግባቱን ስታረጋግጥ ወደ አድሚን ገጽህ በመሄድ ID <code>{user_id}</code> ላይ {amount} ብር ጨምርለት።"
        )
        
        # ዌብሁክ ሳይኖር ቦቱ ቀጥታ ላንተ የግል አካውንት ፎቶውን ይልካል
        bot.send_photo(chat_id=MY_PRIVATE_CHAT_ID, photo=receipt_file.stream.read(), caption=caption_text)
        return jsonify({"status": "success", "message": "የክፍያ ማረጋገጫዎ ለአስተዳዳሪው በግል ተልኳል!"})
    except Exception as e:
        report_error_to_admin(f"Web Deposit Error: {str(e)}")
        return jsonify({"status": "error", "message": f"ለአድሚን መላክ አልተቻለም: {str(e)}"}), 500

# --- 📤 ከዌብአፕ ቀጥታ ወደ አንተ የግል ቴሌግራም የሚመጣ WITHDRAW ---
@server.route('/api/withdraw', methods=['POST'])
def handle_web_withdraw():
    try:
        data = request.json
        user_id = str(data.get("user_id"))
        user_name = data.get("user_name", "የሰፈር ልጅ")
        amount = float(data.get("amount", 0))
        phone = data.get("phone", "").strip()
        
        current_balance = float(redis.hget("users:balance", user_id) or 0)
        if current_balance < amount:
            return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

        redis.hincrbyfloat("users:balance", user_id, -amount)
        
        message_text = (
            f"💸 <b>አዲስ የ Withdraw ጥያቄ ከዌብአፕ!</b>\n\n"
            f"👤 <b>ተጫዋች፦</b> {user_name}\n"
            f"🆔 <b>የጠያቂው ID:</b> <code>{user_id}</code>\n"
            f"📱 <b>የቴሌብር ስልክ:</b> <code>{phone}</code>\n"
            f"💰 <b>የማውጫ መጠን:</b> <b>{amount} ብር</b>\n"
        )
        
        bot.send_message(chat_id=MY_PRIVATE_CHAT_ID, text=message_text)
        return jsonify({"status": "success", "message": "የማውጫ ጥያቄዎ ለአስተዳዳሪው ደርሷል!"})
    except Exception as e:
        report_error_to_admin(f"Web Withdraw Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- 🔑 3. ለአንተ ብቻ የሚሆን የዳታቤዝ መቆጣጠሪያ ገጽ (Admin Dashboard) ---

@server.route('/secret-admin-panel', methods=['GET', 'POST'])
def admin_panel():
    msg = ""
    if request.method == 'POST':
        action = request.form.get("action")
        target_id = request.form.get("user_id").strip()
        
        if action == "add":
            amount = float(request.form.get("amount", 0))
            redis.hincrbyfloat("users:balance", target_id, amount)
            msg = f"✅ ለተጠቃሚ {target_id} {amount} ብር በተሳካ ሁኔታ ተጭኗል!"
            try: bot.send_message(target_id, f"🎉 የ <b>{amount} ብር</b> ዴፖዚትዎ ጸድቋል!")
            except: pass
            
        elif action == "deduct":
            amount = float(request.form.get("amount", 0))
            redis.hincrbyfloat("users:balance", target_id, -amount)
            msg = f"🛑 ከተጠቃሚ {target_id} {amount} ብር ተቀንሷል!"

    return f'''
    <html>
        <head><title>Admin Control Panel</title></head>
        <body style="padding:40px; font-family:sans-serif; text-align:center; background:#f4f4f4;">
            <h2> ሰፈር 3D ጌም - የአድሚን ማኔጀር 💻 </h2>
            <p style="color:green; font-weight:bold;">{msg}</p>
            <div style="background:white; padding:30px; display:inline-block; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.1);">
                <form method="POST">
                    <label>የተጫዋች Telegram ID:</label><br>
                    <input type="text" name="user_id" required style="padding:8px; margin:10px; width:250px;"><br>
                    <label>የብር መጠን:</label><br>
                    <input type="number" step="0.01" name="amount" required style="padding:8px; margin:10px; width:250px;"><br><br>
                    <button type="submit" name="action" value="add" style="background:green; color:white; padding:10px 20px; border:none; cursor:pointer; border-radius:4px;">➕ ብር ጫን (Add)</button>
                    <button type="submit" name="action" value="deduct" style="background:red; color:white; padding:10px 20px; border:none; cursor:pointer; border-radius:4px; margin-left:10px;">➖ ብር ቀንስ</button>
                </form>
            </div>
        </body>
    </html>
    '''

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
  