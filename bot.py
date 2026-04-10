import telebot
import time

TOKEN = "8757888085:AAHorIou6gWJjUgvgNeJlC2HbkNq2Wohizs"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['test'])
def test_connection(message):
    bot.reply_to(message, "🚀 Render እና ቦቱ በትክክል ተገናኝተዋል!")

if __name__ == "__main__":
    bot.remove_webhook()
    print("ግንኙነት እየተፈተነ ነው...")
    bot.polling(none_stop=True)
