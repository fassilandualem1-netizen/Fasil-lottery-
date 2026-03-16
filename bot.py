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
data = {
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
        except: pass

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

# --- 4. ግሩፕ አፕዴት ---
def update_group_board(b_id):
    board = data["boards"][b_id]
    text = f"🎰 <b>FASIL BINGO - ሰሌዳ {b_id} (1-{board['max']})</b>\n🎁 ሽልማት፦ <b>{board['prize']} ብር</b>\n💰 የቦታ ዋጋ፦ <b>{board['price']} ብር</b>\n━━━━━━━━━━━━━━━\n"
    line = ""
    for i in range(1, board["max"] + 1):
        s_i = str(i)
        if s_i in board["slots"]:
            short_name = (board["slots"][s_i][:5]) + ".." if len(board["slots"][s_i]) > 5 else board["slots"][s_i]
            line += f"({s_i})🔴{short_name}  "
        else:
            line += f"({s_i})⬜️  "
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
    except: pass

# --- 5. START & PROFILE ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    welcome_text = f"👋 <b>እንኳን ደህና መጡ {message.from_user.first_name}!</b>\n💰 ቀሪ ሂሳብ፦ <b>{user['wallet']} ብር</b>"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    if int(uid) == ADMIN_ID: markup.add("⚙️ Admin Settings")
    bot.send_message(uid, welcome_text, reply_markup=markup, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 <b>የእርስዎ ፕሮፋይል</b>\n💰 ቀሪ ሂሳብ፦ <b>{user['wallet']} ብር</b>", parse_mode="HTML")

# --- 6. ደረሰኝ መቀበያ ---
@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    uid = str(message.chat.id)
    if int(uid) == ADMIN_ID or message.text in ["/start", "🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings"]: return
    bot.send_message(uid, "⏳ <b>ደረሰኝዎ ተልኳል፤ እስኪረጋገጥ ይጠብቁ።</b>")
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    cap = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 ከ፦ {message.from_user.first_name}\n🆔 ID፦ <code>{uid}</code>"
    if message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=cap, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(ADMIN_ID, f"{cap}\n📝 <b>ዝርዝር፦</b>\n{message.text}", reply_markup=markup, parse_mode="HTML")

# --- 7. CALLBACK LISTENERS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    if call.data.startswith('approve_'):
        t_uid = call.data.split('_')[1]
        msg = bot.send_message(ADMIN_ID, f"💵 ለ ID {t_uid} የሚጨመር ብር ይጻፉ፦")
        bot.register_next_step_handler(msg, finalize_approval, t_uid)
    elif call.data.startswith('decline_'):
        t_uid = call.data.split('_')[1]
        msg = bot.send_message(ADMIN_ID, "❌ ምክንያቱን ይጻፉ፦")
        bot.register_next_step_handler(msg, finalize_decline, t_uid)
    elif call.data.startswith('select_'):
        handle_board_selection(call)
    elif call.data == "admin_manage":
        manage_boards_menu(call)
    elif call.data == "admin_reset_menu":
        reset_menu(call)
    elif call.data.startswith('edit_'):
        edit_board(call)
    elif call.data.startswith('toggle_'):
        b_id = call.data.split('_')[1]
        data["boards"][b_id]["active"] = not data["boards"][b_id]["active"]
        save_data(); edit_board(call)
    elif call.data.startswith('set_'):
        field, b_id = call.data.split('_')[1], call.data.split('_')[2]
        msg = bot.send_message(ADMIN_ID, f"አዲሱን {'ዋጋ' if field=='price' else 'ሽልማት'} ይጻፉ፦")
        bot.register_next_step_handler(msg, update_value, b_id, field)
    elif call.data.startswith('doreset_'):
        b_id = call.data.split('_')[1]
        data["boards"][b_id]["slots"] = {}; data["pinned_msgs"][b_id] = None
        save_data(); bot.answer_callback_query(call.id, "ተጸድቷል!"); update_group_board(b_id)

def finalize_approval(message, t_uid):
    try:
        amt = int(message.text)
        data["users"][str(t_uid)]["wallet"] += amt
        save_data()
        bot.send_message(t_uid, f"✅ <b>{amt}</b> ብር ተጨምሮልዎታል።")
        bot.send_message(ADMIN_ID, "✅ ተፈጽሟል።")
    except: bot.send_message(ADMIN_ID, "⚠️ ቁጥር ብቻ!")

def finalize_decline(message, t_uid):
    bot.send_message(t_uid, f"❌ ደረሰኝዎ ውድቅ ሆኗል።\nምክንያት፦ {message.text}")
    bot.send_message(ADMIN_ID, "❌ ተልኳል።")

# --- 8. ምዝገባ ---
@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} | {b_info['price']} ብር", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "ሰሌዳ ይምረጡ፦", reply_markup=markup)

def handle_board_selection(call):
    b_id = call.data.split('_')[1]
    user = get_user(call.message.chat.id)
    if user["wallet"] < data["boards"][b_id]["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ብር የለም!", show_alert=True)
        return
    msg = bot.send_message(call.message.chat.id, "👤 ስም ይጻፉ፦")
    bot.register_next_step_handler(msg, get_reg_name, b_id)

def get_reg_name(message, b_id):
    name = message.text
    msg = bot.send_message(message.chat.id, f"🔢 ቁጥር (1-{data['boards'][b_id]['max']}) ይጻፉ፦")
    bot.register_next_step_handler(msg, finalize_registration, b_id, name)

def finalize_registration(message, b_id, name):
    uid = str(message.chat.id)
    try:
        num = str(int(message.text))
        board = data["boards"][b_id]
        if num in board["slots"]:
            bot.send_message(uid, "❌ ተይዟል!")
            return
        data["users"][uid]["wallet"] -= board["price"]
        board["slots"][num] = name
        save_data()
        bot.send_message(uid, "✅ ተመዝግበዋል!")
        update_group_board(b_id)
    except: bot.send_message(uid, "⚠️ ቁጥር ብቻ!")

# --- 9. ADMIN SETTINGS (COMPLETE) ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.chat.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("⚙️ ሰሌዳዎችን ማስተካከያ", callback_data="admin_manage"),
               types.InlineKeyboardButton("🔄 ሰሌዳ ማጽጃ (Reset)", callback_data="admin_reset_menu"))
    bot.send_message(ADMIN_ID, "🛠 <b>የአድሚን ፓነል</b>", reply_markup=markup, parse_mode="HTML")

