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
TOKEN = "8721334129:AAEbMUHHLcVTv9pGzTwMwC_Wi4tLx3R_F5k"
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

def save_data():
    try:
        redis.set("fasil_lotto_db", json.dumps(data))
        with open(DB_FILE, "w") as f:
            json.dump(data, f)
    except: pass

def load_data():
    global data
    try:
        raw_redis_data = redis.get("fasil_lotto_db")
        if raw_redis_data:
            data = json.loads(raw_redis_data)
        elif os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                data.update(json.load(f))
    except: pass

load_data()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

def main_menu_markup(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS: markup.add("⚙️ Admin Settings")
    return markup

def update_group_board(b_id):
    b_id = str(b_id)
    board = data["boards"][b_id]
    active_pay = PAYMENTS[data.get("current_shift", "me")]
    text = f"🇪🇹 🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ!</b> 🏟️ 🇪🇹\n              <b>በ {board['price']} ብር</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    for i in range(1, board["max"] + 1):
        n = str(i)
        if n in board["slots"]:
            text += f"<b>{i}👉</b> <b><i><code>{board['slots'][n]}</code></i></b> ✅🏆🙏\n"
        else:
            text += f"<b>{i}👉</b> @@@@ ✅🏆🙏\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n🤖 <b>ለመጫወት፦</b> @"+bot.get_me().username
    try:
        msg_id = data.get("pinned_msgs", {}).get(b_id)
        if msg_id: bot.edit_message_text(text, GROUP_ID, msg_id)
        else:
            m = bot.send_message(GROUP_ID, text)
            data["pinned_msgs"][b_id] = m.message_id
            save_data()
    except: pass

# --- Handlers ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    bot.send_message(uid, f"👋 እንኳን መጡ {user['name']}!\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር", reply_markup=main_menu_markup(uid))

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    if message.chat.id == GROUP_ID or message.chat.type == 'private':
        uid = str(message.from_user.id)
        u_name = message.from_user.first_name
        mid = message.message_id if message.chat.id == GROUP_ID else 0
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"g_app_{uid}_{mid}_{u_name}"))
        for adm in ADMIN_IDS:
            bot.send_photo(adm, message.photo[-1].file_id, caption=f"📩 ደረሰኝ ከ {u_name}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    parts = call.data.split('_')
    
    if call.data.startswith('g_app_') and is_admin:
        target_id, r_mid, u_name = parts, parts, parts
        msg = bot.send_message(call.message.chat.id, f"💰 ለ <b>{u_name}</b> የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(msg, send_picker_to_group, target_id, r_mid, u_name)

    elif call.data.startswith('p_'):
        uid, bid, num = parts, parts, parts
        if str(call.from_user.id) != str(uid):
            bot.answer_callback_query(call.id, "⚠️ የእርስዎ ምርጫ አይደለም!", show_alert=True)
            return
        process_secure_pick(call, uid, bid, num)

    elif call.data == "admin_manage" and is_admin:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("💵 ካሽ", callback_data="admin_cash"), types.InlineKeyboardButton("❌ ሰርዝ", callback_data="admin_delete"))
        bot.edit_message_text("🛠 አድሚን ስራዎች", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "admin_cash" and is_admin:
        m = bot.send_message(call.from_user.id, "ጻፉ፦ ሰሌዳ-ቁጥር ስም (1-05 አበበ)")
        bot.register_next_step_handler(m, process_cash_reg)

    elif call.data.startswith('select_'): handle_selection(call)

def send_picker_to_group(message, target_id, receipt_mid, user_name):
    try:
        amt = int(message.text)
        user = get_user(target_id, user_name)
        user["wallet"] += amt
        save_data()
        
        bid = "1"
        for b_id, b_info in data["boards"].items():
            if b_info["active"] and b_info["price"] <= user["wallet"]:
                bid = b_id; break
        
        board = data["boards"][bid]
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(str(i), callback_data=f"p_{target_id}_{bid}_{i}") if str(i) not in board["slots"] else types.InlineKeyboardButton("❌", callback_data="t") for i in range(1, board["max"] + 1)]
        markup.add(*btns)
        
        text = f"✅ <b>ክፍያ ተረጋግጧል!</b>\n👤 <b>ተጫዋች፦</b> {user_name}\n💰 <b>ቀሪ፦</b> {user['wallet']} ብር"
        bot.send_message(GROUP_ID, text, reply_to_message_id=int(receipt_mid) if int(receipt_mid) != 0 else None, reply_markup=markup)
    except: bot.send_message(message.chat.id, "❌ ስህተት! ቁጥር ብቻ ያስገቡ።")

def process_secure_pick(call, uid, bid, num):
    user = get_user(uid); board = data["boards"][bid]
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "❌ በቂ ሂሳብ የለም!", show_alert=True); return
    user["wallet"] -= board["price"]; board["slots"][num] = user["name"]
    save_data(); update_group_board(bid)
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")
    if user["wallet"] >= board["price"]: handle_selection(call)
    else: bot.delete_message(call.message.chat.id, call.message.message_id)

def handle_selection(call):
    bid = call.data.split('_') if '_' in call.data else "1"
    user = get_user(call.from_user.id); board = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"p_{call.from_user.id}_{bid}_{i}") for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
    markup.add(*btns)
    bot.send_message(call.message.chat.id, f"🎰 ሰሌዳ {bid} ቁጥር ይምረጡ", reply_markup=markup)

def process_cash_reg(message):
    try:
        parts = message.text.split(' ')
        bid, num = parts.split('-')
        name = parts
        data["boards"][bid]["slots"][num] = name
        save_data(); update_group_board(bid)
        bot.send_message(message.chat.id, "✅ ተመዝግቧል!")
    except: bot.send_message(message.chat.id, "❌ ስህተት! (1-05 አበበ)")

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def start_selection(message):
    markup = types.InlineKeyboardMarkup()
    for b_id in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"ሰሌዳ {b_id}", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "ሰሌዳ ይምረጡ፦", reply_markup=markup)

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    while True:
        try: bot.polling(none_stop=True, interval=1, timeout=20)
        except: time.sleep(5)
