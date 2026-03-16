import telebot, re, os, json, time
from flask import Flask
from threading import Thread

# --- 1. መለያዎች (Settings) ---
TOKEN = '8721334129:AAEQQi1RtA6PKqTUg59sThJs6sRm_BnBr68'
ADMIN_ID = 8488592165            
GROUP_ID = -1003881429974        
DB_CHANNEL_ID = -1003747262103  

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# --- 2. የዳታ መዋቅር ---
data = {
    "config": {"db_msg_id": None},
    "boards": {
        "1": {"name": "ሰሌዳ 1", "max": 100, "active": True, "slots": {}, "msg_id": None, "prizes": [500, 300, 100], "price": 20},
        "2": {"name": "ሰሌዳ 2", "max": 50, "active": False, "slots": {}, "msg_id": None, "prizes": [250, 150, 50], "price": 10},
        "3": {"name": "ሰሌዳ 3", "max": 25, "active": False, "slots": {}, "msg_id": None, "prizes": [100, 50, 20], "price": 5}
    },
    "users": {}
}

# --- 3. ዳታቤዝ ኢንጂን ---
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
                    data["users"].update(loaded.get("users", {}))
                    data["boards"].update(loaded.get("boards", {}))
                    data["config"].update(loaded.get("config", {}))
                    return True
                except: continue
    except: pass
    return False

# --- 4. ሰርቨር ---
@app.route('/')
def home(): return "Bot is active!"

# --- 5. የሰሌዳ አሳሳል ---
def refresh_group(bid, new=False):
    b = data["boards"][bid]
    status = "🟢 ክፍት" if b["active"] else "🔴 ዝግ"
    txt = f"🔥 **{b['name']}** {status}\n━━━━━━━━━━━━━\n"
    txt += f"💵 **መደብ:** `{b['price']} ETB` | 🎁 **ሽልማት:** `{sum(b['prizes'])} ETB` \n━━━━━━━━━━━━━\n"
    
    max_num = b["max"]
    rows = (max_num + 2) // 3 
    for i in range(1, rows + 1):
        line = ""
        for col in range(3):
            num_val = i + (col * rows)
            if num_val <= max_num:
                n = str(num_val)
                if n in b["slots"]:
                    p_name = b["slots"][n]["name"][:6] 
                    line += f"{num_val:02d}.{p_name}🏆 "
                else: line += f"{num_val:02d}.FREE 🆓 "
        txt += line + "\n" 
    txt += f"\n💰 🥇{b['prizes'][0]} | 🥈{b['prizes'][1]} | 🥉{b['prizes'][2]}\n━━━━━━━━━━━━━\n🕹 @fasil_assistant_bot"
    
    try:
        if new or not b["msg_id"]:
            m = bot.send_message(GROUP_ID, txt, parse_mode="Markdown")
            b["msg_id"] = m.message_id
            bot.pin_chat_message(GROUP_ID, m.message_id)
        else: bot.edit_message_text(txt, GROUP_ID, b["msg_id"], parse_mode="Markdown")
    except: pass
    save_db()

# --- 6. አድሚን ፓነል ---
def admin_panel(uid):
    kb = telebot.types.InlineKeyboardMarkup()
    for k, v in data["boards"].items():
        kb.add(telebot.types.InlineKeyboardButton(f"⚙️ {v['name']} ማስተካከያ", callback_data=f"manage_{k}"))
    bot.send_message(uid, "🛠 **የአድሚን መቆጣጠሪያ ሰሌዳ**", reply_markup=kb)

# --- 7. ዋና HANDLERS ---

