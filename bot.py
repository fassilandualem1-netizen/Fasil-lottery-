import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time
from upstash_redis import Redis

# --- 1. Web Hosting ---
app = Flask('')
@app.route('/')
def home(): return "Fasil Lotto System is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. ቦት መረጃዎች ---
TOKEN = "8721334129:AAFF0Irx3Pa7add9rnMcm855Xsg2G3zMzFM"
MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003749311489
DB_CHANNEL_ID = -1003747262103
ADMIN_IDS = [MY_ID, ASSISTANT_ID]

PAYMENTS = {
    "me": {"tele": "0951381356", "cbe": "1000584461757"},
    "assistant": {"tele": "0973416038", "cbe": "1000718691323"}
}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Redis Connection
REDIS_URL = "https://sunny-ferret-79578.upstash.io"
REDIS_TOKEN = "gQAAAAAAATbaAAIncDE4MTQ2MThjMjVjYjI0YzU5OGQ0MjMzZGI0MGIwZTkwNXAxNzk1Nzg"
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

# --- 3. ዳታቤዝ አያያዝ ---
def load_data():
    try:
        raw = redis.get("fasil_lotto_db")
        if raw: return json.loads(raw)
    except: pass
    return {
        "users": {}, "current_shift": "me",
        "boards": {
            "1": {"max": 25, "price": 50, "prize": "1ኛ 200, 2ኛ 100", "active": True, "slots": {}},
            "2": {"max": 50, "price": 100, "prize": "1ኛ 400, 2ኛ 200", "active": True, "slots": {}},
            "3": {"max": 100, "price": 200, "prize": "1ኛ 800, 2ኛ 400", "active": True, "slots": {}}
        },
        "pinned_msgs": {"1": None, "2": None, "3": None}
    }

data = load_data()

def save_data():
    redis.set("fasil_lotto_db", json.dumps(data))

# --- 4. ግሩፕ ላይ ሰሌዳ የማደሻ ኮድ ---
def update_group_board(b_id):
    b_id = str(b_id)
    board = data["boards"][b_id]
    current_shift = data.get("current_shift", "me")
    active_pay = PAYMENTS[current_shift]
    
    # የሰሌዳው ዲዛይን (የቀድሞው ዲዛይንህ)
    text = "🇪🇹 🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ!</b> 🏟️ 🇪🇹\n"
    text += f"              <b>በ {board['price']} ብር</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

    board_slots = board["slots"]
    for i in range(1, board["max"] + 1):
        n = str(i)
        if n in board_slots:
            text += f"<b>{i}👉</b> {board_slots[n]} ✅🏆🙏\n"
        else:
            text += f"<b>{i}👉</b> @@@@ ✅🏆🙏\n"
            
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"👉 <b>Telebirr:</b> <code>{active_pay['tele']}</code>\n"
    text += f"👉 <b>CBE:</b> <code>{active_pay['cbe']}</code>\n"

    # --- ዋናው ማስተካከያ እዚህ ጋር ነው ---
    msg_id = data.get("pinned_msgs", {}).get(b_id)
    
    try:
        if msg_id:
            # የድሮው መልዕክት ካለ በላዩ ላይ አርመው (Edit)
            bot.edit_message_text(text, GROUP_ID, msg_id, parse_mode="HTML")
        else:
            # የድሮው መልዕክት ከሌለ (ከተሰረዘ) አዲስ ልከህ ፒን አድርግ
            m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
            data["pinned_msgs"][b_id] = m.message_id
            bot.pin_chat_message(GROUP_ID, m.message_id)
            save_data()
    except Exception as e:
        # መልዕክቱ ካልተገኘ (ለምሳሌ ግሩፑ ላይ ከተሰረዘ) አዲስ ልከህ ፒን አድርግ
        m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
        data["pinned_msgs"][b_id] = m.message_id
        bot.pin_chat_message(GROUP_ID, m.message_id)
        save_data()

# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    if int(uid) in ADMIN_IDS:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("⚙️ Admin Settings")
        bot.send_message(uid, "ሰላም አድሚን!", reply_markup=markup)
    else:
        bot.send_message(uid, "👋 እንኳን ወደ ፋሲል መዝናኛ መጡ!")

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id in ADMIN_IDS)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("⚙️ ሰሌዳዎችን አስተካክል", callback_data="admin_manage"),
        types.InlineKeyboardButton("🔍 አሸናፊ ፈልግ", callback_data="lookup_winner"),
        types.InlineKeyboardButton("🔄 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset")
    )
    bot.send_message(message.chat.id, "🛠 <b>የአድሚን ዳሽቦርድ</b>", reply_markup=markup)

