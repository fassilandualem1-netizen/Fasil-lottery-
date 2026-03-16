import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time

# --- 1. Render መቆያ (Flask) ---
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

# --- 2. ቦት መረጃዎች ---
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
ADMIN_ID = 8488592165 
GROUP_ID = -1003881429974
DB_CHANNEL_ID = -1003747262103

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- 3. ዳታቤዝ ---
DEFAULT_DATA = {
    "users": {},
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "1,000", "active": True, "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "2,500", "active": True, "slots": {}},
        "3": {"max": 100, "price": 200, "prize": "5,000", "active": True, "slots": {}}
    },
    "pinned_msgs": {"1": None, "2": None, "3": None}
}

DB_FILE = "fasil_db.json"

def save_data():
    with open(DB_FILE, "w") as f:
        json.dump(data, f)
    try:
        with open(DB_FILE, "rb") as f:
            bot.send_document(DB_CHANNEL_ID, f, caption=f"🔄 Backup - {time.ctime()}")
    except: pass

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        try: data = json.load(f)
        except: data = DEFAULT_DATA.copy()
else:
    data = DEFAULT_DATA.copy()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

# --- 4. የሰሌዳ መልክ ማደሻ ---
def update_group_board(b_id):
    board = data["boards"][str(b_id)]
    text = f"🎰 <b>FASIL BINGO - ሰሌዳ {b_id}</b>\n🎁 ሽልማት፦ <b>{board['prize']} ብር</b>\n━━━━━━━━━━━━━━━\n"
    line = ""
    for i in range(1, board["max"] + 1):
        s_i = str(i)
        if s_i in board["slots"]:
            short_name = (board["slots"][s_i][:5])
            line += f"({s_i})🔴{short_name}  "
        else:
            line += f"({s_i})⬜️  "
        if i % 3 == 0:
            text += line + "\n"
            line = ""
    text += line
    
    try:
        if data["pinned_msgs"].get(str(b_id)):
            bot.edit_message_text(text, GROUP_ID, data["pinned_msgs"][str(b_id)])
        else:
            m = bot.send_message(GROUP_ID, text)
            bot.pin_chat_message(GROUP_ID, m.message_id)
            data["pinned_msgs"][str(b_id)] = m.message_id
            save_data()
    except: pass

# --- 5. ዋና ዋና ትዕዛዞች (Handlers) ---

