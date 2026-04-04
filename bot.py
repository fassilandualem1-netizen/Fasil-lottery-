import telebot  # እዚህ ጋር 'i' ትንሽ መሆን አለባት
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
        with open(DB_FILE, "rb") as f:
            bot.send_document(DB_CHANNEL_ID, f, caption=f"🔄 Database Backup - {time.ctime()}")
    except: pass

def load_data():
    global data
    try:
        raw_redis_data = redis.get("fasil_lotto_db")
        if raw_redis_data:
            data = json.loads(raw_redis_data)
        elif os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                data.update(json.load(f))
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

# --- 4. ሰሌዳ ማደሻ ---
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
            line += f"<code>{s_i}</code>✅{u_name[:5]}\t\t\t\t"
        else:
            line += f"<code>{s_i}</code>⬜️\t\t\t\t\t\t"
        if i % 2 == 0:
            text += line + "\n"
            line = ""
    text += line + f"\n━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🎁 <b>ሽልማት፦ {board['prize']}</b>\n🤖 @Fasil_assistant_bot"
    
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

# --- 5. Handlers ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    active_pay = PAYMENTS[data.get("current_shift", "me")]
    text = (f"👋 <b>እንኳን መጡ!</b>\n👤 <b>ስም፦</b> {user['name']}\n💰 <b>ቀሪ፦</b> {user['wallet']} ብር\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n🏦 <b>Telebirr:</b> <code>{active_pay['tele']}</code>\n"
            f"🔸 <b>CBE:</b> <code>{active_pay['cbe']}</code>")
    bot.send_message(uid, text, reply_markup=main_menu_markup(uid))

@bot.message_handler(content_types=['photo'])
def handle_receipts(message):
    if message.chat.type in ['group', 'supergroup']:
        uid = str(message.from_user.id)
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"ga_{uid}"), 
                   types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"gd_{uid}"))
        cap = f"📩 <b>አዲስ ክፍያ (ከግሩፕ)</b>\n👤 <b>ከ፦</b> {message.from_user.first_name}\n🆔 <b>ID፦</b> <code>{uid}</code>"
        for adm in ADMIN_IDS:
            bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    
    if call.data.startswith('ga_') and is_admin:
        target_id = call.data.split('_') # እዚህ ጋር መኖሩ ወሳኝ ነው
        m = bot.send_message(call.from_user.id, f"💵 ለ ID {target_id} የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_group_app, target_id)
        
    elif call.data.startswith('select_'):
        handle_selection(call)
        
    elif call.data.startswith('pick_'):
        _, bid, num = call.data.split('_')
        finalize_reg_inline(call, bid, num)

def finalize_group_app(message, target_id):
    try:
        amount = int(message.text)
        user = get_user(target_id)
        user['wallet'] += amount
        save_data()
        
        bot.send_message(target_id, f"✅ {amount} ብር ተፈቅዷል። አሁን ካርድ ይምረጡ!")
        
        # ምርጫውን ግሩፕ ላይ መላክ
        markup = types.InlineKeyboardMarkup(row_width=1)
        for b_id, b_info in data["boards"].items():
            if b_info["active"]:
                markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} | {b_info['price']} ብር", callback_data=f"select_{b_id}"))
        
        sent_msg = bot.send_message(GROUP_ID, f"🔔 <a href='tg://user?id={target_id}'>ደንበኛ</a> ሆይ ክፍያዎ ጸድቋል፤ ካርድ ይምረጡ።", reply_markup=markup)
        
        def auto_delete(msg_id):
            time.sleep(60)
            try: bot.delete_message(GROUP_ID, msg_id)
            except: pass
        Thread(target=auto_delete, args=(sent_msg.message_id,)).start()
        
    except:
        bot.send_message(message.chat.id, "⚠️ ስህተት! ቁጥር ብቻ ይጻፉ።")

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
    bot.edit_message_text(f"🎰 <b>ሰሌዳ {bid}</b>\n💰 ቀሪ፦ {user['wallet']} ብር\nቁጥር ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

def finalize_reg_inline(call, bid, num):
    uid = str(call.message.chat.id)
    user = get_user(uid)
    board = data["boards"][bid]
    
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!")
        return
        
    user["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data()
    update_group_board(bid)
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")
    
    if user["wallet"] >= board["price"]:
        handle_selection(call)
    else:
        bot.edit_message_text(f"✅ ምዝገባ ተጠናቋል።\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር", uid, call.message.message_id, reply_markup=main_menu_markup(uid))

# --- ሰርቨር ማስጀመሪያ ---
if __name__ == "__main__":
    save_data()
    keep_alive()
    bot.remove_webhook()
    while True:
        try: bot.polling(none_stop=True, interval=1, timeout=20)
        except: time.sleep(5)
