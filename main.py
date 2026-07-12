import os
import random
import threading
import telebot
from telebot import types
import requests
from flask import Flask, render_template, jsonify, request
from upstash_redis import Redis

# --- 1. የቦት እና የዳታቤዝ ቁልፎች (Configuration) ---
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com" 

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

# ያንተ የቴሌግራም ID
ADMIN_IDS = [8443303643]  
PRIMARY_ADMIN = ADMIN_IDS[0]

GAME_CONFIG = {
    "beg_rucha": {"name": "🐑 የበግ ሩጫ", "fee": 2, "multiplier": 0.02},
    "ayi_game": {"name": "🧀 የአይጧ ጨዋታ", "fee": 5, "multiplier": 0.50},
    "anbessa_aden": {"name": "🦁 የአንበሳ አደን", "fee": 10, "multiplier": 1.50},
    "coin_flip": {"name": "🪙 እጥፍ ወይስ ባዶ (ዘውድ/ጎፈር)", "fee": 0, "multiplier": 2.0, "type": "luck"}
}

# --- 2. የ Flask የዌብአፕ እና የ API መስመሮች ---

@server.route('/')
def index():
    return render_template('index.html')

@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.json
    user_id = str(data.get('user_id'))
    balance = float(redis.hget("users:balance", user_id) or 0)
    return jsonify({"status": "success", "balance": balance})

@server.route('/api/start_game', methods=['POST'])
def start_game():
    data = request.json
    user_id = str(data.get('user_id'))
    game_type = data.get('game_type')

    config = GAME_CONFIG.get(game_type)
    if not config:
        return jsonify({"status": "error", "message": "ያልታወቀ ጨዋታ!"}), 400

    current_balance = float(redis.hget("users:balance", user_id) or 0)
    if current_balance < config["fee"]:
        return jsonify({"status": "no_money", "message": "ለመጫወት በቂ የቦት ብር የለዎትም!"}), 400

    if config["fee"] > 0:
        redis.hincrbyfloat("users:balance", user_id, -config["fee"])
    return jsonify({"status": "ready", "new_balance": current_balance - config["fee"]})

@server.route('/api/save_score', methods=['POST'])
def save_score():
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
    data = request.json
    user_id = str(data.get('user_id'))
    player_choice = data.get('choice')
    bet_amount = float(data.get('bet_amount', 0))

    current_balance = float(redis.hget("users:balance", user_id) or 0)
    if current_balance < bet_amount:
        return jsonify({"status": "error", "message": "በቂ የቦት ብር የለዎትም!"}), 400

    redis.hincrbyfloat("users:balance", user_id, -bet_amount)
    server_result = 'gofer' if random.randint(0, 1) == 0 else 'zewd'

    if player_choice == server_result:
        winnings = bet_amount * 2
        redis.hincrbyfloat("users:balance", user_id, winnings)
        return jsonify({"status": "win", "result": server_result, "message": f"🎉 ማሸነፍዎን ያረጋግጡ! {server_result} ወጥቷል።"})
    else:
        return jsonify({"status": "lose", "result": server_result, "message": f"😢 ያዝናለን! {server_result} ወጥቷል።"})

