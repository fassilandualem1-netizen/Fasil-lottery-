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
                    data["users"].update(loaded.get("users", {}))
                    data["boards"].update(loaded.get("boards", {}))
                    data["config"].update(loaded.get("config", {}))
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
    
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    for k, v in data["boards"].items():
        if v["active"]:
            kb.add(telebot.types.InlineKeyboardButton(f"🎰 {v['name']} - ({v['price']} ETB)", callback_data=f"start_sel_{k}"))
    
    main_kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    main_kb.add("🕹 ቁጥር ምረጥ", "💰 የእኔ ዋሌት")
    if int(uid) == ADMIN_ID: main_kb.add("🛠 Admin Panel")
    
    bot.send_message(uid, f"🌟 **እንኳን ወደ ፋሲል ልዩ ዕጣ በሰላም መጡ!** 🌟\n\nቀሪ ሂሳብዎ፦ `{data['users'][uid]['wallet']} ETB`", reply_markup=main_kb, parse_mode="Markdown")
    bot.send_message(uid, "👇 ሰሌዳ እዚህ ይምረጡ፦", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def handle_calls(c):
    uid = str(c.from_user.id)
    u = data["users"].get(uid)
    if not u: return

    if c.data.startswith("start_sel_"):
        bid = c.data.split("_")[-1]
        u["sel_bid"] = bid
        b = data["boards"][bid]
        bot.edit_message_text(f"✅ **{b['name']} ተመርጧል!**\n💰 መደብ፦ `{b['price']} ETB` \n━━━━━━━━━━━━━\n📩 እባክዎ ደረሰኝ እዚህ ይላኩ።", uid, c.message.message_id, parse_mode="Markdown")

    elif c.data.startswith("ok_") and int(uid) == ADMIN_ID:
        _, t_uid, amt = c.data.split("_")
        data["users"][t_uid]["wallet"] += float(amt)
        bot.send_message(t_uid, f"✅ ደረሰኝዎ ጸድቋል!\n💰 `{amt} ETB` ዋሌትዎ ላይ ተጨምሯል።")
        bot.delete_message(ADMIN_ID, c.message.message_id); save_db()

    elif c.data.startswith("manual_") and int(uid) == ADMIN_ID:
        t_uid = c.data.split("_")[1]
        data["users"][uid]["step"] = f"INPUT_AMT_{t_uid}"
        bot.send_message(ADMIN_ID, "✍️ የሚጨመረውን ብር መጠን ይጻፉ፦")

    elif c.data.startswith("n_"):
        bid = u.get("sel_bid")
        n = c.data.split("_")[1]
        if not bid: return
        b = data["boards"][bid]
        if u["wallet"] >= b["price"]:
            if n not in b["slots"]:
                u["wallet"] -= b["price"]
                b["slots"][n] = {"name": u["name"], "id": uid}
                refresh_group(bid)
                bot.answer_callback_query(c.id, f"✅ ቁጥር {n} ተይዟል!")
                save_db()
            else: bot.answer_callback_query(c.id, "⚠️ ተይዟል!", show_alert=True)
        else: bot.answer_callback_query(c.id, "❌ በቂ ዋሌት የለም!", show_alert=True)

    elif c.data == "adm_reset_main" and int(uid) == ADMIN_ID:
        for k in data["boards"]: data["boards"][k]["slots"] = {}; refresh_group(k, new=True)
        bot.answer_callback_query(c.id, "ሁሉም ሰሌዳዎች ጸድተዋል!")

    elif c.data == "adm_toggle_main" and int(uid) == ADMIN_ID:
        kb = telebot.types.InlineKeyboardMarkup()
        for k,v in data["boards"].items(): kb.add(telebot.types.InlineKeyboardButton(f"{'🟢' if v['active'] else '🔴'} ሰሌዳ {k}", callback_data=f"tog_{k}"))
        bot.edit_message_text("ሰሌዳ ክፈት/ዝጋ፦", ADMIN_ID, c.message.message_id, reply_markup=kb)

    elif c.data.startswith("tog_") and int(uid) == ADMIN_ID:
        bid = c.data.split("_")[1]
        data["boards"][bid]["active"] = not data["boards"][bid]["active"]
        refresh_group(bid, new=True); bot.answer_callback_query(c.id, "ተቀይሯል!")

@bot.message_handler(content_types=['text', 'photo'])
def handle_msgs(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    u = data["users"][uid]

    if u['step'].startswith("INPUT_AMT_") and int(uid) == ADMIN_ID:
        t_uid = u['step'].split("_")[-1]
        try:
            amt = float(m.text)
            data["users"][t_uid]["wallet"] += amt
            u['step'] = ""; bot.send_message(t_uid, f"✅ `{amt} ETB` ዋሌትዎ ላይ ተጨምሯል።")
            bot.send_message(ADMIN_ID, "✅ ተጨምሯል!"); save_db()
        except: bot.send_message(ADMIN_ID, "⚠️ ቁጥር ብቻ ይጻፉ።")
        return

    if m.text == "💰 የእኔ ዋሌት":
        bot.send_message(uid, f"💵 **የእርስዎ ቀሪ ሂሳብ፦** `{u['wallet']} ETB`", parse_mode="Markdown")

    elif m.text == "🕹 ቁጥር ምረጥ":
        bid = u.get("sel_bid")
        if bid:
            b = data["boards"][bid]
            kb = telebot.types.InlineKeyboardMarkup(row_width=5)
            kb.add(*[telebot.types.InlineKeyboardButton(str(i), callback_data=f"n_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]])
            bot.send_message(uid, f"🔢 {b['name']} ቁጥር ይምረጡ፦", reply_markup=kb)

    elif m.text == "🛠 Admin Panel" and int(uid) == ADMIN_ID:
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("🟢/🔴 ክፈት/ዝጋ", callback_data="adm_toggle_main"),
               telebot.types.InlineKeyboardButton("♻️ ሰሌዳ አጽዳ", callback_data="adm_reset_main"))
        bot.send_message(uid, "🛠 **Admin Control**", reply_markup=kb)

    elif m.content_type == 'photo':
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ 20 ETB", callback_data=f"ok_{uid}_20"),
               telebot.types.InlineKeyboardButton("✍️ መጠን ጻፍ", callback_data=f"manual_{uid}"))
        bot.send_message(ADMIN_ID, f"📩 ደረሰኝ ከ {m.from_user.first_name}", reply_markup=kb)
        bot.send_message(uid, "ደረሰኝዎ እየታየ ነው...")

# --- 6. SERVER ---
@app.route('/')
def home(): return "Bot Active"

if __name__ == "__main__":
    load_db()
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()
    while True:
        try: bot.polling(none_stop=True)
        except: time.sleep(5)
