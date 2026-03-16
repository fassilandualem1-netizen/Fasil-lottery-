import telebot
import json
import re
from threading import Thread
from flask import Flask

# --- 1. CONFIG (ቅንጅቶች) ---
TOKEN = '8721334129:AAEQQi1RtA6PKqTUg59sThJs6sRm_BnBr68'
ADMIN_ID = 8488592165            
GROUP_ID = -1003881429974        
DB_CHANNEL_ID = -1003747262103  
CBE_ACCOUNT = "1000584461757"
TELEBIRR_NUMBER = "0951381356"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# --- 2. DATABASE LOGIC (መረጃ ማከማቻ) ---
data = {
    "config": {"db_msg_id": None},
    "boards": {
        "1": {"name": "ሰሌዳ 1", "max": 100, "active": True, "slots": {}, "msg_id": None, "prizes": [500, 300, 100], "price": 50},
        "2": {"name": "ሰሌዳ 2", "max": 50, "active": True, "slots": {}, "msg_id": None, "prizes": [250, 150, 50], "price": 20}
    },
    "users": {}
}

def save_db():
    try:
        payload = "💾 DB_STORAGE " + json.dumps(data)
        db_id = data["config"].get("db_msg_id")
        if db_id: 
            bot.edit_message_text(payload, DB_CHANNEL_ID, db_id)
        else:
            m = bot.send_message(DB_CHANNEL_ID, payload)
            data["config"]["db_msg_id"] = m.message_id
    except: pass

def load_db():
    try:
        chat = bot.get_chat(DB_CHANNEL_ID)
        if chat.pinned_message:
            raw = chat.pinned_message.text.replace("💾 DB_STORAGE", "").strip()
            data.update(json.loads(raw))
    except: pass

# --- 3. REFRESH GROUP BOARD (ሰሌዳውን ግሩፕ ላይ ማደሻ) ---
def refresh_group(bid, new=False):
    b = data["boards"][bid]
    status = "🟢 ክፍት" if b["active"] else "🔴 ዝግ"
    txt = f"🔥 **{b['name']}** {status}\n━━━━━━━━━━━━━\n"
    txt += f"💵 **መደብ:** `{b['price']} ETB` | 🎁 **ሽልማት:** `{sum(b['prizes'])} ETB` \n━━━━━━━━━━━━━\n"
    for i in range(1, b["max"] + 1):
        n = str(i)
        txt += f"{i:02d}.{b['slots'][n]['name'][:4]}🏆 " if n in b["slots"] else f"{i:02d}.⚪️ "
        if i % 3 == 0: txt += "\n"
    txt += f"\n💰 🥇{b['prizes'][0]} | 🥈{b['prizes'][1]} | 🥉{b['prizes'][2]}\n━━━━━━━━━━━━━\n🕹 @{bot.get_me().username}"
    
    try:
        if new or not b.get("msg_id"):
            m = bot.send_message(GROUP_ID, txt, parse_mode="Markdown")
            b["msg_id"] = m.message_id
            bot.pin_chat_message(GROUP_ID, m.message_id)
        else:
            bot.edit_message_text(txt, GROUP_ID, b["msg_id"], parse_mode="Markdown")
    except: pass
    save_db()

# --- 4. CALLBACK HANDLERS (አዝራሮች) ---
@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(c):
    uid = str(c.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "tks": 0, "name": c.from_user.first_name, "step": ""}
    u = data["users"][uid]

    # ሰሌዳ ኦን/ኦፍ (Photo 691)
    if c.data.startswith("tog_") and int(uid) == ADMIN_ID:
        bid = c.data.split("_")[1]
        data["boards"][bid]["active"] = not data["boards"][bid]["active"]
        refresh_group(bid)
        bot.answer_callback_query(c.id, f"ሰሌዳ {bid} ተቀይሯል!")

    # ሰሌዳ መምረጥ
    elif c.data.startswith("sel_"):
        u["sel_bid"] = c.data.split("_")[1]
        bot.edit_message_text(f"✅ ሰሌዳ {u['sel_bid']} ተመርጧል!", uid, c.message.message_id)

    # አጽድቅ (Admin)
    elif c.data.startswith("ok_"):
        _, t_uid, amt, bid = c.data.split("_")
        data["users"][t_uid]["wallet"] += float(amt)
        save_db()
        bot.send_message(t_uid, f"✅ {amt} ETB ዋሌትዎ ላይ ተጨምሯል!")
        bot.delete_message(ADMIN_ID, c.message.message_id)

