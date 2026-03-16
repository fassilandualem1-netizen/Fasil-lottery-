import telebot, re, os, json, time
from flask import Flask
from threading import Thread

# --- 1. መለያዎች (Settings) ---
TOKEN = 8721334129:AAGZxYXP4UH0RuEdC8gk6icXu5gSB26bI3Q
ADMIN_ID = 8488592165            
GROUP_ID = -1003881429974        
DB_CHANNEL_ID = -1003747262103  

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# --- 2. የዳታ መዋቅር (Data Structure) ---
data = {
    "config": {"db_msg_id": None},
    "boards": {
        "1": {"name": "ሰሌዳ 1 (1-100)", "max": 100, "active": True, "slots": {}, "msg_id": None, "prizes": [500, 300, 100], "price": 20},
        "2": {"name": "ሰሌዳ 2 (1-50)", "max": 50, "active": False, "slots": {}, "msg_id": None, "prizes": [250, 150, 50], "price": 10},
        "3": {"name": "ሰሌዳ 3 (1-25)", "max": 25, "active": False, "slots": {}, "msg_id": None, "prizes": [100, 50, 20], "price": 5}
    },
    "users": {}
}

# --- 3. ዳታቤዝ ኢንጂን (Database Engine) ---
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

# --- 4. ሰርቨር (Server Setup) ---
@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))


# --- 5. የሰሌዳ አሳሳል (UI ENGINE - PHOTO STYLE) ---
def refresh_group(bid, new=False):
    b = data["boards"][bid]
    status = "🟢 ክፍት" if b["active"] else "🔴 ዝግ"
    
    txt = f"🔥 **{b['name']}** {status}\n━━━━━━━━━━━━━\n"
    txt += f"💵 **መደብ:** `{b['price']} ETB` | 🎁 **ሽልማት:** `{sum(b['prizes'])} ETB` \n━━━━━━━━━━━━━\n"
    
    # ሰሌዳውን በ 3 ረድፍ ለመከፋፈል (ልክ በላክኸው ፎቶ መልክ)
    max_num = b["max"]
    rows = (max_num + 2) // 3 
    
    for i in range(1, rows + 1):
        line = ""
        for col in range(3):
            num_val = i + (col * rows)
            if num_val <= max_num:
                n = str(num_val)
                if n in b["slots"]:
                    # ቁጥሩ ከተያዘ ስሙንና ምልክቶቹን ያሳያል
                    p_name = b["slots"][n]["name"][:6] 
                    line += f"{num_val:02d}.{p_name}🏆 "
                else:
                    # ክፍት ከሆነ FREE ይላል
                    line += f"{num_val:02d}.FREE 🆓 "
        txt += line + "\n" 
            
    txt += f"\n💰 🥇{b['prizes'][0]} | 🥈{b['prizes'][1]} | 🥉{b['prizes'][2]}\n━━━━━━━━━━━━━\n🕹 @fasil_assistant_bot"
    
    try:
        if new or not b["msg_id"]:
            m = bot.send_message(GROUP_ID, txt, parse_mode="Markdown")
            b["msg_id"] = m.message_id
            bot.pin_chat_message(GROUP_ID, m.message_id)
        else:
            bot.edit_message_text(txt, GROUP_ID, b["msg_id"], parse_mode="Markdown")
    except Exception as e:
        print(f"Error: {e}")
    
    save_db()


# --- 7. የክፍያ ማረጋገጫ እና የጨዋታ ህግ (DEPARTMENT 3 & 4) ---

