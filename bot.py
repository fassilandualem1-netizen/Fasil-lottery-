import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time

# --- 1. Render Health Check (ሰርቨሩ እንዳይተኛ) ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Bingo is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት መረጃዎች (አረጋግጥ!) ---
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
ADMIN_ID = 8488592165 
GROUP_ID = -1003881429974
DB_CHANNEL_ID = -1003747262103

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- 3. ዳታቤዝ አያያዝ ---
DB_FILE = "fasil_db.json"
data = {
    "users": {},
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "1,000", "active": True, "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "2,500", "active": True, "slots": {}},
        "3": {"max": 100, "price": 200, "prize": "5,000", "active": True, "slots": {}}
    },
    "pinned_msgs": {"1": None, "2": None, "3": None}
}

def save_data():
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f)
        # ዳታውን ወደ ቻናል መላክ (Backup)
        with open(DB_FILE, "rb") as f:
            bot.send_document(DB_CHANNEL_ID, f, caption=f"🔄 Database Backup - {time.ctime()}")
    except: pass

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        try:
            loaded = json.load(f)
            data.update(loaded)
        except: pass

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

# --- 4. የሰሌዳ ማሳያ (ግሩፕ ላይ) ---
def update_group_board(b_id):
    board = data["boards"][b_id]
    text = f"🎰 <b>FASIL BINGO - ሰሌዳ {b_id} (1-{board['max']})</b>\n"
    text += f"🎫 መደብ፦ <b>{board['price']} ብር</b> | 🎁 ሽልማት፦ <b>{board['prize']} ብር</b>\n"
    text += f"━━━━━━━━━━━━━━━\n"
    
    line = ""
    for i in range(1, board["max"] + 1):
        s_i = str(i)
        if s_i in board["slots"]:
            u_name = board["slots"][s_i]
            short = (u_name[:5] + "..") if len(u_name) > 5 else u_name
            line += f"({s_i})🔴{short} "
        else:
            line += f"({s_i})⬜️ "
        if i % 3 == 0:
            text += line + "\n"
            line = ""
    text += line

    try:
        if data["pinned_msgs"].get(b_id):
            bot.edit_message_text(text, GROUP_ID, data["pinned_msgs"][b_id])
        else:
            m = bot.send_message(GROUP_ID, text)
            bot.pin_chat_message(GROUP_ID, m.message_id)
            data["pinned_msgs"][b_id] = m.message_id
            save_data()
    except:
        m = bot.send_message(GROUP_ID, text)
        bot.pin_chat_message(GROUP_ID, m.message_id)
        data["pinned_msgs"][b_id] = m.message_id
        save_data()

# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    
    # ሰሌዳ እንዲመርጡ እና ፕሮፋይል እንዲያዩ የሚያደርጉ ቁልፎች
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    if int(uid) == ADMIN_ID:
        markup.add("⚙️ Admin Settings")
    
    # አንተ የፈለግከው የSTART መልዕክት ዲዛይን
    welcome_text = (
        f"👋 <b>እንኳን ወደ ፋሲል ዕጣ ደህና መጡ!</b>\n\n"
        f"👤 <b>ስም፦</b> {user['name']}\n"
        f"💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🏦 <b>Telebirr:</b> <code>0951381356</code>\n"
        f"🔸 <b>CBE:</b> <code>1000584461757</code>\n\n"
        f"⚠️ <b>ብር ሲያስገቡ የደረሰኙን ፎቶ ወይም መልዕክት እዚህ ይላኩ።</b>"
    )
    
    bot.send_message(uid, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} | 🎫 {b_info['price']} ብር", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "<b>ሰሌዳ ይምረጡ፦</b>", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 <b>ፕሮፋይል</b>\n📛 ስም፦ {user['name']}\n💰 ቀሪ፦ {user['wallet']} ብር")

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("⚙️ ሰሌዳዎችን አስተካክል", callback_data="admin_manage"),
               types.InlineKeyboardButton("🔄 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset"))
    bot.send_message(ADMIN_ID, "🛠 <b>የአድሚን መቆጣጠሪያ</b>", reply_markup=markup)

# --- 6. የደረሰኝ መቀበያ ---
@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    uid = str(message.chat.id)
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings"]: return

    bot.send_message(uid, "⏳ <b>ደረሰኝዎ ለባለቤቱ ተልኳል...</b>\nእባክዎ እስኪረጋገጥ ይጠብቁ። 🙏")
    
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    
    cap = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 <b>ከ፦</b> {message.from_user.first_name}\n🆔 <b>ID፦</b> <code>{uid}</code>"
    if message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=cap, reply_markup=markup)
    else:
        bot.send_message(ADMIN_ID, f"{cap}\n📝 <b>ዝርዝር፦</b>\n<code>{message.text}</code>", reply_markup=markup)

