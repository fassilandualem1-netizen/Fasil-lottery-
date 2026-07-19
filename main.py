import gevent.monkey
gevent.monkey.patch_all()

import os
import time
import json
import uuid
import threading
import re
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import telebot
from telebot.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# ከ config.py የጋራ ማዋቀሪያዎችንና ረዳቶችን ማስገባት
from config import (
    bot, redis, TOKEN, ADMIN_ID, WEB_APP_URL,
    telegram_auth_required, deduct_balance_safely, add_to_history, update_history_tx_status,
    save_user_withdraw_details, get_user_withdraw_details
)

# 🎮 6ቱንም የጌሞች ብሉፕሪንቶች ማስገባት
from games.gofere_zewd import gofere_zewd_bp
from games.aviator import aviator_bp
from games.chicken import chicken_bp
from games.keno import keno_bp
from games.virtual_sports import virtual_sports_bp
from games.real_sports import real_sports_bp

import requests
import os  # ይሄ ከሌለ ከላይ መጨመርህን አትርሳ

@bot.message_handler(commands=['testapi'])
def test_api_from_bot(message):
    bot.reply_to(message, "🔍 አዲሱን (The Odds API) በመመርመር ላይ... እባክዎ ትንሽ ይጠብቁ።")
    
    # Render ላይ ያስቀመጥነው አዲሱ ቁልፍ
    API_KEY = os.getenv("THE_ODDS_API_KEY") 
    
    if not API_KEY:
        bot.reply_to(message, "❌ API Key አልተገኘም! እባክዎ Render ላይ 'THE_ODDS_API_KEY' መኖሩን ያረጋግጡ።")
        return

    try:
        # ይህ ኤንድፖይንት ከላይ በፎቶ እንዳየነው ከኮታ(Limit) አይቀንስም! ነጻ ነው።
        url = f"https://api.the-odds-api.com/v4/sports/?apiKey={API_KEY}"
        response = requests.get(url)
        
        if response.status_code == 200:
            # The Odds API ስንት ጥሪ እንደቀረን የሚነግረን በ Headers ውስጥ ነው
            used = response.headers.get('x-requests-used', 'ያልታወቀ')
            remaining = response.headers.get('x-requests-remaining', 'ያልታወቀ')
            
            msg = "✅ አዲሱ API (The Odds API) በትክክል እየሰራ ነው!\n\n"
            msg += f"📉 ዛሬ የተጠቀሙት (Used): {used}\n"
            msg += f"📊 ቀሪ የጥሪ ብዛት (Remaining): {remaining}\n\n"
            msg += "👍 የድሮው መታገድ እና እገዳ አሁን የለም!"
            
            bot.reply_to(message, msg)
        else:
            data = response.json()
            bot.reply_to(message, f"❌ ችግር ተገኝቷል ({response.status_code}):\n{data.get('message', 'Unknown Error')}")
            
    except Exception as e:
        bot.reply_to(message, f"❌ ከ API ጋር መገናኘት አልተቻለም:\n{e}")


server = Flask(__name__)
server.secret_key = os.environ.get("SECRET_KEY", "gashabet_secret_super_key_123")

# የ SocketIO ማስተካከያ 
socketio = SocketIO(server, cors_allowed_origins="*", async_mode='gevent')

# Blueprints
server.register_blueprint(gofere_zewd_bp)
server.register_blueprint(aviator_bp)
server.register_blueprint(chicken_bp)
server.register_blueprint(keno_bp)
server.register_blueprint(virtual_sports_bp)
server.register_blueprint(real_sports_bp)


@server.route('/real_sports')
def real_sports_page():
    return render_template('real_sports.html')


# --- VALIDATION HELPERS ---
def is_text_only(text):
    return bool(re.match(r'^[a-zA-Z\u1200-\u137F\s\.]+$', text))

def is_number_only(text):
    return bool(re.match(r'^\+?[0-9]+$', text))

ALLOWED_BANKS = ["CBE", "Telebirr", "Awash", "Abyssinia"]

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton

# 1. ቋሚ ሜኑ (ከታች የሚቀመጥ) - ለተጠቃሚው ሁሌም ዝግጁ ነው
def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🎮 ጌም ጀምር"), KeyboardButton("💬 የደንበኞች ድጋፍ"))
    return markup