@bot.message_handler(commands=['start'])
def welcome(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: 
        data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    
    main_kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    main_kb.add("🕹 ቁጥር ምረጥ", "💰 የእኔ ዋሌት")
    if int(uid) == ADMIN_ID: main_kb.add("🛠 Admin Panel")
    
    rules = (
        f"🌟 **እንኳን ወደ ፋሲል ልዩ ዕጣ በሰላም መጡ!** 🌟\n\n"
        f"📜 **ሕግ እና ደንብ፦**\n1. መጀመሪያ በባንክ ወይም በቴሌብር ብር ይላኩ።\n2. ደረሰኝ (Screenshot/SMS) እዚህ ይላኩ።\n\n"
        f"🏦 **የባንክ አካውንቶች፦**\n🔸 CBE: `1000584461757` (ፋሲል...)\n🔸 Telebirr: `0951381356`\n\n"
        f"💰 **የእርስዎ ቀሪ ሂሳብ፦** `{data['users'][uid]['wallet']} ETB`"
    )
    bot.send_message(uid, rules, reply_markup=main_kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: True)
def handle_calls(c):
    uid = str(c.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": c.from_user.first_name, "step": "", "sel_bid": "1"}
    u = data["users"][uid]

    # --- አድሚን ብቻ ---
    if int(uid) == ADMIN_ID:
        if c.data.startswith("manage_"):
            bid = c.data.split("_")[1]
            b = data["boards"][bid]
            kb = telebot.types.InlineKeyboardMarkup(row_width=2)
            st_txt = "🔴 ዝጋ" if b["active"] else "🟢 ክፈት"
            kb.add(telebot.types.InlineKeyboardButton(st_txt, callback_data=f"tog_{bid}"),
                   telebot.types.InlineKeyboardButton("🧹 አፅዳ", callback_data=f"clear_{bid}"))
            kb.add(telebot.types.InlineKeyboardButton("💰 ዋጋ ቀይር", callback_data=f"edit_price_{bid}"),
                   telebot.types.InlineKeyboardButton("🎁 ሽልማት ቀይር", callback_data=f"edit_priz_{bid}"))
            bot.edit_message_text(f"⚙️ **{b['name']}**\nዋጋ፦ {b['price']} | ሽልማት፦ {b['prizes']}", uid, c.message.message_id, reply_markup=kb)

        elif c.data.startswith("tog_"):
            bid = c.data.split("_")[1]
            data["boards"][bid]["active"] = not data["boards"][bid]["active"]
            refresh_group(bid); admin_panel(uid)

        elif c.data.startswith("clear_"):
            bid = c.data.split("_")[1]
            data["boards"][bid]["slots"] = {}
            refresh_group(bid); bot.answer_callback_query(c.id, "ሰሌዳው ፀድቷል!")

        elif c.data.startswith("edit_price_"):
            u["step"] = f"SET_PRICE_{c.data.split('_')[2]}"
            bot.send_message(uid, "✍️ አዲሱን ዋጋ ይጻፉ፦")

        elif c.data.startswith("edit_priz_"):
            u["step"] = f"SET_PRIZ_{c.data.split('_')[2]}"
            bot.send_message(uid, "✍️ ሽልማቶችን በኮማ ለይተው ይጻፉ (ለምሳሌ፦ 500,300,100)፦")

        elif c.data.startswith("manual_"):
            target = c.data.split("_")[1]
            u["step"] = f"DEP_{target}"
            bot.send_message(uid, f"✍️ ለ ID {target} የሚገባውን የብር መጠን ይጻፉ፦")

        elif c.data.startswith("no_"):
            bot.send_message(c.data.split("_")[1], "❌ ደረሰኝዎ ውድቅ ተደርጓል።")

    # --- ተጠቃሚ ---
    if c.data.startswith("start_sel_"):
        bid = c.data.split("_")[-1]
        if u["wallet"] < data["boards"][bid]["price"]:
            bot.answer_callback_query(c.id, "❌ ሂሳብዎ አይበቃም!", show_alert=True)
        else:
            u["sel_bid"] = bid
            u["step"] = "SET_NAME"
            bot.send_message(uid, "✅ ሰሌዳ ተመርጧል። ለመመዝገቢያ የሚሆን ስምዎን ይጻፉ፦")

    elif c.data.startswith("n_"):
        bid = u.get("sel_bid", "1")
        n = c.data.split("_")[1]
        b = data["boards"][bid]
        if u["wallet"] >= b["price"] and n not in b["slots"]:
            u["wallet"] -= b["price"]
            b["slots"][n] = {"name": u["name"], "id": uid}
            refresh_group(bid)
            bot.edit_message_text(f"✅ ቁጥር {n} ተይዟል!\n💰 ቀሪ፦ `{u['wallet']} ETB`", uid, c.message.message_id)
            save_db()

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    u = data["users"][uid]

    if m.content_type == 'photo':
        kb = telebot.types.InlineKeyboardMarkup().add(
            telebot.types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"manual_{uid}"),
            telebot.types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"no_{uid}"))
        bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"📩 ደረሰኝ ከ {m.from_user.first_name}\nID: `{uid}`", reply_markup=kb)
        bot.send_message(uid, "📩 ደረሰኝዎ ደርሶናል፣ እያረጋገጥን ነው...")
        return

    # ትዕዛዞች
    if m.text == "🕹 ቁጥር ምረጥ":
        kb = telebot.types.InlineKeyboardMarkup()
        for k, v in data["boards"].items():
            if v["active"]: kb.add(telebot.types.InlineKeyboardButton(f"🎰 {v['name']} ({v['price']} ETB)", callback_data=f"start_sel_{k}"))
        bot.send_message(uid, "👇 ሰሌዳ ይምረጡ፦", reply_markup=kb)
    elif m.text == "💰 የእኔ ዋሌት":
        bot.send_message(uid, f"💵 ቀሪ ሂሳብ፦ `{u['wallet']} ETB`")
    elif m.text == "🛠 Admin Panel" and int(uid) == ADMIN_ID:
        admin_panel(uid)
    
    # ደረጃዎች (Steps)
    elif u["step"] == "SET_NAME":
        u["name"] = m.text + " 🏆🏆👍🙏"
        u["step"] = ""
        b = data["boards"][u["sel_bid"]]
        kb = telebot.types.InlineKeyboardMarkup(row_width=5)
        btns = [telebot.types.InlineKeyboardButton(str(i), callback_data=f"n_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]]
        kb.add(*btns)
        bot.send_message(uid, f"ሰላም {m.text}፣ ቁጥር ይምረጡ፦", reply_markup=kb)
    
    elif int(uid) == ADMIN_ID and u["step"].startswith("DEP_"):
        target = u["step"].split("_")[-1]
        try:
            amt = float(m.text)
            data["users"][target]["wallet"] += amt
            u["step"] = ""; save_db()
            bot.send_message(target, f"✅ {amt} ETB ዋሌትዎ ላይ ተጨምሯል!"); bot.send_message(ADMIN_ID, "✅ ተፈጽሟል!")
        except: bot.send_message(ADMIN_ID, "❌ ቁጥር ብቻ ይጻፉ!")
    
    elif int(uid) == ADMIN_ID and u["step"].startswith("SET_PRICE_"):
        bid = u["step"].split("_")[-1]
        data["boards"][bid]["price"] = float(m.text)
        u["step"] = ""; save_db(); refresh_group(bid); bot.send_message(ADMIN_ID, "✅ ዋጋ ተቀይሯል!")

    elif int(uid) == ADMIN_ID and u["step"].startswith("SET_PRIZ_"):
        bid = u["step"].split("_")[-1]
        data["boards"][bid]["prizes"] = [float(x.strip()) for x in m.text.split(",")]
        u["step"] = ""; save_db(); refresh_group(bid); bot.send_message(ADMIN_ID, "✅ ሽልማቶች ተቀይረዋል!")
    
    elif int(uid) != ADMIN_ID:
        # SMS መቀበያ
        bot.send_message(ADMIN_ID, f"📩 **SMS ደረሰኝ**\nከ፦ {m.from_user.first_name}\n`{m.text}`", 
                         reply_markup=telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"manual_{uid}")))
        bot.send_message(uid, "📩 ደረሰኝዎ ተልኳል...")

# --- 8. ማስነሻ ---
if __name__ == "__main__":
    load_db()
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()
    while True:
        try: bot.polling(none_stop=True, interval=0, timeout=20)
        except: time.sleep(5)
