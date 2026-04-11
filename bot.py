import telebot
import time

# ቶከኑን እዚህ ጋር በጥንቃቄ ለጥፍ
TOKEN = "8757888085:AAHHv6ne3gDNeO-d8TjX2ag26bQrT53Z28Q"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "ቦቱ በሰላም ሰርቷል!")

if __name__ == "__main__":
    print("ቦቱ እየጀመረ ነው...")
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling()
