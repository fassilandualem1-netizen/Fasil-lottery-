import telebot
from telebot import types
import os
import json
from flask import Flask
from threading import Thread

# --- 1. Render መቆያ ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Bingo is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. ቦት መረጃዎች ---
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
ADMIN_ID = 8488592165 

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- 3. ዳታቤዝ (Wallet ዳታ እንዲቀመጥ) ---
DB_FILE = "wallets.json"
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f: wallets = json.load(f)
else:
    wallets = {}

def save_db():
    with open(DB_FILE, "w") as f: json.dump(wallets, f)

# --- 4. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    if uid not in wallets: wallets[uid] = 0; save_db()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    if int(uid) == ADMIN_ID: markup.add("⚙️ Admin Settings")
    
    bot.send_message(uid, f"👋 <b>እንኳን ደህና መጡ!</b>\n💰 ቀሪ ሂሳብ፦ <b>{wallets[uid]} ብር</b>\n\n⚠️ ብር ሲያስገቡ ደረሰኝ እዚህ ይላኩ።", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    uid = str(message.chat.id)
    bal = wallets.get(uid, 0)
    bot.send_message(uid, f"👤 <b>ፕሮፋይል</b>\n💰 ቀሪ ሂሳብ፦ <b>{bal} ብር</b>")

# --- 5. የደረሰኝ መቀበያ ---
@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    uid = str(message.chat.id)
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings"]: return

    bot.send_message(uid, "⏳ <b>ደረሰኝዎ ለባለቤቱ ተልኳል...</b>\nእባክዎ እስኪረጋገጥ ይጠብቁ። 🙏")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"app_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"dec_{uid}"))
    
    caption = f"📩 <b>አዲስ ደረሰኝ</b>\n🆔 <b>ID፦</b> <code>{uid}</code>"
    if message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=markup)
    else:
        bot.send_message(ADMIN_ID, f"{caption}\n📝 <b>ዝርዝር፦</b>\n<code>{message.text}</code>", reply_markup=markup)

# --- 6. አፅድቅ/ውድቅ ሲጫን ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    uid = call.data.split('_')[1]
    if call.data.startswith('app_'):
        msg = bot.send_message(ADMIN_ID, f"💵 ለ ID <code>{uid}</code> የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(msg, finalize_deposit, uid)
    elif call.data.startswith('dec_'):
        bot.send_message(uid, "❌ ይቅርታ፣ የላኩት ደረሰኝ ተቀባይነት አላገኘም።")
        bot.send_message(ADMIN_ID, "ውድቅ ተደርጓል!")

def finalize_deposit(message, target_uid):
    try:
        amount = int(message.text)
        if target_uid not in wallets: wallets[target_uid] = 0
        wallets[target_uid] += amount
        save_db()
        bot.send_message(target_uid, f"✅ <b>{amount} ብር ተጨምሮልዎታል!</b>\n💰 አጠቃላይ ቀሪ ሂሳብ፦ <b>{wallets[target_uid]} ብር</b>")
        bot.send_message(ADMIN_ID, f"✅ ለ {target_uid} {amount} ብር ተጨምሯል።")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ስህተት፦ እባክዎ ቁጥር ብቻ ይጻፉ!")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