# 2. የ /start ኮማንድ - ንፁህ እና ቀጥተኛ
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.from_user.id)

    # የታገደ መሆኑን ቼክ ማድረግ
    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "❌ መለያዎ ታግዷል! አድሚንን ያግኙ።")
        return

    # የዌብ አፕ በተን (Inline)
    inline_markup = InlineKeyboardMarkup()
    inline_markup.add(InlineKeyboardButton("🎮 ጌም ጀምር (Play)", web_app=WebAppInfo(url=WEB_APP_URL)))

    # አንድ ንፁህ መልዕክት ብቻ ላክ
    bot.send_message(
        message.chat.id,
        "👋 <b>እንኳን ወደ 'Just Relax' በደህና መጡ!</b>\n\n"
        "ከታች ካለው ሜኑ ወይም ከላይ ካለው በተን በመጠቀም ጨዋታውን ይጀምሩ።",
        parse_mode="HTML",
        reply_markup=inline_markup
    )
    # ሜኑውን ለብቻው ላክ
    bot.send_message(message.chat.id, "አገልግሎት ለመምረጥ ከታች ያለውን ሜኑ ይጠቀሙ:", reply_markup=get_main_keyboard())

# 3. የሜኑ በተኖች ማዳመጫ (Handlers)
@bot.message_handler(func=lambda message: message.text == "🎮 ጌም ጀምር")
def handle_play(message):
    # ሰውን ወደ ስታርት ኮማንድ መልሰው (ወይም ተመሳሳይ ዌብ አፕ ሊንክ ላክለት)
    send_welcome(message)

@bot.message_handler(func=lambda message: message.text == "💬 የደንበኞች ድጋፍ")
def handle_support(message):
    # ቀጥታ የhelp ኮማንዱን ጥራ
    help_command(message)

# 4. የ /help ኮማንድ
@bot.message_handler(commands=['help'])
def help_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💰 ዴፖዚት እንዴት?", callback_data="help_deposit"))
    markup.add(InlineKeyboardButton("💸 ገንዘብ ማውጣት", callback_data="help_withdraw"))
    markup.add(InlineKeyboardButton("📜 የጨዋታ ህጎች", callback_data="help_rules"))
    markup.add(InlineKeyboardButton("💬 አድሚን ያግኙ", url="https://t.me/fassilandualem"))

    bot.send_message(
        message.chat.id,
        "👋 <b>የድጋፍ ማዕከል</b>\n\nየሚፈልጉትን አማራጭ ይምረጡ፡",
        parse_mode="HTML",
        reply_markup=markup
    )

# 5. የ Callback Handler (መልዕክት ሳይደግም በቦታው ላይ ይቀይራል)
@bot.callback_query_handler(func=lambda call: call.data.startswith("help_"))
def help_callback(call):
    if call.data == "help_deposit":
        text = "💰 <b>ዴፖዚት ለማድረግ፡</b>\n\n1. በዌብ አፕ ውስጥ 'Deposit' ይጫኑ።\n2. ክፍያ ከፈጸሙ በኋላ ስክሪንሾት ይላኩ።"
    elif call.data == "help_withdraw":
        text = "💸 <b>ገንዘብ ለማውጣት፡</b>\n\n- ባላንስዎ 50 ብር መሆን አለበት።\n- ባንክ እና ቁጥርዎን በትክክል ያስገቡ።"
    elif call.data == "help_rules":
        text = "📜 <b>የጨዋታ ህጎች፡</b>\n\n- መለያዎን ለሌላ ሰው አያጋሩ።\n- ከአንድ በላይ አካውንት ክልክል ነው።"
    else:
        text = "መረጃ አልተገኘም!"

    bot.answer_callback_query(call.id)
    # አስፈላጊው ክፍል እዚህ ላይ ነው: bot.edit_message_text ይጠቀሙ (ይህ መልዕክት እንዳይደገም ያደርጋል)
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, parse_mode="HTML", reply_markup=call.message.reply_markup)


# --- ROUTES ---
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.json or {}
    user_id = data.get("user_id")
    
    if not user_id: 
        return jsonify({"status": "error", "message": "Missing user_id"}), 400

    # 🛡️ ደህንነት: ተጠቃሚው ከታገደ የባላንስ መረጃ እንዳያገኝ እንከለክለዋለን
    if is_user_banned(user_id):
        return jsonify({"status": "error", "message": "አካውንትዎ ታግዷል!"}), 403

    # የ Real balance ብቻ ነው የሚመጣው
    balance_raw = redis.hget("users:balance", user_id)
    current_balance = float(balance_raw) if balance_raw else 0.0
    
    return jsonify({
        "status": "success", 
        "balance": current_balance
    })



