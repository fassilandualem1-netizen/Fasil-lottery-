import os
import random
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, render_template, jsonify, request
from upstash_redis import Redis

# --- 1. Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com" 

# የአድሚን ግሩፕ ID እና የአንተ የግል ID
ADMIN_GROUP_ID = -1003943321922
MY_PRIVATE_CHAT_ID = 8488592165

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

GAME_CONFIG = {
    "beg_rucha": {"name": "🐑 የበግ ሩጫ", "fee": 2, "multiplier": 0.02},
    "ayi_game": {"name": "🧀 የአይጧ ጨዋታ", "fee": 5, "multiplier": 0.50},
    "anbessa_aden": {"name": "🦁 የአንበሳ አደን", "fee": 10, "multiplier": 1.50},
    "coin_flip": {"name": "🪙 እጥፍ ወይስ ባዶ", "fee": 0, "multiplier": 2.0}
}

def report_error_to_admin(error_msg):
    try: 
        bot.send_message(MY_PRIVATE_CHAT_ID, f"🚨 <b>ALERT: ሰርቨር ላይ ስህተት ተፈጥሯል!</b>\n\n<code>{error_msg}</code>")
    except: 
        pass

# --- 2. Flask API Routes ---
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.json
    user_id = str(data.get('user_id'))
    balance = float(redis.hget("users:balance", user_id) or 0)
    return jsonify({"status": "success", "balance": balance})

# አዲስ የ Deposit ጥያቄ (ወደ ግሩፕ የሚላክ)
@server.route('/api/deposit', methods=['POST'])
def handle_web_deposit():
    try:
        user_id = request.form.get("user_id")
        user_name = request.form.get("user_name", "የሰፈር ልጅ")
        amount = request.form.get("amount")
        receipt_file = request.files.get("receipt")
        
        # ፎቶ ካልተላከ የሚሰጥ ምላሽ (Error Prevention)
        if not receipt_file or receipt_file.filename == '':
            return jsonify({"status": "error", "message": "እባክዎ የክፍያ ማረጋገጫ (Screenshot) ያያይዙ!"}), 400
        
        caption_text = f"🔔 <b>አዲስ የ Deposit ጥያቄ!</b>\n\n👤 <b>ተጫዋች፦</b> {user_name}\n🆔 <b>ID:</b> <code>{user_id}</code>\n💰 <b>መጠን:</b> <b>{amount} ብር</b>"
        
        markup = InlineKeyboardMarkup()
        approve_url = f"{WEB_APP_URL}/quick-approve?user_id={user_id}&amount={amount}"
        reject_url = f"{WEB_APP_URL}/quick-reject?user_id={user_id}"
        markup.add(InlineKeyboardButton("✅ አጽድቅ", url=approve_url),
                   InlineKeyboardButton("❌ አትም", url=reject_url))
        
        bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=receipt_file.stream.read(), caption=caption_text, reply_markup=markup)
        return jsonify({"status": "success", "message": "ጥያቄዎ ለአስተዳዳሪው ተልኳል!"})
    except Exception as e:
        report_error_to_admin(f"Web Deposit Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@server.route('/quick-approve', methods=['GET'])
def quick_approve():
    try:
        target_id = request.args.get("user_id")
        amount = float(request.args.get("amount", 0))
        redis.hincrbyfloat("users:balance", target_id, amount)
        try: 
            bot.send_message(target_id, f"🎉 የ <b>{amount} ብር</b> ዴፖዚትዎ ጸድቋል!")
        except: 
            pass
        return f'<html><body style="text-align:center; padding-top:50px; font-family:sans-serif; color:green;"><h1>✅ ለተጠቃሚ {target_id} {amount} ብር ተጭኗል!</h1></body></html>'
    except Exception as e: 
        return f"Error: {str(e)}", 500

@server.route('/quick-reject', methods=['GET'])
def quick_reject():
    try:
        target_id = request.args.get("user_id")
        try: 
            bot.send_message(target_id, "❌ ይቅርታ፣ የላኩት የክፍያ ማረጋገጫ ተቀባይነት አላገኘም! እባክዎ እንደገና ይሞክሩ።")
        except: 
            pass
        return f'<html><body style="text-align:center; padding-top:50px; font-family:sans-serif; color:red;"><h1>❌ ለተጠቃሚ {target_id} መከልከያ መልዕክት ተልኳል።</h1></body></html>'
    except Exception as e: 
        return f"Error: {str(e)}", 500

@server.route('/api/withdraw', methods=['POST'])
def handle_web_withdraw():
    try:
        data = request.json
        user_id = str(data.get("user_id"))
        user_name = data.get("user_name", "የሰፈር ልጅ")
        phone = data.get("phone", "ስልክ አልተገኘም") # ከ JS የተላከው key "phone" ነው
        amount = float(data.get("amount", 0))
        
        current_balance = float(redis.hget("users:balance", user_id) or 0)
        if current_balance < amount: 
            return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
        
        # Withdraw ጥያቄውን ወደ አድሚን ግሩፕ መላክ
        msg = (f"💸 <b>አዲስ የ Withdraw ጥያቄ!</b>\n\n"
               f"👤 <b>ተጠቃሚ:</b> {user_name}\n"
               f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
               f"📱 <b>ስልክ:</b> <code>{phone}</code>\n"
               f"💰 <b>መጠን:</b> <b>{amount} ብር</b>")
        
        markup = InlineKeyboardMarkup()
        # ADMIN_SECRET_TOKEN መጠቀሙን አትርሳ
        paid_url = f"{WEB_APP_URL}/mark-paid?user_id={user_id}&amount={amount}&token={ADMIN_SECRET_TOKEN}"
        markup.add(InlineKeyboardButton("✅ Paid (ተከፍሏል)", url=paid_url))
        
        bot.send_message(chat_id=ADMIN_GROUP_ID, text=msg, reply_markup=markup, parse_mode="HTML")
        
        return jsonify({"status": "success", "message": "ጥያቄዎ ለአድሚን ደርሷል!"})
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)}), 500

