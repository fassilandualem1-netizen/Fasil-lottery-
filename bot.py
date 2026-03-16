import telebot, re, os, json, time 
from flask import Flask
from threading import Thread

# --- 1. SETUP ---
TOKEN = '8721334129:AAEQQi1RtA6PKqTUg59sThJs6sRm_BnBr68'
ADMIN_ID = 8488592165            
GROUP_ID = -1003881429974        
DB_CHANNEL_ID = -1003747262103  

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

data = {
    "config": {"db_msg_id": None},
    "boards": {
        "1": {"name": "ሰሌዳ 1 (1-100)", "max": 100, "active": True, "slots": {}, "msg_id": None, "prizes": [500, 300, 100], "price": 20},
        "2": {"name": "ሰሌዳ 2 (1-50)", "max": 50, "active": False, "slots": {}, "msg_id": None, "prizes": [250, 150, 50], "price": 10},
        "3": {"name": "ሰሌዳ 3 (1-25)", "max": 25, "active": False, "slots": {}, "msg_id": None, "prizes": [100, 50, 20], "price": 5}
    },
    "users": {}
}

# --- 3. DATABASE ENGINE (ጥንቃቄ የተሞላበት አቀማመጥ) ---
def save_db():
    try:
        payload = "💾 DB_STORAGE " + json.dumps(data)
        db_id = data["config"].get("db_msg_id")
        if db_id: 
            try:
                bot.edit_message_text(payload, DB_CHANNEL_ID, db_id)
            except:
                m = bot.send_message(DB_CHANNEL_ID, payload)
                data["config"]["db_msg_id"] = m.message_id
        else:
            m = bot.send_message(DB_CHANNEL_ID, payload)
            data["config"]["db_msg_id"] = m.message_id
    except: pass

def load_db():
    try:
        # የመጨረሻውን የዳታ መልዕክት ለማግኘት
        msgs = bot.get_chat_history(DB_CHANNEL_ID, limit=10)
        for m in msgs:
            if m.text and "💾 DB_STORAGE" in m.text:
                loaded = json.loads(m.text.replace("💾 DB_STORAGE", "").strip())
                # ዋናውን ዳታ እንዳያጠፋ በጥንቃቄ መተካት
                if "users" in loaded: data["users"].update(loaded["users"])
                if "boards" in loaded: data["boards"].update(loaded["boards"])
                if "config" in loaded: data["config"].update(loaded["config"])
                return True
    except: pass
    return False

# --- 4. UI ENGINE ---
def refresh_group(bid, new=False):
    b = data["boards"][bid]
    status = "🟢 ክፍት" if b["active"] else "🔴 ዝግ"
    txt = f"🔥 **{b['name']}** {status}\n━━━━━━━━━━━━━\n"
    txt += f"💵 **መደብ:** `{b['price']} ETB` | 🎁 **ሽልማት:** `{sum(b['prizes'])} ETB` \n━━━━━━━━━━━━━\n"
    for i in range(1, b["max"] + 1):
        n = str(i)
        txt += f"{i:02d}.{b['slots'][n]['name'][:4]}🏆 " if n in b["slots"] else f"{i:02d}.⚪️ "
        if i % 3 == 0: txt += "\n"
    txt += f"\n💰 🥇{b['prizes'][0]} | 🥈{b['prizes'][1]} | 🥉{b['prizes'][2]}\n━━━━━━━━━━━━━\n🕹 @fasil_assistant_bot"
    try:
        if new or not b["msg_id"]:
            m = bot.send_message(GROUP_ID, txt, parse_mode="Markdown")
            b["msg_id"] = m.message_id
            bot.pin_chat_message(GROUP_ID, m.message_id)
        else: bot.edit_message_text(txt, GROUP_ID, b["msg_id"], parse_mode="Markdown")
    except: pass
    save_db()