# ==========================================
# ⚽ REAL SPORTS - REDIS CACHE SYSTEM
# ==========================================

# 1. ይሄንን Google App Script (GAS) በየ 10 ደቂቃው ይጠራዋል
@server.route('/api/internal/update_sports_data', methods=['GET'])
def update_sports_data():
    # ማንም ሰው ይሄን ራውት እየጠራ API እንዳይጨርስብህ ሚስጥራዊ ኮድ እንጠቀማለን
    secret = request.args.get("secret")
    if secret != "mypassword123": # ይሄንን የራስህ ፓስወርድ አድርገው
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    API_KEY = os.getenv("API_FOOTBALL_KEY") 
    headers = {
        "x-apisports-key": API_KEY, 
        "x-apisports-host": "v3.football.api-sports.io"
    }

    try:
        # ለምሳሌ የ Live ጨዋታዎችን ለማምጣት (እንደፍላጎትህ የ API ሊንኩን ቀይረው)
        response = requests.get("https://v3.football.api-sports.io/fixtures?live=all", headers=headers)
        data = response.json()
        
        # የመጣውን ዳታ ሙሉ በሙሉ ወደ Redis ሴቭ እናደርገዋለን!
        redis.set("cache:real_sports_data", json.dumps(data))
        
        return jsonify({"status": "success", "message": "✅ Data successfully updated and cached in Redis!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# 2. ዌብሳይትህ (Frontend) ዳታ ሲፈልግ ይሄንን ይጠራል (ከ 10 ሺህ ሰውም በላይ ቢመጣ አይጨናነቅም)
@server.route('/api/get_real_sports', methods=['GET'])
def get_real_sports():
    try:
        # ዋናውን API አንጠይቅም፤ በቀጥታ ከ Redis ላይ እናነባለን!
        cached_data = redis.get("cache:real_sports_data")
        
        if cached_data:
            # Redis ላይ ያለው String ስለሆነ ወደ JSON እንቀይረዋለን
            parsed_data = json.loads(cached_data)
            return jsonify({"status": "success", "source": "redis", "data": parsed_data})
        else:
            return jsonify({"status": "error", "message": "የጨዋታ መረጃ ገና አልገባም (እየተዘጋጀ ነው)።"}), 404

    except Exception as e:
        return jsonify({"status": "error", "message": "የዳታቤዝ ስህተት አጋጥሟል"}), 500



@server.route('/api/get_user_history', methods=['POST'])
@telegram_auth_required
def get_user_history():
    data = request.json or {}
    user_id = data.get("user_id")
    if not user_id: return jsonify({"status": "error", "message": "Missing user_id"}), 400
    try:
        raw_history = redis.lrange(f"history:{user_id}", 0, -1) or []
    except Exception as e:
        if "WRONGTYPE" in str(e):
            redis.delete(f"history:{user_id}")
            raw_history = []
        else: return jsonify({"status": "error", "message": "የዳታቤዝ ስህተት"}), 500
    return jsonify({"status": "success", "history": [json.loads(item) for item in raw_history]})

def send_photo_background(user_name, user_id, amount, tx_id, photo_data):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ አጽድቅ", callback_data=f"ok|deposit|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no|deposit|{tx_id}|{user_id}|{amount}")
    )
    caption = f"🔔 <b>አዲስ Deposit ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: <code>{user_id}</code>\n💰 መጠን: <b>{amount} ብር</b>\n🔑 TxID: <code>{tx_id}</code>"
    try:
        bot.send_photo(ADMIN_ID, photo_data, caption=caption, reply_markup=markup)
    except:
        bot.send_message(ADMIN_ID, caption, reply_markup=markup)

def is_user_banned(user_id):
    if not user_id: return False
    return redis.sismember("banned_users", str(user_id))

# ==========================================
# 💰 DEPOSIT LOGIC
# ==========================================
@server.route('/api/deposit', methods=['POST'])
@telegram_auth_required
def handle_deposit():
    user_id = request.form.get("user_id")
    if is_user_banned(user_id):
        return jsonify({"status": "error", "message": "አካውንትዎ ታግዷል! መገልገያዎችን መጠቀም አይችሉም።"}), 403

    user_name = request.form.get("user_name", "የሰፈር ልጅ")
    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        return jsonify({"status": "error", "message": "የተሳሳተ የገንዘብ መጠን ነው"}), 400

    receipt_file = request.files.get("receipt")
    if not user_id or amount <= 0 or not receipt_file: 
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    photo_data = receipt_file.read()
    tx_id = str(uuid.uuid4())[:8]
    redis.set(f"tx:{tx_id}", json.dumps({"user_id": user_id, "amount": amount, "type": "deposit", "status": "pending"}))
    add_to_history(user_id, {"tx_id": tx_id, "type": "ገቢ", "amount": amount, "status": "pending", "date": time.strftime("%Y-%m-%d %H:%M")})

    thread = threading.Thread(target=send_photo_background, args=(user_name, user_id, amount, tx_id, photo_data))
    thread.start()
    return jsonify({"status": "success"})

# ==========================================
# 💸 WITHDRAW LOGIC
# ==========================================
@server.route('/api/withdraw', methods=['POST'])
@telegram_auth_required
def handle_withdraw():
    data = request.json or {}
    user_id = data.get("user_id")

    if is_user_banned(user_id):
        return jsonify({"status": "error", "message": "አካውንትዎ ታግዷል! መገልገያዎችን መጠቀም አይችሉም።"}), 403

    user_name = data.get("user_name", "የሰፈር ልጅ")
    try:
        amount = float(data.get("amount", 0))
    except ValueError:
        return jsonify({"status": "error", "message": "የተሳሳተ የገንዘብ መጠን ነው"}), 400

    phone = str(data.get("phone", ""))
    bank_name = data.get("bank_name", "")
    account_name = data.get("account_name", "")

    if not user_id or amount <= 0: return jsonify({"status": "error", "message": "የጎደለ መረጃ"}), 400
    if bank_name not in ALLOWED_BANKS: return jsonify({"status": "error", "message": "እባክዎ ትክክለኛ ባንክ ይምረጡ"}), 400
    if not is_number_only(phone): return jsonify({"status": "error", "message": "ስልክ ቁጥር ቁጥር ብቻ መሆን አለበት"}), 400
    if not is_text_only(account_name): return jsonify({"status": "error", "message": "የአካውንት ስም ፊደል ብቻ መሆን አለበት"}), 400

    balance_raw = redis.hget("users:balance", user_id)
    current_balance = float(balance_raw) if balance_raw else 0.0

    if amount > current_balance:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400

    redis.hincrbyfloat("users:balance", user_id, -amount)

    withdraw_info = {"bank_name": bank_name, "account_name": account_name, "phone": phone}
    save_user_withdraw_details(user_id, withdraw_info)

    tx_id = "WD-" + str(uuid.uuid4())[:5]
    withdraw_data = {
        "user_id": user_id, "amount": amount, "type": "withdraw", "status": "pending",
        "phone": phone, "bank_name": bank_name, "account_name": account_name
    }
    redis.set(f"tx:{tx_id}", json.dumps(withdraw_data))
    add_to_history(user_id, {"tx_id": tx_id, "type": "ወጪ", "amount": amount, "status": "pending", "date": time.strftime("%Y-%m-%d %H:%M")})

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ አጽድቅ (ክፍያ ፈጸምኩ)", callback_data=f"ok|withdraw|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no|withdraw|{tx_id}|{user_id}|{amount}")
    )
    caption = f"💸 <b>አዲስ የወጪ (Withdraw) ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: <code>{user_id}</code>\n💰 መጠን: <b>{amount} ብር</b>\n\n🏦 ባንክ: <b>{bank_name}</b>\n💳 የባንክ ስም: <b>{account_name}</b>\n📱 አካውንት/ስልክ: <code>{phone}</code>"

    try:
        bot.send_message(ADMIN_ID, caption, parse_mode="HTML", reply_markup=markup)
    except Exception: pass

    return jsonify({"status": "success", "message": "የወጪ ጥያቄዎ ለአድሚን ተልኳል። ክፍያው ሲፈጸም መልዕክት ይደርስዎታል!"})

