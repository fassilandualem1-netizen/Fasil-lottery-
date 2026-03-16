Import telebot, re, os, json, time
from flask import Flask
from threading import Thread

# --- 1. SETUP ---
TOKEN = '8721334129:AAEQQi1RtA6PKqTUg59sThJs6sRm_BnBr68'
ADMIN_ID = 8488592165            
GROUP_ID = -1003881429974        
DB_CHANNEL_ID = -1003747262103  

bot = telebot.TeleBot(TOKEN, threaded=False)
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
        if db_id: bot.edit_message_text(payload, DB_CHANNEL_ID, db_id)
        else:
            m = bot.send_message(DB_CHANNEL_ID, payload)
            data["config"]["db_msg_id"] = m.message_id
    except: pass

def load_db():
    try:
        msgs = bot.get_chat_history(DB_CHANNEL_ID, limit=5)
        for m in msgs:
            if m.text and "💾 DB_STORAGE" in m.text:
                loaded = json.loads(m.text.replace("💾 DB_STORAGE", "").strip())
                data.update(loaded); return True
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
    if uid not in data["users"]: data["users"][uid] = {"tks": 0, "wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": None}
    if "wallet" not in data["users"][uid]: data["users"][uid]["wallet"] = 0
    
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    for k, v in data["boards"].items():
        if v["active"]:
            kb.add(telebot.types.InlineKeyboardButton(f"🎰 {v['name']} - ({v['price']} ETB)", callback_data=f"start_sel_{k}"))
    
    main_kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    main_kb.add("🕹 ቁጥር ምረጥ", "🎫 የእኔ እጣ")
    if int(uid) == ADMIN_ID: main_kb.add("🛠 Admin Panel")
    
    bot.send_message(uid, f"🌟 **እንኳን ወደ ፋሲል ልዩ ዕጣ በሰላም መጡ!** 🌟\n\nለመጫወት መጀመሪያ ሰሌዳ ይምረጡ፦", reply_markup=main_kb, parse_mode="Markdown")
    bot.send_message(uid, "👇 ሰሌዳ እዚህ ይምረጡ፦", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def handle_calls(c):
    uid = str(c.from_user.id)
    if c.data.startswith("start_sel_"):
        bid = c.data.split("_")[-1]
        data["users"][uid]["sel_bid"] = bid
        b = data["boards"][bid]
        bot.edit_message_text(f"✅ **{b['name']} ተመርጧል!**\n💰 መደብ፦ `{b['price']} ETB` \n🏦 CBE: `1000584461757` | 📱 Telebirr: `0951381356` \n━━━━━━━━━━━━━\n📩 እባክዎ ደረሰኝ እዚህ ይላኩ።", uid, c.message.message_id, parse_mode="Markdown")

    elif c.data.startswith("ok_") and int(uid) == ADMIN_ID:
        _, t_uid, amt, bid = c.data.split("_")
        price = data["boards"][bid]["price"]
        amt_val = float(amt)
        tks_to_add = int(amt_val // price)
        rem_money = amt_val % price
        data["users"][t_uid]["tks"] += tks_to_add
        data["users"][t_uid]["wallet"] = data["users"][t_uid].get("wallet", 0) + rem_money
        data["users"][t_uid]["sel_bid"] = bid
        data["users"][t_uid]["step"] = "ASK_NAME"
        msg = f"✅ ደረሰኝዎ ጸድቋል!\n🎫 {tks_to_add} እጣ ተሰጥቶዎታል።"
        if rem_money > 0: msg += f"\n💰 ቀሪ {rem_money} ETB ዋሌትዎ ላይ ተቀምጧል።"
        msg += "\n\nአሁን ስምዎን ይጻፉ፦"
        bot.send_message(t_uid, msg)
        bot.delete_message(ADMIN_ID, c.message.message_id); save_db()

    # አድሚኑ ብር እራሱ እንዲጽፍ የሚያደርግ ቁልፍ
    elif c.data.startswith("manual_") and int(uid) == ADMIN_ID:
        _, t_uid, bid = c.data.split("_")
        data["users"][uid]["step"] = f"INPUT_AMT_{t_uid}_{bid}"
        bot.send_message(ADMIN_ID, "✍️ እባክህ ለዚህ ደረሰኝ የሚመዘገበውን የብር መጠን በቁጥር ብቻ ጻፍ (ለምሳሌ፡ 100)፦")

    elif c.data.startswith("no_") and int(uid) == ADMIN_ID:
        t_uid = c.data.split("_")[1]
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("💰 ብር አነስተኛ ነው", callback_data=f"rej_low_{t_uid}"),
               telebot.types.InlineKeyboardButton("❌ ደረሰኙ ልክ አይደለም", callback_data=f"rej_wrong_{t_uid}"))
        bot.edit_message_text("❓ ውድቅ የተደረገበት ምክንያት ምንድነው?", ADMIN_ID, c.message.message_id, reply_markup=kb)

    elif c.data.startswith("rej_") and int(uid) == ADMIN_ID:
        rtype, t_uid = c.data.split("_")[1], c.data.split("_")[2]
        txt = "❌ ደረሰኝዎ ውድቅ ተደርጓል!\nምክንያት፦ ብር አነስተኛ ነው።" if rtype=="low" else "❌ ደረሰኝዎ ውድቅ ተደርጓል!\nምክንያት፦ ደረሰኙ ትክክል አይደለም።"
        bot.send_message(t_uid, txt); bot.delete_message(ADMIN_ID, c.message.message_id)

    elif c.data.startswith("n_"):
        bid = data["users"][uid].get("sel_bid")
        n = c.data.split("_")[1]
        if bid and data["users"][uid]["tks"] > 0:
            if n not in data["boards"][bid]["slots"]:
                data["boards"][bid]["slots"][n] = {"name": data["users"][uid]["name"], "id": uid}
                data["users"][uid]["tks"] -= 1
                refresh_group(bid); bot.answer_callback_query(c.id, f"✅ ቁጥር {n} ተይዟል!")
                bot.delete_message(uid, c.message.message_id)
            else:
                bot.answer_callback_query(c.id, "⚠️ ይቅርታ፣ ይህ ቁጥር አሁን ተይዟል! ሌላ ይምረጡ።", show_alert=True)
        else: bot.answer_callback_query(c.id, "❌ እጣ የለዎትም!", show_alert=True)

    elif c.data == "adm_price_main" and int(uid) == ADMIN_ID:
        kb = telebot.types.InlineKeyboardMarkup()
        for k in data["boards"]: kb.add(telebot.types.InlineKeyboardButton(f"ሰሌዳ {k} ዋጋ", callback_data=f"aprice_{k}"))
        bot.edit_message_text("ዋጋ ለመቀየር ሰሌዳ ይምረጡ፦", ADMIN_ID, c.message.message_id, reply_markup=kb)
    
    elif c.data.startswith("aprice_") and int(uid) == ADMIN_ID:
        bid = c.data.split("_")[1]
        data["users"][uid]["step"] = f"SET_PRICE_{bid}"
        bot.send_message(uid, f"💵 ለሰሌዳ {bid} አዲስ ዋጋ ያስገቡ፦")

    elif c.data == "adm_prizes_main" and int(uid) == ADMIN_ID:
        kb = telebot.types.InlineKeyboardMarkup()
        for k in data["boards"]: kb.add(telebot.types.InlineKeyboardButton(f"ሰሌዳ {k} ሽልማት", callback_data=f"aprize_{k}"))
        bot.edit_message_text("ሽልማት ለመቀየር ሰሌዳ ይምረጡ፦", ADMIN_ID, c.message.message_id, reply_markup=kb)

    elif c.data.startswith("aprize_") and int(uid) == ADMIN_ID:
        bid = c.data.split("_")[1]
        data["users"][uid]["step"] = f"SET_PRIZES_{bid}"
        bot.send_message(uid, f"🏆 ለሰሌዳ {bid} ሽልማቶችን በኮማ ይጻፉ (ምሳሌ: 500,300,100)፦")

    elif c.data == "adm_reset_main" and int(uid) == ADMIN_ID:
        kb = telebot.types.InlineKeyboardMarkup()
        for k in data["boards"]: kb.add(telebot.types.InlineKeyboardButton(f"ሰሌዳ {k} አጽዳ", callback_data=f"areset_{k}"))
        bot.edit_message_text("የትኛውን ሰሌዳ ማጽዳት ይፈልጋሉ?", ADMIN_ID, c.message.message_id, reply_markup=kb)
    
    elif c.data.startswith("areset_") and int(uid) == ADMIN_ID:
        bid = c.data.split("_")[1]; data["boards"][bid]["slots"] = {}; refresh_group(bid, new=True); bot.answer_callback_query(c.id, "ጸድቷል!")
    
    elif c.data == "adm_toggle_main" and int(uid) == ADMIN_ID:
        kb = telebot.types.InlineKeyboardMarkup()
        for k, v in data["boards"].items(): kb.add(telebot.types.InlineKeyboardButton(f"{'🟢' if v['active'] else '🔴'} ሰሌዳ {k}", callback_data=f"tog_{k}"))
        bot.edit_message_text("ሰሌዳ ለመክፈት/ለመዝጋት ይጫኑ፦", ADMIN_ID, c.message.message_id, reply_markup=kb)
    
    elif c.data.startswith("tog_") and int(uid) == ADMIN_ID:
        bid = c.data.split("_")[1]; data["boards"][bid]["active"] = not data["boards"][bid]["active"]; refresh_group(bid, new=True)

@bot.message_handler(content_types=['text', 'photo'])
def handle_msgs(m):
    uid = str(m.from_user.id)
    u = data["users"].get(uid)
    if not u: return

    # አድሚኑ ብር ሲጽፍ መቀበያ
    if u['step'].startswith("INPUT_AMT_") and int(uid) == ADMIN_ID:
        _, _, t_uid, bid = u['step'].split("_")
        try:
            amt_val = float(m.text)
            price = data["boards"][bid]["price"]
            tks_to_add = int(amt_val // price)
            rem_money = amt_val % price
            data["users"][t_uid]["tks"] += tks_to_add
            data["users"][t_uid]["wallet"] = data["users"][t_uid].get("wallet", 0) + rem_money
            data["users"][t_uid]["sel_bid"] = bid
            data["users"][t_uid]["step"] = "ASK_NAME"
            u['step'] = ""
            msg = f"✅ ደረሰኝዎ ጸድቋል!\n🎫 {tks_to_add} እጣ ተሰጥቶዎታል።"
            if rem_money > 0: msg += f"\n💰 ቀሪ {rem_money} ETB ዋሌትዎ ላይ ተቀምጧል።"
            bot.send_message(t_uid, msg + "\n\nአሁን ስምዎን ይጻፉ፦")
            bot.send_message(ADMIN_ID, "✅ በተሳካ ሁኔታ ተመዝግቧል!"); save_db()
        except: bot.send_message(ADMIN_ID, "⚠️ እባክህ ቁጥር ብቻ ጻፍ።")
        return

    if u['step'].startswith("SET_PRICE_") and int(uid) == ADMIN_ID:
        bid = u['step'].split("_")[-1]
        try:
            data["boards"][bid]["price"] = int(m.text)
            u['step'] = ""; save_db(); refresh_group(bid)
            bot.send_message(uid, f"✅ የሰሌዳ {bid} ዋጋ ተቀይሯል!")
        except: bot.send_message(uid, "⚠️ ቁጥር ብቻ ያስገቡ።")

    elif u['step'].startswith("SET_PRIZES_") and int(uid) == ADMIN_ID:
        bid = u['step'].split("_")[-1]
        try:
            p_list = [int(x.strip()) for x in m.text.split(',')]
            if len(p_list) == 3:
                data["boards"][bid]["prizes"] = p_list
                u['step'] = ""; save_db(); refresh_group(bid)
                bot.send_message(uid, f"✅ የሰሌዳ {bid} ሽልማቶች ተቀምጠዋል!")
            else: bot.send_message(uid, "⚠️ 3 ሽልማቶችን በኮማ ይለዩ።")
        except: bot.send_message(uid, "⚠️ ስህተት! ምሳሌ፦ 500,300,100")

    elif m.text == "🎫 የእኔ እጣ":
        u_wallet = u.get("wallet", 0)
        msg = f"🎫 **የእርስዎ የዕጣ መረጃ**\n━━━━━━━━━━━━━\n👤 ስም፦ {u['name']}\n💰 ቀሪ እጣዎች፦ `{u['tks']}`\n💵 ዋሌት፦ `{u_wallet} ETB` \n━━━━━━━━━━━━━\n"
        found = False
        for bid, b in data["boards"].items():
            user_nums = [n for n, info in b["slots"].items() if info["id"] == uid]
            if user_nums:
                found = True
                msg += f"📍 **{b['name']}**፦ `{', '.join(user_nums)}` ቁጥሮች\n"
        if not found: msg += "⚠️ እስካሁን ምንም ቁጥር አልያዙም።"
        bot.send_message(uid, msg, parse_mode="Markdown")

    elif m.text == "🕹 ቁጥር ምረጥ":
        bid = u.get("sel_bid")
        if u['tks'] > 0 and bid:
            b = data["boards"][bid]
            kb = telebot.types.InlineKeyboardMarkup(row_width=5)
            kb.add(*[telebot.types.InlineKeyboardButton(str(i), callback_data=f"n_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]])
            bot.send_message(uid, f"🔢 {b['name']} ቁጥር ይምረጡ፦", reply_markup=kb)
        else: bot.send_message(uid, "❌ መጀመሪያ ሰሌዳ መርጠው ደረሰኝ ይላኩ።")

    elif u['step'] == "ASK_NAME":
        u['name'] = m.text; u['step'] = ""; save_db()
        bot.send_message(uid, "✅ ተመዝግቧል! አሁን '🕹 ቁጥር ምረጥ' ይጫኑ።")

    elif m.text == "🛠 Admin Panel" and int(uid) == ADMIN_ID:
        kb = telebot.types.InlineKeyboardMarkup(row_width=1)
        kb.add(telebot.types.InlineKeyboardButton("💵 ዋጋ ቀይር", callback_data="adm_price_main"),
               telebot.types.InlineKeyboardButton("🏆 ሽልማት ወስን", callback_data="adm_prizes_main"),
               telebot.types.InlineKeyboardButton("♻️ ሰሌዳ አጽዳ (Reset)", callback_data="adm_reset_main"),
               telebot.types.InlineKeyboardButton("🟢/🔴 ሰሌዳ ክፈት/ዝጋ", callback_data="adm_toggle_main"))
        bot.send_message(uid, "🛠 **የአድሚን መቆጣጠሪያ ክፍል**", reply_markup=kb)

    elif m.content_type == 'photo' or (m.text and re.search(r"(FT|DCA|[0-9]{10})", m.text)):
        bid = u.get("sel_bid")
        if not bid: bot.send_message(uid, "⚠️ መጀመሪያ ሰሌዳ ይምረጡ (/start)"); return
        price = data["boards"][bid]["price"]
        sent_amount = price 
        if m.text:
            amt_match = re.search(r"(\d+)", m.text)
            if amt_match: 
                sent_amount = float(amt_match.group(1))
                if sent_amount < price:
                    bot.send_message(uid, f"❌ የላኩት ብር ከሰሌዳው ዋጋ ({price} ETB) በታች ስለሆነ ደረሰኙ ውድቅ ተደርጓል።"); return
        
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"ok_{uid}_{sent_amount}_{bid}"),
               telebot.types.InlineKeyboardButton("✅ በቁጥር አጽድቅ", callback_data=f"manual_{uid}_{bid}"),
               telebot.types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"no_{uid}"))
        
        if m.content_type == 'photo': bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"📩 ፎቶ ከ {m.from_user.first_name}\nሰሌዳ {bid}\nየተላከው ብር፡ {sent_amount}", reply_markup=kb)
        else: bot.send_message(ADMIN_ID, f"📩 SMS ከ {m.from_user.first_name}\nሰሌዳ {bid}\nየተላከው ብር፡ {sent_amount}\n`{m.text}`", reply_markup=kb, parse_mode="Markdown")
        bot.send_message(uid, "📩 ደረሰኝዎ ደርሶናል! እባክዎን ከ 1 እስከ 5 ደቂቃ ባለው ጊዜ እስኪረጋገጥ ድረስ በትዕግስት ይታገሱን። 🙏")

# --- 6. SERVER & POLLING ---
@app.route('/')
def home(): return "Bot Active"

if __name__ == "__main__":
    load_db()
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
    bot.infinity_polling(timeout=25, long_polling_timeout=5)