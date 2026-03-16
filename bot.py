import telebot, re, os, json, time
from flask import Flask
from threading import Thread

# --- 1. SETUP ---
TOKEN = '8721334129:AAEQQi1RtA6PKqTUg59sThJs6sRm_BnBr68'
ADMIN_ID = 8488592165            
GROUP_ID = -1003881429974        
DB_CHANNEL_ID = -1003747262103  

# threaded=True ቦቱ ብዙ ሰዎችን በአንድ ጊዜ እንዲያስተናግድ ያደርገዋል
bot = telebot.TeleBot(TOKEN, threaded=True)
app = Flask(__name__)

data = {
    "config": {"db_msg_id": None},
    "boards": {
        "1": {"name": "ሰሌዳ 1", "max": 100, "active": True, "slots": {}, "msg_id": None, "prizes": [500, 300, 100], "price": 20},
        "2": {"name": "ሰሌዳ 2", "max": 50, "active": True, "slots": {}, "msg_id": None, "prizes": [250, 150, 50], "price": 10}
    },
    "users": {}
}

# --- 2. DATABASE ENGINE ---
def save_db():
    try:
        payload = "💾 DB_STORAGE " + json.dumps(data)
        db_id = data["config"].get("db_msg_id")
        if db_id: bot.edit_message_text(payload, DB_CHANNEL_ID, db_id)
        else:
            m = bot.send_message(DB_CHANNEL_ID, payload)
            data["config"]["db_msg_id"] = m.message_id
    except: pass

# --- 3. UI ENGINE (የተስተካከለ የአፃፃፍ ዘዴ) ---
def refresh_group(bid):
    b = data["boards"][bid]
    status = "🟢 ክፍት" if b["active"] else "🔴 ዝግ"
    txt = f"🏆 **{b['name']}** {status}\n"
    txt += f"💵 **መደብ:** `{b['price']} ETB`\n"
    txt += "━━━━━━━━━━━━━\n"
    
    # ሰሌዳውን በ 2 column ማሳያ (ስማቸው በደንብ እንዲታይ)
    slots_list = []
    for i in range(1, b["max"] + 1):
        n = str(i)
        if n in b["slots"]:
            name = b["slots"][n]["name"][:6] # ስሙ እንዳይረዝም ቆርጦ ማሳያ
            slots_list.append(f"{i:02d}. {name}🏆")
        else:
            slots_list.append(f"{i:02d}. ⚪️⚪️⚪️")

    # ሁለት ሁለት እያደረገ መስመር መስራት
    for i in range(0, len(slots_list), 2):
        line = slots_list[i].ljust(15) 
        if i+1 < len(slots_list):
            line += slots_list[i+1]
        txt += f"`{line}`\n"

    txt += "━━━━━━━━━━━━━\n🕹 @fasil_assistant_bot"
    try:
        if not b["msg_id"]:
            m = bot.send_message(GROUP_ID, txt, parse_mode="Markdown")
            b["msg_id"] = m.message_id
        else:
            bot.edit_message_text(txt, GROUP_ID, b["msg_id"], parse_mode="Markdown")
    except: pass
    save_db()

# --- 4. HANDLERS ---
@bot.message_handler(commands=['start'])
def welcome(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]:
        data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🕹 ቁጥር ምረጥ", "💰 ዋሌትና መረጃ")
    if int(uid) == ADMIN_ID: kb.add("🛠 Admin Panel")
    
    bot.send_message(uid, "እንኳን ወደ ፋሲል ዕጣ በደህና መጡ! \n\nክፍያ ለመፈጸም ደረሰኝ ይላኩ።", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "💰 ዋሌትና መረጃ")
def show_wallet(m):
    uid = str(m.from_user.id)
    u = data["users"].get(uid, {"wallet": 0})
    bot.send_message(m.chat.id, f"🎫 **የእርስዎ መረጃ**\n\n💵 ቀሪ ሂሳብ፦ `{u['wallet']} ETB`", parse_mode="Markdown")

