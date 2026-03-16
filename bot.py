import telebot
from telebot import types, apihelper
import json
import os
from flask import Flask
from threading import Thread

# --- 1. Render እንዳይዘጋው ፖርት የሚከፍት ሲስተም ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Bot is Alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. የቦቱ መረጃዎች ---
TOKEN = "8721334129:AAGZxYXP4UH0RuEdC8gk6icXu5gSB26bI3Q"
ADMIN_ID = 8488592165
GROUP_ID = -1003881429974
DB_CHANNEL_ID = -1003747262103

# ቦቱ በፍጥነት እንዲሰራ (Threaded) እናደርገዋለን
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=True, num_threads=4)

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
            bot.send_document(DB_CHANNEL_ID, f, caption="🔄 Backup")
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

# --- 4. START COMMAND ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    get_user(uid, message.from_user.first_name)
    
    welcome_text = (
        "🎰 <b>እንኳን ወደ FASIL ዕጣ በሰላም መጡ!</b> 🎰\n\n"
        "ታማኝነት መለያችን ነው! የእርስዎን ዕድል ይሞክሩ።\n\n"
        "💳 <b>አካውንቶች፡</b>\n"
        "🔸 ቴሌብር፡ <code>951381356</code> (Fasil)\n"
        "🔸 CBE: <code>1000584461757</code> (Fasil)\n\n"
        "⚠️ <i>ክፍያ ከፈጸሙ በኋላ ደረሰኙን እዚህ ይላኩ።</i>"
    )
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    if int(uid) == ADMIN_ID: markup.add("⚙️ Admin Settings")
    bot.send_message(uid, welcome_text, reply_markup=markup)

# --- 5. ደረሰኝ መቀበያ ---
@bot.message_handler(content_types=['photo', 'text'], func=lambda m: m.text not in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings"])
def handle_receipts(message):
    uid = str(message.chat.id)
    if int(uid) == ADMIN_ID: return

    bot.send_message(uid, "⏳ <b>ደረሰኝዎ እየተረጋገጠ ነው...</b>")
    
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
                     types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    
    caption = f"📩 <b>አዲስ ደረሰኝ</b>\nከ፡ {message.from_user.first_name}\nID: <code>{uid}</code>"
    if message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=admin_markup)
    else:
        bot.send_message(ADMIN_ID, f"{caption}\n\nጽሁፍ፦ {message.text}", reply_markup=admin_markup)

# --- 6. አድሚን ውሳኔ (CALLBACK) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    if call.data.startswith('select_'):
        handle_board_selection(call)
    elif call.data.startswith('approve_'):
        target_uid = call.data.split('_')[1]
        msg = bot.send_message(ADMIN_ID, f"💵 ለ ID {target_uid} የሚገባውን ብር ይጻፉ (ቁጥር ብቻ):")
        bot.register_next_step_handler(msg, finalize_approval, target_uid)
    elif call.data.startswith('decline_'):
        target_uid = call.data.split('_')[1]
        msg = bot.send_message(ADMIN_ID, "❌ ውድቅ የሆነበትን ምክንያት ይጻፉ:")
        bot.register_next_step_handler(msg, finalize_decline, target_uid)
    elif call.data == "admin_reset":
        reset_menu(call)
    elif call.data.startswith('doreset_'):
        perform_reset(call)

def finalize_approval(message, target_uid):
    try:
        amount = int(message.text)
        data["users"][target_uid]["wallet"] += amount
        save_data()
        bot.send_message(target_uid, f"✅ <b>ክፍያዎ ተረጋግጧል!</b>\n{amount} ብር ዋሌትዎ ላይ ተጨምሯል።")
        bot.send_message(ADMIN_ID, "✅ ተፈጽሟል።")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ስህተት (ቁጥር ብቻ ያስገቡ)።")

def finalize_decline(message, target_uid):
    bot.send_message(target_uid, f"❌ ደረሰኝዎ ውድቅ ሆኗል። ምክንያት፦ {message.text}")
    bot.send_message(ADMIN_ID, "❌ ውድቅ ተደርጓል።")

# --- 7. ሰሌዳ እና ምዝገባ ---
@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        markup.add(types.InlineKeyboardButton(f"ሰሌዳ {b_id} ({b_info['price']} ብር)", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "ሰሌዳ ይምረጡ፦", reply_markup=markup)

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
    
    bot.send_message(uid, f"✅ ክፍት ቁጥሮች፦ {', '.join(map(str, available[:30]))}...\n\nእባክዎ ስምዎን ይጻፉ፦")
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
        if num in board["slots"]:
            bot.send_message(uid, "❌ ቁጥሩ ተይዟል።")
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
    text = f"🎰 <b>ሰሌዳ {b_id}</b>\n━━━━━━━━━━━━━━━\n"
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
    except: pass

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Reset Board", callback_data="admin_reset"))
    bot.send_message(ADMIN_ID, "Admin Menu:", reply_markup=markup)

def reset_menu(call):
    markup = types.InlineKeyboardMarkup()
    for b in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"Reset {b}", callback_data=f"doreset_{b}"))
    bot.edit_message_text("የትኛው ይጽዳ?", ADMIN_ID, call.message.message_id, reply_markup=markup)

def perform_reset(call):
    b_id = call.data.split('_')[1]
    data["boards"][b_id]["slots"] = {}
    save_data()
    bot.answer_callback_query(call.id, "ተጠርጓል!")
    update_group_board(b_id)

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 <b>ስም፦</b> {message.from_user.first_name}\n💰 <b>ዋሌት፦</b> {user['wallet']} ብር")

# --- 8. ማስጀመሪያ (Conflict መከላከያ) ---
if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.remove_webhook()
    # Conflict 409 ን ለዘላለም ለመከላከል:
    bot.polling(none_stop=True, skip_pending_updates=True, timeout=120)
