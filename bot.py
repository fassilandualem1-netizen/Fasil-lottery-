import telebot
from telebot import types
import os
from flask import Flask
import threading

# --- ውቅረት (Configuration) ---
TOKEN = "8663228906:AAFsTC0fKqAVEWMi7rk59iSdfVD-1vlJA0Y"
ADMIN_IDS =
DRIVER_CHANNEL_ID = -1003962139457
PORT = int(os.getenv("PORT", 8080))

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
server = Flask(__name__)

@server.route('/')
def health_check(): return "Delivery Bot is Active!", 200

# --- የአድሚን ቁልፎች ---
def get_driver_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("አዳዲስ ትዕዛዞች 📦")
    btn2 = types.KeyboardButton("እቃ ጨምር (Vendor) ➕")
    btn3 = types.KeyboardButton("ሪፖርት 📊")
    markup.add(btn1)
    markup.add(btn2, btn3)
    return markup

# --- የገዢ ቁልፎች ---
def get_customer_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("ሱቆችን ተመልከት 🏪"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, f"ሰላም ሾፌር {message.from_user.first_name}!", reply_markup=get_driver_keyboard())
    else:
        bot.send_message(message.chat.id, "እንኳን ወደ Beu-Style በደህና መጡ!", reply_markup=get_customer_keyboard())

@bot.message_handler(func=lambda m: m.text == "አዳዲስ ትዕዛዞች 📦")
def check_orders(message):
    if message.from_user.id in ADMIN_IDS:
        try:
            bot.send_message(DRIVER_CHANNEL_ID, f"🔔 ሾፌር {message.from_user.first_name} ለስራ ዝግጁ ነው።")
            bot.reply_to(message, "ማሳወቂያ ወደ ቻናሉ ተልኳል! ✅")
        except Exception as e:
            bot.reply_to(message, f"ስህተት፡ {e}\n(ቦቱ ቻናሉ ላይ አድሚን መሆኑን እባክህ አረጋግጥ)")

def run_flask():
    server.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 ቦቱ በሰላም ተነስቷል...")
    bot.infinity_polling()