# --- 5. MESSAGE HANDLERS (መልእክቶች) ---
@bot.message_handler(content_types=['text', 'photo'])
def handle_msgs(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"wallet": 0, "tks": 0, "name": m.from_user.first_name, "step": ""}
    u = data["users"][uid]

    # አድሚን ብር ሲያስገባ (Photo 692)
    if u['step'].startswith("INPUT_AMT_") and int(uid) == ADMIN_ID:
        _, _, t_uid, bid = u['step'].split("_")
        try:
            amt_val = float(m.text)
            price = data["boards"][bid]["price"]
            tks_to_add = int(amt_val // price)
            rem_money = amt_val % price
            
            data["users"][t_uid]["tks"] += tks_to_add
            data["users"][t_uid]["wallet"] += rem_money
            u['step'] = ""
            save_db()
            bot.send_message(t_uid, f"✅ ደረሰኝዎ ጸድቋል!\n🎫 {tks_to_add} እጣ ተሰጥቶዎታል።\n💰 ቀሪ {rem_money} ETB ዋሌትዎ ገብቷል።")
            bot.send_message(ADMIN_ID, "✅ ተመዝግቧል!")
        except: bot.send_message(ADMIN_ID, "⚠️ እባክዎ ቁጥር ብቻ ይጻፉ!")
        return

    # ዋጋ መቀየር (Photo 693)
    if u['step'].startswith("SET_PRICE_") and int(uid) == ADMIN_ID:
        bid = u['step'].split("_")[-1]
        try:
            data["boards"][bid]["price"] = int(m.text)
            u['step'] = ""; save_db(); refresh_group(bid)
            bot.send_message(uid, f"✅ የሰሌዳ {bid} ዋጋ ተቀይሯል!")
        except: bot.send_message(uid, "⚠️ ቁጥር ብቻ ያስገቡ!")
        return

    # ሜኑዎች
    if m.text == "🎰 ሰሌዳ ምረጥ":
        kb = telebot.types.InlineKeyboardMarkup()
        for k, v in data["boards"].items():
            if v["active"]: kb.add(telebot.types.InlineKeyboardButton(f"{v['name']} ({v['price']} ETB)", callback_data=f"sel_{k}"))
        bot.send_message(uid, "ሰሌዳ ይምረጡ፦", reply_markup=kb)

    elif m.text == "🎫 የእኔ እጣ": # Photo 694
        u_wallet = u.get("wallet", 0)
        msg = f"🎫 **የእርስዎ የዕጣ መረጃ**\n👤 ስም፦ {u['name']}\n💰 ዋሌት፦ {u_wallet} ETB\n"
        found = False
        for bid, b in data["boards"].items():
            user_nums = [n for n, info in b["slots"].items() if info["id"] == uid]
            if user_nums:
                found = True
                msg += f"📍 **{b['name']}**፦ `{', '.join(user_nums)}` ቁጥሮች\n"
        if not found: msg += "⚠️ እስካሁን ምንም ቁጥር አልያዙም።"
        bot.send_message(uid, msg, parse_mode="Markdown")

    elif m.text == "🕹 ቁጥር ምረጥ": # Photo 695
        bid = u.get("sel_bid")
        if u.get('tks', 0) > 0 and bid:
            b = data["boards"][bid]
            kb = telebot.types.InlineKeyboardMarkup(row_width=5)
            btns = [telebot.types.InlineKeyboardButton(str(i), callback_data=f"n_{i}") for i in range(1, b["max"]+1) if str(i) not in b["slots"]]
            kb.add(*btns)
            bot.send_message(uid, f"🔢 {b['name']} ቁጥር ይምረጡ፦", reply_markup=kb)
        else: bot.send_message(uid, "❌ አስቀድመው ደረሰኝ በመላክ እጣ ማስመዝገብ አለብዎት!")

    elif m.text == "🛠 Admin Panel" and int(uid) == ADMIN_ID: # Photo 695/696
        kb = telebot.types.InlineKeyboardMarkup(row_width=1)
        kb.add(telebot.types.InlineKeyboardButton("💵 ዋጋ ቀይር", callback_data="adm_price_main"),
               telebot.types.InlineKeyboardButton("🏆 ሽልማት ወስን", callback_data="adm_prizes_main"),
               telebot.types.InlineKeyboardButton("♻️ ሰሌዳ አጽዳ (Reset)", callback_data="adm_reset_main"),
               telebot.types.InlineKeyboardButton("🟢/🔴 ሰሌዳ ክፈት/ዝጋ", callback_data="adm_toggle_main"))
        bot.send_message(uid, "🛠 **የአድሚን መቆጣጠሪያ ክፍል**", reply_markup=kb)

    # ደረሰኝ መቀበያ (Photo 696/697)
    elif m.content_type == 'photo' or (m.text and re.search(r"(FT|DCA|[0-9]{10})", m.text)):
        bid = u.get("sel_bid")
        if not bid: bot.send_message(uid, "⚠️ መጀመሪያ ሰሌዳ ይምረጡ (/start)"); return
        
        price = data["boards"][bid]["price"]
        sent_amount = price # Default
        if m.text:
            amt_match = re.search(r"(\d+)", m.text)
            if amt_match: sent_amount = float(amt_match.group(1))
        
        if sent_amount < price:
            bot.send_message(uid, f"❌ የላኩት ብር ከሰሌዳው ዋጋ ({price} ETB) በታች ነው።"); return
        
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"ok_{uid}_{sent_amount}_{bid}"),
               telebot.types.InlineKeyboardButton("✅ በቁጥር አጽድቅ", callback_data=f"manual_{uid}_{bid}"),
               telebot.types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"no_{uid}"))
        
        if m.content_type == 'photo':
            bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"📩 ፎቶ ከ {u['name']}\nሰሌዳ {bid}\nብር፦ {sent_amount}", reply_markup=kb)
        else:
            bot.send_message(ADMIN_ID, f"📩 SMS ከ {u['name']}\nሰሌዳ {bid}\nብር፦ {sent_amount}\n`{m.text}`", reply_markup=kb)
        bot.send_message(uid, "📩 ደረሰኝዎ ደርሶናል! ከ1-5 ደቂቃ በትዕግስት ይጠብቁ። 🙏")

# --- 6. SERVER & POLLING (Photo 698/699) ---
@app.route('/')
def home(): return "Bot Active"

if __name__ == "__main__":
    load_db()
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
    bot.infinity_polling(timeout=25, long_polling_timeout=15)
