import telebot
from telebot import types
import os
from flask import Flask
from threading import Thread
import time
from supabase import create_client, Client

# --- 1. Web Hosting (Railway/Render) ---
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

# --- 2. ቦት እና Supabase መረጃዎች ---
# በ Railway Variables ውስጥ ማስገባትህን እርግጠኛ ሁን
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "የእርስዎ_URL_እዚህ")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "የእርስዎ_KEY_እዚህ")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003881429974
ADMIN_IDS = [MY_ID, ASSISTANT_ID]

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323"}
}

# ጨዋታው በሰርቨሩ ሚሞሪ ላይ ይቆያል (ለፍጥነት)
data = {
    "current_shift": "me",
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "1ኛ 200, 2ኛ 100, 3ኛ 50", "active": True, "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "1ኛ 400, 2ኛ 200, 3ኛ 100", "active": True, "slots": {}},
        "3": {"max": 100, "price": 200, "prize": "1ኛ 800, 2ኛ 400, 3ኛ 200", "active": True, "slots": {}}
    },
    "pinned_msgs": {"1": None, "2": None, "3": None}
}

# --- 3. Supabase Database Helpers ---

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    try:
        res = supabase.table("users").select("*").eq("user_id", uid).execute()
        if not res.data:
            user_data = {"user_id": uid, "name": name[:5], "wallet": 0}
            supabase.table("users").insert(user_data).execute()
            return user_data
        return res.data
    except:
        return {"user_id": uid, "name": name[:5], "wallet": 0}

def update_wallet(uid, amount):
    user = get_user(uid)
    new_bal = user['wallet'] + amount
    supabase.table("users").update({"wallet": new_bal}).eq("user_id", str(uid)).execute()
    return new_bal

def update_name(uid, new_name):
    supabase.table("users").update({"name": new_name[:5]}).eq("user_id", str(uid)).execute()

# --- 4. ቦት ፋንክሽኖች ---

def main_menu_markup(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS: markup.add("⚙️ Admin Settings")
    return markup

def update_group_board(b_id):
    board = data["boards"][b_id]
    text = f"🎰 <b>ፋሲል ዕጣ - ሰሌዳ {b_id} (1-{board['max']})</b>\n"
    text += f"🎫 መደብ፦ <b>{board['price']} ብር</b>\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━\n"
    line = ""
    for i in range(1, board["max"] + 1):
        s_i = str(i).zfill(2)
        if str(i) in board["slots"]:
            u_name = board["slots"][str(i)]
            line += f"<code>{s_i}</code>🔴{u_name[:5]}\t"
        else:
            line += f"<code>{s_i}</code>⬜️\t\t"
        if i % 3 == 0:
            text += line + "\n"
            line = ""
    text += line + "\n━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🎁 <b>ሽልማት፦ {board['prize']}</b>\n"
    text += f"🤖 ለመጫወት፦ @{bot.get_me().username}"
    try:
        m_id = data["pinned_msgs"].get(b_id)
        if m_id: bot.edit_message_text(text, GROUP_ID, m_id)
        else:
            m = bot.send_message(GROUP_ID, text)
            bot.pin_chat_message(GROUP_ID, m.message_id)
            data["pinned_msgs"][b_id] = m.message_id
    except:
        m = bot.send_message(GROUP_ID, text)
        data["pinned_msgs"][b_id] = m.message_id

@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    active_pay = PAYMENTS[data["current_shift"]]
    msg = (f"👋 <b>እንኳን መጡ!</b>\n👤 ስም፦ {user['name']}\n💰 ቀሪ፦ {user['wallet']} ብር\n"
           f"━━━━━━━━━━━━━━━━━━━━━\n🏦 Tele: <code>{active_pay['tele']}</code>\n"
           f"🔸 CBE: <code>{active_pay['cbe']}</code>")
    bot.send_message(uid, msg, reply_markup=main_menu_markup(uid))

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 <b>ፕሮፋይል</b>\n📛 ስም፦ {user['name']}\n💰 ቀሪ፦ {user['wallet']} ብር")

@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    if message.chat.type != 'private': return
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings", "🎫 የያዝኳቸው ቁጥሮች"]: return
    bot.send_message(message.chat.id, "⏳ ደረሰኝዎ እየታየ ነው...")
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{message.chat.id}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{message.chat.id}"))
    cap = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 {message.from_user.first_name}\n🆔 <code>{message.chat.id}</code>"
    for adm in ADMIN_IDS:
        if message.photo: bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup)
        else: bot.send_message(adm, f"{cap}\n📝 {message.text}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    if call.data.startswith('approve_') and is_admin:
        target = call.data.split('_')
        m = bot.send_message(call.from_user.id, f"💵 ለ ID {target} የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_app, target)
    elif call.data.startswith('select_'):
        handle_selection(call)
    elif call.data.startswith('pick_'):
        _, bid, num = call.data.split('_')
        finalize_reg_inline(call, bid, num)

def finalize_app(message, target):
    try:
        amt = int(message.text)
        update_wallet(target, amt)
        bot.send_message(target, f"✅ {amt} ብር ተጨምሯል!")
        m = bot.send_message(target, "በሰሌዳ ላይ የሚወጣውን ስምዎን ይጻፉ፦")
        bot.register_next_step_handler(m, save_name, target)
    except: bot.send_message(message.chat.id, "❌ ቁጥር ብቻ!")

def save_name(message, uid):
    update_name(uid, message.text)
    bot.send_message(uid, f"✅ ስምዎ '{message.text[:5]}' ተብሎ ተመዝግቧል!")

def handle_selection(call):
    bid = call.data.split('_')
    user = get_user(call.message.chat.id)
    board = data["boards"][bid]
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True); return
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}") 
            for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
    markup.add(*btns)
    bot.edit_message_text(f"🎰 ሰሌዳ {bid}\n💰 ቀሪ፦ {user['wallet']} ብር\nቁጥር ይምረጡ፦", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup)

def finalize_reg_inline(call, bid, num):
    uid = str(call.message.chat.id); user = get_user(uid); board = data["boards"][bid]
    if user["wallet"] < board["price"]: return
    update_wallet(uid, -board["price"])
    board["slots"][num] = user["name"]
    update_group_board(bid)
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተይዟል!")
    new_user = get_user(uid)
    if new_user["wallet"] >= board["price"]: handle_selection(call)
    else: bot.edit_message_text(f"✅ ተጠናቋል! ቀሪ፦ {new_user['wallet']} ብር", uid, call.message.message_id)

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
