import telebot
import os
from flask import Flask
from threading import Thread

# Web server for Render
app = Flask('')
@app.route('/')
def home(): return "I am alive!"

def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# ቦቱ መስራቱን ቼክ ማድረጊያ
TOKEN = "8757888085:AAHorIou6gWJjUgvgNeJlC2HbkNq2Wohizs"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "✅ ቦቱ አሁን በትክክል እየሰራ ነው!")

if __name__ == "__main__":
    t = Thread(target=run)
    t.start()
    bot.infinity_polling()
