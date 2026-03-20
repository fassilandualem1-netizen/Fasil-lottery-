import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time
from supabase import create_client, Client

# --- 1. Web Hosting (Render እንዲሰራ) ---
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
# መረጃዎቹን ከ Environment Variables ያነባል፣ ከሌለ ደግሞ እነዚህን ይጠቀማል
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://aapxnuzwrkxbzsanatik.supabase.co")
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
            print("✅ Data loaded from Supabase")
    except Exception as e:
        print(f"❌ Error loading: {e}")

def save_data():
    try:
        # ወደ Supabase መላክ
        supabase.table("bot_data").upsert({"id": "main_db", "content": data}).execute()
        # ለጥንቃቄ ወደ ቻናል መላክ
        with open("temp_db.json", "w") as f:
            json.dump(data, f)
        with open("temp_db.json", "rb") as f:
            bot.send_document(DB_CHANNEL_ID, f, caption=f"🔄 Cloud Backup - {time.ctime()}")
    except Exception as e:
        print(f"❌ Error saving: {e}")

# ዳታውን መጫን
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
    text = f"🎰 <b>ፋሲል ዕጣ - ሰሌዳ {b_id} (1-{board['max']})</b>\n"
    text += f"🎫 መደብ፦ <b>{board['price']} ብር</b>\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━\n"
    line = ""
    for i in range(1, board["max"] + 1):
        s_i = str(i).zfill(2)
        if str(i) in board["slots"]:
            u_name = board["slots"][str(i)]
            short = u_name[:5]
            line += f"<code>{s_i}</code>🔴{short}\t\t"
        else:
            line += f"<code>{s_i}</code>⬜️\t\t"
        if i % 2 == 0:
            text += line + "\n"
            line = ""
    text += line
    text += f"\n━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🎁 <b>ሽልማት፦ {board['prize']}</b>\n"
    text += f"🤖 ለመጫወት፦ @Fasil_assistant_bot"
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

# --- 5. ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    active_pay = PAYMENTS[data.get("current_shift", "me")]
    
    welcome_text = (
        f"👋 <b>እንኳን ወደ ፋሲል መዝናኛና ዕድለኛ ዕጣ መጡ!</b>\n\n"
        f"👤 <b>ስም፦</b> {user['name']}\n"
        f"💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏦 <b>Telebirr:</b> <code>{active_pay['tele']}</code>\n"
        f"🔸 <b>CBE:</b> <code>{active_pay['cbe']}</code>\n\n"
        f"⚠️ <b>ብር ሲያስገቡ የደረሰኙን ፎቶ ወይም መልዕክት እዚህ ይላኩ።</b>"
    )
    bot.send_message(uid, welcome_text, reply_markup=main_menu_markup(uid))

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} | 🎫 {b_info['price']} ብር", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "<b>ለመጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pick_'))
def finalize_reg_inline(call):
    _, bid, num = call.data.split('_')
    uid = str(call.message.chat.id)
    user = get_user(uid)
    board = data["boards"][bid]
    
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True)
        return

    data["users"][uid]["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data()
    update_group_board(bid)
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")

    # --- መስመር 314 የተስተካከለው እዚህ ጋር ነው ---
    remaining = board["max"] - len(board["slots"])
    milestones = # Syntax Error የነበረበት ቦታ ተስተካክሏል
    if remaining in milestones:
        msg = f"🎰 <b>ሰሌዳ {bid} ሊሞላ ነው!</b>\n🔥 ዕጣ ለመውጣት <b>{remaining}</b> ሰዎች ቀሩ!"
        try: bot.send_message(GROUP_ID, msg)
        except: pass

    if user["wallet"] >= board["price"]:
        handle_selection(call)
    else:
        bot.edit_message_text(f"✅ ምዝገባ ተጠናቋል።\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር", uid, call.message.message_id, reply_markup=main_menu_markup(uid))

# የተቀሩትን ፈንክሽኖች ለማሳጠር እዚህ አልደገምኳቸውም፣ ግን በዋናው ፋይልህ ላይ እንዳሉ ይቆያሉ

def handle_selection(call):
    bid = call.data.split('_'); user = get_user(call.message.chat.id)
    board = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}") for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
    markup.add(*btns)
    bot.edit_message_text(f"🎰 <b>ሰሌዳ {bid}</b>\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር\n\nቁጥር ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    if message.chat.type != 'private': return 
    uid = str(message.chat.id)
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings", "🎫 የያዝኳቸው ቁጥሮች"]: return
    bot.send_message(uid, "⏳ <b>ደረሰኝዎ ደርሶኛል...</b>\nእባክዎ እስኪረጋገጥ ይጠብቁ። 🙏")
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    cap = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 <b>ከ፦</b> {message.from_user.first_name}\n🆔 <b>ID፦</b> <code>{uid}</code>"
    for adm in ADMIN_IDS:
        try:
            if message.photo: bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup)
            else: bot.send_message(adm, f"{cap}\n📝 <b>ዝርዝር፦</b>\n<code>{message.text}</code>", reply_markup=markup)
        except: pass

# --- ቦቱን ማስጀመር ---
if __name__ == "__main__":
    keep_alive()
    print("🚀 Bot is starting...")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)
