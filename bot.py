import os
TOKEN = os.environ.get
8721334129:AAFukMOE8qoJPOZAleW7tLxHN8qpxr92IAc
import telebot
from telebot import types
import json, time, os
from upstash_redis import Redis
from flask import Flask
from threading import Thread

# --- 1. WEB HOSTING (For Render) ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Bingo is Active!"

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. CONFIGURATION ---
TOKEN = "8721334129:AAFpNmNq1PpTQ_SWsj4dye8T3-TXNAZA7Kg"
ADMIN_IDS = 8488592165
GROUP_ID = -1003749311489

# Redis - አዲሱን መረጃ እዚህ አስገብቻለሁ
REDIS_URL = "https://charmed-sailfish-95943.upstash.io"
REDIS_TOKEN = "gQAAAAAAAXbHAAIncDJmOWM3ZWY3ZTc5MmQ0ZmI0OWIyNjUzY2Y4YmFlZGEyM3AyOTU5NDM"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

# --- 3. DATA MANAGEMENT ---
def load_data():
    raw = redis.get("fasil_bingo_v2_db")
    if raw: return json.loads(raw)
    return {
        "users": {},
        "board": {"max": 25, "price": 50, "prize": "ያልተወሰነ", "slots": {}},
        "pinned_msg_id": None
    }

data = load_data()
def save_data(): redis.set("fasil_bingo_v2_db", json.dumps(data))

# --- 4. BOARD UI ---
def update_group_board():
    b = data["board"]
    text = f"🏟️ <b>ፋሲል ዲጂታል ቢንጎ</b> 🏟️\n"
    text += f"💰 ዋጋ፦ <b>{b['price']} ብር</b> | 🎁 ሽልማት፦ <b>{b['prize']}</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

    for i in range(1, b["max"] + 1):
        n = str(i)
        status = f"✅ {data['board']['slots'][n]}" if n in data['board']['slots'] else "⬜️ @@@@"
        text += f"<b>{i:02}👉</b> {status}\t\t"
        if i % 2 == 0: text += "\n"
    
    text += "\n" + "━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 ዙር፦ አዲስ | ሰዓት፦ {time.strftime('%H:%M')}"

    try:
        if data["pinned_msg_id"]:
            bot.edit_message_text(text, GROUP_ID, data["pinned_msg_id"])
        else:
            m = bot.send_message(GROUP_ID, text)
            bot.pin_chat_message(GROUP_ID, m.message_id)
            data["pinned_msg_id"] = m.message_id
            save_data()
    except:
        m = bot.send_message(GROUP_ID, text)
        data["pinned_msg_id"] = m.message_id
        save_data()

# --- 5. HANDLERS ---
@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.id == GROUP_ID)
def handle_group_photo(message):
    uid = message.from_user.id
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    for adm in ADMIN_IDS:
        bot.send_photo(adm, message.photo[-1].file_id, 
                       caption=f"📩 <b>አዲስ ደረሰኝ</b>\n👤 ከ፦ {message.from_user.first_name}\n🆔 ID፦ <code>{uid}</code>", 
                       reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    if call.data.startswith("approve_") and is_admin:
        target_id = call.data.split("_")
        m = bot.send_message(call.from_user.id, "💰 <b>የተከፈለውን ብር ይጻፉ፦</b>")
        bot.register_next_step_handler(m, process_wallet_add, target_id)
    
    elif call.data.startswith("pick_"):
        num = call.data.split("_")
        uid = str(call.from_user.id)
        if num in data["board"]["slots"]: return
        
        user = data["users"].get(uid, {"name": call.from_user.first_name, "wallet": 0})
        price = data["board"]["price"]
        
        if user["wallet"] >= price:
            user["wallet"] -= price
            data["board"]["slots"][num] = user["name"][:10]
            data["users"][uid] = user
            save_data(); update_group_board()
            
            if user["wallet"] < price:
                bot.edit_message_text(f"✅ ምርጫዎ ተጠናቋል። ቀሪ ሂሳብ፦ {user['wallet']} ብር", call.message.chat.id, call.message.message_id)
            else:
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=gen_pick_buttons(uid))
        else:
            bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የለዎትም!", show_alert=True)

    elif call.data == "admin_reset" and is_admin:
        m = bot.send_message(call.from_user.id, "📝 <b>መረጃውን ይጻፉ (ሰው-ዋጋ-ሽልማት)፦</b>\nምሳሌ፦ <code>25-50-1ኛ 500</code>")
        bot.register_next_step_handler(m, execute_reset)

def process_wallet_add(message, target_id):
    try:
        amount = int(''.join(filter(str.isdigit, message.text)))
        uid = str(target_id)
        if uid not in data["users"]: data["users"][uid] = {"name": "ተጫዋች", "wallet": 0}
        data["users"][uid]["wallet"] += amount
        save_data()
        bot.send_message(uid, f"✅ <b>{amount} ብር ተሞልቷል!</b>\nእባክዎ ቁጥር ይምረጡ፦", reply_markup=gen_pick_buttons(uid))
        bot.send_message(message.chat.id, "✅ ተሞልቷል!")
    except: bot.send_message(message.chat.id, "❌ ቁጥር ብቻ ይጻፉ!")

def gen_pick_buttons(uid):
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{i}") 
            for i in range(1, data["board"]["max"] + 1) if str(i) not in data["board"]["slots"]]
    markup.add(*btns)
    return markup

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id in ADMIN_IDS:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🧹 ሰሌዳ አጽዳ (አዲስ ዙር)", callback_data="admin_reset"))
        bot.send_message(message.chat.id, "🛠 <b>አድሚን ፓናል</b>", reply_markup=markup)

def execute_reset(message):
    try:
        parts = message.text.replace(' ', '').replace('–', '-').split('-')
        data["board"].update({"max": int(parts), "price": int(parts), "prize": parts, "slots": {}})
        save_data(); update_group_board()
        bot.send_message(message.chat.id, "✅ ሰሌዳው ተከፍቷል!")
    except: bot.send_message(message.chat.id, "❌ ስህተት! (ሰው-ዋጋ-ሽልማት)")

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    bot.infinity_polling()
