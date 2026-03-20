import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time
from supabase import create_client, Client

# --- 1. Web Hosting (Render እንዳይዘጋው) ---
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
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
SUPABASE_URL = "https://aapxnuzwrkxbzsanatik.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "EyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFhcHhudXp3cmt4YnpzYW5hdGlrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM5Njg0NDcsImV4cCI6MjA4OTU0NDQ0N30.FdM3KkTBit3b35wK9obuJvPUhetAWGwL_tqM4pgDM0k")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003881429974
DB_CHANNEL_ID = -1003747262103
ADMIN_IDS = [MY_ID, ASSISTANT_ID]

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323"}
}

# --- 3. ዳታቤዝ አያያዝ ---
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

def load_from_supabase():
    global data
    try:
        res = supabase.table("bot_data").select("content").eq("id", "main_db").execute()
        if res.data and res.data['content']:
            data.update(res.data['content'])
    except Exception as e:
        print(f"Load Error: {e}")

def save_data():
    try:
        supabase.table("bot_data").upsert({"id": "main_db", "content": data}).execute()
        with open("temp_db.json", "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Save Error: {e}")

load_from_supabase()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
        save_data()
    return data["users"][uid]

def main_menu_markup(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS: markup.add("⚙️ Admin Settings")
    return markup

# --- 4. የሰሌዳ ዲዛይን ---
def update_group_board(b_id):
    board = data["boards"][b_id]
    text = f"🎰 <b>ፋሲል ዕጣ - ሰሌዳ {b_id}</b>\n🎫 መደብ፦ <b>{board['price']} ብር</b>\n━━━━━━━━━━━━━\n"
    line = ""
    for i in range(1, board["max"] + 1):
        s_i = str(i).zfill(2)
        if str(i) in board["slots"]:
            line += f"<code>{s_i}</code>🔴\t"
        else:
            line += f"<code>{s_i}</code>⬜️\t"
        if i % 4 == 0:
            text += line + "\n"
            line = ""
    text += f"\n━━━━━━━━━━━━━\n🎁 ሽልማት፦ {board['prize']}"
    try:
        if data["pinned_msgs"].get(b_id):
            bot.edit_message_text(text, GROUP_ID, data["pinned_msgs"][b_id])
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
    bot.send_message(uid, f"👋 ሰላም {user['name']}! ሂሳብዎ፦ {user['wallet']} ብር", reply_markup=main_menu_markup(uid))

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup()
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} - {b_info['price']} ብር", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "ሰሌዳ ይምረጡ፦", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def handle_selection(call):
    bid = call.data.split('_')
    user = get_user(call.message.chat.id)
    board = data["boards"][bid]
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True)
        return
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}") for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
    markup.add(*btns)
    bot.edit_message_text(f"🎰 ሰሌዳ {bid} - ቁጥር ይምረጡ", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pick_'))
def finalize_reg(call):
    _, bid, num = call.data.split('_')
    uid = str(call.message.chat.id)
    user = get_user(uid)
    board = data["boards"][bid]
    
    if user["wallet"] >= board["price"]:
        data["users"][uid]["wallet"] -= board["price"]
        board["slots"][num] = user["name"]
        save_data()
        update_group_board(bid)
        
        # --- የተስተካከለው መስመር ---
        remaining = board["max"] - len(board["slots"])
        milestones =
        if remaining in milestones:
            bot.send_message(GROUP_ID, f"🎰 ሰሌዳ {bid} ሊሞላ {remaining} ሰዎች ቀሩ!")
            
        bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተይዟል!")
        bot.send_message(uid, f"✅ ቁጥር {num} ተይዟል! ቀሪ ሂሳብ፦ {data['users'][uid]['wallet']} ብር")
    else:
        bot.answer_callback_query(call.id, "⚠️ ሂሳብዎ አልቋል!")

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 ስም፦ {user['name']}\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር")

@bot.message_handler(content_types=['photo', 'text'])
def receipts(message):
    if message.chat.type != 'private' or message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል"]: return
    for adm in ADMIN_IDS:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{message.chat.id}"))
        bot.send_message(adm, f"📩 ደረሰኝ ከ {message.from_user.first_name} (ID: {message.chat.id})", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def admin_approve(call):
    target = call.data.split('_')
    msg = bot.send_message(call.from_user.id, f"ለ ID {target} የሚጨመረውን ብር ይጻፉ፦")
    bot.register_next_step_handler(msg, lambda m: finalize_add(m, target))

def finalize_add(message, target):
    try:
        amt = int(message.text)
        data["users"][str(target)]["wallet"] += amt
        save_data()
        bot.send_message(target, f"✅ {amt} ብር ተጨምሮልሃል!")
        bot.send_message(message.chat.id, "✅ ተከናውኗል!")
    except: bot.send_message(message.chat.id, "⚠️ ቁጥር ብቻ ይጻፉ!")

# --- ማስጀመሪያ ---
if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            time.sleep(5)