@server.route('/api/get_withdraw_info', methods=['POST'])
def api_get_withdraw_info():
    data = request.json or {}
    user_id = data.get("user_id")
    if not user_id: return jsonify({"status": "error", "message": "የጎደለ መረጃ"}), 400
    info = get_user_withdraw_details(user_id)
    return jsonify({"status": "success", "info": info}) if info else jsonify({"status": "success", "info": None})

# --- CALLBACK SYSTEM ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("ok") or call.data.startswith("no"))
def process_admin_action(call):
    try:
        parts = call.data.split("|")
        action, tx_type, tx_id, user_id, amount = parts[0], parts[1], parts[2], parts[3], float(parts[4])

        tx_data_raw = redis.get(f"tx:{tx_id}")
        if not tx_data_raw:
            bot.answer_callback_query(call.id, "⚠️ ይህ ትራንዛክሽን ቀደም ብሎ ተሰርዟል ወይም አልተገኘም!")
            return

        tx_data = json.loads(tx_data_raw)
        if tx_data.get("status") != "pending":
            bot.answer_callback_query(call.id, f"⚠️ ይህ ጥያቄ ቀደም ብሎ {tx_data.get('status')} ሆኗል!")
            return

        if tx_type == "deposit":
            if action == "ok":
                redis.hincrbyfloat("users:balance", user_id, amount)
                redis.incrbyfloat("stats:total_deposits", amount)
                tx_data["status"] = "approved"
                update_history_tx_status(user_id, tx_id, "approved")
                bot.send_message(user_id, f"✅ <b>ዴፖዚትዎ ጸድቋል!</b>\n💰 መጠን: <b>{amount} ብር</b> ወደ አካውንትዎ ገብቷል።")
                bot.answer_callback_query(call.id, "✅ በተሳካ ሁኔታ ጸድቋል!")
                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=call.message.caption + "\n\n🟢 <b>[የጸደቀ ገቢ]</b>")
            else:
                tx_data["status"] = "rejected"
                update_history_tx_status(user_id, tx_id, "rejected")
                bot.send_message(user_id, f"❌ የ <b>{amount} ብር</b> ገቢ ጥያቄዎ በባለሙያ ውድቅ ተደርጓል።")
                bot.answer_callback_query(call.id, "❌ ውድቅ ተደርጓል!")
                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=call.message.caption + "\n\n🔴 <b>[ውድቅ የተደረገ ገቢ]</b>")

        elif tx_type == "withdraw":
            if action == "ok":
                redis.incrbyfloat("stats:total_withdrawals", amount)
                tx_data["status"] = "approved"
                update_history_tx_status(user_id, tx_id, "approved")
                bot.send_message(user_id, f"✅ የ <b>{amount} ብር</b> ወጪ (Withdraw) ጥያቄዎ ተከፍሏል!")
                bot.answer_callback_query(call.id, "✅ ክፍያ መፈጸሙ ተረጋግጧል!")
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n🟢 <b>[ክፍያ የተፈጸመለት]</b>")
            else:
                redis.hincrbyfloat("users:balance", user_id, amount)
                tx_data["status"] = "refunded" 
                update_history_tx_status(user_id, tx_id, "refunded") 
                bot.send_message(user_id, f"❌ የ <b>{amount} ብር</b> ወጪ ጥያቄዎ ተሰርዟል! ገንዘቡ ወደ ባላንስዎ ተመልሷል (Refunded)።")
                bot.answer_callback_query(call.id, "❌ ወጪው ተሰርዟል፣ ገንዘቡ ተመልሷል!")
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n🔴 <b>[የተሰረዘ እና የተመለሰ (Refunded)]</b>")

        redis.set(f"tx:{tx_id}", json.dumps(tx_data))
    except Exception as e:
        bot.answer_callback_query(call.id, f"⚠️ ስህተት፡ {str(e)}")

