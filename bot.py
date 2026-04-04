import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time
from upstash_redis import Redis

# --- 1. Web Hosting (Keep Alive) ---
app = Flask('')
@app.route('/')
def home(): return "Fasil & Damene Bot is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    try: app.run(host='0.0.0.0', port=port)
    except: pass

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት እና ዳታቤዝ መረጃዎች ---
TOKEN = "8721334129:AAEbMUHHLcVTv9pGzTwMwC_Wi4tLx3R_F5k"
MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003749311489
DB_CHANNEL_ID = -1003747262103

ADMIN_IDS = [MY_ID, ASSISTANT_ID]

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757", "name": "Fassil"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323", "name": "Damene"}
}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Redis Connection
REDIS_URL = "https://sunny-ferret-79578.upstash.io"
REDIS_TOKEN = "gQAAAAAAATbaAAIncDE4MTQ2MThjMjVjYjI0YzU5OGQ0MjMzZGI0MGIwZTkwNXAxNzk1Nzg"
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

DB_FILE = "fasil_db.json"
data = {
    "users": {},
    "current_shift": "me",
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "200, 100, 50", "active": True, "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "400, 200, 100", "active": True, "slots": {}},
        "3": {"max": 100, "price": 200, "prize": "800, 400, 200", "active": True, "slots": {}}
    },
    "pinned_msgs": {}
}

def save_data():
    try:
        redis.set("fasil_lotto_db", json.dumps(data))
        with open(DB_FILE, "w") as f: json.dump(data, f)
    except: pass

def load_data():
    global data
    try:
        raw = redis.get("fasil_lotto_db")
        if raw: data = json.loads(raw)
    except: pass

load_data()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid).strip()
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

# --- 3. አዲሱ የሰሌዳ ዲዛይን (Update Board) ---
def update_group_board(b_id):
    board = data["boards"][b_id]
    current_shift = data.get("current_shift", "me")
    active_pay = PAYMENTS[current_shift]
    
    text = "🇪🇹 🏟️ ፋሲል እና ዳመነ ዲጂታል ዕጣ! 🏟️ 🇪🇹\n"
    text += f"              በ {board['price']} ብር\n"
    text += "             👇👇👇👇👇\n"
    
    prizes = board['prize'].split(',')
    labels = ["1ኛ🟢", "2ኛ🟡", "3ኛ🔴"]
    for i, p in enumerate(prizes):
        if i < 3: text += f"             {labels[i]} {p.strip()}\n"

    text += "\n☎️ ለውድ ቤተሰቦቻችን መልካም እድል! 🏆\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

    for i in range(1, board["max"] + 1):
        num_str = str(i)
        if num_str in board["slots"]:
            text += f"{i}👉 {board['slots'][num_str]} ✅🏆🙏\n"
        else:
            text += f"{i}👉 @@@@ ⬜️\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += "🏟️ ፋሲል እና ዳመነ ዲጂታል ዕጣ! 🏟️\n"
    text += f"📞 ስልክ፦ 0973416038\n\n"
    text += f"🏦 <b>ተረኛ ገቢ ማስገቢያ ({active_pay['name']})፦</b>\n"
    text += f"👉 Telebirr: <code>{active_pay['tele']}</code>\n"
    text += f"👉 CBE: <code>{active_pay['cbe']}</code>\n"

    try:
        if b_id in data["pinned_msgs"]:
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

# --- 4. ደረሰኝ መቀበል እና ማፅደቅ ---
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
    if message.chat.type != 'private': return
    if message.text in ["👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች", "⚙️ Admin Settings", "💵 በካሽ መዝግብ", "❌ ተጫዋች ሰርዝ"]: return
    
    uid = str(message.from_user.id)
    user = get_user(uid, message.from_user.first_name)
    if user['name'] == "ደንበኛ": user['name'] = message.from_user.first_name[:10]

    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    
    cap = f"📩 <b>አዲስ ክፍያ</b>\n👤 ከ፦ {message.from_user.first_name}\n🆔 ID፦ <code>{uid}</code>"
    for adm in ADMIN_IDS:
        try:
            if message.photo: bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup)
            else: bot.send_message(adm, f"{cap}\n📝፦ {message.text}", reply_markup=markup)
        except: pass
    bot.send_message(uid, "⏳ ደረሰኝዎ ደርሶኛል... እባክዎ እስኪረጋገጥ ይጠብቁ። 🙏")

