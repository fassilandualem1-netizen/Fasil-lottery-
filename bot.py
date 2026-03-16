import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread

# --- Render እንዳይዘጋ ፖርት የሚከፍት ሲስተም ---
app = Flask('')

@app.route('/')
def home():
    return "Fasil Bot is Alive!"

def run():
    # Render አውቶማቲክ ፖርት ስለሚሰጠው ከ "PORT" ኢንቫይሮመንት እናነባለን
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ዋናው የቦት መረጃ ---
TOKEN = "8721334129:AAGZxYXP4UH0RuEdC8gk6icXu5gSB26bI3Q"
ADMIN_ID = 8488592165
GROUP_ID = -1003881429974
DB_CHANNEL_ID = -1003747262103

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- የዳታ መዋቅር ---
data = {
    "users": {},
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "1000", "active": True, "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "2500", "active": True, "slots": {}},
        "3": {"max": 100, "price": 200, "prize": "5000", "active": True, "slots": {}}
    },
    "pinned_msgs": {"1": None, "2": None, "3": None}
}

DB_FILE = "fasil_db.json"

def save_data():
    with open(DB_FILE, "w") as f:
        json.dump(data, f)
    try:
        with open(DB_FILE, "rb") as f:
            bot.send_document(DB_CHANNEL_ID, f, caption="🔄 Auto Backup")
    except: pass

def load_data():
    global data
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
        except: pass

load_data()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

# --- USER INTERFACE ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    get_user(uid, message.from_user.first_name)
    
    welcome_msg = (
        "🎰 <b>እንኳን ወደ FASIL ዕጣ በሰላም መጡ!</b> 🎰\n\n"
        "ታማኝነት መለያችን ነው! በግልጽነት የእርስዎን ዕድል ይሞክሩ።\n\n"
        "💳 <b>የክፍያ አካውንቶች፡</b>\n"
        "🔸 ቴሌብር፡ <code>951381356</code> (Fasil)\n"
        "🔸 CBE: <code>1000584461757</code> (Fasil)\n\n"
        "⚠️ <i>ክፍያ ከፈጸሙ በኋላ ደረሰኙን (Screenshot ወይም SMS) እዚህ ይላኩ።</i>"
    )
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    if int(uid) == ADMIN_ID:
        markup.add("⚙️ Admin Settings")
    bot.send_message(uid, welcome_msg, reply_markup=markup)

@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    uid = str(message.chat.id)
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings"] or int(uid) == ADMIN_ID:
        return

    bot.send_message(uid, "⏳ <b>ደረሰኝዎ እየተረጋገጠ ነው...</b>\nእባክዎ ከ1-5 ደቂቃ ይታገሱን።")
    
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
                     types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    
    caption = f"📩 <b>አዲስ ደረሰኝ</b>\nከ፡ {message.from_user.first_name}\nID: <code>{uid}</code>"
    if message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=admin_markup)
    else:
        bot.send_message(ADMIN_ID, f"{caption}\n\nየደረሰኝ ጽሁፍ፦\n<code>{message.text}</code>", reply_markup=admin_markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'decline_')))
def admin_decision(call):
    target_uid = call.data.split('_')[1]
    action = call.data.split('_')[0]
    if action == "approve":
        msg = bot.send_message(ADMIN_ID, "💵 ለተጠቃሚው የሚገባውን ብር ይጻፉ (ቁጥር ብቻ):")
        bot.register_next_step_handler(msg, finalize_approval, target_uid)
    else:
        msg = bot.send_message(ADMIN_ID, "❌ ውድቅ የሆነበትን ምክንያት ይጻፉ:")
        bot.register_next_step_handler(msg, finalize_decline, target_uid)

def finalize_approval(message, target_uid):
    try:
        amount = int(message.text)
        data["users"][target_uid]["wallet"] += amount
        save_data()
        bot.send_message(target_uid, f"✅ <b>ክፍያዎ ተረጋግጧል!</b>\n{amount} ብር ዋሌትዎ ላይ ተጨምሯል።")
        bot.send_message(ADMIN_ID, "✅ ተፈጽሟል።")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ስህተት፦ ቁጥር ብቻ ያስገቡ።")