def manage_boards_menu(call):
    markup = types.InlineKeyboardMarkup()
    for b_id in data["boards"]:
        status = "🟢" if data["boards"][b_id]["active"] else "🔴"
        markup.add(types.InlineKeyboardButton(f"ሰሌዳ {b_id} {status}", callback_data=f"edit_{b_id}"))
    bot.edit_message_text("ለማስተካከል ይምረጡ፦", ADMIN_ID, call.message.message_id, reply_markup=markup)

def edit_board(call):
    b_id = call.data.split('_')[1]
    b = data["boards"][b_id]
    markup = types.InlineKeyboardMarkup(row_width=2)
    t_text = "🔴 ዝጋ" if b["active"] else "🟢 ክፈት"
    markup.add(types.InlineKeyboardButton(t_text, callback_data=f"toggle_{b_id}"),
               types.InlineKeyboardButton("💰 ዋጋ ቀይር", callback_data=f"set_price_{b_id}"),
               types.InlineKeyboardButton("🎁 ሽልማት ቀይር", callback_data=f"set_prize_{b_id}"),
               types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
    bot.edit_message_text(f"📊 <b>ሰሌዳ {b_id}</b>\n💰 ዋጋ፦ {b['price']}\n🎁 ሽልማት፦ {b['prize']}", ADMIN_ID, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def update_value(message, b_id, field):
    try:
        data["boards"][b_id][field] = message.text
        save_data()
        bot.send_message(ADMIN_ID, f"✅ ሰሌዳ {b_id} {field} ተቀይሯል።")
        update_group_board(b_id)
    except: bot.send_message(ADMIN_ID, "⚠️ ስህተት!")

def reset_menu(call):
    markup = types.InlineKeyboardMarkup()
    for b_id in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"Reset ሰሌዳ {b_id}", callback_data=f"doreset_{b_id}"))
    bot.send_message(ADMIN_ID, "የትኛው ይጽዳ?", reply_markup=markup)

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling()
