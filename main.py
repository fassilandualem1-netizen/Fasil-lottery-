import os
import random
import threading
import telebot
from telebot import types
import requests
from flask import Flask, render_template, jsonify, request
from upstash_redis import Redis

# --- 1. የቦት እና የዳታቤዝ ቁልፎች (Configuration ከ Environment Variables) ---
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")

# BotFather ላይ የፈጠርከው የ 3D ዌብአፕ ሊንክ ወይም ሆስት የተደረገበት ዌብሳይት
WEB_APP_URL = "https://sefer-bot.onrender.com" 

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

# ያንተ የቴሌግራም ID (ክፍያዎችን በእጅ Approve/Reject ለማድረግ እና የዌብአፕ ኖቲፊኬሽን ለመቀበል)
ADMIN_IDS = [8443303643]  
PRIMARY_ADMIN = ADMIN_IDS[0] # ለ requests.post መላኪያ የሚያገለግል ዋና ID

# የአራቱ ጨዋታዎች ታሪፍ እና የማባዣ ህጎች
GAME_CONFIG = {
    "beg_rucha": {"name": "🐑 የበግ ሩጫ", "fee": 2, "multiplier": 0.02},
    "ayi_game": {"name": "🧀 የአይጧ ጨዋታ", "fee": 5, "multiplier": 0.50},
    "anbessa_aden": {"name": "🦁 የአንበሳ አደን", "fee": 10, "multiplier": 1.50},
    "coin_flip": {"name": "🪙 እጥፍ ወይስ ባዶ (ዘውድ/ጎፈር)", "fee": 0, "multiplier": 2.0, "type": "luck"}
}

# --- 2. የ Flask የዌብአፕ እና የ API መስመሮች (Web App & API Routes) ---

@server.route('/')
def index():
    """ 3D ጨዋታዎቹ ቴሌግራም ላይ ሲከፈቱ የሚታዩበት ዋና ገጽ """
    return render_template('index.html')

@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    """ የልጁን ወቅային ባላንስ ከሪዲስ አንብቦ ለጃቫስክሪፕቱ የሚሰጥ """
    data = request.json
    user_id = str(data.get('user_id'))
    balance = float(redis.hget("users:balance", user_id) or 0)
    return jsonify({"status": "success", "balance": balance})

@server.route('/api/start_game', methods=['POST'])
def start_game():
    """ ልጁ በችሎታ የሚጫወቱትን 3 ጌሞች ሲጀምር መግቢያ ክፍያ የሚቀንስ """
    data = request.json
    user_id = str(data.get('user_id'))
    game_type = data.get('game_type')

    config = GAME_CONFIG.get(game_type)
    if not config:
        return jsonify({"status": "error", "message": "ያልታወቀ ጨዋታ!"}), 400

    current_balance = float(redis.hget("users:balance", user_id) or 0)

    if current_balance < config["fee"]:
        return jsonify({"status": "no_money", "message": "ለመጫወት በቂ የቦት ብር የለዎትም!"}), 400

    # የመግቢያ ክፍያውን መቀነስ
    if config["fee"] > 0:
        redis.hincrbyfloat("users:balance", user_id, -config["fee"])
    return jsonify({"status": "ready", "new_balance": current_balance - config["fee"]})

@server.route('/api/save_score', methods=['POST'])
def save_score():
    """ ልጁ በችሎታው ተጫውቶ ሲሸነፍ ያገኘውን ነጥብ አባዝቶ ሪዲስ ላይ የሚጨምር """
    data = request.json
    user_id = str(data.get('user_id'))
    game_type = data.get('game_type')
    score = int(data.get('score', 0))

    config = GAME_CONFIG.get(game_type)
    if not config:
        return jsonify({"status": "error", "message": "የተሳሳተ የጨዋታ መለያ"}), 400

    winnings = round(score * config["multiplier"], 2)

    if winnings > 0:
        redis.hincrbyfloat("users:balance", user_id, winnings)

    return jsonify({"status": "success", "winnings": winnings})

