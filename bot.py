import telebot, re, os, json, time
from flask import Flask
from threading import Thread

# --- 1. SETUP ---
TOKEN = '8721334129:AAEQQi1RtA6PKqTUg59sThJs6sRm_BnBr68'
ADMIN_ID = 8488592165            
GROUP_ID = -1003881429974        
DB_CHANNEL_ID = -1003747262103  

bot = telebot.TeleBot(TOKEN, threaded=True)
app = Flask(__name__)

# የመጀመሪያ ዳታ (ዳታቤዝ ላይ ከሌለ ይህ ጥቅም ላይ ይውላል)
data = {
    "config": {"db_msg_id": None},
    "boards": {
        "1": {"name": "ሰሌዳ 1", "max": 100, "active": True, "slots": {}, "msg_id": None, "prizes": [500, 300, 100], "price": 20},
        "2": {"name": "ሰሌዳ 2", "max": 50, "active": True, "slots": {}, "msg_id": None, "prizes": [250, 150, 50], "price": 10},
        "3": {"name": "ሰሌዳ 3", "max": 25, "active": True, "slots": {}, "msg_id": None, "prizes": [100, 50, 20], "price": 5}
    },
    "users": {}
}

# --- 2. DATABASE ENGINE ---
def save_db():
    try:
        payload = "💾 DB_STORAGE " + json.dumps(data)
        db_id = data["config"].get("db_msg_id")
        if db_id:
            try: bot.edit_message_text(payload, DB_CHANNEL_ID, db_id)
            except: 
                m = bot.send_message(DB_CHANNEL_ID, payload)
                data["config"]["db_msg_id"] = m.message_id
        else:
            m = bot.send_message(DB_CHANNEL_ID, payload)
            data["config"]["db_msg_id"] = m.message_id
    except Exception as e: print(f"Save Error: {e}")

def load_db():
    try:
        msgs = bot.get_chat_history(DB_CHANNEL_ID, limit=10)
        for m in msgs:
            if m.text and "💾 DB_STORAGE" in m.text:
                clean_json = m.text.replace("💾 DB_STORAGE", "").strip()
                loaded_data = json.loads(clean_json)
                data.update(loaded_data)
                return True
    except Exception as e: print(f"Load Error: {e}")
    return False

