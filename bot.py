import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time
from upstash_redis import Redis

# --- 1. Web Hosting ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Lotto System is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት መረጃዎች ---
TOKEN = "8721334129:AAF8Uexl1shbdyg2sdYT_aqWE1r1kzQH39k"
MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003749311489
DB_CHANNEL_ID = -1003747262103
ADMIN_IDS = [MY_ID, ASSISTANT_ID]

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323"}
}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Redis Connection
REDIS_URL = "https://sunny-ferret-79578.upstash.io"
REDIS_TOKEN = "gQAAAAAAATbaAAIncDE4MTQ2MThjMjVjYjI0YzU5OGQ0MjMzZGI0MGIwZTkwNXAxNzk1Nzg"
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

# --- 3. ዳታቤዝ አያያዝ ---
def load_data():
    try:
        raw = redis.get("fasil_lotto_db")
        if raw: return json.loads(raw)
    except: pass
    return {
        "users": {}, "current_shift": "me",
        "boards": {
            "1": {"max": 25, "price": 50, "prize": "1ኛ 200, 2ኛ 100", "active": True, "slots": {}},
            "2": {"max": 50, "price": 100, "prize": "1ኛ 400, 2ኛ 200", "active": True, "slots": {}},
            "3": {"max": 100, "price": 200, "prize": "1ኛ 800, 2ኛ 400", "active": True, "slots": {}}
        },
        "pinned_msgs": {"1": None, "2": None, "3": None}
    }

data = load_data()

def save_data():
    redis.set("fasil_lotto_db", json.dumps(data))

# --- 4. ግሩፕ ላይ ሰሌዳ የማደሻ ኮድ ---
def update_group_board(bid):
    bid = str(bid)
    board = data["boards"][bid]
    active_pay = PAYMENTS[data.get("current_shift", "me")]
    
    text = f"🇪🇹 🏟️ <b>ፋሲል ዕጣ - ሰሌዳ {bid}</b> 🏟️ 🇪🇹\n"
    text += f"              <b>በ {board['price']} ብር</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

    for i in range(1, board["max"] + 1):
        n = str(i)
        if n in board["slots"]:
            text += f"<b>{i}👉</b> <code>{board['slots'][n]}</code> ✅🏆🙏\n"
        else:
            text += f"<b>{i}👉</b> @@@@ ✅🏆🙏\n"
            
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"👉 <b>Telebirr:</b> <code>{active_pay['tele']}</code>\n"
    text += f"👉 <b>CBE:</b> <code>{active_pay['cbe']}</code>\n"

    try:
        msg_id = data.get("pinned_msgs", {}).get(bid)
        if msg_id:
            bot.edit_message_text(text, GROUP_ID, msg_id, parse_mode="HTML")
        else:
            m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
            data["pinned_msgs"][bid] = m.message_id
            bot.pin_chat_message(GROUP_ID, m.message_id)
            save_data()
    except:
        m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
        data["pinned_msgs"][bid] = m.message_id
        save_data()

# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    if int(uid) in ADMIN_IDS:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("⚙️ Admin Settings")
        bot.send_message(uid, "ሰላም አድሚን!", reply_markup=markup)
    else:
        bot.send_message(uid, "👋 እንኳን ወደ ፋሲል መዝናኛ መጡ!")

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id in ADMIN_IDS)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("⚙️ ሰሌዳዎችን አስተካክል", callback_data="admin_manage"),
        types.InlineKeyboardButton("🔍 አሸናፊ ፈልግ", callback_data="lookup_winner"),
        types.InlineKeyboardButton("🔄 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset")
    )
    bot.send_message(message.chat.id, "🛠 <b>የአድሚን ዳሽቦርድ</b>", reply_markup=markup)