@server.route('/api/coin_flip', methods=['POST'])
def coin_flip():
    """ 4ኛው ጨዋታ፦ እጥፍ ወይስ ባዶ (የጎፈር እና ዘውድ ምርጫ) """
    data = request.json
    user_id = str(data.get('user_id'))
    player_choice = data.get('choice')
    bet_amount = float(data.get('bet_amount', 0))

    current_balance = float(redis.hget("users:balance", user_id) or 0)
    if current_balance < bet_amount:
        return jsonify({"status": "error", "message": "በቂ የቦት ብር የለዎትም!"}), 400

    # የውርርድ ብሩን መቀነስ
    redis.hincrbyfloat("users:balance", user_id, -bet_amount)

    # ሰርቨሩ በ 50/50 ዕድል ያሽከረክራል
    server_result = 'gofer' if random.randint(0, 1) == 0 else 'zewd'

    if player_choice == server_result:
        winnings = bet_amount * 2
        redis.hincrbyfloat("users:balance", user_id, winnings)
        return jsonify({
            "status": "win",
            "result": server_result,
            "message": f"🎉 ማሸነፍዎን ያረጋግጡ! {server_result} ወጥቷል። እጥፍ ተደመረልዎት!"
        })
    else:
        return jsonify({
            "status": "lose",
            "result": server_result,
            "message": f"😢 ያዝናለን! {server_result} ወጥቷል። በሚቀጥለው ይሞክሩ!"
        })

