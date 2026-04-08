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
TOKEN = "8721334129:AAF8Uexl1shbdyg2sdYT_aqWE1r1kzQH39k"
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
DB_FILE = "fasil_db.json"
data = {
    "users": {},
    "current_shift": "me",
    "boards": {
        "1": {"max": 25, "price": 50, "prize": "1ኛ 200, 2ኛ 100, 3ኛ 50", "active": True, "slots": {}},
        "2": {"max": 50, "price": 100, "prize": "1ኛ 400, 2ኛ 200, 3ኛ 100", "active": True, "slots": {}},
        "3": {"max": 100, "price": 200, "prize": "1ኛ 800, 2ኛ 400, 3ኛ 200", "active": True, "slots": {}}
    },
    "pinned_msgs": {"1": None, "2": None, "3": None}
}

def save_data():
    try:
        # መረጃውን ወደ Redis መላክ
        redis.set("fasil_lotto_db", json.dumps(data))
        
        # የድሮው የፋይል አቀማመጥ እንዳይበላሽ (Backups)
        with open(DB_FILE, "w") as f:
            json.dump(data, f)
        with open(DB_FILE, "rb") as f:
            bot.send_document(DB_CHANNEL_ID, f, caption=f"🔄 Database Backup - {time.ctime()}")
    except: pass

def load_data():
    global data
    try:
        # መጀመሪያ ከ Redis ዳታ ለመሳብ መሞከር
        raw_redis_data = redis.get("fasil_lotto_db")
        if raw_redis_data:
            data = json.loads(raw_redis_data)
        elif os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                loaded = json.load(f)
                data.update(loaded)
    except: pass

# ቦቱ ስራ ሲጀምር ዳታውን እንዲያነብ ጥሪ ማድረግ
load_data()

def get_user(uid, name="ደንበኛ"):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "wallet": 0}
    return data["users"][uid]

