import telebot
from telebot import types
import json, os, time
from flask import Flask
from threading import Thread
from upstash_redis import Redis

# --- 1. ሰርቨር ማቆያ (Render/Keep Alive) ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Lotto Flow is Active!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት እና ዳታቤዝ መረጃዎች ---
TOKEN = "8721334129:AAFF0Irx3Pa7add9rnMcm855Xsg2G3zMzFM"
MY_ID = 8488592165          
GROUP_ID = -1003749311489
ADMIN_IDS = [MY_ID, 7072611117]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Redis Connection
REDIS_URL = "https://sunny-ferret-79578.upstash.io"
REDIS_TOKEN = "gQAAAAAAATbaAAIncDE4MTQ2MThjMjVjYjI0YzU5OGQ0MjMzZGI0MGIwZTkwNXAxNzk1Nzg"
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

# ዳታቤዝ መዋቅር
data = {
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "1ኛ 200, 2ኛ 100", "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "1ኛ 400, 2ኛ 200", "slots": {}}
    },
    "pinned_msgs": {},
    "pending_selections": {}
}

def save_data(): redis.set("fasil_lotto_db", json.dumps(data))
def load_data():
    global data
    rd = redis.get("fasil_lotto_db")
    if rd: data.update(json.loads(rd))

# --- 3. የሰሌዳ ዲዛይን (Group Update) ---
def update_group_board(b_id):
    b_id = str(b_id)
    board = data["boards"][b_id]
    
    text = f"🇪🇹 🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ!</b> 🏟️ 🇪🇹\n"
    text += f"              <b>በ {board['price']} ብር</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    for i in range(1, board["max"] + 1):
        n = str(i)
        name = board["slots"].get(n, "@@@@")
        text += f"<b>{i}👉</b> {name} {'✅🏆🙏' if n in board['slots'] else ''}\n\n"
            
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🤖 <b>ለመጫወት እዚህ ይጫኑ፦</b> @{bot.get_me().username}"

    try:
        m_id = data["pinned_msgs"].get(b_id)
        if m_id: bot.edit_message_text(text, GROUP_ID, m_id)
        else:
            m = bot.send_message(GROUP_ID, text)
            data["pinned_msgs"][b_id] = m.message_id
            bot.pin_chat_message(GROUP_ID, m.message_id)
            save_data()
    except: pass

# --- 4. የደረሰኝ ፍሰት (Group Flow) ---

@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.id == GROUP_ID)
def handle_group_photo(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ለቦርድ 1 አፅድቅ", callback_data=f"app_1_{message.from_user.id}"),
        types.InlineKeyboardButton("✅ ለቦርድ 2 አፅድቅ", callback_data=f"app_2_{message.from_user.id}"),
        types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"rej_{message.from_user.id}")
    )
    bot.send_photo(MY_ID, message.photo[-1].file_id, 
                   caption=f"📩 <b>አዲስ ደረሰኝ!</b>\nከ: {message.from_user.first_name}\nID: <code>{message.from_user.id}</code>", 
                   reply_markup=markup)
    bot.reply_to(message, "ደረሰኝህ ለባለቤቱ ተልኳል! ተረጋግጦ ምርጫ ይላክልሃል።")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('app_', 'rej_', 'pick_')))
def handle_callbacks(call):
    p = call.data.split('_')
    
    if p == "app":
        msg = bot.send_message(call.message.chat.id, f"💰 <b>ቦርድ {p}</b>\nተጠቃሚው የከፈለውን የብር መጠን ያስገቡ፦")
        bot.register_next_step_handler(msg, process_allowed_slots, p, p)
    
    elif p == "rej":
        bot.edit_message_caption("❌ ውድቅ ተደርጓል።", call.message.chat.id, call.message.message_id)
        bot.send_message(p, "ይቅርታ፣ የላኩት ደረሰኝ ውድቅ ተደርጓል።")

    elif p == "pick":
        u_id = str(call.from_user.id)
        b_id, num = p, p
        if u_id not in data["pending_selections"]: return
        if num in data["boards"][b_id]["slots"]: return
        
        data["boards"][b_id]["slots"][num] = call.from_user.first_name
        data["pending_selections"][u_id]["selected"] += 1
        
        if data["pending_selections"][u_id]["selected"] >= data["pending_selections"][u_id]["allowed"]:
            bot.edit_message_text("✅ ተመዝግቧል! መልካም ዕድል!", u_id, call.message.message_id)
            del data["pending_selections"][u_id]
            save_data()
            update_group_board(b_id)
        else:
            send_picker(u_id, b_id, edit=True, m_id=call.message.message_id)

def process_allowed_slots(message, b_id, u_id):
    try:
        allowed = int(message.text) // data["boards"][b_id]["price"]
        if allowed < 1: return bot.reply_to(message, "⚠️ ብሩ አይበቃም!")
        
        data["pending_selections"][str(u_id)] = {"b_id": b_id, "allowed": allowed, "selected": 0}
        save_data()
        bot.send_message(message.chat.id, f"✅ ተረጋግጧል! ተጠቃሚው {allowed} ቁጥር እንዲመርጥ ተፈቅዶለታል።")
        send_picker(u_id, b_id)
    except: bot.reply_to(message, "እባክዎ ቁጥር ብቻ ያስገቡ!")

def send_picker(u_id, b_id, edit=False, m_id=None):
    board = data["boards"][b_id]
    u_info = data["pending_selections"].get(str(u_id))
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = []
    for i in range(1, board["max"] + 1):
        n = str(i)
        txt = "❌" if n in board["slots"] else n
        btns.append(types.InlineKeyboardButton(txt, callback_data=f"pick_{b_id}_{n}"))
    markup.add(*btns)
    
    rem = u_info["allowed"] - u_info["selected"]
    text = f"🎫 <b>ቦርድ {b_id}</b>\nየሚቀረው ምርጫ፦ <b>{rem}</b>\nእባክዎ ቁጥር ይምረጡ፦"
    
    if edit: bot.edit_message_text(text, u_id, m_id, reply_markup=markup)
    else: bot.send_message(u_id, text, reply_markup=markup)

# --- 5. ቦቱን ማስነሻ ---
if __name__ == "__main__":
    load_data()
    keep_alive()
    bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Fasil Lotto Flow is Running...")
    bot.infinity_polling(skip_pending_updates=True)
