import telebot, re, os, json, time
from flask import Flask
from threading import Thread

# --- 1. SETUP ---
TOKEN = '8721334129:AAEQQi1RtA6PKqTUg59sThJs6sRm_BnBr68'
ADMIN_ID = 8488592165            
GROUP_ID = -1003881429974        
DB_CHANNEL_ID = -1003747262103  

bot = telebot.TeleBot(TOKEN, threaded=False) # Threaded False ለ Render ይሻላል
app = Flask(__name__)

# --- 2. DATA STRUCTURE ---
data = {
    "config": {"db_msg_id": None},
    "boards": {
        "1": {"name": "ሰሌዳ 1 (1-100)", "max": 100, "active": True, "slots": {}, "msg_id": None, "prizes": [500, 300, 100], "price": 20},
        "2": {"name": "ሰሌዳ 2 (1-50)", "max": 50, "active": False, "slots": {}, "msg_id": None, "prizes": [250, 150, 50], "price": 10},
        "3": {"name": "ሰሌዳ 3 (1-25)", "max": 25, "active": False, "slots": {}, "msg_id": None, "prizes": [100, 50, 20], "price": 5}
    },
    "users": {}
}

# --- 3. DATABASE ENGINE ---
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
    except: pass

def load_db():
    try:
        msgs = bot.get_chat_history(DB_CHANNEL_ID, limit=10)
        for m in msgs:
            if m.text and "💾 DB_STORAGE" in m.text:
                try:
                    clean_json = m.text.replace("💾 DB_STORAGE", "").strip()
                    loaded = json.loads(clean_json)
                    if "users" in loaded: data["users"].update(loaded["users"])
                    if "boards" in loaded: data["boards"].update(loaded["boards"])
                    if "config" in loaded: data["config"].update(loaded["config"])
                    return True
                except: continue
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
    
    u = data["users"][uid]
    main_kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    main_kb.add("🕹 ቁጥር ምረጥ", "💰 የእኔ ዋሌት")
    if int(uid) == ADMIN_ID: main_kb.add("🛠 Admin Panel")
    
    welcome_text = (
        f"🌟 **እንኳን ወደ ፋሲል ልዩ ዕጣ በሰላም መጡ!** 🌟\n\n"
        f"👤 **ስም፦** {u['name']}\n"
        f"💰 **ቀሪ ሂሳብ፦** `{u['wallet']} ETB`\n\n"
        f"🕹 ለመጫወት '🕹 ቁጥር ምረጥ' የሚለውን ይጫኑ።"
    )
    bot.send_message(uid, welcome_text, reply_markup=main_kb, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🕹 ቁጥር ምረጥ")
def choose_board(m):
    uid = str(m.from_user.id)
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    for k, v in data["boards"].items():
        if v["active"]:
            kb.add(telebot.types.InlineKeyboardButton(f"🎰 {v['name']} - ({v['price']} ETB)", callback_data=f"start_sel_{k}"))
    bot.send_message(uid, "👇 እባክዎ መጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def handle_calls(c):
    uid = str(c.from_user.id)
    u = data["users"].get(uid)
    if not u: return

    if c.data.startswith("start_sel_"):
        bid = c.data.split("_")[-1]
        u["sel_bid"] = bid
        b = data["boards"][bid]
        
        if u["wallet"] >= b["price"]:
            kb = telebot.types.InlineKeyboardMarkup(row_width=5)
            btns = [telebot.types.InlineKeyboardButton(str(i), callback_data=f"n_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]]
            kb.add(*btns)
            bot.edit_message_text(f"🔢 **{b['name']}**\n💰 ሂሳብዎ፦ `{u['wallet']} ETB`\n\nእባክዎ ቁጥር ይምረጡ፦", uid, c.message.message_id, reply_markup=kb, parse_mode="Markdown")
        else:
            txt = (f"❌ **ሂሳብዎ ለዚህ ሰሌዳ አይበቃም!**\n\n"
                   f"💰 የሰሌዳው ዋጋ፦ `{b['price']} ETB` \n"
                   f"💵 የእርስዎ ሂሳብ፦ `{u['wallet']} ETB` \n\n"
                   f"🏦 **CBE:** `1000584461757` \n"
                   f"📱 **Telebirr:** `0951381356` \n\n"
                   f"📩 እባክዎ ብር ከላኩ በኋላ ደረሰኙን (ፎቶ) እዚህ ይላኩ።")
            bot.edit_message_text(txt, uid, c.message.message_id, parse_mode="Markdown")

    elif c.data.startswith("n_"):
        bid = u.get("sel_bid")
        n = c.data.split("_")[1]
        b = data["boards"][bid]
        
        if u["wallet"] >= b["price"]:
            if n not in b["slots"]:
                u["wallet"] -= b["price"]
                b["slots"][n] = {"name": u["name"], "id": uid}
                refresh_group(bid)
                bot.answer_callback_query(c.id, f"✅ ቁጥር {n} ተይዟል!")
                bot.edit_message_text(f"✅ ቁጥር {n} ተይዟል!\n💰 ቀሪ ሂሳብዎ፦ `{u['wallet']} ETB`", uid, c.message.message_id)
                save_db()
            else: bot.answer_callback_query(c.id, "⚠️ ይቅርታ፣ ይህ ቁጥር ተይዟል!", show_alert=True)
        else: bot.answer_callback_query(c.id, "❌ በቂ ሂሳብ የለዎትም!", show_alert=True)

    elif c.data.startswith("manual_") and int(uid) == ADMIN_ID:
        t_uid = c.data.split("_")[1]
        data["users"][uid]["step"] = f"DEP_{t_uid}"
        bot.send_message(ADMIN_ID, "✍️ የሚጨመረውን የብር መጠን ይጻፉ፦")

    elif c.data.startswith("no_") and int(uid) == ADMIN_ID:
        t_uid = c.data.split("_")[1]
        bot.send_message(t_uid, "❌ ደረሰኝዎ ውድቅ ተደርጓል።")
        bot.delete_message(ADMIN_ID, c.message.message_id)

@bot.message_handler(content_types=['text', 'photo'])
def handle_msgs(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    u = data["users"][uid]

    if u.get('step', '').startswith("DEP_") and int(uid) == ADMIN_ID:
        t_uid = u['step'].split("_")[-1]
        try:
            amt = float(m.text)
            data["users"][t_uid]["wallet"] += amt
            u['step'] = ""
            bot.send_message(t_uid, f"✅ `{amt} ETB` ዋሌትዎ ላይ ተጨምሯል።")
            bot.send_message(ADMIN_ID, "✅ ተጨምሯል!"); save_db()
        except: bot.send_message(ADMIN_ID, "⚠️ ቁጥር ብቻ ይጻፉ።")
        return

    if m.text == "💰 የእኔ ዋሌት":
        bot.send_message(uid, f"💵 **የእርስዎ ቀሪ ሂሳብ፦** `{u['wallet']} ETB`", parse_mode="Markdown")

    elif m.content_type == 'photo':
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ መጠን ጻፍና አጽድቅ", callback_data=f"manual_{uid}"),
               telebot.types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no_{uid}"))
        bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"📩 ደረሰኝ ከ {m.from_user.first_name}\n🆔 ID: `{uid}`", reply_markup=kb)
        bot.send_message(uid, "📩 ደረሰኝዎ ደርሶናል፣ እየታየ ነው እባኮትን ይታገሱን...")

# --- 6. SERVER & POLLING ---
@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    load_db()
    Thread(target=run_flask).start()
    print("🚀 Bot is starting...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            time.sleep(5)