def finalize_decline(message, target_uid):
    bot.send_message(target_uid, f"❌ <b>ደረሰኝዎ ውድቅ ሆኗል።</b>\nምክንያት፦ {message.text}")
    bot.send_message(ADMIN_ID, "❌ ውድቅ ተደርጓል።")

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            markup.add(types.InlineKeyboardButton(f"ሰሌዳ {b_id} ({b_info['price']} ብር)", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "ሰሌዳ ይምረጡ፦", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def handle_board_selection(call):
    b_id = call.data.split('_')[1]
    uid = str(call.message.chat.id)
    user = get_user(uid)
    board = data["boards"][b_id]
    
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ ዋሌትዎ በቂ አይደለም!", show_alert=True)
        return
    
    all_num = set(range(1, board["max"] + 1))
    taken = set(int(n) for n in board["slots"].keys())
    available = sorted(list(all_num - taken))
    
    if not available:
        bot.send_message(uid, "ሰሌዳው ሞልቷል።")
        return
        
    bot.send_message(uid, f"✅ ሰሌዳ {b_id}\nክፍት ቁጥሮች፦ {', '.join(map(str, available))}\n\nእባክዎ ስምዎን ይጻፉ፦")
    bot.register_next_step_handler(call.message, get_reg_name, b_id)

def get_reg_name(message, b_id):
    name = message.text
    bot.send_message(message.chat.id, "የሚፈልጉትን ቁጥር ይጻፉ፦")
    bot.register_next_step_handler(message, finalize_registration, b_id, name)

def finalize_registration(message, b_id, name):
    uid = str(message.chat.id)
    try:
        num = str(int(message.text))
        board = data["boards"][b_id]
        if num in board["slots"] or int(num) < 1 or int(num) > board["max"]:
            bot.send_message(uid, "❌ ቁጥሩ ስህተት ነው ወይም ተይዟል።")
            return
        
        data["users"][uid]["wallet"] -= board["price"]
        board["slots"][num] = name
        save_data()
        bot.send_message(uid, f"✅ ተመዝግበዋል! ቁጥር {num}")
        update_group_board(b_id)
    except:
        bot.send_message(uid, "⚠️ ቁጥር ብቻ ይጻፉ።")

def update_group_board(b_id):
    board = data["boards"][b_id]
    text = f"🎰 <b>ሰሌዳ {b_id} (ዋጋ፦ {board['price']})</b>\n🎁 <b>ሽልማት፦ {board['prize']}</b>\n"
    text += "━━━━━━━━━━━━━━━\n"
    for i in range(1, board["max"] + 1):
        s_i = str(i)
        text += f"{s_i} ✅ {board['slots'][s_i]}\n" if s_i in board["slots"] else f"{s_i} ⬜️ ክፍት\n"
    
    try:
        if data["pinned_msgs"][b_id]:
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

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Reset Board", callback_data="admin_reset"))
    bot.send_message(ADMIN_ID, "Admin Menu:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_reset")
def reset_menu(call):
    markup = types.InlineKeyboardMarkup()
    for b in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"Reset {b}", callback_data=f"doreset_{b}"))
    bot.send_message(ADMIN_ID, "የትኛው ይጽዳ?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('doreset_'))
def perform_reset(call):
    b_id = call.data.split('_')[1]
    data["boards"][b_id]["slots"] = {}
    data["pinned_msgs"][b_id] = None
    save_data()
    bot.send_message(ADMIN_ID, f"ሰሌዳ {b_id} ጸድቷል!")
    update_group_board(b_id)

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 ስም፦ {message.from_user.first_name}\n💰 ዋሌት፦ {user['wallet']} ብር")

# --- ማስጀመሪያ ---
if __name__ == "__main__":
    keep_alive() # Render እንዳይዘጋው
    print("Bot is Starting...")
    bot.remove_webhook()
    bot.polling(none_stop=True, skip_pending_updates=True)