# --- 📥 ከዌብአፕ (Wallet Modal) የሚመጣ የDeposit ጥያቄ መቀበያ ---
@server.route('/api/deposit', methods=['POST'])
def handle_web_deposit():
    user_id = request.form.get("user_id")
    amount = request.form.get("amount")
    receipt_file = request.files.get("receipt")
    
    if not user_id or not amount or not receipt_file:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ!"}), 400

    # ለአድሚኑ በቦቱ በኩል የደረሰኝ ፎቶ እና ማረጋገጫ በተን መላኪያ ሎጂክ
    caption_text = (
        f"🔔 <b>አዲስ የ Deposit ጥያቄ ከዌብአፕ ቀርቧል!</b>\n\n"
        f"👤 <b>ተጫዋች ID:</b> <code>{user_id}</code>\n"
        f"💰 <b>የጠየቀው የብር መጠን:</b> {amount} ብር\n\n"
        f"👉 እባክዎ የቴሌብር አካውንትዎን አይተው ገቢ መሆኑን ካረጋገጡ በኋላ ከታች ካሉት በተኖች የአንዱን መጠን ይፍቀዱ!"
    )
    
    # ለአድሚኑ ማጽደቂያ Dynamic በተን ማዘጋጀት
    markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton("✅ መጠኑን አጽድቅ", callback_data=f"dep_app_{user_id}_WEB")
    btn_reject = types.InlineKeyboardButton("❌ Reject (ውድቅ አድርግ)", callback_data=f"dep_rej_{user_id}")
    markup.add(btn_approve, btn_reject)
    
    try:
        # ቴሌግራም ላይ ፎቶ ለመላክ የ bot.send_photo መጠቀም የበለጠ አስተማማኝ ነው
        bot.send_photo(
            chat_id=PRIMARY_ADMIN, 
            photo=receipt_file.stream.read(), 
            caption=caption_text, 
            parse_mode="HTML", 
            reply_markup=markup
        )
        return jsonify({"status": "success", "message": "የክፍያ ማረጋገጫ ጥያቄዎ በተሳካ ሁኔታ ለአስተዳዳሪው ተልኳል!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"ለአስተዳዳሪው መላክ አልተቻለም: {str(e)}"}), 500

# --- 📤 ከዌብአፕ (Wallet Modal) የሚመጣ የWithdraw ጥያቄ መቀበያ ---
@server.route('/api/withdraw', methods=['POST'])
def handle_web_withdraw():
    data = request.json
    user_id = str(data.get("user_id"))
    amount = float(data.get("amount", 0))
    phone = data.get("phone", "").strip()
    
    if not user_id or amount <= 0 or not phone:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ!"}), 400

    current_balance = float(redis.hget("users:balance", user_id) or 0)
    if current_balance < amount:
        return jsonify({"status": "error", "message": "ይቅርታ፣ ማውጣት የፈለጉት መጠን ካለዎት ባላንስ ይበልጣል!"}), 400

    # ከባላንሱ ላይ በጊዜው ማሳገድ/መቀነስ
    redis.hincrbyfloat("users:balance", user_id, -amount)

    # ለአድሚኑ የቪዝድሮው መረጃ መላኪያ ከ Paid በተን ጋር
    message_text = (
        f"💸 <b>አዲስ የ Withdraw ጥያቄ ከዌብአፕ ደርሷል!</b>\n\n"
        f"👤 <b>ተጫዋች ID:</b> <code>{user_id}</code>\n"
        f"📱 <b>የቴሌብር ስልክ:</b> <code>{phone}</code> (ለመቅዳት ይጫኑት)\n"
        f"💰 <b>ማውጣት የፈለገው:</b> <b>{amount} ብር</b>\n\n"
        f"👉 እባክዎ ወደዚህ ስልክ ቁጥር ብሩን በቴሌብር ልከው 'Paid' የሚለውን ይጫኑ!"
    )
    
    markup = types.InlineKeyboardMarkup()
    btn_paid = types.InlineKeyboardButton("💸 Paid (ተከፍሏል)", callback_data=f"wit_paid_{user_id}_{amount}")
    markup.add(btn_paid)
    
    try:
        bot.send_message(chat_id=PRIMARY_ADMIN, text=message_text, parse_mode="HTML", reply_markup=markup)
        return jsonify({"status": "success", "message": "የማውጫ ጥያቄዎ ለአስተዳዳሪው ደርሷል!"})
    except Exception as e:
        # በሆነ ምክንያት ካልተላከ የተቆረጠውን ባላንስ መመለስ
        redis.hincrbyfloat("users:balance", user_id, amount)
        return jsonify({"status": "error", "message": "ጥያቄውን ማስተላለፍ አልተቻለም"}), 500


# --- 3. የቴሌግራም ቦት መልዕክቶች እና ትዕዛዞች ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        user_id = str(message.from_user.id)
        username = message.from_user.username or "የሰፈር ልጅ"

        if not redis.hexists("users:balance", user_id):
            redis.hset("users:balance", user_id, "0")
            redis.hset("users:username", user_id, username)

        balance_raw = redis.hget("users:balance", user_id)
        balance = balance_raw if balance_raw is not None else "0"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn_games = types.KeyboardButton("🕹️ 3D ጨዋታዎችን ይምረጡ", web_app=types.WebAppInfo(url=WEB_APP_URL))
        btn_wallet = types.KeyboardButton("💰 የኪስ ቦርሳ (Balance)")
        btn_deposit = types.KeyboardButton("📥 ብር አስገባ (Deposit)")
        btn_withdraw = types.KeyboardButton("📤 ብር አውጣ (Withdraw)")

        markup.add(btn_games)
        markup.add(btn_wallet, btn_deposit, btn_withdraw)

        msg = (
            f"<b>እንኳን ወደ ሰፈር 3D ጌሚንግ ቦት በሰላም መጡ! 👋</b>\n\n"
            f"💰 ወቅታዊ የኪስ ቦርሳዎ፦ <b>{balance} የቦት ብር</b>\n\n"
            f"ለመጫወት ከታች ካሉት በተኖች አንዱን ይጫኑ።"
        )
        bot.send_message(message.chat.id, msg, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        print(f"❌ [START COMMAND ERROR]: {e}")


@bot.message_handler(func=lambda m: m.text == "💰 የኪስ ቦርሳ (Balance)")
def check_balance(message):
    user_id = str(message.from_user.id)
    balance = redis.hget("users:balance", user_id) or "0"
    bot.send_message(message.chat.id, f"💰 ወቅታዊ የኪስ ቦርሳዎ የсаንቲም መጠን፦ <b>{balance} የቦት ብር</b> ነው።")

# --- 📥 በቦት ቴክስት በእጅ ብር ማጫኛ መዋቅር (Text-based Deposit) ---
@bot.message_handler(func=lambda m: m.text == "📥 ብር አስገባ (Deposit)")
def deposit_instruction(message):
    msg = (
        "<b>📥 ብር ለማስገባት መመሪያ፦</b>\n\n"
        "1. ሊያጫውቱት የሚፈልጉትን የብር መጠን ወደዚህ የቴሌብር ቁጥር ይላኩ፦ <code>0951381356</code>\n"
        "2. ብሩን ከላኩ በኋላ <b>የደረሰኝ ቁጥሩን (Transaction ID)</b> ብቻ እዚህ ላይ ይጻፉልን።\n\n"
        "<i>ማሳሰቢያ፦ የላኩት መረጃ በአስተዳዳሪው ተረጋግጦ ወዲያው ባላንስዎ ላይ ይጫናል!</i>"
    )
    bot.send_message(message.chat.id, msg)
    bot.register_next_step_handler(message, process_deposit_request)

def process_deposit_request(message):
    tx_id = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "የሰፈር ልጅ"

    markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton("✅ Approve", callback_data=f"dep_app_{user_id}_{tx_id}")
    btn_reject = types.InlineKeyboardButton("❌ Reject", callback_data=f"dep_rej_{user_id}")
    markup.add(btn_approve, btn_reject)

    for admin in ADMIN_IDS:
        bot.send_message(
            admin, 
            f"🔔 <b>አዲስ የብር ማጫኛ ጥያቄ (በጽሑፍ)!</b>\n\n"
            f"👤 ተጠቃሚ፦ @{username} (ID: {user_id})\n"
            f"🧾 የደረሰኝ ቁጥር፦ <code>{tx_id}</code>\n\n"
            f"እባክዎ ቴሌብርዎ ላይ መግባቱን አይተው ያረጋግጡ!",
            reply_markup=markup
        )
    bot.send_message(message.chat.id, "⏳ የደረሰኝ ቁጥርዎ ለአስተዳዳሪው ተልኳል። ሲረጋገጥ ወዲያው መልዕክት ይደርስዎታል!")

# --- 📤 በቦት ቴክስት በእጅ ብር ማውጫ መዋቅር (Text-based Withdraw) ---
@bot.message_handler(func=lambda m: m.text == "📤 ብር አውጣ (Withdraw)")
def withdraw_request(message):
    msg = "📤 ማውጣት የሚፈልጉትን የብር መጠን እና የቴሌብር ስልክ ቁጥርዎን በዚህ መልክ ይጻፉልን፦\nየብር መጠን - ስልክ ቁጥር\n(ምሳሌ፦ <code>100 - 0912345678</code>)"
    bot.send_message(message.chat.id, msg)
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
            bot.send_message(message.chat.id, "❌ በኪስዎ ውስጥ በቂ የቦት ብር የለም!")
            return

        redis.hincrbyfloat("users:balance", user_id, -amount)

        markup = types.InlineKeyboardMarkup()
        btn_paid = types.InlineKeyboardButton("💸 Paid (ተከፍሏል)", callback_data=f"wit_paid_{user_id}_{amount}")
        markup.add(btn_paid)

        for admin in ADMIN_IDS:
            bot.send_message(
                admin,
                f"🚨 <b>የብር ማውጫ ጥያቄ መጥቷል (በጽሑፍ)!</b>\n\n"
                f"👤 ተጠቃሚ ID: {user_id}\n"
                f"💰 ሊያወጣ የጠየቀው፦ <b>{amount} ብር</b>\n"
                f"📱 የቴሌብር ስልክ ቁጥር፦ <code>{phone}</code>\n\n"
                f"እባክዎ ብሩን በስልክዎ ልከው 'Paid' የሚለውን ይጫኑ!",
                reply_markup=markup
            )
        bot.send_message(message.chat.id, "⏳ የብር ማውጫ ጥያቄዎ ተመዝግቧል። አስተዳዳሪው ቴሌብር ላይ ሲልክልዎ ማረጋገጫ ይደርስዎታል።")
    except:
        bot.send_message(message.chat.id, "❌ የተሳሳተ አጻጻፍ ፎርማት ተጠቅመዋል። እባክዎ ድጋሚ ይሞክሩ።")

# --- 🎛️ የአድሚን በተኖች ስራ (Callback Query Handlers) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_admin_buttons(call):
    data = call.data

    if data.startswith("dep_app_"):
        parts = data.split("_")
        user_id = parts[2]
        tx_id = parts[3]

        # አድሚኑ ተመጣጣኙን የብር መጠን መርጦ እንዲጭን Dynamic በተን ማሳየት
        markup = types.InlineKeyboardMarkup()
        btn_25 = types.InlineKeyboardButton("25 ብር", callback_data=f"add_{user_id}_25")
        btn_50 = types.InlineKeyboardButton("50 ብር", callback_data=f"add_{user_id}_50")
        btn_100 = types.InlineKeyboardButton("100 ብር", callback_data=f"add_{user_id}_100")
        btn_200 = types.InlineKeyboardButton("200 ብር", callback_data=f"add_{user_id}_200")
        markup.add(btn_25, btn_50, btn_100, btn_200)

        bot.edit_message_caption(
            caption=f"🧾 ማረጋገጫ (Tx/WEB)፦ <code>{tx_id}</code>\n\nእባክዎ ተጠቃሚው የላከውን ትክክለኛ የብር መጠን ይምረጡ፦", 
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id, 
            reply_markup=markup
        ) if call.message.photo else bot.edit_message_text(
            text=f"🧾 የደረሰኝ ቁጥር፦ <code>{tx_id}</code>\n\nእባክዎ ተጠቃሚው የላከውን የብር መጠን ይምረጡ፦", 
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id, 
            reply_markup=markup
        )

    elif data.startswith("add_"):
        _, user_id, amount = data.split("_")
        amount = float(amount)

        redis.hincrbyfloat("users:balance", user_id, amount)
        try:
            bot.send_message(user_id, f"🎉 <b>የማጫኛ ጥያቄዎ ጸድቋል! {amount} የቦት ብር በኪስዎ ላይ ተጨምሯል።</b>")
        except: pass
        
        if call.message.photo:
            bot.edit_message_caption(f"✅ ለተጠቃሚ {user_id} {amount} ብር በተሳካ ሁኔታ ተጭኗል።", call.message.chat.id, call.message.message_id)
        else:
            bot.edit_message_text(f"✅ ለተጠቃሚ {user_id} {amount} ብር በተሳካ ሁኔታ ተጭኗል።", call.message.chat.id, call.message.message_id)

    elif data.startswith("dep_rej_"):
        _, _, user_id = data.split("_")
        try:
            bot.send_message(user_id, "❌ የላኩት የደረሰኝ ቁጥር ወይም ማረጋገጫ ትክክል አይደለም ተብሎ በአስተዳዳሪው ውድቅ ተደርጓል።")
        except: pass
        
        if call.message.photo:
            bot.edit_message_caption("❌ ማጫኛ ውድቅ ተደርጓል።", call.message.chat.id, call.message.message_id)
        else:
            bot.edit_message_text("❌ ማጫኛ ውድቅ ተደርጓል።", call.message.chat.id, call.message.message_id)

    elif data.startswith("wit_paid_"):
        _, _, user_id, amount = data.split("_")
        try:
            bot.send_message(user_id, f"💸 <b>የጠየቁት {amount} ብር በቴሌብርዎ በተሳካ ሁኔታ ተልኮልዎታል!</b>")
        except: pass
        bot.edit_message_text(f"✅ ለተጠቃሚ {user_id} {amount} ብር መከፈሉ ተረጋግጧል።", call.message.chat.id, call.message.message_id)


# --- 🚀 የቦት እና ሰርቨር ማስነሻ ---

def run_flask():
    print("🎮 የፍላስክ ሰርቨር እየተነሳ ነው...")
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))

if __name__ == "__main__":
    bot.remove_webhook()

    # የፍላስክ ሰርቨሩን በስተጀርባ (Thread) ማስነሳት
    threading.Thread(target=run_flask, daemon=True).start()

    print("🤖 ቦቱ በፖሊንግ አማካኝነት በጠንካራ ሁኔታ ተነሳ!")
    bot.infinity_polling(skip_pending_updates=True)
