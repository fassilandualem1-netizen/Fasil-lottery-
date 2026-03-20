import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time
from supabase import create_client, Client

# --- 1. Web Hosting (Railway እንዳይዘጋ) ---
app = Flask('')
@app.route('/')
def home(): return "🔥 Fasil Lotto System is Ultra-Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት እና ዳታቤዝ መረጃዎች ---
TOKEN = "8721334129:AAGEh7OBPVZVmDaSOXTdP5NPy53LH5ap-0Q"
SUPABASE_URL = "https://aapxnuzwrkxbzsanatik.supabase.co"
SUPABASE_KEY = "EyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFhcHhudXp3cmt4YnpzYW5hdGlrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM5Njg0NDcsImV4cCI6MjA4OTU0NDQ0N30.FdM3KkTBit3b35wK9obuJvPUhetAWGwL_tqM4pgDM0k"

MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003881429974
ADMIN_IDS = [MY_ID, ASSISTANT_ID]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

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

def load_data():
    global data
    try:
        res = supabase.table("bot_data").select("content").eq("id", "main_db").execute()
        if res.data:
            data.update(res.data['content'])
            print("✅ ዳታ ተጭኗል")
    except: print("⚠️ ዳታ መጫን አልተቻለም")

def save_data():
    try:
        supabase.table("bot_data").upsert({"id": "main_db", "content": data}).execute()
    except: print("⚠️ ዳታ ሴቭ አልተደረገም")

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

def main_menu_markup(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS: markup.add("⚙️ Admin Settings")
    return markup

# --- 4. የሰሌዳ ዲዛይን (Group View) ---
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
            line += f"<code>{s_i}</code>🔴{u_name[:5]}\t\t"
        else:
            line += f"<code>{s_i}</code>⬜️\t\t"
        if i % 3 == 0:
            text += line + "\n"
            line = ""
    text += line + "\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━\n"
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
    except: pass

# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    active_pay = PAYMENTS[data.get("current_shift", "me")]
    bot.send_message(uid, f"👋 <b>እንኳን ደህና መጡ!</b>\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር", reply_markup=main_menu_markup(uid))

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    user = get_user(message.chat.id)
    text = (f"👤 <b>የእርስዎ ፕሮፋይል</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>ID:</b> <code>{message.chat.id}</code>\n"
            f"📛 <b>ስም:</b> {user['name']}\n"
            f"💰 <b>ቀሪ ሂሳብ:</b> {user['wallet']} ብር\n")
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id in ADMIN_IDS)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🔄 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset"),
               types.InlineKeyboardButton("📢 መልዕክት ለሁሉም", callback_data="admin_broadcast"))
    bot.send_message(message.chat.id, "🛠 <b>የአድሚን ዳሽቦርድ</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    bot.answer_callback_query(call.id) # Loading እንዲቆም
    
    if call.data.startswith('approve_') and is_admin:
        target = call.data.split('_') # የቀኝ ስህተት ማስተካከያ
        m = bot.send_message(call.from_user.id, f"💵 ለ ID <code>{target}</code> የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_app, target)
        
    elif call.data.startswith('decline_') and is_admin:
        target = call.data.split('_')
        m = bot.send_message(call.from_user.id, "❌ ውድቅ የተደረገበትን ምክንያት ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_dec, target)
        
    elif call.data.startswith('select_'):
        handle_selection(call) # የምላሽ ማጣት ማስተካከያ
        
    elif call.data.startswith('pick_'):
        p = call.data.split('_')
        finalize_reg_inline(call, p, p)
        
    elif call.data == "admin_reset" and is_admin:
        markup = types.InlineKeyboardMarkup()
        for b in data["boards"]: markup.add(types.InlineKeyboardButton(f"Reset ሰሌዳ {b}", callback_data=f"doreset_{b}"))
        bot.edit_message_text("የትኛው ሰሌዳ ይጽዳ?", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif call.data.startswith('doreset_') and is_admin:
        bid = call.data.split('_')
        data["boards"][bid]["slots"] = {}
        save_data()
        bot.send_message(call.message.chat.id, f"✅ ሰሌዳ {bid} ጸድቷል!")
        update_group_board(bid)

def handle_selection(call):
    bid = call.data.split('_')
    user = get_user(call.message.chat.id)
    board = data["boards"][bid]
    
    if user["wallet"] < board["price"]:
        bot.send_message(call.message.chat.id, "⚠️ በቂ ሂሳብ የሎትም! እባክዎ መጀመሪያ ሂሳብ ይሙሉ።")
        return

    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}") for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
    markup.add(*btns)
    bot.edit_message_text(f"🎰 <b>ሰሌዳ {bid}</b>\nእባክዎ ቁጥር ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

def finalize_reg_inline(call, bid, num):
    uid = str(call.message.chat.id); user = get_user(uid); board = data["boards"][bid]
    if user["wallet"] < board["price"]: return
    
    data["users"][uid]["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data(); update_group_board(bid)
    bot.edit_message_text(f"✅ ቁጥር {num} ተመርጧል!\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር", uid, call.message.message_id)

def finalize_app(message, target):
    try:
        amt = int(message.text)
        data["users"][str(target)]["wallet"] += amt
        save_data()
        bot.send_message(target, f"✅ <b>{amt} ብር ተጨምሯል!</b>")
        bot.send_message(message.chat.id, "✅ ተሞልቷል።")
    except: bot.send_message(message.chat.id, "⚠️ ቁጥር ብቻ ይጻፉ!")

def finalize_dec(message, target):
    bot.send_message(target, f"❌ ደረሰኝዎ ውድቅ ሆኗል።\nምክንያት፦ {message.text}")

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} ({b_info['price']} ብር)", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "<b>ሰሌዳ ይምረጡ፦</b>", reply_markup=markup)

@bot.message_handler(content_types=['photo'])
def handle_receipts(message):
    uid = str(message.chat.id)
    bot.reply_to(message, "⏳ ደረሰኝዎ እየታየ ነው...")
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    for adm in ADMIN_IDS:
        bot.send_photo(adm, message.photo[-1].file_id, caption=f"📩 አዲስ ደረሰኝ ከ {message.from_user.first_name}\nID: <code>{uid}</code>", reply_markup=markup)

if __name__ == "__main__":
    load_data(); keep_alive()
    while True:
        try: bot.polling(none_stop=True, interval=0, timeout=20)
        except: time.sleep(5)