def main_menu_markup(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    if int(uid) in ADMIN_IDS:
        markup.add("⚙️ Admin Settings") # አድሚን ብቻ ይሄን ያያል
        return markup
    return types.ReplyKeyboardRemove() # ሌላ ሰው ምንም አያይም

# --- 4. የሰሌዳ ዲዛይን (Group View) ---
def update_group_board(b_id):
    b_id = str(b_id)
    if b_id not in data["boards"]: return
    
    board = data["boards"][b_id]
    current_shift = data.get("current_shift", "me")
    
    # --- 🎨 ራስጌ (Header) ---
    text = "🇪🇹 🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ!</b> 🏟️ 🇪🇹\n"
    text += f"              <b>በ {board['price']} ብር</b>\n"
    text += "             👇👇👇👇👇\n"
    
    prizes = board['prize'].split(',')
    labels = ["1ኛ🟢", "2ኛ🟡", "3ኛ🔴"]
    for i, p in enumerate(prizes):
        if i < 3: text += f"             {labels[i]} {p.strip()}\n"

    text += "\n☎️⏰⏰ ለውድ 🏟️ ፋሲል እና ዳመነ ዲጂታል ዕጣ! 🏟️ ቤተሰብ\n"
    text += "<b>መልካም ቀን🏆 መልካም ጤና🏆 መልካም እድል።</b>\n"
    text += "<b>USE IT OR LOSE IT</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    # --- 🎫 የቁጥሮች ዝርዝር (በ 1 መስመር ክፍተት) ---
    board_slots = board.get("slots", {})
    for i in range(1, board["max"] + 1):
        n = str(i)
        status = board_slots[n] if n in board_slots else "@@@@"
        text += f"<b>{i}👉</b>{status} ✅🏆🙏\n\n"
            
    # --- 👣 ግርጌ (Footer) ---
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += "🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ!</b> 🏟️\n"
    text += "<b>ስልክ ደውሎ ለማግኘት ከፈለጉ</b>\n"
    text += "                 👇👇👇\n"
    text += "          👉 <code>0973416038</code>\n\n"
    
    text += "           <b>ገቢ ማስገቢያ አማራጮች</b>\n"
    text += "              👇👇👇👇👇\n\n"
    
    # --- ተለዋዋጭ የአካውንት መረጃ ---
    if current_shift == "me":
        text += "👉 <b>Telebirr:</b> <code>0951381356</code>  <b>fassil</b>\n\n"
        text += "👉 <b>CBE:</b> <code>1000584461757</code> <b>fassil</b>\n"
    else:
        text += "👉 <b>CBE:</b> <code>1000718691323</code> <b>ዳመነ</b>\n\n"
        text += "👉 <b>Telebirr:</b> <code>0973416038</code>  <b>ፀጋ</b>\n"
    
    text += f"\n🤖 <b>ለመጫወት እዚህ ይጫኑ፦</b> @{bot.get_me().username}"

    # --- መልዕክቱን መላክ/ማስተካከል ---
    try:
        msg_id = data.get("pinned_msgs", {}).get(b_id)
        if msg_id:
            bot.edit_message_text(text, GROUP_ID, msg_id, parse_mode="HTML")
        else:
            m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
            if "pinned_msgs" not in data: data["pinned_msgs"] = {}
            data["pinned_msgs"][b_id] = m.message_id
            save_data()
            bot.pin_chat_message(GROUP_ID, m.message_id)
    except:
        m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
        if "pinned_msgs" not in data: data["pinned_msgs"] = {}
        data["pinned_msgs"][b_id] = m.message_id
        save_data()
         
# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = message.chat.id
    
    if uid in ADMIN_IDS:
        # አድሚን ከሆነ የአድሚን ሴቲንግ ያሳያል
        bot.send_message(
            uid, 
            "👋 ሰላም አድሚን!\nወደ ቁጥጥር ፓነል እንኳን መጡ።", 
            reply_markup=main_menu_markup(uid)
        )
    else:
        # ተራ ተጫዋች ከሆነ የድሮ በተኖችን በሙሉ ያጠፋል
        bot.send_message(
            uid, 
            "🇪🇹 🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ!</b> 🏟️ 🇪🇹\n\n"
            "⚠️ ይህ ቦት ለክፍያ ማረጋገጫ ብቻ የሚያገለግል ነው።\n"
            "እባክዎ ለመጫወት እና ደረሰኝ ለመላክ ወደ ግሩፑ ይሂዱ።", 
            reply_markup=types.ReplyKeyboardRemove(), # የድሮ በተኖችን ያጠፋል
            parse_mode="HTML"
        )

# --- 🛠 1. የአድሚን ዋና ሜኑ (Main Admin Panel) ---
@bot.message_handler(func=lambda message: message.text == "⚙️ Admin Settings" and message.from_user.id in ADMIN_IDS)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # ሲስተም መቆጣጠሪያ
    btn_shift = types.InlineKeyboardButton("🔄 ሺፍት ቀይር (Shift)", callback_data="admin_toggle_shift")
    btn_lookup = types.InlineKeyboardButton("🏆 አሸናፊ ፈልግ", callback_data="admin_lookup_winner")
    
    # የካሽ ስራዎች
    btn_cash = types.InlineKeyboardButton("💵 በካሽ መዝግብ", callback_data="admin_cash_reg")
    btn_delete = types.InlineKeyboardButton("❌ ቁጥር ሰርዝ", callback_data="admin_delete_num")
    
    # የሰሌዳ መቆጣጠሪያዎች (ለ 3ቱም ሰሌዳ)
    btn_manage = types.InlineKeyboardButton("⚙️ ሰሌዳዎችን አስተካክል", callback_data="admin_manage_boards")
    
    markup.add(btn_shift, btn_lookup)
    markup.add(btn_cash, btn_delete)
    markup.add(btn_manage)
    
    bot.send_message(message.chat.id, "🛠 <b>የአድሚን መቆጣጠሪያ ሰሌዳ</b>\n\nየሚፈልጉትን ተግባር ይምረጡ፦", reply_markup=markup, parse_mode="HTML")

# --- 🔄 2. የሺፍት መቀየሪያ Logic ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_toggle_shift")
def toggle_shift_callback(call):
    if call.from_user.id not in ADMIN_IDS: return
    
    new_shift = "assistant" if data.get("current_shift") == "me" else "me"
    data["current_shift"] = new_shift
    save_data()
    
    shift_name = "ፀጋ (Assistant)" if new_shift == "assistant" else "ፋሲል (Me)"
    bot.answer_callback_query(call.id, f"✅ ሺፍት ወደ {shift_name} ተቀይሯል!", show_alert=True)
    
    # ሁሉንም ሰሌዳዎች ግሩፕ ላይ ወዲያው ያድሳል
    for bid in data["boards"]:
        update_group_board(bid)

# --- 🏆 3. አሸናፊ መፈለጊያ (Account Link ያለው) ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_lookup_winner")
def start_lookup(call):
    m = bot.send_message(call.from_user.id, "🔍 <b>አሸናፊ ለመፈለግ፦</b>\n\nሰሌዳ-ቁጥር ይጻፉ (ምሳሌ፦ <code>2-15</code>)", parse_mode="HTML")
    bot.register_next_step_handler(m, process_lookup)

def process_lookup(message):
    try:
        text = message.text.strip()
        bid, num = text.split('-')
        
        if bid in data["boards"] and num in data["boards"][bid]["slots"]:
            winner_name = data["boards"][bid]["slots"][num]
            
            # የተጫዋቹን ID መፈለግ (ከ users ዳታ ውስጥ በስሙ መፈለግ)
            winner_id = None
            for uid, info in data["users"].items():
                if info.get("name") == winner_name:
                    winner_id = uid
                    break
            
            res = f"🏆 <b>አሸናፊ ተገኝቷል!</b>\n\n"
            res += f"🎰 <b>ሰሌዳ፦</b> {bid}\n"
            res += f"🔢 <b>ቁጥር፦</b> {num}\n"
            
            if winner_id:
                # 🔗 የአካውንት ሊንክ (ተጠቃሚው ቦቱን ስታርት ባያደርግም ይሰራል)
                res += f"👤 <b>ተጫዋች፦</b> <a href='tg://user?id={winner_id}'>{winner_name}</a>\n"
                res += f"🆔 <b>User ID፦</b> <code>{winner_id}</code>"
            else:
                res += f"👤 <b>ተጫዋች፦</b> {winner_name} (በካሽ የተመዘገበ)"
                
            bot.send_message(message.chat.id, res, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ ስህተት፦ ቁጥሩ አልተያዘም ወይም ሰሌዳው የለም።")
    except:
        bot.send_message(message.chat.id, "⚠️ ስህተት፦ አጻጻፉ ተሳስቷል። ምሳሌ፦ <code>2-15</code>")

# --- 💵 4. በካሽ መመዝገቢያ ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_cash_reg") # ስሙን አስተካክለነዋል
def start_cash_reg(call):
    m = bot.send_message(call.from_user.id, "📝 <b>በካሽ ለመመዝገብ፦</b>\nሰሌዳ-ቁጥር ስም ይጻፉ\n\nምሳሌ፦ <code>1-05 አበበ</code>", parse_mode="HTML")
    bot.register_next_step_handler(m, process_cash_reg)

def process_cash_reg(message):
    try:
        text = message.text.strip()
        
        if ' ' not in text or '-' not in text:
            bot.send_message(message.chat.id, "❌ ስህተት! ትክክለኛ አጻጻፍ፦ <code>1-05 አበበ</code>", parse_mode="HTML")
            return
            
        board_info, name = text.split(' ', 1)
        bid, num_raw = board_info.split('-', 1)
        
        # ቁጥሩን ወደ ትክክለኛ ፎርማት መቀየር (ለምሳሌ 5 ከሆነ 05 እንዲሆን)
        if not num_raw.isdigit():
            bot.send_message(message.chat.id, "❌ ስህተት! ቁጥር ብቻ ያስገቡ።")
            return
            
        num = num_raw.zfill(2) if int(num_raw) < 10 else num_raw # 5 ከሆነ 05 ያደርገዋል
        
        if bid in data["boards"]:
            board = data["boards"][bid]
            if int(num) > board["max"] or int(num) < 1:
                bot.send_message(message.chat.id, f"❌ ስህተት! በሰሌዳ {bid} ውስጥ ያሉት ቁጥሮች ከ1-{board['max']} ብቻ ናቸው።")
                return

            # ቁጥሩ ቀድሞ የተያዘ መሆኑን ማረጋገጥ
            if num in board["slots"]:
                bot.send_message(message.chat.id, f"❌ ስህተት! ቁጥር {num} ቀድሞ በ {board['slots'][num]} ተይዟል።")
                return

            board["slots"][num] = name[:15]
            save_data()
            update_group_board(bid)
            bot.send_message(message.chat.id, f"✅ ሰሌዳ {bid} ቁጥር {num} ለ <b>{name[:15]}</b> ተመዝግቧል!", parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, f"❌ ሰሌዳ {bid} አልተገኘም!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት ተከስቷል! አጻጻፍ፦ 1-05 አበበ")

# --- ⚙️ 5. የሰሌዳዎች አስተዳደር (Manage Boards) ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_boards")
def manage_boards_list(call):
    markup = types.InlineKeyboardMarkup()
    for bid in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"⚙️ ሰሌዳ {bid} አስተካክል", callback_data=f"editboard_{bid}"))
    bot.edit_message_text("የሚስተካከለውን ሰሌዳ ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("editboard_"))
def edit_specific_board(call):
    try:
        # 1. መጀመሪያ bid ን በትክክል መለየት (ሁለተኛውን ክፍል ብቻ መውሰድ)
        bid = call.data.split('_')
        
        # 2. በ bid ተጠቅሞ የሰሌዳውን ዳታ መሳብ
        b = data["boards"][bid]
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # ሁኔታውን መቀየር (Open/Close)
        # ማሳሰቢያ፦ ከስር ያለው toggle_active_logic መኖሩን አረጋግጥ
        status_text = "🔴 ሰሌዳውን ዝጋ" if b["active"] else "🟢 ሰሌዳውን ክፈት"
        markup.add(types.InlineKeyboardButton(status_text, callback_data=f"togact_{bid}"))
        
        # ሌሎች በተኖች
        markup.add(types.InlineKeyboardButton("🎫 ዋጋ ቀይር", callback_data=f"set_price_{bid}"),
                   types.InlineKeyboardButton("🎁 ሽልማት ቀይር", callback_data=f"set_prize_{bid}"))
        
        markup.add(types.InlineKeyboardButton("🧹 ሰሌዳ አጽዳ (Reset)", callback_data=f"cnfreset_{bid}"))
        markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage_boards"))
        
        txt = (f"📊 <b>የሰሌዳ {bid} መቆጣጠሪያ</b>\n"
               f"━━━━━━━━━━━━━\n"
               f"💰 <b>ዋጋ፦</b> {b['price']} ብር\n"
               f"🏆 <b>ሽልማት፦</b> {b['prize']}\n"
               f"📝 <b>ሁኔታ፦</b> {'🟢 ክፍት' if b['active'] else '🔴 ዝግ'}")
        
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"Error in edit_board: {e}")
        bot.answer_callback_query(call.id, "❌ ስህተት ተከስቷል!")

