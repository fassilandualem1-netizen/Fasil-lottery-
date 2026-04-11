import telebot
import time

# ቶከኑን እዚህ ጋር በጥንቃቄ ለጥፍ
TOKEN = "8721334129:AAFukMOE8qoJPOZAleW7tLxHN8qpxr92IAc"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "ቦቱ በሰላም ሰርቷል!")

if __name__ == "__main__":
    print("ቦቱ እየጀመረ ነው...")
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling()