# --- 📥 ከዌብአፕ የሚመጣ የDeposit ጥያቄ መቀበያ ---
@server.route('/api/deposit', methods=['POST'])
def handle_web_deposit():
    user_id = request.form.get("user_id")
    amount = request.form.get("amount")
    receipt_file = request.files.get("receipt")
    
    if not user_id or not amount or not receipt_file:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ!"}), 400

    caption_text = (
        f"🔔 <b>አዲስ የ Deposit ጥያቄ ከዌብአፕ!</b>\n\n"
        f"👤 <b>ተጫዋች ID:</b> <code>{user_id}</code>\n"
        f"💰 <b>የጠየቀው መጠን:</b> <b>{amount} ብር</b>\n"
    )
    
    markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton("✅ Approve", callback_data=f"wa_ap_{user_id}_{amount}")
    btn_reject = types.InlineKeyboardButton("❌ Reject", callback_data=f"wa_rj_{user_id}")
    markup.add(btn_approve, btn_reject)
    
    try:
        bot.send_photo(chat_id=PRIMARY_ADMIN, photo=receipt_file.stream.read(), caption=caption_text, reply_markup=markup)
        return jsonify({"status": "success", "message": "የክፍያ ማረጋገጫዎ ለአስተዳዳሪው ተልኳል!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"ስህተት ተፈጥሯል: {str(e)}"}), 500

# --- 📤 ከዌብአፕ የሚመጣ የWithdraw ጥያቄ መቀበያ ---
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
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

    redis.hincrbyfloat("users:balance", user_id, -amount)

    message_text = (
        f"💸 <b>አዲስ የ Withdraw ጥያቄ ከዌብአፕ!</b>\n\n"
        f"👤 <b>ተጫዋች ID:</b> <code>{user_id}</code>\n"
        f"📱 <b>ስልክ:</b> <code>{phone}</code>\n"
        f"💰 <b>መጠን:</b> <b>{amount} ብር</b>\n"
    )
    
    markup = types.InlineKeyboardMarkup()
    btn_paid = types.InlineKeyboardButton("💸 Paid", callback_data=f"wt_pd_{user_id}_{amount}")
    markup.add(btn_paid)
    
    try:
        bot.send_message(chat_id=PRIMARY_ADMIN, text=message_text, reply_markup=markup)
        return jsonify({"status": "success", "message": "የማውጫ ጥያቄዎ ለአስተዳዳሪው ደርሷል!"})
    except Exception as e:
        redis.hincrbyfloat("users:balance", user_id, amount)
        return jsonify({"status": "error", "message": "ጥያቄውን ማስተላለፍ አልተቻለም"}), 500


# --- 🔗 3. የዌብሁክ መቀበያ መስመሮች ---

@server.route('/webhook/' + TOKEN, methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    except Exception as e:
        print(f"Webhook error: {e}")
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
        return f"❌ Webhook Setup Failed: {e}", 500


# --- 4. የቴሌግራም ቦት መልዕክቶች እና ትዕዛዞች ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
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

    msg = f"<b>እንኳን ወደ ሰፈር 3D ጌሚንግ ቦት በሰላም መጡ! 👋</b>\n\n💰 ባላንስዎ፦ <b>{balance} ብር</b>"
    bot.send_message(message.chat.id, msg, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💰 የኪስ ቦርሳ (Balance)")
def check_balance(message):
    user_id = str(message.from_user.id)
    balance = redis.hget("users:balance", user_id) or "0"
    bot.send_message(message.chat.id, f"💰 ወቅታዊ የኪስ ቦርሳዎ፦ <b>{balance} ብር</b> ነው።")

# --- 📥 በቦት ቴክስት (Text-based Deposit) ---
@bot.message_handler(func=lambda m: m.text == "📥 ብር አስገባ (Deposit)")
def deposit_instruction(message):
    msg = "<b>📥 ብር ለማስገባት፦</b>\n\n ወደ <code>0951381356</code> በቴሌብር ልከው <b>የደረሰኝ ቁጥሩን (Transaction ID)</b> ብቻ እዚህ ይጻፉ።"
    bot.send_message(message.chat.id, msg)
    bot.register_next_step_handler(message, process_deposit_request)

def process_deposit_request(message):
    tx_id = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username or "የሰፈር ልጅ"

    markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton("✅ Approve", callback_data=f"tx_ap_{user_id}_{tx_id}")
    btn_reject = types.InlineKeyboardButton("❌ Reject", callback_data=f"tx_rj_{user_id}")
    markup.add(btn_approve, btn_reject)

    for admin in ADMIN_IDS:
        bot.send_message(admin, f"🔔 <b>አዲስ የጽሑፍ ማጫኛ ጥያቄ!</b>\n👤 @{username}\n🧾 Tx ID: <code>{tx_id}</code>", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ ጥያቄዎ ለአስተዳዳሪው ቀርቧል።")

# --- 📤 በቦት ቴክስት (Text-based Withdraw) ---
@bot.message_handler(func=lambda m: m.text == "📤 ብር አውጣ (Withdraw)")
def withdraw_request(message):
    msg = "📤 የብር መጠን እና የቴሌብር ስልክዎን በዚህ ፎርማት ይጻፉ፦\n<code>መጠን - ስልክ</code> (ምሳሌ፦ 100 - 0912345678)"
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
            bot.send_message(message.chat.id, "❌ በቂ የቦት ብር የለም!")
            return

        redis.hincrbyfloat("users:balance", user_id, -amount)

        markup = types.InlineKeyboardMarkup()
        btn_paid = types.InlineKeyboardButton("💸 Paid", callback_data=f"wt_pd_{user_id}_{amount}")
        markup.add(btn_paid)

        for admin in ADMIN_IDS:
            bot.send_message(admin, f"🚨 <b>የጽሑፍ ማውጫ ጥያቄ!</b>\n👤 ID: {user_id}\n💰 መጠን: {amount}\n📱 ስልክ: <code>{phone}</code>", reply_markup=markup)
        bot.send_message(message.chat.id, "⏳ ጥያቄዎ ተመዝግቧል።")
    except:
        bot.send_message(message.chat.id, "❌ የተሳሳተ አጻጻፍ!")


# --- 🎛️ 5. የተስተካከለው እና ደህንነቱ የተጠበቀው በተን መቆጣጠሪያ ---

@bot.callback_query_handler(func=lambda call: True)
def handle_admin_buttons(call):
    # 🚨 የደህንነት ማጣሪያ (Security Guard)፦ በተኑን የነካው ሰው አድሚን መሆኑን ያረጋግጣል
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ ይህንን አዝራር ለመጫን ፍቃድ የለዎትም!", show_alert=True)
        return

    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    try:
        # --- ሀ. የ WEB APP DEPOSIT APPROVE ---
        if data.startswith("wa_ap_"):
            _, _, user_id, amount = data.split("_", 3)
            amount = float(amount)

            redis.hincrbyfloat("users:balance", user_id, amount)
            try:
                bot.send_message(user_id, f"🎉 ከዌብአፕ የላኩት የ <b>{amount} ብር</b> ዴፖዚት ጸድቋል!")
            except: pass
            
            bot.answer_callback_query(call.id, "በተሳካ ሁኔታ ጸድቋል!")
            bot.edit_message_caption(f"✅ ለተጠቃሚ {user_id} {amount} ብር ተጭኗል።", chat_id, message_id)

        # --- ለ. የ WEB APP DEPOSIT REJECT ---
        elif data.startswith("wa_rj_"):
            _, _, user_id = data.split("_", 2)
            try:
                bot.send_message(user_id, "❌ ከዌብአፕ የላኩት የዴፖዚት ጥያቄ ውድቅ ሆኗል።")
            except: pass
            
            bot.answer_callback_query(call.id, "ጥያቄው ውድቅ ተደርጓል")
            bot.edit_message_caption("❌ ማጫኛ ጥያቄው ውድቅ ተደርጓል።", chat_id, message_id)

        # --- ሐ. የጽሑፍ DEPOSIT APPROVE (መጠን መምረጫ ያመጣል) ---
        elif data.startswith("tx_ap_"):
            _, _, user_id, tx_id = data.split("_", 3)

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("25 ብር", callback_data=f"fc_{user_id}_25"),
                types.InlineKeyboardButton("50 ብር", callback_data=f"fc_{user_id}_50")
            )
            markup.add(
                types.InlineKeyboardButton("100 ብር", callback_data=f"fc_{user_id}_100"),
                types.InlineKeyboardButton("200 ብር", callback_data=f"fc_{user_id}_200")
            )

            bot.edit_message_text(f"🧾 Tx ID: {tx_id}\n\nእባክዎ የሚጫነውን መጠን ይምረጡ፦", chat_id, message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        # --- መ. የጽሑፍ DEPOSIT FINAL CONFIRM ---
        elif data.startswith("fc_"):
            _, user_id, amount = data.split("_", 2)
            amount = float(amount)

            redis.hincrbyfloat("users:balance", user_id, amount)
            try:
                bot.send_message(user_id, f"🎉 የ <b>{amount} ብር</b> ማጫኛ ጥያቄዎ ጸድቋል!")
            except: pass
            
            bot.answer_callback_query(call.id, "ብር ተጭኗል!")
            bot.edit_message_text(f"✅ ለተጠቃሚ {user_id} {amount} ብር ተጭኗል።", chat_id, message_id)

        # --- ሠ. የጽሑፍ DEPOSIT REJECT ---
        elif data.startswith("tx_rj_"):
            _, _, user_id = data.split("_", 2)
            try:
                bot.send_message(user_id, "❌ የጽሑፍ ማጫኛ ጥያቄዎ ውድቅ ሆኗል።")
            except: pass
            
            bot.answer_callback_query(call.id, "ጥያቄው ውድቅ ተደርጓል")
            bot.edit_message_text("❌ ማጫኛ ጥያቄው ውድቅ ተደርጓል።", chat_id, message_id)

        # --- ረ. WITHDRAW PAID (ለሁለቱም የሚሰራ) ---
        elif data.startswith("wt_pd_"):
            _, _, user_id, amount = data.split("_", 3)
            try:
                bot.send_message(user_id, f"💸 የጠየቁት <b>{amount} ብር</b> በቴሌብር ተልኮልዎታል።")
            except: pass
            
            bot.answer_callback_query(call.id, "ክፍያ መፈጸሙ ተመዝግቧል!")
            bot.edit_message_text(f"✅ ለተጠቃሚ {user_id} {amount} ብር መከፈሉ ተረጋግጧል።", chat_id, message_id)

    except Exception as e:
        bot.answer_callback_query(call.id, f"⚠️ ስህተት፡ {str(e)}", show_alert=True)

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
