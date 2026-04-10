import telebot
from telebot import types
import json, os, time
from flask import Flask
from threading import Thread
from upstash_redis import Redis

# --- 1. Web Hosting (Render እንዲቀበለው) ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Assistant Bot is Live!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት መረጃዎች ---
TOKEN = "8757888085:AAHorIou6gWJjUgvgNeJlC2HbkNq2Wohizs"
MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003749311489
DB_CHANNEL_ID = -1003747262103

ADMIN_IDS = [MY_ID, ASSISTANT_ID]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Redis Connection
REDIS_URL = "https://sunny-ferret-79578.upstash.io"
REDIS_TOKEN = "gQAAAAAAATbaAAIncDE4MTQ2MThjMjVjYjI0YzU5OGQ0MjMzZGI0MGIwZTkwNXAxNzk1Nzg"
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

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

def save_data():
    try:
        redis.set("fasil_lotto_db", json.dumps(data))
    except: pass

def load_data():
    global data
    try:
        raw = redis.get("fasil_lotto_db")
        if raw: 
            loaded_data = json.loads(raw)
            data.update(loaded_data)
    except: pass

load_data()

# --- 4. ቦት ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    if uid not in data["users"]:
        data["users"][uid] = {"name": message.from_user.first_name, "wallet": 0}
        save_data()
    
    user = data["users"][uid]
    welcome_text = (
        f"👋 <b>እንኳን ወደ ፋሲል ረዳት ቦት በደህና መጡ!</b>\n\n"
        f"👤 <b>ስም፦</b> {user['name']}\n"
        f"💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ ብር ሲያስገቡ የደረሰኙን ፎቶ እዚህ ይላኩ።"
    )
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if int(uid) in ADMIN_IDS:
        markup.add("⚙️ Admin Settings")
        bot.send_message(uid, welcome_text, reply_markup=markup)
    else:
        bot.send_message(uid, welcome_text, reply_markup=types.ReplyKeyboardRemove())

if __name__ == "__main__":
    keep_alive()
    
    # የቆዩ ሜሴጆችን እንዲዘል (Drop pending updates)
    try:
        bot.delete_webhook(drop_pending_updates=True)
        print("✅ የቆዩ ሜሴጆች ተሰርዘዋል!")
    except:
        pass

    print("🚀 ቦቱ አሁን ስራ ጀምሯል...")
    
    # ስህተት የነበረበትን መስመር በዚህ ይተካል
    bot.infinity_polling() 