# --- 6. የ Callback Listener (የተስተካከለ) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    d = call.data

    if d == "admin_manage" and is_admin:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("💵 በካሽ መዝግብ", callback_data="admin_cash"),
                   types.InlineKeyboardButton("🗑 ቁጥር ሰርዝ", callback_data="admin_delete"))
        for bid in data["boards"]:
            markup.add(types.InlineKeyboardButton(f"⚙️ ሰሌዳ {bid} አስተካክል", callback_data=f"edit_{bid}"))
        bot.edit_message_text("🛠 <b>ማስተካከያ ይምረጡ፦</b>", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif d.startswith('edit_') and is_admin:
        bid = d.split('_')
        b = data["boards"][bid]
        markup = types.InlineKeyboardMarkup(row_width=2)
        status = "🟢 ክፍት" if b['active'] else "🔴 ዝግ"
        markup.add(types.InlineKeyboardButton(status, callback_data=f"toggle_{bid}"))
        markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
        bot.edit_message_text(f"📊 <b>ሰሌዳ {bid}</b>\nዋጋ፦ {b['price']} ብር\nሽልማት፦ {b['prize']}", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif d == "admin_reset" and is_admin:
        markup = types.InlineKeyboardMarkup()
        for bid in data["boards"]:
            markup.add(types.InlineKeyboardButton(f"Reset ሰሌዳ {bid}", callback_data=f"doreset_{bid}"))
        bot.edit_message_text("🗑 <b>የትኛው ሰሌዳ ይጽዳ?</b>", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif d.startswith('doreset_') and is_admin:
        bid = d.split('_')
        data["boards"][bid]["slots"] = {}
        data["pinned_msgs"][bid] = None
        save_data()
        update_group_board(bid)
        bot.answer_callback_query(call.id, "ሰሌዳው ጸድቷል!", show_alert=True)

    elif d == "admin_cash" and is_admin:
        m = bot.send_message(call.from_user.id, "📝 <b>በካሽ ለመመዝገብ፦</b>\nሰሌዳ-ቁጥር ስም ይጻፉ\nምሳሌ፦ 1-05 አበበ")
        bot.register_next_step_handler(m, process_cash)

    elif d == "admin_delete" and is_admin:
        m = bot.send_message(call.from_user.id, "🗑 <b>ቁጥር ለመሰረዝ፦</b>\nሰሌዳ-ቁጥር ይጻፉ\nምሳሌ፦ 1-05")
        bot.register_next_step_handler(m, process_delete)

    elif d == "lookup_winner" and is_admin:
        m = bot.send_message(call.from_user.id, "🔍 አሸናፊ ፈልግ (ምሳሌ፦ 2-13)")
        bot.register_next_step_handler(m, process_lookup)

# --- 7. አጋዥ ፈንክሽኖች ---
def process_cash(message):
    try:
        info, name = message.text.split(' ', 1)
        bid, num = info.split('-')
        bid, num = str(bid), str(int(num))
        data["boards"][bid]["slots"][num] = name[:15]
        save_data()
        update_group_board(bid) # ግሩፕ ላይ ያለውን ወዲያው ያድሳል
        bot.send_message(message.chat.id, f"✅ ሰሌዳ {bid} ቁጥር {num} ለ {name} ተመዝግቧል!")
    except: bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 1-05 አበበ")

def process_delete(message):
    try:
        bid, num = message.text.split('-')
        bid, num = str(bid), str(int(num))
        if num in data["boards"][bid]["slots"]:
            del data["boards"][bid]["slots"][num]
            save_data()
            update_group_board(bid) # ግሩፕ ላይ ያለውን ወዲያው ያድሳል
            bot.send_message(message.chat.id, f"🗑 ሰሌዳ {bid} ቁጥር {num} ተሰርዟል!")
        else:
            bot.send_message(message.chat.id, "❌ ቁጥሩ አልተገኘም!")
    except: bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 1-05")

def process_lookup(message):
    try:
        bid, num = message.text.split('-')
        bid, num = str(bid), str(int(num))
        name = data["boards"][bid]["slots"].get(num)
        if name: bot.send_message(message.chat.id, f"🏆 አሸናፊ፦ {name}")
        else: bot.send_message(message.chat.id, "⚠️ ቁጥሩ ገና አልተያዘም!")
    except: bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 2-13")

if __name__ == "__main__":
    keep_alive()
    print("Fasil Bot is LIVE...")
    bot.infinity_polling()
