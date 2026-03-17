import telebot
from telebot import types
import os
from flask import Flask
from threading import Thread

# --- 1. Render Health Check (Render ሰርቨሩ እንዲነቃ) ---
app = Flask('')

@app.route('/')
def home():
    return "Fasil Bingo is Online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. ቦት መረጃዎች (ID በትክክል መሆኑን አረጋግጥ) ---
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
ADMIN_ID = 8488592165 # በምስሉ ላይ ያየነው ያንተ ID

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- 3. ቦት ሎጂክ ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል")
    if int(uid) == ADMIN_ID:
        markup.add("⚙️ Admin Settings")
    
    bot.send_message(uid, f"✅ <b>Fasil Assistant ንቁ ነው!</b>\n\n💰 ቀሪ ሂሳብ፦ <b>0 ብር</b>\n\n⚠️ ደረሰኝ እዚህ ይላኩ።", reply_markup=markup)

@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    uid = str(message.chat.id)
    
    # የኪቦርድ ቁልፎች ከሆኑ ስራ እንዳያቆም
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings"]:
        bot.send_message(uid, f"የመረጡት፦ {message.text}")
        return

    # ለደንበኛው መልስ
    bot.send_message(uid, "⏳ <b>ደረሰኝዎ ለባለቤቱ ተልኳል...</b>\nእባክዎ እስኪረጋገጥ ይጠብቁ። 🙏")
    
    # ለአድሚኑ የሚላክ ማጽደቂያ ቁልፍ (Inline Keyboard)
    # ይህ ነው ምስሉ ላይ ያልመጣው ክፍል!
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_approve = types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}")
    btn_decline = types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}")
    markup.add(btn_approve, btn_decline)
    
    caption = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 <b>ከ፦</b> {message.from_user.first_name}\n🆔 <b>ID፦</b> <code>{uid}</code>"
    
    # ለአድሚኑ መላክ
    if message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=markup)
    else:
        bot.send_message(ADMIN_ID, f"{caption}\n📝 <b>ዝርዝር፦</b>\n<code>{message.text}</code>", reply_markup=markup)

# --- 4. ቁልፎቹ ሲጫኑ የሚሰሩት ስራዎች ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    if call.data.startswith('approve_'):
        target_uid = call.data.split('_')[1]
        bot.send_message(ADMIN_ID, f"ለ ID {target_uid} የሚጨመረውን የብር መጠን ይጻፉ፦")
        # እዚህ ጋር የአድሚኑን ምላሽ ለመቀበል register_next_step_handler መጠቀም ይቻላል
    elif call.data.startswith('decline_'):
        target_uid = call.data.split('_')[1]
        bot.send_message(target_uid, "❌ ይቅርታ፣ የላኩት ደረሰኝ ተቀባይነት አላገኘም።")
        bot.answer_callback_query(call.id, "ውድቅ ተደርጓል")

if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.infinity_polling()