@bot.message_handler(content_types=['photo', 'text'])
def handle_all(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": ""}
    u = data["users"][uid]

    # አድሚን ብር ሲያጸድቅ (በቀጥታ ዋሌት ውስጥ ይገባል)
    if int(uid) == ADMIN_ID and u["step"].startswith("ADD_CASH_"):
        target_id = u["step"].split("_")[2]
        try:
            amt = float(m.text)
            data["users"][target_id]["wallet"] += amt
            u["step"] = ""
            bot.send_message(target_id, f"✅ ደረሰኝዎ ጸድቋል! {amt} ETB ዋሌትዎ ላይ ተጨምሯል።\nአሁን መጫወት ይችላሉ።")
            bot.send_message(ADMIN_ID, "ተሳክቷል!")
            save_db()
        except: bot.send_message(ADMIN_ID, "ቁጥር ብቻ ይላኩ!")
        return

    # ተጠቃሚ ስም ሲያስገባ
    if u["step"] == "ASK_NAME":
        u["name"] = m.text
        u["step"] = ""
        bot.send_message(uid, f"ደህና {m.text}! አሁን '🕹 ቁጥር ምረጥ' የሚለውን ተጭነው ቁጥር ይምረጡ።")
        save_db(); return

    if m.text == "🕹 ቁጥር ምረጥ":
        bid = u.get("sel_bid", "1")
        b = data["boards"][bid]
        if u["wallet"] < b["price"]:
            bot.send_message(uid, f"❌ በቂ ሂሳብ የለዎትም። የሰሌዳው ዋጋ {b['price']} ETB ነው።\nእባክዎ መጀመሪያ ደረሰኝ ይላኩ።")
        else:
            kb = telebot.types.InlineKeyboardMarkup(row_width=5)
            btns = [telebot.types.InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]]
            kb.add(*btns)
            bot.send_message(uid, f"🎰 {b['name']} ቁጥር ይምረጡ፦", reply_markup=kb)

    # ደረሰኝ መቀበያ
    elif m.content_type == 'photo' or (m.text and "FT" in m.text):
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"))
        bot.send_message(ADMIN_ID, f"📩 ደረሰኝ ከ {uid} ({u['name']})", reply_markup=kb)
        bot.send_message(uid, "ደረሰኝዎ ደርሶናል፣ እያረጋገጥን ነው...")

@bot.callback_query_handler(func=lambda c: True)
def calls(c):
    uid = str(c.from_user.id)
    if c.data.startswith("approve_"):
        target_id = c.data.split("_")[1]
        data["users"][uid]["step"] = f"ADD_CASH_{target_id}"
        bot.send_message(ADMIN_ID, "ስንት ብር ይግባለት? ቁጥሩን ብቻ ይላኩ፦")
    
    elif c.data.startswith("num_"):
        u = data["users"][uid]
        bid = u.get("sel_bid", "1")
        b = data["boards"][bid]
        num = c.data.split("_")[1]
        
        if u["wallet"] >= b["price"]:
            if num not in b["slots"]:
                if u["name"] == m.from_user.first_name: # ገና ስም ካልቀየረ
                    u["step"] = "ASK_NAME"
                    bot.send_message(uid, "እባክዎ በሰሌዳው ላይ የሚወጣልዎትን ስም ይጻፉ፦")
                    return
                u["wallet"] -= b["price"]
                b["slots"][num] = {"name": u["name"], "id": uid}
                refresh_group(bid)
                bot.answer_callback_query(c.id, "✅ ተመዝግቧል!")
                bot.send_message(uid, f"ቁጥር {num} ተይዟል! ቀሪ ዋሌት፦ {u['wallet']} ETB")
            else: bot.answer_callback_query(c.id, "⚠️ ተይዟል!")
        else: bot.answer_callback_query(c.id, "❌ በቂ ብር የለም!")

# --- 5. SERVER ---
@app.route('/')
def home(): return "Bot is Online"

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=os.environ.get("PORT", 8080))).start()
    bot.infinity_polling(skip_pending=True)