# --- 🟢/🔴 ሰሌዳውን ክፍት/ዝግ ማድረጊያ Logic ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("togact_"))
def toggle_active_logic(call):
    bid = call.data.split('_')
    data["boards"][bid]["active"] = not data["boards"][bid]["active"]
    save_data()
    bot.answer_callback_query(call.id, "✅ የሰሌዳ ሁኔታ ተቀይሯል!")
    # ገጹን ወዲያውኑ እንዲያድሰው ደግመን የላይኛውን ፈንክሽን እንጠራለን
    edit_specific_board(call)

# --- 🧹 ሰሌዳውን ባዶ ማድረጊያ (Reset) Logic ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("cnfreset_"))
def confirm_reset_logic(call):
    bid = call.data.split('_')
    data["boards"][bid]["slots"] = {} # ሁሉንም ቁጥሮች ማጥፋት
    save_data()
    update_group_board(bid) # ግሩፕ ላይ ያለውን ሰሌዳ ማደስ
    bot.answer_callback_query(call.id, f"🧹 ሰሌዳ {bid} ጸድቷል!", show_alert=True)
    edit_specific_board(call)

import threading

# --- 1. ደረሰኝ መቀበያ (ከግሩፕ ወደ Admin) ---
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    if message.chat.id != GROUP_ID: return
    if message.from_user.id in ADMIN_IDS: return # አድሚን ከሆነ ችላ ይለዋል

    uid = str(message.from_user.id)
    name = message.from_user.first_name[:15] # ስሙን መቁረጥ
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"app_{uid}"),
        types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"rej_{uid}")
    )
    
    cap = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 ከ፦ {name}\n🆔 ID፦ <code>{uid}</code>"
    
    for adm in ADMIN_IDS:
        try: bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup, parse_mode="HTML")
        except: pass