# --- 5. Admin Functions ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings")
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS: return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💵 በካሽ መዝግብ", "❌ ተጫዋች ሰርዝ")
    markup.add("🔄 Shift ቀይር", "🔙 ተመለስ")
    bot.send_message(message.chat.id, "🛠 የአድሚን መቆጣጠሪያ፦", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💵 በካሽ መዝግብ")
def quick_cash_start(message):
    if message.from_user.id not in ADMIN_IDS: return
    m = bot.send_message(message.chat.id, "📝 <b>ፈጣን ምዝገባ</b>\nእንዲህ ይጻፉ፦ <code>ሰሌዳ-ቁጥር ስም</code>\n\nምሳሌ፦ 1-05 አበበ")
    bot.register_next_step_handler(m, process_quick_cash)

def process_quick_cash(message):
    try:
        parts = message.text.split(' ', 1)
        info, name = parts, parts
        bid, num = info.split('-')
        board = data["boards"][bid]
        if num in board["slots"]:
            bot.send_message(message.chat.id, f"⚠️ ቁጥር {num} ተይዟል!"); return
        board["slots"][num] = name
        save_data(); update_group_board(bid)
        bot.send_message(GROUP_ID, f"✅ <b>በካሽ ተመዝግቧል</b>\n👤 ተጫዋች፦ {name}\n🎰 ሰሌዳ፦ {bid}\n🎫 ቁጥር፦ {num} 🍀")
    except: bot.send_message(message.chat.id, "❌ ስህተት! (ምሳሌ፦ 1-05 አበበ)")

@bot.message_handler(func=lambda m: m.text == "❌ ተጫዋች ሰርዝ")
def delete_player_start(message):
    if message.from_user.id not in ADMIN_IDS: return
    m = bot.send_message(message.chat.id, "ከሰሌዳው ላይ የሚጠፋውን ቁጥር ይጻፉ (ለምሳሌ፦ 5)፦")
    bot.register_next_step_handler(m, process_delete_player)

def process_delete_player(message):
    num = message.text
    for b_id, board in data["boards"].items():
        if num in board["slots"]:
            del board["slots"][num]
            update_group_board(b_id); save_data()
            bot.send_message(message.chat.id, f"✅ ቁጥር {num} ተሰርዟል።"); return
    bot.send_message(message.chat.id, "⚠️ ቁጥሩ አልተገኘም።")

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    if call.data.startswith('approve_'):
        target = call.data.split('_')
        m = bot.send_message(call.from_user.id, f"💵 ለ ID {target} የሚጨመር ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_app, target)
    elif call.data.startswith('select_'):
        bid = call.data.split('_')
        handle_selection(call, bid)
    elif call.data.startswith('pick_'):
        _, bid, num, owner_id = call.data.split('_')
        if str(call.from_user.id) != owner_id:
            bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True); return
        finalize_reg(call, bid, num)

def finalize_app(message, target):
    try:
        amt = int(message.text)
        uid = str(target).strip()
        user = get_user(uid)
        user["wallet"] += amt; save_data()
        
        markup = types.InlineKeyboardMarkup()
        for bid, info in data["boards"].items():
            if info["active"] and user["wallet"] >= info["price"]:
                markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {bid}", callback_data=f"select_{bid}"))
        
        bot.send_message(GROUP_ID, f"✅ <b>ክፍያ ጸድቋል!</b>\n👤 ተጫዋች፦ <b>{user['name']}</b>\n💰 መጠን፦ {amt} ብር\n👇 ሰሌዳ ይምረጡ፦", reply_markup=markup)
    except: bot.send_message(message.chat.id, "⚠️ ቁጥር ብቻ ይጻፉ!")

def handle_selection(call, bid):
    uid = str(call.from_user.id); user = get_user(uid); board = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}_{uid}") 
            for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
    markup.add(*btns)
    bot.edit_message_text(f"🎰 <b>ሰሌዳ {bid}</b>\n💰 ሂሳብ፦ {user['wallet']} ብር\nቁጥር ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

def finalize_reg(call, bid, num):
    uid = str(call.from_user.id); user = get_user(uid); board = data["boards"][bid]
    if user["wallet"] < board["price"]: return
    user["wallet"] -= board["price"]; board["slots"][num] = user["name"]
    save_data(); update_group_board(bid)
    if user["wallet"] >= board["price"]: handle_selection(call, bid)
    else:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(GROUP_ID, f"✅ <b>{user['name']}</b> ምዝገባዎን አጠናቀዋል። መልካም እድል! 🍀")

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
