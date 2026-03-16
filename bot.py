import telebot
from telebot import types
import re

# --- ማዋቀሪያ ---
TOKEN = '8721334129:AAGZxYXP4UH0RuEdC8gk6icXu5gSB26bI3Q'
ADMIN_ID = 8488592165 
GROUP_ID = -1003881429974    # ሰሌዳው የሚለጠፍበት ግሩፕ
DB_CHANNEL_ID = -1003747262103 # ዳታቤዝ (ማህደር) ቻናል

bot = telebot.TeleBot(TOKEN)
users_db = {} 

def get_user(uid):
    uid = str(uid)
    if uid not in users_db:
        users_db[uid] = {'wallet': 0, 'name': '', 'board': ''}
    return users_db[uid]

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    get_user(uid)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💰 ዋሌት", "🎮 ሰሌዳ ምረጥ")
    
    msg = (
        "እንኳን ወደ Fasil ዕጣ በደህና መጣህ!\n\n"
        "CBE: 1000xxxxxxxxx\n"
        "Telebirr: 09xxxxxxxx\n\n"
        "እባክዎ ደረሰኝ (SMS/Photo) ይላኩ።"
    )
    bot.send_message(uid, msg, reply_markup=markup)

# --- የክፍያ ማረጋገጫ ---
@bot.message_handler(content_types=['photo', 'text'])
def handle_receipt(message):
    uid = message.chat.id
    if uid == ADMIN_ID: return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"ok_{uid}"),
        types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"no_{uid}")
    )
    bot.send_message(uid, "🔄 ደረሰኝዎ እየተረጋገጠ ነው... እባክዎ ከ1-5 ደቂቃ ይታገሱን።")
    
    user_info = f"👤 @{message.from_user.username} | ID: `{uid}`"
    if message.text:
        amount_match = re.findall(r'(\d+(?:\.\d+)?)\s*(?:ብር|ETB)', message.text)
        money = f"\n💰 የታየ መጠን: {amount_match[0]} ETB" if amount_match else ""
        bot.send_message(ADMIN_ID, f"📩 **አዲስ SMS**\n{user_info}{money}\n\n`{message.text}`", reply_markup=markup)
    else:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"🖼 **አዲስ ፎቶ**\n{user_info}", reply_markup=markup)

# --- አድሚን ---
@bot.callback_query_handler(func=lambda call: True)
def admin_actions(call):
    target_uid = call.data.split('_')[1]
    if call.data.startswith("ok"):
        msg = bot.send_message(ADMIN_ID, "የሚጨመረውን ብር በቁጥር ብቻ ይጻፉ:")
        bot.register_next_step_handler(msg, finalize_ok, target_uid)
    elif call.data.startswith("no"):
        msg = bot.send_message(ADMIN_ID, "ምክንያቱን ይጻፉ:")
        bot.register_next_step_handler(msg, finalize_no, target_uid)

def finalize_ok(message, target_uid):
    try:
        amount = int(message.text)
        users_db[target_uid]['wallet'] += amount
        bot.send_message(target_uid, f"🔔 ክፍያዎ ተረጋግጧል! {amount} ብር ተጨምሯል።")
        bot.send_message(ADMIN_ID, f"✅ ተረጋግጧል።")
        
        # ወደ ዳታቤዝ ቻናል መላክ (Deposit Archive)
        db_msg = f"➕ **Wallet Deposit**\nUser ID: `{target_uid}`\nAmount: {amount} ETB"
        bot.send_message(DB_CHANNEL_ID, db_msg)
    except:
        bot.send_message(ADMIN_ID, "ቁጥር ብቻ ያስገቡ!")

def finalize_no(message, target_uid):
    reason = message.text
    bot.send_message(target_uid, f"❌ ደረሰኝዎ ውድቅ ተደርጓል!\nምክንያት: {reason}")
    bot.send_message(ADMIN_ID, "❌ ውድቅ ተደርጓል።")

# --- ምዝገባ ---
@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("ሰሌዳ 1 (50 ብር)", "ሰሌዳ 2 (100 ብር)", "ተመለስ")
    bot.send_message(message.chat.id, "ሰሌዳ ይምረጡ:", reply_markup=markup)

@bot.message_handler(func=lambda m: "ሰሌዳ" in m.text)
def handle_board(message):
    uid = str(message.chat.id)
    price = 50 if "50" in message.text else 100
    if get_user(uid)['wallet'] < price:
        bot.send_message(uid, f"⚠️ ቀሪ ሂሳብዎ በቂ አይደለም! (ያለዎት: {users_db[uid]['wallet']} ብር)")
    else:
        users_db[uid]['board'] = message.text
        msg = bot.send_message(uid, "ሙሉ ስምዎን ያስገቡ:")
        bot.register_next_step_handler(msg, ask_num, price)

def ask_num(message, price):
    uid = str(message.chat.id)
    users_db[uid]['name'] = message.text
    msg = bot.send_message(uid, "የሚመርጡትን ቁጥር ይጻፉ:")
    bot.register_next_step_handler(msg, complete_reg, price)

def complete_reg(message, price):
    uid = str(message.chat.id)
    num = message.text
    users_db[uid]['wallet'] -= price
    
    bot.send_message(uid, f"✅ ተመዝግበዋል!\nስም: {users_db[uid]['name']}\nቁጥር: {num}\nቀሪ: {users_db[uid]['wallet']} ብር")
    
    # ለግሩፑ የሚላክ መልዕክት (የሰሌዳ ምዝገባ)
    group_msg = (
        f"📝 **አዲስ ተመዝጋቢ**\n"
        f"👤 ስም፦ {users_db[uid]['name']}\n"
        f"🔢 ቁጥር፦ {num}\n"
        f"🎮 ሰሌዳ፦ {users_db[uid]['board']}"
    )
    bot.send_message(GROUP_ID, group_msg)
    
    # ለዳታቤዝ ቻናል የሚላክ (Registration Archive)
    db_report = (
        f"📋 **Registration Log**\n"
        f"User ID: `{uid}`\n"
        f"Name: {users_db[uid]['name']}\n"
        f"Board: {users_db[uid]['board']}\n"
        f"Price: {price} ETB"
    )
    bot.send_message(DB_CHANNEL_ID, db_report)

@bot.message_handler(func=lambda m: m.text == "💰 ዋሌት")
def check_balance(message):
    uid = str(message.chat.id)
    bot.send_message(uid, f"የእርስዎ ዋሌት: {get_user(uid)['wallet']} ብር")

bot.polling(none_stop=True)
