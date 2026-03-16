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
        "1": {"name": "ሰሌዳ 1 (1-100)", "max": 100, "active": True, "slots": {}, "msg_id": None, "prizes": [500, 300, 100], "price": 20},
        "2": {"name": "ሰሌዳ 2 (1-50)", "max": 50, "active": False, "slots": {}, "msg_id": None, "prizes": [250, 150, 50], "price": 10},
        "3": {"name": "ሰሌዳ 3 (1-25)", "max": 25, "active": False, "slots": {}, "msg_id": None, "prizes": [100, 50, 20], "price": 5}
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
def home(): return "Bot is running!"

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
            b.update({"msg_id": m.message_id})
            bot.pin_chat_message(GROUP_ID, m.message_id)
        else: bot.edit_message_text(txt, GROUP_ID, b["msg_id"], parse_mode="Markdown")
    except: pass
    save_db()

# --- 6. ቦት Logic ---

@bot.message_handler(commands=['start'])
def welcome(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: 
        data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    
    main_kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    main_kb.add("🕹 ቁጥር ምረጥ", "💰 የእኔ ዋሌት")
    
    rules = (
        f"🌟 **እንኳን ወደ ፋሲል ልዩ ዕጣ በሰላም መጡ!** 🌟\n\n"
        f"📜 **ሕግ እና ደንብ፦**\n1. መጀመሪያ በባንክ ወይም በቴሌብር ብር ይላኩ።\n2. ደረሰኝ (Screenshot/SMS) እዚህ ይላኩ።\n\n"
        f"🏦 **የባንክ አካውንቶች፦**\n🔸 CBE: `1000584461757` (ፋሲል...)\n🔸 Telebirr: `0951381356`\n\n"
        f"💰 **የእርስዎ ቀሪ ሂሳብ፦** `{data['users'][uid]['wallet']} ETB`"
    )
    bot.send_message(uid, rules, reply_markup=main_kb, parse_mode="Markdown")

def choose_board(m):
    uid = str(m.from_user.id)
    kb = telebot.types.InlineKeyboardMarkup()
    for k, v in data["boards"].items():
        if v["active"]:
            kb.add(telebot.types.InlineKeyboardButton(f"🎰 {v['name']} - {v['price']} ETB", callback_data=f"start_sel_{k}"))
    bot.send_message(uid, "👇 እባክዎ ሰሌዳ ይምረጡ፦", reply_markup=kb)

@bot.message_handler(content_types=['photo'])
def handle_receipt_photo(m):
    uid = str(m.from_user.id)
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"manual_{uid}"),
           telebot.types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"no_{uid}"))
    bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"📩 **አዲስ ደረሰኝ**\nከ፦ {m.from_user.first_name}\nID፦ `{uid}`", reply_markup=kb)
    bot.send_message(uid, "📩 ደረሰኝዎ ደርሶናል፣ እያረጋገጥን ነው...")

@bot.callback_query_handler(func=lambda c: True)
def handle_calls(c):
    uid = str(c.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": c.from_user.first_name, "step": "", "sel_bid": "1"}
    u = data["users"][uid]

    if c.data.startswith("manual_") and int(uid) == ADMIN_ID:
        target_uid = c.data.split("_")[1]
        data["users"][uid]["step"] = f"DEP_{target_uid}"
        bot.send_message(ADMIN_ID, f"✍️ ለ ID `{target_uid}` የብር መጠን ይጻፉ፦")

    elif c.data.startswith("no_") and int(uid) == ADMIN_ID:
        target_uid = c.data.split("_")[1]
        bot.send_message(target_uid, "❌ ደረሰኝዎ ተቀባይነት አላገኘም።")

    elif c.data.startswith("start_sel_"):
        bid = c.data.split("_")[-1]
        if u["wallet"] < data["boards"][bid]["price"]:
            bot.answer_callback_query(c.id, "❌ ቀሪ ሂሳብዎ አይበቃም!", show_alert=True)
        else:
            u["sel_bid"] = bid
            bot.send_message(uid, "✅ ሰሌዳ ተመርጧል። አሁን ስምዎን ይጻፉ፦")
            u["step"] = "SET_NAME"

    elif c.data.startswith("n_"):
        bid = u["sel_bid"]
        n = c.data.split("_")[1]
        b = data["boards"][bid]
        if u["wallet"] >= b["price"] and n not in b["slots"]:
            u["wallet"] -= b["price"]
            b["slots"][n] = {"name": u["name"], "id": uid}
            refresh_group(bid)
            bot.edit_message_text(f"✅ ቁጥር {n} ተመዝግቧል!\n💰 ቀሪ፦ `{u['wallet']} ETB`", uid, c.message.message_id)
            save_db()

@bot.message_handler(func=lambda m: True)
def handle_all_texts(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    u = data["users"][uid]

    if u.get("step", "").startswith("DEP_") and int(uid) == ADMIN_ID:
        target_uid = u["step"].split("_")[-1]
        try:
            amt = float(m.text)
            data["users"][target_uid]["wallet"] += amt
            u["step"] = ""
            bot.send_message(target_uid, f"✅ `{amt} ETB` ዋሌትዎ ላይ ተጨምሯል።")
            bot.send_message(ADMIN_ID, "✅ ተረጋግጧል!"); save_db()
        except: bot.send_message(ADMIN_ID, "⚠️ ቁጥር ብቻ ይጻፉ።")
        return

    if u.get("step") == "SET_NAME":
        u["name"] = m.text + " 🏆🏆👍🙏"
        u["step"] = ""
        b = data["boards"][u["sel_bid"]]
        kb = telebot.types.InlineKeyboardMarkup(row_width=5)
        btns = [telebot.types.InlineKeyboardButton(str(i), callback_data=f"n_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]]
        kb.add(*btns)
        bot.send_message(uid, f"ሰላም {m.text}፣ ቁጥር ይምረጡ፦", reply_markup=kb)
        return

    if m.text == "🕹 ቁጥር ምረጥ": choose_board(m)
    elif m.text == "💰 የእኔ ዋሌት": bot.send_message(uid, f"💵 ቀሪ ሂሳብ፦ `{u['wallet']} ETB`")
    elif not u.get("step") and int(uid) != ADMIN_ID:
        # SMS መላክ
        bot.send_message(ADMIN_ID, f"📩 **አዲስ SMS**\nከ፦ {m.from_user.first_name}\n`{m.text}`", 
                         reply_markup=telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"manual_{uid}")))
        bot.send_message(uid, "📩 ደረሰኝዎ ተልኳል...")

# --- 8. ማስነሻ ---
if __name__ == "__main__":
    load_db()
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()
    while True:
        try: bot.polling(none_stop=True, interval=0, timeout=20)
        except: time.sleep(5)