# --- 6. የ Callback Listener (የተስተካከለ) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    d = call.data
    
    # 🛠 የአድሚን ዋና ማስተካከያ ገጽ
    if d == "admin_manage" and is_admin:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("💵 በካሽ መዝግብ", callback_data="admin_cash"),
                   types.InlineKeyboardButton("🗑 ቁጥር ሰርዝ", callback_data="admin_delete"))
        for bid in data["boards"]:
            status = "🟢" if data["boards"][bid]["active"] else "🔴"
            markup.add(types.InlineKeyboardButton(f"⚙️ ሰሌዳ {bid} {status}", callback_data=f"setup_{bid}"))
        markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_panel_back"))
        bot.edit_message_text("🛠 <b>ለማስተካከል ሰሌዳ ይምረጡ፦</b>", call.message.chat.id, call.message.message_id, reply_markup=markup)

    # 📊 የአንድን ሰሌዳ ዝርዝር ማስተካከያ (On/Off, ዋጋ, ሽልማት)
    elif d.startswith('setup_') and is_admin:
        bid = d.split('_') # እዚህ ጋር መኖሩን እርግጠኛ ሁን
        b = data["boards"][bid]
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        status_text = "🔴 ዝጋ (OFF)" if b['active'] else "🟢 ክፈት (ON)"
        markup.add(types.InlineKeyboardButton(status_text, callback_data=f"switch_{bid}"))
        
        markup.add(
            types.InlineKeyboardButton("💰 ዋጋ ቀይር", callback_data=f"change_price_{bid}"),
            types.InlineKeyboardButton("🎁 ሽልማት ቀይር", callback_data=f"change_prize_{bid}")
        )
        markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))

        msg = (f"📊 <b>የሰሌዳ {bid} ማስተካከያ</b>\n\n"
               f"🔘 <b>ሁኔታ፦</b> {'ክፍት' if b['active'] else 'ዝግ'}\n"
               f"💵 <b>ዋጋ፦</b> {b['price']} ብር\n"
               f"🏆 <b>ሽልማት፦</b> {b['prize']}")
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup)

    # 🔄 ሁኔታ መቀያየሪያ (Switch ON/OFF)
    elif d.startswith('switch_') and is_admin:
        bid = d.split('_')
        data["boards"][bid]["active"] = not data["boards"][bid]["active"]
        save_data()
        bot.answer_callback_query(call.id, f"ሰሌዳ {bid} ተቀይሯል!")
        
        # ገጹን ወዲያው እንዲያድሰው የ setup ገጹን ድጋሚ እንጠራለን
        call.data = f"setup_{bid}"
        callback_listener(call)

    # ሌሎቹ የ callback ተግባራት (ለምሳሌ select_, pick_) እዚህ ይቀጥላሉ...


@bot.callback_query_handler(func=lambda call: (call.data.startswith('change_price_') or call.data.startswith('change_prize_')) and call.from_user.id in ADMIN_IDS)
def request_new_value(call):
    parts = call.data.split('_')
    action = parts # price ወይም prize
    bid = parts
    
    label = "አዲስ ዋጋ (በቁጥር)" if action == "price" else "አዲስ የሽልማት ዝርዝር"
    m = bot.send_message(call.from_user.id, f"📝 ለሰሌዳ {bid} {label} ይጻፉ፦")
    bot.register_next_step_handler(m, update_board_setting, bid, action)

def update_board_setting(message, bid, action):
    try:
        new_val = message.text.strip()
        if action == "price":
            data["boards"][bid]["price"] = int(new_val)
        else:
            data["boards"][bid]["prize"] = new_val
            
        save_data()
        update_group_board(bid) # ግሩፑ ላይ ያለውን ዲዛይን ወዲያው እንዲቀይር
        bot.send_message(message.chat.id, f"✅ ሰሌዳ {bid} በትክክል ተስተካክሏል!")
    except:
        bot.send_message(message.chat.id, "❌ ስህተት! እባክዎ በትክክል መጻፍዎን ያረጋግጡ።")


# --- ጠንካራ የሰሌዳ ማጽጃ (Reset) ኮድ ---

@bot.callback_query_handler(func=lambda call: call.data == "admin_reset" and call.from_user.id in ADMIN_IDS)
def reset_selection_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for bid in data["boards"]:
        slots_count = len(data["boards"][bid]["slots"])
        markup.add(types.InlineKeyboardButton(
            f"🧹 ሰሌዳ {bid} አጽዳ ({slots_count} ቁጥሮች ተይዘዋል)", 
            callback_data=f"confirm_reset_{bid}"
        ))
    
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
    bot.edit_message_text("⚠️ <b>የትኛው ሰሌዳ እንዲጸዳ ይፈልጋሉ?</b>\nያስታውሱ፦ አንዴ ከጸዳ መመለስ አይቻልም!", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_reset_') and call.from_user.id in ADMIN_IDS)
def confirm_reset(call):
    bid = call.data.split('_')
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ አዎ አጽዳ", callback_data=f"do_final_reset_{bid}"),
        types.InlineKeyboardButton("❌ ይቅር", callback_data="admin_reset")
    )
    bot.edit_message_text(f"❓ <b>ሰሌዳ {bid} በእርግጥ ይጥፋ?</b>", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith('do_final_reset_') and call.from_user.id in ADMIN_IDS)