# --- 5. HANDLERS ---
@bot.message_handler(commands=['start'])
def welcome(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: 
        data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    
    main_kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    main_kb.add("🕹 ቁጥር ምረጥ", "💰 የእኔ ዋሌት")
    if int(uid) == ADMIN_ID: main_kb.add("🛠 Admin Panel")
    
    bot.send_message(uid, f"🌟 **እንኳን ወደ ፋሲል ልዩ ዕጣ በሰላም መጡ!** 🌟\n\nቀሪ ሂሳብዎ፦ `{data['users'][uid]['wallet']} ETB`", reply_markup=main_kb, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💰 የእኔ ዋሌት")
def check_wal(m):
    uid = str(m.from_user.id)
    wal = data["users"].get(uid, {}).get("wallet", 0)
    bot.send_message(uid, f"💵 **የእርስዎ ቀሪ ሂሳብ፦** `{wal} ETB`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🕹 ቁጥር ምረጥ")
def start_pick(m):
    uid = str(m.from_user.id)
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    for k, v in data["boards"].items():
        if v["active"]:
            kb.add(telebot.types.InlineKeyboardButton(f"🎰 {v['name']} ({v['price']} ETB)", callback_data=f"sel_{k}"))
    bot.send_message(uid, "ሰሌዳ ይምረጡ፦", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def calls(c):
    uid = str(c.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": c.from_user.first_name, "step": "", "sel_bid": "1"}
    u = data["users"][uid]

    if c.data.startswith("sel_"):
        bid = c.data.split("_")[1]
        u["sel_bid"] = bid
        b = data["boards"][bid]
        if u["wallet"] < b["price"]:
            bot.send_message(uid, f"❌ በቂ ሂሳብ የለዎትም። ዋጋ፦ {b['price']} ETB | ቀሪዎ፦ {u['wallet']} ETB")
        else:
            kb = telebot.types.InlineKeyboardMarkup(row_width=5)
            btns = [telebot.types.InlineKeyboardButton(str(i), callback_data=f"n_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]]
            kb.add(*btns)
            bot.edit_message_text(f"🎰 {b['name']} ቁጥር ይምረጡ፦", uid, c.message.message_id, reply_markup=kb)

    elif c.data.startswith("n_"):
        bid = u.get("sel_bid", "1")
        b = data["boards"][bid]
        num = c.data.split("_")[1]
        if u["wallet"] >= b["price"]:
            if num not in b["slots"]:
                u["wallet"] -= b["price"]
                b["slots"][num] = {"name": u["name"], "id": uid}
                refresh_group(bid)
                bot.answer_callback_query(c.id, f"✅ ቁጥር {num} ተይዟል!")
                bot.send_message(uid, f"✅ ተመዝግቧል! ቀሪ ዋሌት፦ {u['wallet']} ETB")
                save_db() # እዚህ ጋር ወዲያው እናስቀምጥ
            else: bot.answer_callback_query(c.id, "⚠️ ተይዟል!")
        else: bot.answer_callback_query(c.id, "❌ በቂ ዋሌት የለም!")

    elif c.data.startswith("approve_") and int(uid) == ADMIN_ID:
        target_id = c.data.split("_")[1]
        data["users"][uid]["step"] = f"CASH_{target_id}"
        bot.send_message(ADMIN_ID, f"ለ {target_id} የሚገባ የብር መጠን በቁጥር ብቻ ጻፍ፦")

@bot.message_handler(content_types=['photo', 'text'])
def handle_all(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": ""}
    u = data["users"][uid]

    # አድሚን ብር ሲያስገባ (Save ይደረጋል)
    if int(uid) == ADMIN_ID and u["step"].startswith("CASH_"):
        target_id = u["step"].split("_")[1]
        try:
            amt = float(m.text)
            if target_id not in data["users"]: data["users"][target_id] = {"wallet": 0, "name": "User", "step": ""}
            data["users"][target_id]["wallet"] += amt
            u["step"] = ""
            save_db() # ወዲያው ዳታቤዝ ላይ ይጻፍ
            bot.send_message(target_id, f"✅ {amt} ETB ዋሌትዎ ላይ ተጨምሯል።")
            bot.send_message(ADMIN_ID, f"✅ ተሳክቷል! {target_id} አሁን {data['users'][target_id]['wallet']} ETB አለው።")
        except: bot.send_message(ADMIN_ID, "ቁጥር ብቻ ይላኩ!")
        return

    if m.content_type == 'photo' or (m.text and "FT" in m.text):
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"))
        bot.send_message(ADMIN_ID, f"📩 ደረሰኝ ከ {uid} ({m.from_user.first_name})", reply_markup=kb)
        bot.send_message(uid, "ደረሰኝዎ ደርሶናል፣ እያረጋገጥን ነው...")

# --- 6. SERVER & POLLING ---
@app.route('/')
def home(): return "Bot Active"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    load_db() # ቦቱ ሲነሳ ዳታውን ከቻናሉ ይጫናል
    Thread(target=run_flask).start()
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
