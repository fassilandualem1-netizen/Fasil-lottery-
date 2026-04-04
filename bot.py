import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time
from upstash_redis import Redis

# --- 1. Web Hosting (Render እንዳይዘጋ) ---
app = Flask('')
@app.route('/')
def home(): return "Fasil & Damene Digital Lotto is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት እና የዳታቤዝ መረጃዎች ---
TOKEN = "8721334129:AAEbMUHHLcVTv9pGzTwMwC_Wi4tLx3R_F5k"
MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003749311489

ADMIN_IDS = [MY_ID, ASSISTANT_ID]

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757", "name": "Fassil"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323", "name": "Damene"}
}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Redis Connection
REDIS_URL = "https://sunny-ferret-79578.upstash.io"
REDIS_TOKEN = "gQAAAAAAATbaAAIncDE4MTQ2MThjMjVjYjI0YzU5OGQ0MjMzZGI0MGIwZTkwNXAxNzk1Nzg"
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

data = {
    "users": {},
    "current_shift": "me",
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "200, 100, 50", "active": True, "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "400, 200, 100", "active": True, "slots": {}},
        "3": {"max": 100, "price": 200, "prize": "800, 400, 200", "active": True, "slots": {}}
    },
    "pinned_msgs": {}
}

def save_data():
    try: redis.set("fasil_lotto_db", json.dumps(data))
    except: pass

def load_data():
    global data
    try:
        raw = redis.get("fasil_lotto_db")
        if raw: data.update(json.loads(raw))
    except: pass

load_data()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid).strip()
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

# --- 3. የሰሌዳ ዲዛይን (ግሩፕ ላይ የሚለጠፍ) ---
def update_group_board(b_id):
    b_id = str(b_id)
    board = data["boards"][b_id]
    active_pay = PAYMENTS[data.get("current_shift", "me")]
    
    text = "🇪🇹 🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ!</b> 🏟️ 🇪🇹\n"
    text += f"              በ {board['price']} ብር\n"
    text += "             👇👇👇👇👇\n"
    
    prizes = board['prize'].split(',')
    labels = ["1ኛ🟢", "2ኛ🟡", "3ኛ🔴"]
    for i, p in enumerate(prizes):
        if i < 3: text += f"             {labels[i]} {p.strip()} ብር\n"

    text += "\n🏆 <b>መልካም እድል ለሁላችሁም!</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

    for i in range(1, board["max"] + 1):
        num_str = str(i)
        if num_str in board["slots"]:
            text += f"{i}👉 {board['slots'][num_str]} ✅\n"
        else:
            text += f"{i}👉 @@@@ ⬜️\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🏦 <b>ተረኛ ገቢ ማስገቢያ ({active_pay['name']})፦</b>\n"
    text += f"👉 Telebirr: <code>{active_pay['tele']}</code>\n"
    text += f"👉 CBE: <code>{active_pay['cbe']}</code>\n"
    text += f"\n🤖 ለመጫወት፦ @{bot.get_me().username}"

    try:
        if b_id in data["pinned_msgs"]:
            bot.edit_message_text(text, GROUP_ID, data["pinned_msgs"][b_id])
        else:
            m = bot.send_message(GROUP_ID, text)
            bot.pin_chat_message(GROUP_ID, m.message_id)
            data["pinned_msgs"][b_id] = m.message_id
            save_data()
    except:
        m = bot.send_message(GROUP_ID, text)
        data["pinned_msgs"][b_id] = m.message_id
        save_data()

# --- 4. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS: markup.add("⚙️ Admin Settings")
    bot.send_message(uid, f"👋 ሰላም {user['name']}!\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} | 🎫 {b_info['price']} ብር", callback_data=f"sel_{b_id}"))
    bot.send_message(message.chat.id, "<b>ለመጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦</b>", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings")
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS: return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💵 በካሽ መዝግብ", callback_data="admin_cash"),
               types.InlineKeyboardButton("🔄 Shift ቀይር", callback_data="admin_shift"),
               types.InlineKeyboardButton("🧹 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset"))
    bot.send_message(message.chat.id, "🛠 <b>የአድሚን መቆጣጠሪያ፦</b>", reply_markup=markup)