def execute_reset(call):
    bid = call.data.split('_')
    
    # 1. ዳታውን ማጽዳት
    data["boards"][bid]["slots"] = {}
    
    # 2. የድሮውን ፒን ሜሴጅ ማጥፋት (አዲስ እንዲላክ)
    if "pinned_msgs" in data and bid in data["pinned_msgs"]:
        data["pinned_msgs"][bid] = None
    
    # 3. መረጃውን ሴቭ ማድረግ
    save_data()
    
    # 4. ግሩፕ ላይ አዲስ ባዶ ሰሌዳ መላክ
    try:
        update_group_board(bid)
        bot.answer_callback_query(call.id, f"✅ ሰሌዳ {bid} በትክክል ጸድቷል!", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, "⚠️ ዳታው ጸድቷል ግን ግሩፕ ላይ ማደስ አልተቻለም።")

    # 5. ወደ አድሚን ፓናል መመለስ
    admin_panel(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('do_final_reset_') and call.from_user.id in ADMIN_IDS)
def execute_reset(call):
    bid = call.data.split('_')
    
    # 1. ዳታውን ብቻ አጽዳ (pinned_msgs IDውን አትንካው!)
    data["boards"][bid]["slots"] = {}
    
    # 2. ሴቭ አድርግ
    save_data()
    
    # 3. ግሩፕ ላይ ያለውን መልዕክት እንዲያርመው ጥራ
    update_group_board(bid)
    
    bot.answer_callback_query(call.id, f"✅ ሰሌዳ {bid} በትክክል ጸድቷል!", show_alert=True)
    admin_panel(call.message)


def process_lookup(message):
    try:
        # አጻጻፍ፦ 1-05
        bid, num = message.text.split('-')
        bid, num = str(bid), str(int(num))
        
        # በሰሌዳው ላይ የተመዘገበውን ስም መፈለግ
        winner_name = data["boards"][bid]["slots"].get(num)
        
        if winner_name:
            # በዳታቤዝ ውስጥ የዚህን ስም ባለቤት User ID መፈለግ
            winner_id = None
            for uid, info in data["users"].items():
                if info["name"] == winner_name:
                    winner_id = uid
                    break
            
            if winner_id:
                # የቴሌግራም ሊንክ (Mention) ያለው ውጤት
                mention = f'<a href="tg://user?id={winner_id}">{winner_name}</a>'
                res = (f"🏆 <b>አሸናፊ ተገኝቷል!</b>\n\n"
                       f"👤 <b>ስም፦</b> {mention}\n"
                       f"🎰 <b>ሰሌዳ፦</b> {bid} | <b>ቁጥር፦</b> {num}\n"
                       f"🆔 <b>User ID፦</b> <code>{winner_id}</code>\n\n"
                       f"👆 ስሙን ሲነኩት ወደ አካውንቱ ይወስድዎታል።")
            else:
                # በካሽ የተመዘገበ ከሆነ ወይም IDው ካልተገኘ
                res = (f"🏆 <b>አሸናፊ፦</b> {winner_name}\n"
                       f"🎰 <b>ሰሌዳ፦</b> {bid} | <b>ቁጥር፦</b> {num}\n"
                       f"⚠️ <i>ማሳሰቢያ፦ ይህ ተጫዋች በቦቱ በኩል ስላልተመዘገበ ሊንክ የለውም።</i>")
                
            bot.send_message(message.chat.id, res, parse_mode="HTML")
        else: 
            bot.send_message(message.chat.id, "⚠️ ይህ ቁጥር ገና አልተያዘም!")
    except Exception as e: 
        bot.send_message(message.chat.id, "⚠️ ስህተት! (አጻጻፍ፦ 1-05)")



def process_delete(message):
    try:
        bid, num = message.text.split('-')
        bid, num = str(bid), str(int(num))
        if num in data["boards"][bid]["slots"]:
            del data["boards"][bid]["slots"][num]
            save_data()
            update_group_board(bid) # ግሩፕ ላይ ያለውን ወዲያው ያድሳል
            bot.send_message(message.chat.id, f"🗑 ሰሌዳ {bid} ቁጥር {num} ተሰርዟል!")
        else:
            bot.send_message(message.chat.id, "❌ ቁጥሩ አልተገኘም!")
    except: bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 1-05")

def process_lookup(message):
    try:
        bid, num = message.text.split('-')
        bid, num = str(bid), str(int(num))
        name = data["boards"][bid]["slots"].get(num)
        if name: bot.send_message(message.chat.id, f"🏆 አሸናፊ፦ {name}")
        else: bot.send_message(message.chat.id, "⚠️ ቁጥሩ ገና አልተያዘም!")
    except: bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 2-13")

if __name__ == "__main__":
    keep_alive()
    print("Fasil Bot is LIVE...")
    bot.infinity_polling()