# ==========================================
# 🛡️ አዲሱ የአድሚን መቆጣጠሪያ
# ==========================================
@server.route('/admin-panel')
def admin_panel():
    return render_template('admin.html')

@server.route('/api/admin/get_dashboard_data', methods=['POST'])
def get_dashboard_data():
    data = request.json or {}
    admin_id = str(data.get("admin_id"))

    if admin_id != str(ADMIN_ID): 
        return jsonify({"status": "error", "message": "ያልተፈቀደ የደህንነት ጥሰት ሙከራ!"}), 403

    balances_raw = redis.hgetall("users:balance")
    users_list = []
    total_system_balance = 0.0

    for uid_raw, bal_raw in balances_raw.items():
        uid = uid_raw.decode('utf-8') if isinstance(uid_raw, bytes) else str(uid_raw)
        bal = float(bal_raw.decode('utf-8') if isinstance(bal_raw, bytes) else bal_raw)
        users_list.append({"user_id": uid, "balance": bal})
        total_system_balance += bal

    total_users = len(users_list)
    banned_users_count = redis.scard("banned_users")
    total_dep = float(redis.get("stats:total_deposits") or 0.0)
    total_wd = float(redis.get("stats:total_withdrawals") or 0.0)
    net_profit = total_dep - total_wd

    return jsonify({
        "status": "success",
        "stats": {
            "total_users": total_users,
            "banned_users": banned_users_count,
            "total_deposits": total_dep,
            "total_withdrawals": total_wd,
            "net_profit": net_profit,
            "total_user_balances": total_system_balance
        },
        "users": users_list
    })