# --- 7. Callback Listener ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    if call.data.startswith('approve_'):
        target = call.data.split('_')[1]
        m = bot.send_message(ADMIN_ID, f"💵 ለ ID {target} የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_app, target)
    elif call.data.startswith('decline_'):
        target = call.data.split('_')[1]
        m = bot.send_message(ADMIN_ID, "❌ ውድቅ የተደረገበትን ምክንያት ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_dec, target)
    elif call.data.startswith('select_'): handle_selection(call)
    elif call.data == "admin_manage": manage_menu(call)
    elif call.data.startswith('edit_'): edit_board(call)
    elif call.data.startswith('toggle_'):
        bid = call.data.split('_')[1]
        data["boards"][bid]["active"] = not data["boards"][bid]["active"]
        save_data(); edit_board(call)
    elif call.data == "admin_reset": reset_menu(call)
    elif call.data.startswith('doreset_'):
        bid = call.data.split('_')[1]
        data["boards"][bid]["slots"] = {}; data["pinned_msgs"][bid] = None
        save_data(); bot.answer_callback_query(call.id, "ጸድቷል!"); update_group_board(bid)

def finalize_app(message, target):
    try:
        amt = int(message.text)
        user = get_user(target)
        user["wallet"] += amt
        save_data()
        bot.send_message(target, f"✅ <b>{amt} ብር ተጨምሯል!</b>")
        m = bot.send_message(target, "አሁን በሰሌዳ ላይ የሚወጣውን ስምዎን ይጻፉ፦")
        bot.register_next_step_handler(m, save_name, target)
    except: bot.send_message(ADMIN_ID, "⚠️ ቁጥር ብቻ ይጻፉ!")

def save_name(message, uid):
    data["users"][str(uid)]["name"] = message.text
    save_data(); bot.send_message(uid, "✅ ስምዎ ተመዝግቧል!")

def finalize_dec(message, target):
    bot.send_message(target, f"❌ ደረሰኝዎ ውድቅ ሆኗል። ምክንያት፦ {message.text}")

def handle_selection(call):
    bid = call.data.split('_')[1]
    user = get_user(call.message.chat.id)
    board = data["boards"][bid]
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True)
        return
    m = bot.send_message(call.message.chat.id, f"🔢 ከ 1-{board['max']} ቁጥር ይጻፉ፦")
    bot.register_next_step_handler(m, finalize_reg, bid, user["name"])

def finalize_reg(message, bid, name):
    uid = str(message.chat.id)
    try:
        num = str(int(message.text))
        board = data["boards"][bid]
        if num in board["slots"] or int(num) < 1 or int(num) > board["max"]:
            bot.send_message(uid, "❌ ቁጥሩ ተይዟል ወይም ስህተት ነው።")
            return
        data["users"][uid]["wallet"] -= board["price"]
        board["slots"][num] = name
        save_data(); bot.send_message(uid, f"✅ ተመዝግበዋል! ቁጥር፦ {num}")
        update_group_board(bid)
    except: bot.send_message(uid, "⚠️ ቁጥር ብቻ ይጻፉ!")

# --- 8. Admin Helpers ---
def manage_menu(call):
    markup = types.InlineKeyboardMarkup()
    for bid in data["boards"]: markup.add(types.InlineKeyboardButton(f"ሰሌዳ {bid}", callback_data=f"edit_{bid}"))
    bot.edit_message_text("ሰሌዳ ይምረጡ፦", ADMIN_ID, call.message.message_id, reply_markup=markup)

def edit_board(call):
    bid = call.data.split('_')[1]; b = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🔴/🟢 Toggle", callback_data=f"toggle_{bid}"),
               types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
    bot.edit_message_text(f"📊 ሰሌዳ {bid}\nሁኔታ፦ {'🟢 ክፍት' if b['active'] else '🔴 ዝግ'}", ADMIN_ID, call.message.message_id, reply_markup=markup)

def reset_menu(call):
    markup = types.InlineKeyboardMarkup()
    for bid in data["boards"]: markup.add(types.InlineKeyboardButton(f"Reset {bid}", callback_data=f"doreset_{bid}"))
    bot.send_message(ADMIN_ID, "የትኛው ይጽዳ?", reply_markup=markup)

if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    while True:
        try: bot.polling(none_stop=True, interval=0, timeout=20)
        except: time.sleep(5)
