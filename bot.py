import telebot
from telebot import types
import os
from flask import Flask
from threading import Thread

# --- 1. Render Health Check (ይህ የግድ ያስፈልጋል!) ---
app = Flask('')

@app.route('/')
def home():
    return "Fasil Bingo is Online!"

def run():
    # Render የሚሰጠውን PORT መጠቀም አለብን፣ ካልሆነ 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. ቦት መረጃዎች ---
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
ADMIN_ID = 8488592165 

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- 3. ቦት ሎጂክ ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    
    bot.send_message(uid, f"✅ <b>Fasil Assistant ንቁ ነው!</b>\n\n💰 ቀሪ ሂሳብ፦ <b>0 ብር</b>\n\n⚠️ ደረሰኝ እዚህ ይላኩ።", reply_markup=markup)

@bot.message_handler(content_types=['photo', 'text'])
def handle_docs(message):
    uid = str(message.chat.id)
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል"]:
        bot.send_message(uid, f"የመረጡት፦ {message.text}")
        return

    # ደረሰኝ ሲላክ
    bot.send_message(uid, "⏳ ደረሰኝዎ ለባለቤቱ ተልኳል።")
    bot.send_message(ADMIN_ID, f"📩 አዲስ ደረሰኝ ከ {uid}")

if __name__ == "__main__":
    keep_alive() # Flask ሰርቨሩን ያስነሳል (Health check እንዲያልፍ)
    print("Bot is starting...")
    bot.infinity_polling()
