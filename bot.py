import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time
from supabase import create_client, Client

# --- 1. Web Hosting (Railway/Render Port Setup) ---
app = Flask('')

@app.route('/')
def home():
    return "Fasil Lotto System is Active!"

def run():
    # ሰርቨሩ የሚሰጠውን PORT ይጠቀማል፣ ከሌለ 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት መረጃዎች (ከ Variables tab ይነበባሉ) ---
# እነዚህን በ Railway 'Variables' ውስጥ ማስገባትህን እርግጠኛ ሁን
TOKEN = os.environ.get("TOKEN", "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# የ Supabase ግንኙነት
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

MY_ID = 8488592165
ASSISTANT_ID = 7072611117
GROUP_ID = -1003881429974
DB_CHANNEL_ID = -1003747262103
ADMIN_IDS = [MY_ID, ASSISTANT_ID]

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323"}
}

# --- 3. ዳታቤዝ አያያዝ ---
data = {
    "users": {},
    "current_shift": "me",
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "1ኛ 200, 2ኛ 100, 3ኛ 50", "active": True, "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "1ኛ 400, 2ኛ 200, 3ኛ 100", "active": True, "slots": {}},
        "3": {"max": 100, "price": 200, "prize": "1ኛ 800, 2ኛ 400, 3ኛ 200", "active": True, "slots": {}}
    },
    "pinned_msgs": {"1": None, "2": None, "3": None}
}

def load_data():
    global data
    try:
        res = supabase.table("bot_data").select("content").eq("id", "main_db").execute()
        if res.data:
            data.update(res.data['content'])
            print("✅ Data Loaded")
    except Exception as e:
        print(f"❌ Load Error: {e}")

def save_data():
    try:
        supabase.table("bot_data").upsert({"id": "main_db", "content": data}).execute()
        print("✅ Save Success")
    except Exception as e:
        print(f"❌ Save Error: {e}")

load_data()

# --- 4. ቦት ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    if uid not in data["users"]:
        data["users"][uid] = {"name": message.from_user.first_name, "wallet": 0}
        save_data()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የገዛኋቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS:
        markup.add("⚙️ Admin Settings")
    
    bot.send_message(uid, f"👋 <b>እንኳን መጡ {message.from_user.first_name}!</b>", reply_markup=markup)

# ቦት ስራ እንዲጀምር
if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.polling(none_stop=True)