@server.route('/api/admin/user_action', methods=['POST'])
def admin_user_action():
    data = request.json or {}
    admin_id = str(data.get("admin_id"))
    target_user_id = str(data.get("target_user_id"))
    action = data.get("action") 

    if admin_id != str(ADMIN_ID): return jsonify({"status": "error", "message": "ያልተፈቀደ ሙከራ!"}), 403
    if not target_user_id: return jsonify({"status": "error", "message": "የተጠቃሚ ID አልተገኘም!"}), 400

    if action == "ban":
        redis.sadd("banned_users", target_user_id)
        try: bot.send_message(target_user_id, "⚠️ <b>መለያዎ (Account) በህግ ጥሰት ምክንያት ታግዷል!</b>", parse_mode="HTML")
        except: pass
        return jsonify({"status": "success", "message": "ተጠቃሚው በተሳካ ሁኔታ ታግዷል!"})
    elif action == "unban":
        redis.srem("banned_users", target_user_id)
        try: bot.send_message(target_user_id, "🎉 <b>የመለያዎ እገዳ ተነስቷል!</b>\nአሁን መጫወት ይችላሉ።", parse_mode="HTML")
        except: pass
        return jsonify({"status": "success", "message": "የተጠቃሚው እገዳ ተነስቷል!"})
    elif action == "adjust_balance":
        amount = float(data.get("amount", 0))
        current_balance = float(redis.hget("users:balance", target_user_id) or 0.0)
        new_balance = current_balance + amount
        if new_balance < 0: return jsonify({"status": "error", "message": f"ስህተት! ወደ ኔጌቲቭ ማውረድ አይቻልም!"}), 400
        redis.hset("users:balance", target_user_id, new_balance)

        tx_type = "ገቢ" if amount > 0 else "ወጪ"
        tx_id = "ADM-" + str(uuid.uuid4())[:5] 
        add_to_history(target_user_id, {"tx_id": tx_id, "type": tx_type, "amount": abs(amount), "status": "APPROVED", "date": time.strftime("%Y-%m-%d %H:%M")})
        try:
            sign = "+" if amount > 0 else ""
            bot.send_message(target_user_id, f"🔔 <b>የሂሳብ ማስተካከያ!</b>\nባላንስዎ ላይ <b>{sign}{amount} ብር</b> በአድሚን ተስተካክሏል።", parse_mode="HTML")
        except: pass
        return jsonify({"status": "success", "message": "ባላንስ በተሳካ ሁኔታ ተስተካክሏል!"})
    return jsonify({"status": "error", "message": "የማይታወቅ ትዕዛዝ!"}), 400

@bot.message_handler(commands=['admin'])
def send_admin_panel(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📊 የአድሚን ፓነል ክፈት", web_app=WebAppInfo(url=f"{WEB_APP_URL}/admin-panel")))
        bot.send_message(message.chat.id, "🤖 <b>እንኳን ወደ 'የኛ ቤት' መቆጣጠሪያ ፓነል መጡ!</b>", parse_mode="HTML", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "❌ ይህ ትዕዛዝ ለአድሚን ብቻ የተፈቀደ ነው!")


# ==========================================
# 🔌 WEBHOOK & SERVER START
# ==========================================
@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

try:
    bot.remove_webhook()
    time.sleep(0.1)
    bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
except: pass

if __name__ == "__main__":
    socketio.run(server, host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