# --- 2. የማጽደቅ እና የውድቅ Logic (Callback) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(('app_', 'rej_')))
def admin_approval_callback(call):
    if call.from_user.id not in ADMIN_IDS: return
    
    action, target_id = call.data.split('_')
    
    if action == "app":
        m = bot.send_message(call.message.chat.id, f"💰 ለ <code>{target_id}</code> የሚጨመር ብር ይጻፉ፦", parse_mode="HTML")
        bot.register_next_step_handler(m, finalize_deposit, target_id)
        bot.edit_message_caption("⏳ ብር እየተጨመረ ነው...", call.message.chat.id, call.message.message_id)
    else:
        m = bot.send_message(call.message.chat.id, "❌ ውድቅ የሆነበትን ምክንያት ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_decline, target_id)

# --- 3. ብር መጨመሪያ እና ስማርት ፒከር ---
def finalize_deposit(message, target_id):
    try:
        amount = int(message.text.strip())
        user = get_user(target_id)
        user["wallet"] += amount
        save_data()

        bot.send_message(message.chat.id, f"✅ {amount} ብር ለ {user['name']} ተጨምሯል!")

        active_boards = [bid for bid, b in data["boards"].items() if b.get("active")]

        if not active_boards:
            bot.send_message(GROUP_ID, f"✅ የ {user['name']} ክፍያ ደርሷል፣ ግን በአሁኑ ሰዓት ክፍት ሰሌዳ የለም።")
            return

        confirm_text = (f"✅ <b>ክፍያዎ ተረጋግጧል!</b>\n"
                        f"👤 <b>ተጫዋች፦</b> {user['name']}\n"
                        f"💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር\n\n")

        # 1 ሰሌዳ ብቻ ካለ ቀጥታ ቁጥሮቹን ይዘረግፋል
        if len(active_boards) == 1:
            bid = active_boards
            markup = create_picker_markup(target_id, bid)
            confirm_text += f"🎰 <b>ሰሌዳ {bid} ቁጥር ይምረጡ፦</b>"
        else:
            # ከአንድ በላይ ካለ መጀመሪያ ሰሌዳ እንዲመርጥ
            markup = types.InlineKeyboardMarkup()
            for bid in active_boards:
                markup.add(types.InlineKeyboardButton(f"ሰሌዳ {bid}", callback_data=f"u_select_{target_id}_{bid}"))
            confirm_text += "የትኛው ሰሌዳ ላይ መጫወት ይፈልጋሉ?"

        # 🎯 በ Reply መልክ እንዲላክ ማድረግ (የተጫዋቹን ID በመጠቀም)
        # ማሳሰቢያ፡ አድሚኑ ደረሰኙን አይቶ ስለሆነ ብር የጨመረው፣ ግሩፕ ላይ ለተጫዋቹ Reply ይደረጋል
        sent_msg = bot.send_message(GROUP_ID, confirm_text, reply_markup=markup, parse_mode="HTML")

        # 🗑 ግሩፑ እንዳይጨናነቅ ከ120 ሰከንድ (2 ደቂቃ) በኋላ ይጠፋል
        threading.Timer(120.0, lambda: bot.delete_message(GROUP_ID, sent_msg.message_id)).start()

    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ ስህተት፦ እባክዎ የብር መጠን ብቻ በትክክል ያስገቡ።")

# --- ረዳት ፈንክሽን ለተዘረገፉ በተኖች ---
def create_picker_markup(uid, bid):
    board = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = []
    for i in range(1, board["max"] + 1):
        # ቁጥሮቹ 01, 02 እንዲሉ (አማራጭ)
        n = str(i).zfill(2) if i < 10 else str(i)
        if n in board["slots"]:
            btns.append(types.InlineKeyboardButton("❌", callback_data="taken"))
        else:
            btns.append(types.InlineKeyboardButton(n, callback_data=f"pck_{uid}_{bid}_{n}"))
    markup.add(*btns)
    return markup

# --- 4. ውድቅ ማድረጊያ Logic ---
def finalize_decline(message, target_id):
    reason = message.text
    try:
        rej_text = (f"❌ <b>ደረሰኝዎ ውድቅ ተደርጓል!</b>\n"
                    f"━━━━━━━━━━━━━\n"
                    f"📝 <b>ምክንያት፦</b> {reason}\n\n"
                    f"🙏 እባክዎ በትክክለኛ መረጃ በድጋሚ ግሩፕ ላይ ይላኩ።")
        bot.send_message(target_id, rej_text, parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ የውድቅ መልዕክት ለተጫዋቹ ተልኳል።")
    except:
        bot.send_message(message.chat.id, "⚠️ ለተጫዋቹ መልዕክት ማድረስ አልተቻለም (ቦቱን Start አላደረገም)።")

# --- 1. የቁጥር መምረጫውን ማሳያ (Show Picker) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('u_select_'))
def show_picker_callback(call):
    # u_select_targetid_bid
    _, _, target_id, bid = call.data.split('_')
    
    if str(call.from_user.id) != target_id:
        return bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
    
    send_picker(call.message, target_id, bid, is_new=False)

def send_picker(message, uid, bid, is_new=True):
    board = data["boards"][bid]
    user = get_user(uid)
    
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = []
    for i in range(1, board["max"] + 1):
        n = str(i)
        if n in board["slots"]:
            btns.append(types.InlineKeyboardButton("❌", callback_data="taken"))
        else:
            btns.append(types.InlineKeyboardButton(n, callback_data=f"pck_{uid}_{bid}_{n}"))
    markup.add(*btns)
    
    text = (f"🎰 <b>ሰሌዳ {bid} ቁጥር ይምረጡ</b>\n"
            f"👤 ተጫዋች፦ {user['name']}\n"
            f"💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር\n"
            f"💵 የ1 ቁጥር ዋጋ፦ {board['price']} ብር")
    
    if is_new:
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    else:
        bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=markup, parse_mode="HTML")

# --- 2. ቁጥር ሲመረጥ የሚሰራው ስራ (Pick Logic) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('pck_'))
def handle_pick(call):
    _, uid, bid, num = call.data.split('_')
    
    if str(call.from_user.id) != uid:
        return bot.answer_callback_query(call.id, "⚠️ የሌላ ሰው ምርጫ ነው!", show_alert=True)
    
    user = get_user(uid)
    board = data["boards"][bid]
    
    # የሂሳብ ማረጋገጫ
    if user["wallet"] < board["price"]:
        bot.edit_message_text(f"⚠️ <b>በቂ ሂሳብ የሎትም!</b>\n💰 ቀሪ፦ {user['wallet']} ብር\nምዝገባ ተጠናቅቋል።", 
                              call.message.chat.id, call.message.message_id, parse_mode="HTML")
        return

    # ቁጥሩ ከተያዘ መከላከል (Race Condition)
    if num in board["slots"]:
        bot.answer_callback_query(call.id, "❌ ይቅርታ፣ ይህ ቁጥር አሁን ተይዟል!", show_alert=True)
        send_picker(call.message, uid, bid, is_new=False)
        return

    # ምዝገባ
    user["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data()
    
    # ሰሌዳውን ግሩፕ ላይ ወዲያው ማደስ
    update_group_board(bid)
    
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመዝግቧል!")
    
    # ሌላ ቁጥር መግዛት የሚችል ከሆነ Picker ይቀጥላል
    if user["wallet"] >= board["price"]:
        send_picker(call.message, uid, bid, is_new=False)
    else:
        bot.edit_message_text(f"✅ <b>ምዝገባ ተጠናቅቋል!</b>\n👤 {user['name']}\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር\nመልካም እድል!", 
                              call.message.chat.id, call.message.message_id, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "taken")
def handle_taken(call):
    bot.answer_callback_query(call.id, "❌ ይህ ቁጥር ቀድሞ ተይዟል!", show_alert=False)

if __name__ == "__main__":
    # ለጊዜው ይህንን ጨምር (አንድ ጊዜ Deploy ካደረግክ በኋላ መልሰህ ብታጠፋው ይሻላል)
    save_data()
    
    keep_alive()
    # ... ሌላው የ bot.polling ኮድ ይቀጥላል
    bot.remove_webhook()
    while True:
        try: bot.polling(none_stop=True, interval=1, timeout=20)
        except: time.sleep(5)


