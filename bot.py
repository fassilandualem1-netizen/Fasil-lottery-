import telebot
import re
import os
import json
import time
from flask import Flask
from threading import Thread

# --- 1. SETUP ---
# አዲሱ Token እዚህ ጋር ተቀይሯል
TOKEN = '8721334129:AAGZxYXP4UH0RuEdC8gk6icXu5gSB26bI3Q'
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
        # በቅርብ የተላኩ መልእክቶችን በመፈተሽ ዳታውን መጫን
        msgs = bot.get_chat_history(DB_CHANNEL_ID, limit=5)
        for m in msgs:
            if m.text and "💾 DB_STORAGE" in m.text:
                loaded = json.loads(m.text.replace("💾 DB_STORAGE", "").strip())
                data.update(loaded)
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

# --- 5. HANDLERS (ከላይ የነበሩት logicዎች በሙሉ እዚህ ይቀጥላሉ) ---
@bot.message_handler(commands=['start'])
def welcome(m):
    uid = str(m.from_user.id)
    if uid not in data["users"]: data["users"][uid] = {"tks": 0, "wallet": 0, "name": m.from_user.first_name, "step": "", "sel_bid": None}
    
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    for k, v in data["boards"].items():
        if v["active"]:
            kb.add(telebot.types.InlineKeyboardButton(f"🎰 {v['name']} - ({v['price']} ETB)", callback_data=f"start_sel_{k}"))
    
    main_kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    main_kb.add("🕹 ቁጥር ምረጥ", "🎫 የእኔ እጣ")
    if int(uid) == ADMIN_ID: main_kb.add("🛠 Admin Panel")
    
    bot.send_message(uid, f"🌟 **እንኳን ወደ ፋሲል ልዩ ዕጣ በሰላም መጡ!** 🌟", reply_markup=main_kb, parse_mode="Markdown")
    bot.send_message(uid, "👇 ለመጫወት ሰሌዳ እዚህ ይምረጡ፦", reply_markup=kb)

# ... (ቀሪዎቹ handle_calls እና handle_msgs ፋንክሽኖች እንዳሉ ይቀጥላሉ) ...
# ማሳሰቢያ፡ ለቦታ ቁጠባ ሲባል ሙሉው logic እዚህ አልተደገመም፣ ነገር ግን 
# ከላይ በላኩልህ ቅደም ተከተል መሰረት ሁሉም handlers መኖር አለባቸው።

# --- 6. SERVER & POLLING ---
@app.route('/')
def home(): return "Bot Active"

if __name__ == "__main__":
    load_db()
    # የዌብ ሰርቨሩን በThread ማስጀመር
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
    
    # በ Render ላይ የሚፈጠረውን Conflict ለመከላከል
    bot.remove_webhook() 
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