# --- 3. UI ENGINE (አዲሱ የሰሌዳ አፃፃፍ) ---
def refresh_group(bid):
    b = data["boards"][bid]
    status = "🟢 ክፍት" if b["active"] else "🔴 ዝግ"
    txt = f"🏆 **{b['name']}** {status}\n"
    txt += f"💵 **መደብ:** `{b['price']} ETB` | 🎁 **ሽልማት:** `{sum(b['prizes'])} ETB`\n"
    txt += "━━━━━━━━━━━━━\n"
    
    slots_list = []
    for i in range(1, b["max"] + 1):
        n = str(i)
        if n in b["slots"]:
            user_name = b["slots"][n]["name"][:6] # ስሙ እንዳይረዝም
            slots_list.append(f"{i:02d}.{user_name}🏆")
        else:
            slots_list.append(f"{i:02d}.⚪️⚪️⚪️")

    # በ 2 Column አደራጃጀት
    for i in range(0, len(slots_list), 2):
        col1 = slots_list[i].ljust(12)
        col2 = slots_list[i+1] if i+1 < len(slots_list) else ""
        txt += f"`{col1}   {col2}`\n"

    txt += f"\n💰 🥇{b['prizes'][0]} | 🥈{b['prizes'][1]} | 🥉{b['prizes'][2]}\n"
    txt += "━━━━━━━━━━━━━\n🕹 @fasil_assistant_bot"
    
    try:
        if not b["msg_id"]:
            m = bot.send_message(GROUP_ID, txt, parse_mode="Markdown")
            b["msg_id"] = m.message_id
            bot.pin_chat_message(GROUP_ID, m.message_id)
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
    
    main_kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    main_kb.add("🕹 ቁጥር ምረጥ", "💰 ዋሌትና መረጃ")
    if int(uid) == ADMIN_ID: main_kb.add("🛠 Admin Panel")
    
    bot.send_message(uid, f"🌟 **እንኳን ወደ ፋሲል ልዩ ዕጣ በሰላም መጡ!** 🌟\n\nክፍያ ለመፈጸም ደረሰኝ ወይም የ SMS ኮፒ ይላኩ።", reply_markup=main_kb, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💰 ዋሌትና መረጃ")
def show_wallet(m):
    uid = str(m.from_user.id)
    u = data["users"].get(uid, {"wallet": 0, "name": m.from_user.first_name})
    bot.send_message(m.chat.id, f"👤 **ስም:** {u['name']}\n💵 **ቀሪ ዋሌት:** `{u['wallet']} ETB`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🕹 ቁጥር ምረጥ")
def select_board(m):
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    for k, v in data["boards"].items():
        if v["active"]:
            kb.add(telebot.types.InlineKeyboardButton(f"🎰 {v['name']} ({v['price']} ETB)", callback_data=f"selboard_{k}"))
    bot.send_message(m.chat.id, "እባክዎ መጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(c):
    uid = str(c.from_user.id)
    u = data["users"].get(uid)

    if c.data.startswith("selboard_"):
        bid = c.data.split("_")[1]
        u["sel_bid"] = bid
        b = data["boards"][bid]
        if u["wallet"] < b["price"]:
            bot.send_message(uid, f"❌ ዋሌትዎ ላይ በቂ ብር የለም። የሰሌዳው ዋጋ {b['price']} ETB ነው። መጀመሪያ ደረሰኝ ይላኩ።")
        else:
            kb = telebot.types.InlineKeyboardMarkup(row_width=5)
            btns = [telebot.types.InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]]
            kb.add(*btns)
            bot.edit_message_text(f"🎰 {b['name']} ቁጥር ይምረጡ፦", uid, c.message.message_id, reply_markup=kb)

    elif c.data.startswith("num_"):
        bid = u.get("sel_bid")
        b = data["boards"][bid]
        num = c.data.split("_")[1]
        if u["wallet"] >= b["price"]:
            if num not in b["slots"]:
                u["wallet"] -= b["price"]
                b["slots"][num] = {"name": u["name"], "id": uid}
                bot.answer_callback_query(c.id, f"✅ ቁጥር {num} ተመዝግቧል!")
                refresh_group(bid)
                bot.send_message(uid, f"✅ ተመዝግቧል! ቀሪ ዋሌት፦ {u['wallet']} ETB")
            else: bot.answer_callback_query(c.id, "⚠️ ይቅርታ ቁጥሩ ተይዟል!", show_alert=True)
        else: bot.answer_callback_query(c.id, "❌ በቂ ዋሌት የለም!", show_alert=True)

    elif c.data.startswith("approve_") and int(uid) == ADMIN_ID:
        target_id = c.data.split("_")[1]
        data["users"][uid]["step"] = f"ADD_CASH_{target_id}"
        bot.send_message(ADMIN_ID, "ስንት ብር ይግባለት? (ቁጥር ብቻ ይላኩ)፦")

    # Admin Panel Actions
    elif c.data == "adm_reset_all" and int(uid) == ADMIN_ID:
        for k in data["boards"]: data["boards"][k]["slots"] = {}; refresh_group(k)
        bot.send_message(ADMIN_ID, "ሁሉም ሰሌዳዎች ጸድተዋል።")

@bot.message_handler(content_types=['photo', 'text'])
def handle_all_messages(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    u = data["users"][uid]

    # አድሚን ብር ሲያስገባ
    if int(uid) == ADMIN_ID and u["step"].startswith("ADD_CASH_"):
        target_id = u["step"].split("_")[2]
        try:
            amt = float(m.text)
            data["users"][target_id]["wallet"] += amt
            u["step"] = ""
            bot.send_message(target_id, f"✅ {amt} ETB ዋሌትዎ ላይ ተጨምሯል። አሁን መጫወት ይችላሉ።")
            bot.send_message(ADMIN_ID, "✅ ተሳክቷል!"); save_db()
        except: bot.send_message(ADMIN_ID, "⚠️ እባክዎ ቁጥር ብቻ ይላኩ!")
        return

    # አድሚን ፓናል
    if m.text == "🛠 Admin Panel" and int(uid) == ADMIN_ID:
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("♻️ Reset All Boards", callback_data="adm_reset_all"))
        bot.send_message(uid, "🛠 **የአድሚን መቆጣጠሪያ**", reply_markup=kb)

    # ደረሰኝ መቀበያ
    elif m.content_type == 'photo' or (m.text and re.search(r"(FT|DCA|[0-9]{10})", m.text)):
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"))
        bot.send_message(ADMIN_ID, f"📩 ደረሰኝ ከ {u['name']} ({uid})", reply_markup=kb)
        bot.send_message(uid, "📩 ደረሰኝዎ ደርሶናል፣ እያረጋገጥን ነው...")

# --- 5. SERVER FOR RENDER ---
@app.route('/')
def home(): return "Bot is Online"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    print("መረጃዎችን ከዳታቤዝ በመጫን ላይ...")
    load_db()
    Thread(target=run_flask).start()
    print("ቦቱ ስራ ጀምሯል!")
    bot.infinity_polling(skip_pending=True)
