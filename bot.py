import telebot
from telebot import types
import os
from flask import Flask
from threading import Thread
import time
from supabase import create_client, Client

# --- 1. Web Hosting ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Lotto System (Supabase) is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት እና Supabase መረጃዎች ---
TOKEN = "8721334129:AAHuEJDpuZf5vZ0GzKGPfRALlG3cA1TUmF0"
SUPABASE_URL = "https://aapxnuzwrkxbzsanatik.supabase.co"
SUPABASE_KEY = "EyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFhcHhudXp3cmt4YnpzYW5hdGlrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM5Njg0NDcsImV4cCI6MjA4OTU0NDQ0N30.FdM3KkTBit3b35wK9obuJvPUhetAWGwL_tqM4pgDM0k"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003881429974
ADMIN_IDS = [MY_ID, ASSISTANT_ID]

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323"}
}

# --- 3. ዳታቤዝ ፈንክሽኖች (ከ Supabase ጋር) ---

def get_db_setting(key, default=None):
    res = supabase.table("bot_settings").select("value").eq("key", key).execute()
    return res.data['value'] if res.data and res.data['value'] else default

def set_db_setting(key, value):
    supabase.table("bot_settings").upsert({"key": key, "value": str(value)}).execute()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    res = supabase.table("users").select("*").eq("uid", uid).execute()
    if not res.data:
        new_user = {"uid": uid, "name": name[:5], "wallet": 0}
        supabase.table("users").insert(new_user).execute()
        return new_user
    return res.data

def update_wallet(uid, amount):
    user = get_user(uid)
    new_bal = user['wallet'] + amount
    supabase.table("users").update({"wallet": new_bal}).eq("uid", str(uid)).execute()

def get_all_slots(bid):
    res = supabase.table("slots").select("slot_number, user_name").eq("board_id", str(bid)).execute()
    return {item['slot_number']: item['user_name'] for item in res.data}

# ቋሚ የሰሌዳ መረጃዎች
BOARDS_INFO = {
    "1": {"max": 25, "price": 50, "prize": "1ኛ 200, 2ኛ 100, 3ኛ 50"},
    "2": {"max": 50, "price": 100, "prize": "1ኛ 400, 2ኛ 200, 3ኛ 100"},
    "3": {"max": 100, "price": 200, "prize": "1ኛ 800, 2ኛ 400, 3ኛ 200"}
}

def main_menu_markup(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS: markup.add("⚙️ Admin Settings")
    return markup

# --- 4. የሰሌዳ ዲዛይን (Group View) ---
def update_group_board(b_id):
    info = BOARDS_INFO[b_id]
    slots = get_all_slots(b_id)
    pinned_id = get_db_setting(f"pinned_{b_id}")
    
    text = f"🎰 <b>ፋሲል ዕጣ - ሰሌዳ {b_id} (1-{info['max']})</b>\n"
    text += f"🎫 መደብ፦ <b>{info['price']} ብር</b>\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━\n"
    
    line = ""
    for i in range(1, info["max"] + 1):
        s_i = str(i).zfill(2)
        if str(i) in slots:
            line += f"<code>{s_i}</code>🔴{slots[str(i)][:5]}\t\t"
        else:
            line += f"<code>{s_i}</code>⬜️\t\t"
        if i % 2 == 0:
            text += line + "\n"
            line = ""
    text += line + "\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🎁 <b>ሽልማት፦ {info['prize']}</b>\n"
    text += f"🤖 ለመጫወት፦ @Fasil_assistant_bot"
    
    try:
        if pinned_id:
            bot.edit_message_text(text, GROUP_ID, int(pinned_id))
        else:
            m = bot.send_message(GROUP_ID, text)
            bot.pin_chat_message(GROUP_ID, m.message_id)
            set_db_setting(f"pinned_{b_id}", m.message_id)
    except:
        m = bot.send_message(GROUP_ID, text)
        bot.pin_chat_message(GROUP_ID, m.message_id)
        set_db_setting(f"pinned_{b_id}", m.message_id)

# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    shift = get_db_setting("current_shift", "me")
    active_pay = PAYMENTS[shift]
    
    welcome_text = (
        f"👋 <b>እንኳን ወደ ፋሲል መዝናኛና ዕድለኛ ዕጣ መጡ!</b>\n\n"
        f"👤 <b>ስም፦</b> {user['name']}\n"
        f"💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏦 <b>Telebirr:</b> <code>{active_pay['tele']}</code>\n"
        f"🔸 <b>CBE:</b> <code>{active_pay['cbe']}</code>\n\n"
        f"⚠️ <b>ብር ሲያስገቡ የደረሰኙን ፎቶ ወይም መልዕክት እዚህ ይላኩ።</b>"
    )
    bot.send_message(uid, welcome_text, reply_markup=main_menu_markup(uid))

@bot.message_handler(commands=['shift'])
def toggle_shift(message):
    if message.from_user.id == MY_ID:
        current = get_db_setting("current_shift", "me")
        new_shift = "assistant" if current == "me" else "me"
        set_db_setting("current_shift", new_shift)
        bot.reply_to(message, f"🔄 ፈረቃ ተቀይሯል! አሁን ተረኛው፦ {new_shift}")

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in BOARDS_INFO.items():
        markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} | 🎫 {b_info['price']} ብር", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "<b>ለመጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦</b>", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 <b>ፕሮፋይል</b>\n📛 ስም፦ {user['name']}\n💰 ቀሪ፦ {user['wallet']} ብር")

