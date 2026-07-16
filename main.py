import eventlet
eventlet.monkey_patch()  # 👈 ይህ ከምንም ነገር በፊት እዚህ መሆን አለበት

import os
import time
import json
import uuid
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import telebot
from telebot.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# ከ config.py የጋራ ማዋቀሪያዎችንና ረዳቶችን ማስገባት
import config
from config import (
    bot, redis, TOKEN, ADMIN_ID, WEB_APP_URL,
    telegram_auth_required, deduct_balance_safely, add_to_history, update_history_tx_status
)

# 🎮 6ቱንም የጌሞች ብሉፕሪንቶች ማስገባት
from games.gofere_zewd import gofere_zewd_bp
from games.aviator import aviator_bp
from games.chicken import chicken_bp
from games.keno import keno_bp
from games.virtual_sports import virtual_sports_bp
from games.real_sports import real_sports_bp

server = Flask(__name__)
server.secret_key = os.environ.get("SECRET_KEY", "gashabet_secret_super_key_123")
socketio = SocketIO(server, cors_allowed_origins="*", async_mode='eventlet')

server.register_blueprint(gofere_zewd_bp)
server.register_blueprint(aviator_bp)
server.register_blueprint(chicken_bp)
server.register_blueprint(keno_bp)
server.register_blueprint(virtual_sports_bp)
server.register_blueprint(real_sports_bp)

@server.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print("🔌 አዲስ ተጫዋች በዌብሶኬት ተገናኝቷል!")

@socketio.on('disconnect')
def handle_disconnect():
    print("❌ ተጫዋች ከዌብሶኬት ተለያይቷል!")

@server.route('/api/get_balance', methods=['POST'])
@telegram_auth_required
def get_balance():
    data = request.json or {}
    user_id = data.get("user_id")
    game_mode = data.get("game_mode", "real")

    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400

    if game_mode == "demo":
        balance_raw = redis.hget("users:demo_balance", user_id)
        if balance_raw is None:
            redis.hset("users:demo_balance", user_id, 10000.0)
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
@telegram_auth_required
def get_user_history():
    data = request.json or {}
    user_id = data.get("user_id")
    
    # 🔍 ይሄንን Print ኮድ ጨምርበት
    print(f"DEBUG: Getting history for user: {user_id}")
    
    raw_history = redis.lrange(f"history:{user_id}", 0, -1) or []
    print(f"DEBUG: Found {len(raw_history)} items in Redis.") 
    
    history_list = [json.loads(item) for item in raw_history]
    return jsonify({"status": "success", "history": history_list})

@server.route('/api/deposit', methods=['POST'])
@telegram_auth_required
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

    add_to_history(user_id, {
        "tx_id": tx_id,
        "type": "ገቢ", 
        "amount": amount, 
        "status": "pending", 
        "date": time.strftime("%Y-%m-%d %H:%M")
    })

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
@telegram_auth_required
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

    deduct_status = deduct_balance_safely(user_id, amount, "real")
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ እውነተኛ ባላንስ የለዎትም"}), 400
    elif deduct_status == "ERROR":
        return jsonify({"status": "error", "message": "የሲስተም ስህተት ተፈጥሯል"}), 500

    tx_id = str(uuid.uuid4())[:8]
    tx_data = {"user_id": user_id, "amount": amount, "type": "withdraw", "status": "pending"}
    redis.set(f"tx:{tx_id}", json.dumps(tx_data))

    add_to_history(user_id, {
        "tx_id": tx_id,
        "type": "ወጪ", 
        "amount": amount, 
        "status": "pending", 
        "date": time.strftime("%Y-%m-%d %H:%M")
    })

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ ተከፍሏል", callback_data=f"ok|withdraw|{tx_id}|{user_id}|{amount}"),
        InlineKeyboardButton("❌ ሰርዝ (ተመላሽ አድርግ)", callback_data=f"no|withdraw|{tx_id}|{user_id}|{amount}")
    )

    msg = f"💸 <b>አዲስ Withdraw ጥያቄ</b>\n\n👤 ስም: {user_name}\n🆔 ID: <code>{user_id}</code>\n🏦 ባንክ: {bank_name}\n👤 የአካውንት ስም: {account_name}\n💳 አካውንት/ስልክ: <code>{phone}</code>\n💰 መጠን: <b>{amount} ብር</b>\n🔑 TxID: <code>{tx_id}</code>"
    bot.send_message(ADMIN_ID, msg, reply_markup=markup)
    return jsonify({"status": "success"})

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

    if tx_type == "deposit":
        tx_status = "completed" if action == "ok" else "failed"
        status_text = "🟢 ጸድቋል (Completed)" if action == "ok" else "🔴 ውድቅ ተደርጓል (Failed)"
    else:
        tx_status = "completed" if action == "ok" else "refunded"
        status_text = "🟢 ተከፍሏል (Completed)" if action == "ok" else "🔴 ተሰርዟል/ተመልሷል (Refunded)"

    tx_data["status"] = tx_status
    redis.set(tx_key, json.dumps(tx_data))

    update_history_tx_status(user_id, tx_id, tx_status)

    if tx_type == "deposit":
        if action == "ok":
            redis.hincrbyfloat("users:balance", user_id, amount)
            try:
                bot.send_message(user_id, f"🎉 <b>የገቢ (Deposit) ጥያቄዎ ጸድቋል!</b>\n\n💰 የገንዘብ መጠን: <b>{amount} ETB</b> ዋሌትዎ ላይ ተጨምሯል።")
            except Exception as e:
                pass
        else:
            try:
                bot.send_message(user_id, f"❌ <b>የገቢ (Deposit) ጥያቄዎ ውድቅ ተደርጓል!</b>\n\n💰 የገንዘብ መጠን: <b>{amount} ETB</b>\n🔍 እባክዎ የላኩት የክፍያ ደረሰኝ ትክክለኛ መሆኑን ያረጋግጡ።")
            except Exception as e:
                pass

    elif tx_type == "withdraw":
        if action == "ok":
            try:
                bot.send_message(user_id, f"🎉 <b>የወጪ (Withdraw) ጥያቄዎ ተከፍሏል!</b>\n\n💰 የገንዘብ መጠን: <b>{amount} ETB</b> ወደ ባንክ አካውንትዎ በተሳካ ሁኔታ ተልኳል።")
            except Exception as e:
                pass
        else:
            redis.hincrbyfloat("users:balance", user_id, amount)
            try:
                bot.send_message(user_id, f"❌ <b>የወጪ (Withdraw) ጥያቄዎ ተሰርዟል!</b>\n\n💰 የገንዘብ መጠን: <b>{amount} ETB</b> ወደ ዋሌትዎ ተመልሷል።")
            except Exception as e:
                pass

    bot.answer_callback_query(call.id, f"ጥያቄው: {status_text}")

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

@bot.message_handler(commands=['start'])
def send_welcome(message):
    web_app_info = WebAppInfo(url=WEB_APP_URL)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 Play Games", web_app=web_app_info))
    bot.reply_to(message, "👋 እንኳን ወደ ሰፈር ቦት በደህና መጡ! ለመጫወት እና ዋሌትዎን ለመጠቀም ከታች ያለውን ቁልፍ ይጫኑ።", reply_markup=markup)

if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(0.1)
        bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
        print("✅ Webhook setup was successful!")
    except Exception as e:
        print(f"❌ Webhook Setup Failed: {e}")

    socketio.run(server, host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