@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    welcome_text = (
        f"👋 <b>እንኳን ደህና መጡ {message.from_user.first_name}!</b>\n\n"
        f"💰 <b>ቀሪ ሂሳብ፦</b> <b>{user['wallet']} ብር</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🚀 <b>ለመጀመር፦</b>\n"
        "1️⃣ <b>ብር ያስገቡ</b> (ደረሰኝ እዚህ ይላኩ)\n"
        "2️⃣ <b>'🎮 ሰሌዳ ምረጥ'</b> ይጫኑ\n\n"
        "🏦 <b>Telebirr:</b> <code>951381356</code>"
    )
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    if int(uid) == ADMIN_ID: markup.add("⚙️ Admin Settings")
    bot.send_message(uid, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            text = f"🎰 ሰሌዳ {b_id} | 🎫 {b_info['price']} ብር"
            markup.add(types.InlineKeyboardButton(text, callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "<b>ሰሌዳ ይምረጡ፦</b>", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 <b>ፕሮፋይል</b>\n💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር")

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("⚙️ ሰሌዳዎችን አስተካክል", callback_data="admin_manage"),
               types.InlineKeyboardButton("🔄 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset"))
    bot.send_message(ADMIN_ID, "🛠 <b>Admin Panel</b>", reply_markup=markup)

# --- 6. ደረሰኝ መቀበያ (ይህ ከላይ ካሉት በታች መሆን አለበት) ---
@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    uid = str(message.chat.id)
    if int(uid) == ADMIN_ID: return
    
    bot.send_message(uid, "⏳ <b>ደረሰኝዎ ተልኳል...</b>\nእባክዎ እስኪረጋገጥ ይጠብቁ። 🙏")
    
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
                     types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    
    caption = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 ከ፦ {message.from_user.first_name}\n🆔 ID፦ <code>{uid}</code>"
    if message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=admin_markup)
    else:
        bot.send_message(ADMIN_ID, f"{caption}\n📝 ዝርዝር፦ {message.text}", reply_markup=admin_markup)

# --- 7. CALLBACKS & FINALIZE ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    if call.data.startswith('approve_'):
        target_uid = call.data.split('_')[1]
        msg = bot.send_message(ADMIN_ID, f"💵 ለ ID {target_uid} የሚጨመረውን <b>ብር ይጻፉ፦</b>")
        bot.register_next_step_handler(msg, finalize_approval, target_uid)
    elif call.data.startswith('decline_'):
        target_uid = call.data.split('_')[1]
        msg = bot.send_message(ADMIN_ID, "❌ <b>ምክንያት ይጻፉ፦</b>")
        bot.register_next_step_handler(msg, finalize_decline, target_uid)
    elif call.data.startswith('select_'):
        handle_board_selection(call)
    elif call.data == "admin_manage":
        manage_boards_menu(call)
    elif call.data.startswith('edit_'):
        edit_specific_board(call)
    elif call.data.startswith('toggle_'):
        b_id = call.data.split('_')[1]
        data["boards"][b_id]["active"] = not data["boards"][b_id]["active"]
        save_data(); edit_specific_board(call)
    elif call.data == "admin_reset":
        reset_list(call)
    elif call.data.startswith('doreset_'):
        b_id = call.data.split('_')[1]
        data["boards"][b_id]["slots"] = {}
        save_data(); bot.answer_callback_query(call.id, "ሰሌዳው ጸድቷል!"); update_group_board(b_id)

def finalize_approval(message, target_uid):
    try:
        amount = int(message.text)
        user = get_user(target_uid)
        user["wallet"] += amount
        save_data()
        bot.send_message(target_uid, f"✅ <b>{amount} ብር</b> ተጨምሯል!")
        bot.send_message(ADMIN_ID, "✅ ተፈጽሟል።")
    except: bot.send_message(ADMIN_ID, "⚠️ ቁጥር ብቻ ይጻፉ!")

def finalize_decline(message, target_uid):
    bot.send_message(target_uid, f"❌ ደረሰኝዎ ውድቅ ሆኗል።\nምክንያት፦ {message.text}")
    bot.send_message(ADMIN_ID, "❌ ውድቅ ተደርጓል።")

def handle_board_selection(call):
    b_id = call.data.split('_')[1]
    uid = str(call.message.chat.id)
    user = get_user(uid)
    board = data["boards"][b_id]
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ብር የለዎትም!", show_alert=True)
        return
    bot.send_message(uid, f"📍 ሰሌዳ {b_id} ተመርጧል።\n<b>የሚወጣ ስም ይጻፉ፦</b>")
    bot.register_next_step_handler(call.message, get_reg_name, b_id)

def get_reg_name(message, b_id):
    name = message.text
    bot.send_message(message.chat.id, f"🔢 ከ 1-{data['boards'][b_id]['max']} ቁጥር ይጻፉ፦")
    bot.register_next_step_handler(message, finalize_registration, b_id, name)

def finalize_registration(message, b_id, name):
    uid = str(message.chat.id)
    try:
        num = str(int(message.text))
        board = data["boards"][b_id]
        if num in board["slots"] or int(num) < 1 or int(num) > board["max"]:
            bot.send_message(uid, "❌ ቁጥሩ ተይዟል ወይም ስህተት ነው።")
            return
        data["users"][uid]["wallet"] -= board["price"]
        board["slots"][num] = name
        save_data()
        bot.send_message(uid, f"✅ ተመዝግበዋል! ቁጥር፦ {num}")
        update_group_board(b_id)
    except: bot.send_message(uid, "⚠️ ቁጥር ብቻ!")

def manage_boards_menu(call):
    markup = types.InlineKeyboardMarkup()
    for b_id in data["boards"]:
        status = "🟢" if data["boards"][b_id]["active"] else "🔴"
        markup.add(types.InlineKeyboardButton(f"ሰሌዳ {b_id} {status}", callback_data=f"edit_{b_id}"))
    bot.edit_message_text("ሰሌዳ ይምረጡ፦", ADMIN_ID, call.message.message_id, reply_markup=markup)

def edit_specific_board(call):
    b_id = call.data.split('_')[1]
    b = data["boards"][b_id]
    markup = types.InlineKeyboardMarkup()
    toggle = "🔴 ዝጋ" if b["active"] else "🟢 ክፈት"
    markup.add(types.InlineKeyboardButton(toggle, callback_data=f"toggle_{b_id}"),
               types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
    bot.edit_message_text(f"📊 ሰሌዳ {b_id}\nሽልማት፦ {b['prize']}\nዋጋ፦ {b['price']}", ADMIN_ID, call.message.message_id, reply_markup=markup)

def reset_list(call):
    markup = types.InlineKeyboardMarkup()
    for b_id in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"Reset {b_id}", callback_data=f"doreset_{b_id}"))
    bot.send_message(ADMIN_ID, "የትኛው ይጽዳ?", reply_markup=markup)

# --- 10. ማስጀመሪያ ---
if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    print("ቦቱ እየሰራ ነው...")
    bot.infinity_polling()
