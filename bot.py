import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread, Timer
import time
import requests
import re
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

# --- 2. ቦት እና Redis መረጃዎች ---
TOKEN = "8721334129:AAEbMUHHLcVTv9pGzTwMwC_Wi4tLx3R_F5k"
MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003749311489
DB_CHANNEL_ID = -1003747262103
ADMIN_IDS = [MY_ID, ASSISTANT_ID]

REDIS_URL = "https://sunny-ferret-79578.upstash.io"
REDIS_TOKEN = "gQAAAAAAATbaAAIncDE4MTQ2MThjMjVjYjI0YzU5OGQ0MjMzZGI0MGIwZTkwNXAxNzk1Nzg"
HEADERS = {"Authorization": f"Bearer {REDIS_TOKEN}"}
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323"}
}

# --- 3. ዳታቤዝ አያያዝ ---
DB_FILE = "fasil_db.json"
data = {
    "users": {},
    "current_shift": "me",
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "1ኛ 200, 2ኛ 100, 3ኛ 50", "active": True, "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "1ኛ 400, 2ኛ 200, 3ኛ 100", "active": True, "slots": {}},
        "3": {"max": 100, "price": 200, "prize": "1ኛ 800, 2ኛ 400, 3ኛ 200", "active": True, "slots": {}}
    },
    "pinned_msgs": {"1": None, "2": None, "3": None}
}

def delete_msg_later(chat_id, message_id, delay=120):
    def delete():
        try: bot.delete_message(chat_id, message_id)
        except: pass
    Timer(delay, delete).start()

def save_data():
    try:
        redis.set("fasil_lotto_db", json.dumps(data))
        with open(DB_FILE, "w") as f: json.dump(data, f)
        with open(DB_FILE, "rb") as f: bot.send_document(DB_CHANNEL_ID, f, caption=f"🔄 Backup - {time.ctime()}")
    except: pass

def load_data():
    global data
    try:
        raw_redis_data = redis.get("fasil_lotto_db")
        if raw_redis_data: data = json.loads(raw_redis_data)
    except: pass

load_data()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]: data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

def main_menu_markup(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS: markup.add("⚙️ Admin Settings")
    return markup

# --- 4. የሰሌዳ ዲዛይን ---
def update_group_board(b_id):
    board = data["boards"][b_id]
    text = f"🎰 <b>ፋሲል ዕጣ - ሰሌዳ {b_id}</b>\n🎫 መደብ፦ <b>{board['price']} ብር</b>\n━━━━━━━━━━━━━━━\n"
    line = ""
    for i in range(1, board["max"] + 1):
        s_i = str(i).zfill(2)
        line += f"<code>{s_i}</code>{ '✅'+board['slots'][str(i)][:5] if str(i) in board['slots'] else '⬜️'}\t\t"
        if i % 2 == 0:
            text += line + "\n"
            line = ""
    text += f"\n━━━━━━━━━━━━━━━\n🎁 <b>ሽልማት፦ {board['prize']}</b>\n🤖 @Fasil_assistant_bot"
    try:
        if data["pinned_msgs"].get(b_id): bot.edit_message_text(text, GROUP_ID, data["pinned_msgs"][b_id])
        else:
            m = bot.send_message(GROUP_ID, text)
            bot.pin_chat_message(GROUP_ID, m.message_id)
            data["pinned_msgs"][b_id] = m.message_id
            save_data()
    except: pass

# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    pay = PAYMENTS[data.get("current_shift", "me")]
    text = (f"👋 <b>እንኳን መጡ!</b>\n👤 ስም፦ {user['name']}\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር\n"
            f"━━━━━━━━━━━━━━━\n🏦 Telebirr: <code>{pay['tele']}</code>\n🔸 CBE: <code>{pay['cbe']}</code>\n"
            "⚠️ ደረሰኝ እዚህ ይላኩ።")
    bot.send_message(uid, text, reply_markup=main_menu_markup(uid))

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup()
    for b_id, b_info in data["boards"].items():
        if b_info["active"]: markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} | {b_info['price']} ብር", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "ሰሌዳ ይምረጡ፦", reply_markup=markup)

