import telebot
import time

# አዲሱ ቶከንህ
TOKEN = "8757888085:AAHHv6ne3gDNeO-d8TjX2ag26bQrT53Z28Q"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ ፋሲል ቦት አሁን በDocker በኃይል ተነስቷል!")

if __name__ == "__main__":
    print("Bot is starting...")
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling()