# ጨዋታዎች
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
        return jsonify({"status": "error", "message": str(e)}), 500

@server.route('/api/coin_flip', methods=['POST'])
def api_coin_flip():
    try:
        data = request.json
        user_id = str(data.get('user_id'))
        bet_amount = float(data.get('bet_amount', 0))
        user_choice = data.get('choice')
        
        # 0 ወይም ከዛ በታች የሆኑ ቁጥሮችን መከልከል
        if bet_amount <= 0:
            return jsonify({"status": "error", "message": "ትክክለኛ የውርርድ መጠን ያስገቡ!"}), 400
            
        current_balance = float(redis.hget("users:balance", user_id) or 0)
        if current_balance < bet_amount: 
            return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
            
        sides = ['ዘውድ', 'ጎፈር']
        winning_side = random.choice(sides)
        
        if user_choice == winning_side:
            redis.hincrbyfloat("users:balance", user_id, bet_amount)
            return jsonify({"status": "win", "message": f"🪙 ውጤቱ: {winning_side}!", "new_balance": current_balance + bet_amount})
        else:
            redis.hincrbyfloat("users:balance", user_id, -bet_amount)
            return jsonify({"status": "lose", "message": f"🪙 ውጤቱ: {winning_side}!", "new_balance": current_balance - bet_amount})
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)}), 500

@server.route('/secret-admin-panel', methods=['GET', 'POST'])
def admin_panel():
    msg = ""
    if request.method == 'POST':
        action = request.form.get("action")
        target_id = request.form.get("user_id").strip()
        if action == "add":
            amount = float(request.form.get("amount", 0))
            redis.hincrbyfloat("users:balance", target_id, amount)
            msg = f"✅ ለተጠቃሚ {target_id} {amount} ብር ተጭኗል!"
        elif action == "deduct":
            amount = float(request.form.get("amount", 0))
            redis.hincrbyfloat("users:balance", target_id, -amount)
            msg = f"🛑 ከተጠቃሚ {target_id} {amount} ብር ተቀንሷል!"
            
    return f'''
    <html>
    <body style="padding:40px; font-family:sans-serif; text-align:center; background-color:#f4f4f4;">
        <div style="background:white; padding:20px; border-radius:10px; display:inline-block; box-shadow:0 0 10px rgba(0,0,0,0.1);">
            <h2>Admin Manager 💻</h2>
            <p style="color:green; font-weight:bold;">{msg}</p>
            <form method="POST">
                <input type="text" name="user_id" placeholder="User ID" required style="padding:10px; margin:5px; width:200px;"><br>
                <input type="number" step="0.01" name="amount" placeholder="Amount" required style="padding:10px; margin:5px; width:200px;"><br><br>
                <button type="submit" name="action" value="add" style="padding:10px 20px; background:green; color:white; border:none; cursor:pointer;">Add</button>
                <button type="submit" name="action" value="deduct" style="padding:10px 20px; background:red; color:white; border:none; cursor:pointer;">Deduct</button>
            </form>
        </div>
    </body>
    </html>
    '''

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