# --- 6. አውቶማቲክ ደረሰኝ ማረጋገጫ (Group) ---
@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.type in ['group', 'supergroup'])
def handle_group_auto_verify(message):
    uid = str(message.from_user.id)
    get_user(uid, message.from_user.first_name)
    load_msg = bot.reply_to(message, "⏳ <b>ክፍያዎን እያመሳከርኩ ነው...</b>")
    delete_msg_later(message.chat.id, load_msg.message_id, 20)

    try:
        res = requests.get("https://sunny-ferret-79578.upstash.io/get/last_sms", headers=HEADERS, timeout=12)
        if res.status_code == 200:
            sms = res.json().get('result', "")
            amounts = re.findall(r'\d+(?:\.\d+)?', sms.replace(',', ''))
            if amounts:
                paid_amount = float(amounts)
                data["users"][uid]["wallet"] += int(paid_amount)
                save_data()
                
                active_boards = [b_id for b_id, b_info in data["boards"].items() if b_info["active"]]
                markup = types.InlineKeyboardMarkup()
                if len(active_boards) == 1:
                    bid = active_boards
                    possible = int(paid_amount // data["boards"][bid]["price"])
                    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}_{uid}") for i in range(1, data["boards"][bid]["max"]+1) if str(i) not in data["boards"][bid]["slots"]]
                    markup.add(*btns)
                    msg = f"✅ <b>ተረጋግጧል!</b> ({paid_amount} ብር)\n🔢 የዕጣ ብዛት፦ {possible}\nቁጥር ይምረጡ፦"
                else:
                    for b_id in active_boards: markup.add(types.InlineKeyboardButton(f"ሰሌዳ {b_id}", callback_data=f"select_{b_id}_{uid}"))
                    msg = f"✅ <b>ተረጋግጧል!</b> ({paid_amount} ብር)\nእባክዎ ሰሌዳ ይምረጡ፦"
                
                final = bot.edit_message_text(msg, message.chat.id, load_msg.message_id, reply_markup=markup)
                delete_msg_later(message.chat.id, final.message_id, 180)
    except: pass

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    parts = call.data.split('_')
    uid = str(call.from_user.id)
    
    # የባለቤትነት ማረጋገጫ
    if len(parts) > 3 and parts[-1] != uid:
        bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
        return

    if parts == 'pick':
        finalize_reg_multi(call, parts, parts)
    elif parts == 'select':
        handle_selection(call, parts)
    elif parts == 'approve' and uid in ADMIN_IDS:
        m = bot.send_message(call.from_user.id, "የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_app, parts)
    elif parts == 'doreset' and uid in ADMIN_IDS:
        data["boards"][parts]["slots"] = {}
        save_data(); update_group_board(parts)
        bot.answer_callback_query(call.id, "ጸድቷል!")

def handle_selection(call, bid):
    uid = str(call.from_user.id)
    user = get_user(uid); board = data["boards"][bid]
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True); return
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}_{uid}") for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
    markup.add(*btns)
    bot.edit_message_text(f"🎰 ሰሌዳ {bid}\nቀሪ ሂሳብ፦ {user['wallet']} ብር\nቁጥር ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

def finalize_reg_multi(call, bid, num):
    uid = str(call.from_user.id)
    user = get_user(uid); board = data["boards"][bid]
    if user["wallet"] < board["price"]: return
    
    board["slots"][num] = user["name"]
    data["users"][uid]["wallet"] -= board["price"]
    save_data(); update_group_board(bid)
    
    remaining = data["users"][uid]["wallet"]
    if remaining >= board["price"]:
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}_{uid}") for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
        markup.add(*btns)
        bot.edit_message_text(f"✅ ቁጥር {num} ተይዟል!\n💰 ቀሪ ሂሳብ፦ {remaining} ብር\nተጨማሪ ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)
    else:
        bot.edit_message_text("✅ ምርጫ ተጠናቋል! መልካም ዕድል!", call.message.chat.id, call.message.message_id)

def finalize_app(message, target):
    try:
        amt = int(message.text)
        data["users"][str(target)]["wallet"] += amt
        save_data()
        bot.send_message(target, f"✅ {amt} ብር ተጨምሯል!")
    except: pass

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    while True:
        try: bot.polling(none_stop=True, interval=1, timeout=20)
        except: time.sleep(5)
