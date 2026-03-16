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
TOKEN = "8721334129:AAGZxYXP4UH0RuEdC8gk6icXu5gSB26bI3Q"
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

# --- 4. የሰሌዳ መልክ (Grid View) ---
def update_group_board(b_id):
    board = data["boards"][b_id]
    text = f"🎰 <b>FASIL BINGO - ሰሌዳ {b_id} (1-{board['max']})</b>\n🎁 ሽልማት፦ {board['prize']} ብር\n━━━━━━━━━━━━━━━\n"
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
        if data["pinned_msgs"][b_id]:
            bot.edit_message_text(text, GROUP_ID, data["pinned_msgs"][b_id])
        else:
            m = bot.send_message(GROUP_ID, text)
            bot.pin_chat_message(GROUP_ID, m.message_id)
            data["pinned_msgs"][b_id] = m.message_id
            save_data()
    except: pass

# --- 5. START COMMAND ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    get_user(uid, message.from_user.first_name)
    welcome_text = "🎰 <b>FASIL VIP BINGO</b> 🎰\n━━━━━━━━━━━━━━━\nእንኳን በሰላም መጡ!\n\n💳 <b>Telebirr:</b> <code>951381356</code>\n💳 <b>CBE:</b> <code>1000584461757</code>\n\n⚠️ ደረሰኝ እዚህ ይላኩ።"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    if int(uid) == ADMIN_ID: markup.add("⚙️ Admin Settings")
    bot.send_message(uid, welcome_text, reply_markup=markup)

# --- 6. ደረሰኝ መቀበያ ---
@bot.message_handler(content_types=['photo', 'text'], func=lambda m: m.text not in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings", "/start"])
def handle_receipts(message):
    uid = str(message.chat.id)
    if int(uid) == ADMIN_ID: return
    bot.send_message(uid, "⏳ <b>ደረሰኝዎ እየተረጋገጠ ነው...</b>")
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
                     types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    caption = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 ከ፦ {message.from_user.first_name}\n🆔 ID፦ <code>{uid}</code>"
    if message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=admin_markup)
    else:
        bot.send_message(ADMIN_ID, f"{caption}\n\n📝 ጽሁፍ፦\n<code>{message.text}</code>", reply_markup=admin_markup)

# --- 7. CALLBACK LISTENER ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    if call.data.startswith('approve_'):
        target_uid = call.data.split('_')[1]
        msg = bot.send_message(ADMIN_ID, f"💵 ለ ID {target_uid} ብር ይጻፉ፦")
        bot.register_next_step_handler(msg, finalize_approval, target_uid)
    elif call.data.startswith('decline_'):
        target_uid = call.data.split('_')[1]
        msg = bot.send_message(ADMIN_ID, "❌ ምክንያት ይጻፉ፦")
        bot.register_next_step_handler(msg, finalize_decline, target_uid)
    elif call.data == "admin_manage":
        manage_boards_menu(call)
    elif call.data.startswith('edit_'):
        edit_specific_board(call)
    elif call.data.startswith('toggle_'):
        b_id = call.data.split('_')[1]
        data["boards"][b_id]["active"] = not data["boards"][b_id]["active"]
        save_data(); edit_specific_board(call)
    elif call.data.startswith('set_'):
        action, b_id = call.data.split('_')[1], call.data.split('_')[2]
        msg = bot.send_message(ADMIN_ID, f"አዲሱን {'ሽልማት' if action=='prize' else 'ዋጋ'} ይጻፉ፦")
        bot.register_next_step_handler(msg, update_value, b_id, action)
    elif call.data == "admin_reset":
        reset_list(call)
    elif call.data.startswith('doreset_'):
        b_id = call.data.split('_')[1]
        data["boards"][b_id]["slots"] = {}; data["pinned_msgs"][b_id] = None
        save_data(); bot.answer_callback_query(call.id, "ሰሌዳ ጸድቷል!"); update_group_board(b_id)
    elif call.data.startswith('select_'):
        handle_board_selection(call)

def finalize_approval(message, target_uid):
    try:
        amount = int(message.text)
        data["users"][target_uid]["wallet"] += amount
        save_data()
        bot.send_message(target_uid, f"✅ <b>ክፍያዎ ተረጋግጧል!</b>\n💰 <b>{amount}</b> ብር ተጨምሯል።")
        bot.send_message(ADMIN_ID, "✅ ተፈጽሟል።")
    except: bot.send_message(ADMIN_ID, "⚠️ ቁጥር ብቻ!")