# --- 5. ደረሰኝ አያያዝ ---
@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    if message.chat.type != 'private': return
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች", "⚙️ Admin Settings"]: return
    
    uid = str(message.from_user.id)
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"app_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"dec_{uid}"))
    
    cap = f"📩 <b>አዲስ ክፍያ</b>\n👤 ከ፦ {message.from_user.first_name}\n🆔 ID፦ <code>{uid}</code>"
    for adm in ADMIN_IDS:
        try:
            if message.photo: bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup)
            else: bot.send_message(adm, f"{cap}\n📝፦ {message.text}", reply_markup=markup)
        except: pass
    bot.send_message(uid, "⏳ ደረሰኝዎ ለባለቤቱ ተልኳል... እባክዎ ይጠብቁ። 🙏")

# --- 6. Callback Listener (አዝራሮች) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    uid = str(call.from_user.id)

    if call.data.startswith('app_') and is_admin:
        target = call.data.split('_')
        m = bot.send_message(call.from_user.id, f"💵 ለ ID {target} የሚጨመር ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_app, target)
    
    elif call.data == "admin_shift" and is_admin:
        data["current_shift"] = "assistant" if data["current_shift"] == "me" else "me"
        save_data()
        bot.answer_callback_query(call.id, f"ተረኛ ተቀይሯል፦ {PAYMENTS[data['current_shift']]['name']}")
    
    elif call.data == "admin_cash" and is_admin:
        m = bot.send_message(call.from_user.id, "📝 <b>በካሽ መዝግብ</b>\nምሳሌ፦ <code>1-05 አበበ</code>")
        bot.register_next_step_handler(m, process_cash_reg)

    elif call.data.startswith('sel_'):
        bid = call.data.split('_')
        user = get_user(uid)
        board = data["boards"][bid]
        if user["wallet"] < board["price"]:
            bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True); return
        
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(str(i), callback_data=f"pk_{bid}_{i}") 
                for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
        markup.add(*btns)
        bot.edit_message_text(f"🎰 ሰሌዳ {bid}\n💰 ቀሪ፦ {user['wallet']} ብር\nቁጥር ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith('pk_'):
        _, bid, num = call.data.split('_')
        user = get_user(uid)
        board = data["boards"][bid]
        if user["wallet"] < board["price"]: return
        
        user["wallet"] -= board["price"]
        board["slots"][num] = user["name"]
        save_data()
        update_group_board(bid)
        bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተይዟል!")
        bot.send_message(GROUP_ID, f"🎰 <b>ሰሌዳ {bid}</b>\n👤 {user['name']} ቁጥር <b>{num}</b> መርጧል! 🍀")
        bot.delete_message(call.message.chat.id, call.message.message_id)

def finalize_app(message, target):
    try:
        amt = int(message.text)
        user = get_user(target)
        user["wallet"] += amt
        save_data()
        bot.send_message(target, f"✅ {amt} ብር አካውንትዎ ላይ ተጨምሯል። አሁን 'ሰሌዳ ምረጥ' በማለት መጫወት ይችላሉ።")
        bot.send_message(message.chat.id, "✅ ተጠናቋል።")
    except: bot.send_message(message.chat.id, "❌ ስህተት! ቁጥር ብቻ ይጻፉ።")

def process_cash_reg(message):
    try:
        parts = message.text.split(' ', 1)
        bid_num, name = parts, parts
        bid, num = bid_num.split('-')
        if bid in data["boards"]:
            data["boards"][bid]["slots"][num] = name
            save_data()
            update_group_board(bid)
            bot.send_message(message.chat.id, f"✅ ሰሌዳ {bid} ቁጥር {num} ለ {name} ተመዝግቧል።")
    except: bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍዎን ያስተካክሉ (1-05 አበበ)")

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    while True:
        try: bot.polling(none_stop=True, interval=1, timeout=20)
        except: time.sleep(5)
