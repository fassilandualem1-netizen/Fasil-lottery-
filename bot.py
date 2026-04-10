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
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት መረጃዎች ---
TOKEN = "8721334129:AAFF0Irx3Pa7add9rnMcm855Xsg2G3zMzFM"
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
        # ባክአፕ ወደ ቻናል መላክ (በየ 5 ደቂቃው ቢሆን ይመረጣል ግን ለጊዜው እንዲህ ይቆይ)
        with open(DB_FILE, "rb") as f:
            bot.send_document(DB_CHANNEL_ID, f, caption=f"🔄 Database Backup - {time.ctime()}")
    except Exception as e:
        print(f"Save Error: {e}")

def load_data():
    global data
    try:
        raw_redis_data = redis.get("fasil_lotto_db")
        if raw_redis_data:
            data = json.loads(raw_redis_data)
        elif os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                data.update(json.load(f))
    except Exception as e:
        print(f"Load Error: {e}")

load_data()

def get_user(uid, name="user_name"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name[:15], "wallet": 0}
    return data["users"][uid]

def main_menu_markup(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if int(uid) in ADMIN_IDS:
        markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች", "⚙️ Admin Settings")
    else:
        markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    return markup

# --- 4. ግሩፕ ላይ ሰሌዳ ማደሻ ---
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

    text += "\n━━━━━━━━━━━━━━━━━━━━━\n"
    board_slots = board["slots"]
    for i in range(1, board["max"] + 1):
        n = str(i)
        user_name = board_slots.get(n, "@@@@")
        text += f"<b>{i}👉</b> {user_name} ✅🏆🙏\n"
            
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"👉 <b>Telebirr:</b> <code>{active_pay['tele']}</code>\n"
    text += f"👉 <b>CBE:</b> <code>{active_pay['cbe']}</code>\n"
    text += f"\n🤖 <b>ለመጫወት እዚህ ይጫኑ፦</b> @{bot.get_me().username}"

    try:
        msg_id = data.get("pinned_msgs", {}).get(b_id)
        if msg_id:
            bot.edit_message_text(text, GROUP_ID, msg_id, parse_mode="HTML")
        else:
            m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
            data["pinned_msgs"][b_id] = m.message_id
            save_data()
    except:
        m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
        data["pinned_msgs"][b_id] = m.message_id
        save_data()

# --- 5. Handlers ---
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

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    uid = str(call.from_user.id)
    
    if call.data.startswith('approve_') and is_admin:
        parts = call.data.split('_')
        target_uid = parts
        msg = bot.send_message(call.from_user.id, f"💵 ለ ID {target_uid} የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(msg, finalize_app, target_uid)

    elif call.data.startswith('decline_') and is_admin:
        parts = call.data.split('_')
        target_uid = parts
        msg = bot.send_message(call.from_user.id, "❌ ውድቅ የተደረገበትን ምክንያት ይጻፉ፦")
        bot.register_next_step_handler(msg, finalize_dec, target_uid)

    elif call.data.startswith('u_select_'):
        parts = call.data.split('_')
        # u_select_UID_BID
        target_id = parts
        bid = parts
        if uid != target_id:
            bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
            return
        markup = generate_picker_markup(uid, bid)
        bot.edit_message_text(f"🎰 <b>ሰሌዳ {bid} ተመርጧል!</b>\nቁጥር ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith('p_'):
        parts = call.data.split('_')
        # p_UID_BID_NUM
        target_id = parts
        bid = parts
        num = parts
        if uid != target_id:
            bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
            return
        finalize_reg_inline(call, bid, num)

    elif call.data == "taken":
        bot.answer_callback_query(call.id, "❌ ይህ ቁጥር ተይዟል!")
    
    # የተቀሩት የአድሚን ገጾች...
    elif call.data == "admin_manage" and is_admin:
        admin_manage_menu(call)

def generate_picker_markup(uid, bid):
    board = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = []
    for i in range(1, board["max"] + 1):
        n_str = str(i)
        if n_str not in board["slots"]:
            btns.append(types.InlineKeyboardButton(n_str, callback_data=f"p_{uid}_{bid}_{n_str}"))
        else:
            btns.append(types.InlineKeyboardButton("❌", callback_data="taken"))
    markup.add(*btns)
    return markup

def finalize_app(message, target_uid):
    try:
        amt = int(message.text)
        uid = str(target_uid)
        user = get_user(uid)
        user["wallet"] += amt
        save_data()
        
        active_boards = [bid for bid, info in data["boards"].items() if info["active"]]
        markup = types.InlineKeyboardMarkup(row_width=1)
        for bid in active_boards:
            price = data["boards"][bid]["price"]
            markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {bid} ({price} ብር)", callback_data=f"u_select_{uid}_{uid}_{bid}"))
        
        text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n👤 <b>ተጫዋች፦</b> {user['name']}\n💰 <b>ሂሳብ፦</b> {user['wallet']} ብር\n"
                f"❓ <b>እባክዎ መጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦</b>")
        bot.send_message(GROUP_ID, text, reply_markup=markup)
        bot.send_message(uid, f"✅ {amt} ብር ተጨምሮልዎታል። አሁን መጫወት ይችላሉ!")
    except:
        bot.send_message(message.chat.id, "❌ የተሳሳተ የብር መጠን!")

def finalize_reg_inline(call, bid, num):
    uid = str(call.from_user.id)
    user = get_user(uid)
    board = data["boards"][bid]
    
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True)
        return
        
    if num in board["slots"]:
        bot.answer_callback_query(call.id, "❌ ይቅርታ፣ ቁጥሩ ተይዟል!")
        return

    user["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data()
    update_group_board(bid)
    
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")
    
    if user["wallet"] >= board["price"]:
        # አሁንም መጫወት ከቻለ ሰሌዳውን መልሶ ማሳየት
        markup = generate_picker_markup(uid, bid)
        bot.edit_message_text(f"✅ ቁጥር {num} ተይዟል!\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር\n\nሌላ ቁጥር ይምረጡ፦", 
                              call.message.chat.id, call.message.message_id, reply_markup=markup)
    else:
        bot.edit_message_text(f"✅ ምዝገባ ተጠናቋል!\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር", 
                              call.message.chat.id, call.message.message_id)

# --- ፕሮሰሱን ማስጀመር ---
if __name__ == "__main__":
    keep_alive()
    print("🤖 ቦቱ ስራ ጀምሯል...")
    bot.polling(none_stop=True)