def finalize_decline(message, target_uid):
    bot.send_message(target_uid, f"❌ ደረሰኝ ውድቅ ሆኗል። ምክንያት፦ {message.text}")
    bot.send_message(ADMIN_ID, "❌ ተደርጓል።")

def update_value(message, b_id, action):
    try:
        val = message.text
        if action == "prize": data["boards"][b_id]["prize"] = val
        else: data["boards"][b_id]["price"] = int(val)
        save_data(); bot.send_message(ADMIN_ID, "✅ ተቀይሯል!")
    except: bot.send_message(ADMIN_ID, "⚠️ ስህተት!")

# --- 8. ምዝገባ ---
@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            text = f"🎰 ሰሌዳ {b_id} (1-{b_info['max']}) | ዋጋ፦ {b_info['price']} ብር"
            markup.add(types.InlineKeyboardButton(text, callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "<b>ለመሳተፍ ሰሌዳ ይምረጡ፦</b>", reply_markup=markup)

def handle_board_selection(call):
    b_id = call.data.split('_')[1]
    uid = str(call.message.chat.id)
    user = get_user(uid)
    board = data["boards"][b_id]
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ ቀሪ ሂሳብዎ በቂ አይደለም!", show_alert=True)
        return
    bot.send_message(uid, f"📍 ሰሌዳ {b_id} ተመርጧል። <b>ስምዎን ይጻፉ፦</b>")
    bot.register_next_step_handler(call.message, get_reg_name, b_id)

def get_reg_name(message, b_id):
    name = message.text
    bot.send_message(message.chat.id, "🔢 <b>ቁጥር ይጻፉ፦</b>")
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
        bot.send_message(uid, f"✅ ተመዝግበዋል! ሰሌዳ {b_id} ቁጥር {num}")
        update_group_board(b_id)
    except: bot.send_message(uid, "⚠️ ቁጥር ብቻ!")

# --- 9. ADMIN PANEL ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("⚙️ ሰሌዳዎችን አስተካክል", callback_data="admin_manage"),
               types.InlineKeyboardButton("🔄 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset"))
    bot.send_message(ADMIN_ID, "🛠 <b>የአድሚን መቆጣጠሪያ፦</b>", reply_markup=markup)

def manage_boards_menu(call):
    markup = types.InlineKeyboardMarkup()
    for b_id in data["boards"]:
        status = "🟢" if data["boards"][b_id]["active"] else "🔴"
        markup.add(types.InlineKeyboardButton(f"ሰሌዳ {b_id} {status}", callback_data=f"edit_{b_id}"))
    bot.edit_message_text("ለማስተካከል ይምረጡ፦", ADMIN_ID, call.message.message_id, reply_markup=markup)

def edit_specific_board(call):
    b_id = call.data.split('_')[1]; b = data["boards"][b_id]
    markup = types.InlineKeyboardMarkup(row_width=2)
    toggle = "🔴 ዝጋ" if b["active"] else "🟢 ክፈት"
    markup.add(types.InlineKeyboardButton(toggle, callback_data=f"toggle_{b_id}"),
               types.InlineKeyboardButton("💰 ሽልማት", callback_data=f"set_prize_{b_id}"),
               types.InlineKeyboardButton("🎫 ዋጋ", callback_data=f"set_price_{b_id}"),
               types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
    bot.edit_message_text(f"ሰሌዳ {b_id}\nሽልማት፦ {b['prize']}\nዋጋ፦ {b['price']}", ADMIN_ID, call.message.message_id, reply_markup=markup)

def reset_list(call):
    markup = types.InlineKeyboardMarkup()
    for b_id in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"Reset ሰሌዳ {b_id}", callback_data=f"doreset_{b_id}"))
    bot.send_message(ADMIN_ID, "የትኛው ይጽዳ?", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 <b>{message.from_user.first_name}</b>\n💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር")

# --- 10. ዋና ማስጀመሪያ ---
if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    time.sleep(1)
    print("Bot is starting...")
    bot.infinity_polling()
