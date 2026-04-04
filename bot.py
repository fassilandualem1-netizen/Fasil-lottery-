import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time
from upstash_redis import Redis

# --- 1. Web Hosting ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Lotto System is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    try: app.run(host='0.0.0.0', port=port)
    except: pass

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት መረጃዎች ---
TOKEN = "8721334129:AAEbMUHHLcVTv9pGzTwMwC_Wi4tLx3R_F5k"
MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003749311489
DB_CHANNEL_ID = -1003747262103

ADMIN_IDS = [MY_ID, ASSISTANT_ID]

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323"}
}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Redis Connection
REDIS_URL = "https://sunny-ferret-79578.upstash.io"
REDIS_TOKEN = "gQAAAAAAATbaAAIncDE4MTQ2MThjMjVjYjI0YzU5OGQ0MjMzZGI0MGIwZTkwNXAxNzk1Nzg"
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

# --- 3. ዳታቤዝ አያያዝ ---
DB_FILE = "fasil_db.json"
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

def save_data():
    try:
        redis.set("fasil_lotto_db", json.dumps(data))
        with open(DB_FILE, "w") as f: json.dump(data, f)
        with open(DB_FILE, "rb") as f:
            bot.send_document(DB_CHANNEL_ID, f, caption=f"🔄 Backup - {time.ctime()}")
    except: pass

def load_data():
    global data
    try:
        raw = redis.get("fasil_lotto_db")
        if raw: data = json.loads(raw)
        elif os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f: data.update(json.load(f))
    except: pass

load_data()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

# --- 4. የሰሌዳ ዲዛይን (Group Table) ---
def update_group_board(b_id):
    board = data["boards"][b_id]
    
    # ራስጌ (Header)
    text = "🇪🇹 🏟️ ፋሲል እና ዳመነ ዲጂታል ዕጣ! 🏟️ 🇪🇹\n"
    text += f"              በ {board['price']} ብር\n"
    text += "             👇👇👇👇👇\n"
    
    # ሽልማት (Prizes) - ከዳታቤዝ ሽልማቱን ነጥሎ ያወጣዋል
    prizes = board['prize'].split(',')
    labels = ["1ኛ🟢", "2ኛ🟡", "3ኛ🔴"]
    for i, p in enumerate(prizes):
        if i < 3: text += f"             {labels[i]} {p.strip()}\n"

    text += "\n☎️ ለውድ ቤተሰቦቻችን መልካም እድል! 🏆\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

    # የቁጥሮች ዝርዝር
    for i in range(1, board["max"] + 1):
        num_str = str(i)
        if num_str in board["slots"]:
            # ቁጥሩ ከተያዘ ስሙንና ምልክቱን ያሳያል
            user_name = board["slots"][num_str]
            text += f"{i}👉 {user_name} ✅🏆🙏\n"
        else:
            # ቁጥሩ ካልተያዘ ባዶ መሆኑን ያሳያል
            text += f"{i}👉 @@@@ ⬜️\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += "🏟️ ፋሲል እና ዳመነ ዲጂታል ዕጣ! 🏟️\n"
    text += "📞 ስልክ፦ 0973416038\n\n"
    text += "🏦 ገቢ ማስገቢያ አማራጮች፦\n"
    text += "👉 Telebirr: 0951381356 (Fassil)\n"
    text += "👉 CBE: 1000584461757 (Fassil)\n"
    text += "👉 CBE: 1000718691323 (Damene)"

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
        data["pinned_msgs"][b_id] = m.message_id
        save_data()

# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS: markup.add("⚙️ Admin Settings")
    bot.send_message(uid, f"👋 እንኳን መጡ {user['name']}!\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር", reply_markup=markup)