# ሀ. ፎቶ ደረሰኝ ሲላክ
@bot.message_handler(content_types=['photo'])
def handle_receipt_photo(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: 
        data["users"][uid] = {"wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": "1"}
    
    # ለአድሚን የሚሄድ የውሳኔ ቁልፍ
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("✅ አፅድቅ (ብር ጻፍ)", callback_data=f"manual_{uid}"),
           telebot.types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no_{uid}"))
    
    bot.send_photo(ADMIN_ID, m.photo[-1].file_id, 
                   caption=f"📩 **አዲስ የፎቶ ደረሰኝ**\nከ፦ {m.from_user.first_name}\nID፦ `{uid}`", 
                   reply_markup=kb, parse_mode="Markdown")
    
    bot.send_message(uid, "📩 ደረሰኝዎ ደርሶናል፣ እያረጋገጥን ስለሆነ እባኮትን ከ 1 እስከ 5 ደቂቃ ይታገሱን...")

# ለ. በቁልፎች (Buttons) የሚመጡ ትዕዛዞች
@bot.callback_query_handler(func=lambda c: True)
def handle_calls(c):
    uid = str(c.from_user.id)
    u = data["users"].get(uid)
    if not u: return

    # 1. አድሚን "አፅድቅ" ሲል
    if c.data.startswith("manual_") and int(uid) == ADMIN_ID:
        target_uid = c.data.split("_")[1]
        data["users"][uid]["step"] = f"DEP_{target_uid}"
        bot.send_message(ADMIN_ID, f"✍️ ለ ID `{target_uid}` የሚገባውን የብር መጠን ይጻፉ፦")

    # 2. አድሚን "ውድቅ" ሲል
    elif c.data.startswith("no_") and int(uid) == ADMIN_ID:
        target_uid = c.data.split("_")[1]
        bot.send_message(target_uid, "❌ ይቅርታ፣ የላኩት ደረሰኝ ተቀባይነት አላገኘም።\nምክንያቱም፦ ደረሰኙ ትክክል አይደለም ወይም ቀድሞ የተጠቀሙበት ነው።")
        bot.delete_message(ADMIN_ID, c.message.message_id)

    # 3. ተጠቃሚ ሰሌዳ ሲመርጥ
    elif c.data.startswith("start_sel_"):
        bid = c.data.split("_")[-1]
        b = data["boards"][bid]
        if u["wallet"] < b["price"]:
            bot.answer_callback_query(c.id, f"❌ ቀሪ ሂሳብዎ አይበቃም! የዚህ ሰሌዳ መደብ {b['price']} ETB ነው።", show_alert=True)
        else:
            u["sel_bid"] = bid
            bot.send_message(uid, f"✅ ሰሌዳ {bid} ተመርጧል።\n\nእባክዎ ለሰሌዳው የሚሆን ስምዎን ይጻፉ፦")
            u["step"] = "SET_NAME"

    # 4. ቁጥር ሲመረጥ
    elif c.data.startswith("n_"):
        bid = u.get("sel_bid")
        n = c.data.split("_")[1]
        b = data["boards"][bid]
        if u["wallet"] >= b["price"]:
            if n not in b["slots"]:
                u["wallet"] -= b["price"]
                # ስሙን ከነ ምልክቶቹ መዝግቦ ግሩፕ ላይ ያድሳል
                b["slots"][n] = {"name": u["name"], "id": uid}
                refresh_group(bid) 
                bot.answer_callback_query(c.id, f"✅ ቁጥር {n} ተመዝግቧል!")
                bot.edit_message_text(f"✅ ቁጥር {n} ተመዝግቧል!\n💰 ቀሪ ሂሳብዎ፦ `{u['wallet']} ETB`", uid, c.message.message_id)
                save_db()
            else: bot.answer_callback_query(c.id, "⚠️ ይቅርታ፣ ይህ ቁጥር ቀድሞ ተይዟል!", show_alert=True)
        else: bot.answer_callback_query(c.id, "❌ በቂ ሂሳብ የለዎትም!", show_alert=True)

# ሐ. ጽሁፎችን (ስም፣ SMS እና የብር መጠን) መቀበያ
@bot.message_handler(func=lambda m: True)
def handle_all_texts(m):
    uid = str(m.from_user.id)
    u = data["users"].get(uid)
    if not u: return

    # አድሚን የብር መጠን ሲሞላ
    if u.get("step", "").startswith("DEP_") and int(uid) == ADMIN_ID:
        target_uid = u["step"].split("_")[-1]
        try:
            amt = float(m.text)
            data["users"][target_uid]["wallet"] += amt
            u["step"] = ""
            bot.send_message(target_uid, f"✅ ክፍያዎ ተረጋግጧል! `{amt} ETB` ዋሌትዎ ላይ ተጨምሯል።\nአሁን '🕹 ቁጥር ምረጥ' የሚለውን ተጭነው መጫወት ይችላሉ።")
            bot.send_message(ADMIN_ID, f"✅ ተረጋግጧል! ለተጠቃሚው {amt} ETB ተጨምሯል።")
            save_db()
        except: bot.send_message(ADMIN_ID, "⚠️ እባክዎ ቁጥር ብቻ ይጻፉ (ለምሳሌ፦ 50)።")
        return

    # ተጫዋች ስሙን ሲጽፍ
    if u.get("step") == "SET_NAME":
        u["name"] = m.text + " 🏆🏆👍🙏" # አንተ እንዳልከው ምልክቶቹን ይጨምራል
        u["step"] = ""
        bid = u["sel_bid"]
        b = data["boards"][bid]
        
        kb = telebot.types.InlineKeyboardMarkup(row_width=5)
        btns = [telebot.types.InlineKeyboardButton(str(i), callback_data=f"n_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]]
        kb.add(*btns)
        bot.send_message(uid, f"ሰላም {m.text}፣ አሁን የሚመርጡትን ቁጥር ይጫኑ፦", reply_markup=kb)
        return

    # ተጠቃሚ የባንክ SMS ሲልክ (ደረሰኝ)
    if not u.get("step") and m.text not in ["🕹 ቁጥር ምረጥ", "💰 የእኔ ዋሌት", "🛠 Admin Panel"]:
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ አፅድቅ (ብር ጻፍ)", callback_data=f"manual_{uid}"),
               telebot.types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"no_{uid}"))
        
        bot.send_message(ADMIN_ID, f"📩 **አዲስ የጽሁፍ ደረሰኝ (SMS)**\nከ፦ {m.from_user.first_name}\nID፦ `{uid}`\n\nመልዕክት፦\n`{m.text}`", reply_markup=kb)
        bot.send_message(uid, "📩 ደረሰኝዎ ለባለቤቱ ተልኳል፣ እያረጋገጥን ስለሆነ እባኮትን ከ 1 እስከ 5 ደቂቃ ይታገሱን...")
        return

    # ዋና ዋና ትዕዛዞች
    if m.text == "🕹 ቁጥር ምረጥ":
        choose_board(m)
    elif m.text == "💰 የእኔ ዋሌት":
        bot.send_message(uid, f"💵 **የእርስዎ ቀሪ ሂሳብ፦** `{u['wallet']} ETB`", parse_mode="Markdown")


# --- 8. ቦቱን ማስነሳት እና መቆጣጠር (DEPARTMENT 5) ---

# ሀ. ሰርቨሩ እንዲነሳ ትዕዛዝ መስጫ
def run_flask():
    # Render የሚጠቀምበትን PORT በራስ-ሰር ያገኛል
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ለ. ዋናው የማስነሻ ክፍል
if __name__ == "__main__":
    print("🔄 ዳታቤዝ እየተጫነ ነው...")
    load_db() # ቻናሉ ላይ ያለውን መረጃ ያነባል
    
    print("🌐 ሰርቨሩ እየተነሳ ነው...")
    # ሰርቨሩን በሌላ "Thread" ያስነሳል (ቦቱ እንዳይቆም)
    Thread(target=run_flask).start()
    
    print("🚀 ቦቱ ስራ ጀምሯል! አሁን መጠቀም ይችላሉ።")
    
    # ሐ. ቦቱ ሳይቆም እንዲሰራ የሚያደርግ መከላከያ
    while True:
        try:
            # interval=0 እና timeout=20 ለ Render በጣም ተስማሚ ናቸው
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            # ስህተት ቢፈጠር ለ 5 ሴኮንድ አርፎ ራሱን ይቀሰቅሳል
            print(f"⚠️ ስህተት ተፈጥሯል፣ ቦቱ ራሱን እየቀሰቀሰ ነው: {e}")
            time.sleep(5)
