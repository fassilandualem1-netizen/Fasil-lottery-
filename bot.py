import telebot
from telebot import types
import os
import time

# --- ቦት መረጃዎች (አረጋግጥ!) ---
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
ADMIN_ID = 8488592165 

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- ቀለል ያለ የዳታ አያያዝ ---
users_wallet = {} # ለጊዜው በሜሞሪ እንዲይዘው

@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    if uid not in users_wallet:
        users_wallet[uid] = 0
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    
    bot.send_message(uid, f"👋 <b>እንኳን ደህና መጡ!</b>\n\n💰 ቀሪ ሂሳብ፦ <b>{users_wallet[uid]} ብር</b>\n\n⚠️ ብር ሲያስገቡ የቴሌብር መልዕክት ወይም የደረሰኝ ፎቶ እዚህ ይላኩ።", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def profile(message):
    uid = str(message.chat.id)
    bal = users_wallet.get(uid, 0)
    bot.send_message(uid, f"👤 <b>ፕሮፋይል</b>\n💰 ቀሪ ሂሳብ፦ {bal} ብር")

@bot.message_handler(content_types=['photo', 'text'])
def receipts(message):
    uid = str(message.chat.id)
    
    # ቁልፎችን ችላ እንዲል
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል"]:
        return

    # ለአድሚን አይላክም
    if int(uid) == ADMIN_ID:
        bot.send_message(ADMIN_ID, "አድሚን ነህ፣ ደረሰኝ መላክ አይጠበቅብህም።")
        return

    # ለደንበኛው መልስ
    bot.send_message(uid, "⏳ <b>ደረሰኝዎ ደርሶናል!</b>\nባለቤቱ እስኪያጸድቅ ድረስ እባክዎ ይጠብቁ።")
    
    # ለአድሚኑ ማስተላለፍ
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"ok_{uid}"))
    
    if message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"📩 አዲስ ደረሰኝ ከ ID: {uid}", reply_markup=markup)
    else:
        bot.send_message(ADMIN_ID, f"📩 አዲስ የጽሁፍ ደረሰኝ ከ ID: {uid}\n\n{message.text}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ok_'))
def approve(call):
    target_uid = call.data.split('_')[1]
    bot.send_message(target_uid, "✅ <b>ክፍያዎ ተረጋግጧል!</b> አሁን መጫወት ይችላሉ።")
    bot.answer_callback_query(call.id, "ተረጋግጧል!")

if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()