@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    # ከግሩፕ ወይም ከፕራይቬት ደረሰኝ መቀበል
    if message.text in ["👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች", "⚙️ Admin Settings"]: return
    
    uid = str(message.from_user.id)
    user = get_user(uid, message.from_user.first_name)
    # ስሙ ገና "ደንበኛ" ከሆነ በቴሌግራም ስሙ መተካት
    if user['name'] == "ደንበኛ": 
        user['name'] = message.from_user.first_name[:5]
        save_data()

    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    
    cap = f"📩 <b>አዲስ ክፍያ</b>\n👤 ከ፦ {message.from_user.first_name}\n🆔 ID፦ <code>{uid}</code>"
    
    for adm in ADMIN_IDS:
        try:
            if message.photo: bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup)
            else: bot.send_message(adm, f"{cap}\n📝፦ {message.text}", reply_markup=markup)
        except: pass

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    if call.data.startswith('approve_') and is_admin:
        # እዚህ ጋር ነው ቁጥሩን ብቻ ነጥሎ የሚወስደው
        target = call.data.split('_') 
        
        # መልዕክቱ ላይ ዝርዝሩ (List) እንዳይታይ እንዲህ አስተካክለው
        m = bot.send_message(call.from_user.id, f"💵 ለ ID <code>{target}</code> የሚጨመር ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_app, target)
    elif call.data.startswith('select_'):
        bid = call.data.split('_')
        handle_selection(call, bid)
    elif call.data.startswith('pick_'):
        _, bid, num, owner_id = call.data.split('_')
        if str(call.from_user.id) != owner_id:
            bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
            return
        finalize_reg(call, bid, num)

def finalize_app(message, target):
    try:
        # የላክኸው ጽሁፍ ቁጥር መሆኑን ያረጋግጣል
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "⚠️ እባክዎ ቁጥር ብቻ ያስገቡ (ለምሳሌ፦ 100)")
            return

        amt = int(message.text)
        uid = str(target) # ID-ውን ወደ String መቀየር
        
        user = get_user(uid)
        user["wallet"] += amt
        save_data()
        
        # ለAdmin ማረጋገጫ
        bot.send_message(message.chat.id, f"✅ ለ {user['name']} {amt} ብር ተጨምሯል።")
        
        # ግሩፕ ላይ ምርጫውን መላክ
        markup = types.InlineKeyboardMarkup()
        for bid, info in data["boards"].items():
            if info["active"] and user["wallet"] >= info["price"]:
                markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {bid} ({info['price']} ብር)", callback_data=f"select_{bid}"))
        
        msg = f"✅ <b>ክፍያ ጸድቋል!</b>\n👤 ተጠቃሚ፦ <a href='tg://user?id={uid}'>{user['name']}</a>\n💰 መጠን፦ {amt} ብር\n\n👇 ሰሌዳ ይምረጡ፦"
        bot.send_message(GROUP_ID, msg, reply_markup=markup)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት ተፈጥሯል፦ {str(e)}")

def handle_selection(call, bid):
    uid = str(call.from_user.id)
    user = get_user(uid)
    board = data["boards"][bid]
    
    markup = types.InlineKeyboardMarkup(row_width=5)
    # እዚህ ጋር owner_id ጨምረናል (ሌላ ሰው እንዳይነካው)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}_{uid}") 
            for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
    markup.add(*btns)
    bot.edit_message_text(f"🎰 <b>ሰሌዳ {bid}</b>\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር\nቁጥር ይምረጡ፦", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup)

def finalize_reg(call, bid, num):
    uid = str(call.from_user.id); user = get_user(uid); board = data["boards"][bid]
    if user["wallet"] < board["price"]: return
    
    user["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data(); update_group_board(bid)
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")
    
    if user["wallet"] >= board["price"]:
        handle_selection(call, bid)
    else:
        # ብሩ ሲያልቅ መልዕክቱን ማጥፋት (Cleanup)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(GROUP_ID, f"✅ <a href='tg://user?id={uid}'>{user['name']}</a> ምዝገባዎን አጠናቀዋል። መልካም እድል!", parse_mode="HTML")

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    while True:
        try: bot.polling(none_stop=True)
        except: time.sleep(5)
