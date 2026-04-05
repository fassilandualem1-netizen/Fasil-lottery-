import telebot # ✅ 'Import' የነበረው ወደ 'import' ተስተካክሏል
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
    app.run(host='0.0.0.0', port=port)

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
        with open(DB_FILE, "w") as f:
            json.dump(data, f)
    except: pass

def load_data():
    global data
    try:
        raw_redis_data = redis.get("fasil_lotto_db")
        if raw_redis_data:
            data = json.loads(raw_redis_data)
    except: pass

load_data()

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
    b_id = str(b_id)
    board = data["boards"][b_id]
    current_shift = data.get("current_shift", "me")
    active_pay = PAYMENTS[current_shift]
    
    text = "🇪🇹 🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ!</b> 🏟️ 🇪🇹\n"
    text += f"              <b>በ {board['price']} ብር</b>\n"
    text += "             👇👇👇👇👇\n"
    
    prizes = board['prize'].split(',')
    labels = ["1ኛ🟢", "2ኛ🟡", "3ኛ🔴"]
    for i, p in enumerate(prizes):
        if i < 3: text += f"             {labels[i]} {p.strip()}\n"

    text += "\n☎️⏰⏰ ለውድ 🏟️ ፋሲል እና ዳመነ ዲጂታል ዕጣ! 🏟️ ቤተሰብ\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

    board_slots = board["slots"]
    for i in range(1, board["max"] + 1):
        n = str(i)
        if n in board_slots:
            text += f"<b>{i}👉</b> <b><i><code>{board_slots[n]}</code></i></b> ✅🏆🙏\n\n"
        else:
            text += f"<b>{i}👉</b> @@@@ ✅🏆🙏\n\n"
            
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"👉 <b>Telebirr:</b> <code>{active_pay['tele']}</code>\n"
    text += f"👉 <b>CBE:</b> <code>{active_pay['cbe']}</code>\n"
    text += f"\n🤖 <b>ለመጫወት፦</b> @{bot.get_me().username}"

    try:
        msg_id = data["pinned_msgs"].get(b_id)
        if msg_id:
            bot.edit_message_text(text, GROUP_ID, msg_id)
        else:
            m = bot.send_message(GROUP_ID, text)
            data["pinned_msgs"][b_id] = m.message_id
            save_data()
    except: pass

# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    welcome_text = (f"👋 <b>እንኳን መጡ!</b>\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር")
    bot.send_message(uid, welcome_text, reply_markup=main_menu_markup(uid))

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} | 🎫 {b_info['price']} ብር", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "<b>ሰሌዳ ይምረጡ፦</b>", reply_markup=markup)

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    uid = str(message.from_user.id)
    u_name = message.from_user.first_name if message.from_user.first_name else "User"
    mid = message.message_id
    
    markup = types.InlineKeyboardMarkup()
    # ✅ ዳታው በ '_' ተለይቶ መላኩን እናረጋግጣለን
    markup.add(types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"g_app_{uid}_{mid}_{u_name}"))
    
    cap = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 <b>ከ፦</b> {u_name}\n🆔 🆔 <b>ID፦</b> <code>{uid}</code>"
    for adm in ADMIN_IDS:
        bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup)

# --- 6. የ "Approve" Logic ማስተካከያ (Bad Request Fix) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('g_app_'))
def approve_payment(call):
    is_admin = call.from_user.id in ADMIN_IDS
    if is_admin:
        parts = call.data.split('_')
        target_id = parts
        receipt_mid = parts
        user_name = parts if len(parts) > 4 else "ተጫዋች"
        
        msg = bot.send_message(call.message.chat.id, f"💰 ለ <b>{user_name}</b> የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(msg, send_picker_to_group, target_id, receipt_mid, user_name)

def send_picker_to_group(message, target_id, receipt_mid, user_name):
    try:
        amt = int(message.text)
        user = get_user(target_id, user_name)
        user["wallet"] += amt
        save_data()

        active_board = "1" 
        board = data["boards"][active_board]
        
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = []
        for i in range(1, board["max"] + 1):
            n = str(i)
            if n not in board["slots"]:
                btns.append(types.InlineKeyboardButton(n, callback_data=f"p_{target_id}_{active_board}_{n}"))
            else:
                btns.append(types.InlineKeyboardButton("❌", callback_data="taken"))
        markup.add(*btns)
        
        text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n👤 <b>ተጫዋች፦</b> {user_name}\n💰 <b>ቀሪ፦</b> {user['wallet']} ብር\n\n🎰 <b>ቁጥርዎን ይምረጡ፦</b>")
        
        # ✅ int() በመጠቀም የ Bad Request ስህተትን እንከላከላለን
        if receipt_mid != "0":
            bot.send_message(GROUP_ID, text, reply_to_message_id=int(receipt_mid), reply_markup=markup)
        else:
            bot.send_message(GROUP_ID, text, reply_markup=markup)
            
        bot.send_message(message.chat.id, f"✅ ለ {user_name} ተዘርግቷል።")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት፦ {e}")

# --- 7. የቁጥር ምርጫ Logic ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('p_'))
def handle_secure_pick(call):
    parts = call.data.split('_')
    uid, bid, num = parts, parts, parts
    
    if str(call.from_user.id) != str(uid):
        bot.answer_callback_query(call.id, "⚠️ የሌላ ሰው ምርጫ ነው!", show_alert=True)
        return

    user = data["users"][uid]
    board = data["boards"][bid]

    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "❌ ሂሳብዎ በቂ አይደለም!", show_alert=True)
        bot.delete_message(GROUP_ID, call.message.message_id)
        return

    # ምዝገባ
    user["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data()
    update_group_board(bid)
    
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")

    if user["wallet"] >= board["price"]:
        # በተኑን ማደስ
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(str(i), callback_data=f"p_{uid}_{bid}_{i}") if str(i) not in board["slots"] else types.InlineKeyboardButton("❌", callback_data="t") for i in range(1, board["max"] + 1)]
        markup.add(*btns)
        new_text = (f"♻️ <b>ተጨማሪ ይምረጡ!</b>\n👤 <b>ተጫዋች፦</b> {user['name']}\n💰 <b>ቀሪ፦</b> {user['wallet']} ብር")
        bot.edit_message_text(new_text, GROUP_ID, call.message.message_id, reply_markup=markup)
    else:
        bot.delete_message(GROUP_ID, call.message.message_id)
        bot.send_message(GROUP_ID, f"🎉 <b>{user['name']}</b> መርጠው ጨርሰዋል!")

# --- የቀሩት አድሚን ፈንክሽኖች ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_cash")
def admin_cash_start(call):
    m = bot.send_message(call.from_user.id, "📝 <b>በካሽ መዝግብ፦</b> 1-05 አበበ")
    bot.register_next_step_handler(m, process_cash_reg)

def process_cash_reg(message):
    try:
        parts = message.text.split(' ')
        bid, num = parts.split('-')
        name = parts
        data["boards"][bid]["slots"][num] = name
        save_data()
        update_group_board(bid)
        bot.send_message(message.chat.id, "✅ ተመዝግቧል!")
    except: bot.send_message(message.chat.id, "❌ ስህተት! (1-05 አበበ)")

if __name__ == "__main__":
    keep_alive()
    print("Bot is running...")
    while True:
        try: bot.polling(none_stop=True, interval=1, timeout=20)
        except: time.sleep(5)
