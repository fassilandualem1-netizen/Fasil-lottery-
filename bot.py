import telebot
import json
import os

# ያቀረብካቸው መረጃዎች
TOKEN = "8721334129:AAGZxYXP4UH0RuEdC8gk6icXu5gSB26bI3Q"
ADMIN_ID = 8488592165
GROUP_ID = -1003881429974
DB_CHANNEL_ID = -1003747262103

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.from_user.id == ADMIN_ID:
        bot.reply_to(message, "ሰላም ጌታዬ! ትስስሩ በትክክል እየሰራ ነው። አሁን ሙሉውን ኮድ መጻፍ እንችላለን።")
        
        # ግሩፑ ላይ መላክ መቻሉን እንፈትሽ
        try:
            bot.send_message(GROUP_ID, "✅ ቦቱ ከግሩፑ ጋር ተገናኝቷል!")
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ ግሩፕ ላይ መላክ አልተቻለም: {e}")

        # ዳታቤዝ ቻናሉ ላይ ፋይል መላክ መቻሉን እንፈትሽ
        try:
            test_data = {"test": "success"}
            with open("test.json", "w") as f:
                json.dump(test_data, f)
            with open("test.json", "rb") as f:
                bot.send_document(DB_CHANNEL_ID, f, caption="የዳታቤዝ ፈተና")
            bot.send_message(ADMIN_ID, "✅ ዳታቤዝ ቻናሉ ላይ ፋይል መላክ ተችሏል!")
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ ዳታቤዝ ቻናል ስህተት: {e}")
    else:
        bot.reply_to(message, "እንኳን ወደ FASIL ዕጣ ቦት በደህና መጡ!")

print("ቦቱ ስራ ጀምሯል...")
bot.polling()