@bot.message_handler(func=lambda m: m.text == "🎫 የያዝኳቸው ቁጥሮች")
def my_numbers(message):
    uid = str(message.chat.id)
    user = get_user(uid)
    found = False
    text = "🎫 <b>የያዟቸው ቁጥሮች፦</b>\n\n"
    for bid in BOARDS_INFO:
        slots = get_all_slots(bid)
        user_nums = [n for n, u in slots.items() if u == user['name']]
        if user_nums:
            found = True
            text += f"🎰 <b>ሰሌዳ {bid}:</b> {', '.join(user_nums)}\n"
    if not found: text = "⚠️ እስካሁን ምንም ቁጥር አልያዙም!"
    bot.send_message(uid, text)

@bot.message_handler(content_types=['photo', 'text'])
def handle_receipts(message):
    if message.chat.type != 'private': return 
    uid = str(message.chat.id)
    if message.text in ["🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "⚙️ Admin Settings", "🎫 የያዝኳቸው ቁጥሮች"]: return
    
    bot.send_message(uid, "⏳ <b>ደረሰኝዎ ደርሶኛል...</b>\nእባክዎ እስኪረጋገጥ ይጠብቁ። 🙏")
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    
    cap = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 <b>ከ፦</b> {message.from_user.first_name}\n🆔 <b>ID፦</b> <code>{uid}</code>"
    for adm in ADMIN_IDS:
        if message.photo: bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup)
        else: bot.send_message(adm, f"{cap}\n📝 <b>ዝርዝር፦</b>\n<code>{message.text}</code>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    if call.data.startswith('approve_') and is_admin:
        target = call.data.split('_')
        m = bot.send_message(call.from_user.id, f"💵 ለ ID {target} የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_app, target)
    elif call.data.startswith('select_'):
        bid = call.data.split('_')
        user = get_user(call.message.chat.id)
        info = BOARDS_INFO[bid]
        if user['wallet'] < info['price']:
            bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True); return
        
        slots = get_all_slots(bid)
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}") 
                for i in range(1, info["max"] + 1) if str(i) not in slots]
        markup.add(*btns)
        bot.edit_message_text(f"🎰 <b>ሰሌዳ {bid}</b>\nቁጥር ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif call.data.startswith('pick_'):
        _, bid, num = call.data.split('_')
        uid = str(call.message.chat.id)
        user = get_user(uid)
        price = BOARDS_INFO[bid]['price']
        
        try:
            supabase.table("slots").insert({
                "board_id": bid, "slot_number": num, "user_name": user['name']
            }).execute()
            update_wallet(uid, -price)
            bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተይዟል!")
            update_group_board(bid)
            # ተመልሶ ሰሌዳ እንዲመርጥ
            call.data = f"select_{bid}"
            callback_listener(call)
        except:
            bot.answer_callback_query(call.id, "❌ ይህ ቁጥር ተይዟል!")

def finalize_app(message, target):
    try:
        amt = int(message.text)
        update_wallet(target, amt)
        bot.send_message(target, f"✅ <b>{amt} ብር ተጨምሯል!</b>")
        m = bot.send_message(target, "አሁን በሰሌዳ ላይ የሚወጣውን ስምዎን (እስከ 5 ፊደል) ይጻፉ፦")
        bot.register_next_step_handler(m, save_name, target)
    except: bot.send_message(message.chat.id, "⚠️ ስህተት! ቁጥር ብቻ ይጻፉ።")

def save_name(message, uid):
    name = message.text[:5]
    supabase.table("users").update({"name": name}).eq("uid", str(uid)).execute()
    bot.send_message(uid, f"✅ ስምዎ '{name}' ተብሎ ተመዝግቧል!", reply_markup=main_menu_markup(uid))

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
