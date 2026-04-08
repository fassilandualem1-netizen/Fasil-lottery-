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
TOKEN = "8721334129:AAEbMUHHLcVTv9pGzTwMwC_Wi4tLx3R_F5k"
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
        user = get_user(uid, message.from_user.first_name)
        bot.send_message(
            uid, 
            f"👋 ሰላም አድሚን {user['name']}!\nወደ ቁጥጥር ፓነል እንኳን መጡ።", 
            reply_markup=main_menu_markup(uid)
        )
    else:
        # ተራ ተጠቃሚ ከሆነ ኪቦርዱን አጥፍቶ ማስጠንቀቂያ ይሰጣል
        bot.send_message(
            uid, 
            "⚠️ <b>ይህ ቦት ለአድሚን ብቻ ነው።</b>\nእባክዎ ለመጫወት ወደ ዋናው ግሩፕ ይሂዱ።", 
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
@bot.message_handler(commands=['shift'])
def toggle_shift(message):
    # ባለቤቱ (ፋሲል) ብቻ እንዲቀይር
    if message.from_user.id == MY_ID:
        # ፈረቃውን መቀየር
        data["current_shift"] = "assistant" if data["current_shift"] == "me" else "me"
        save_data()
        
        target = "ረዳት (ዳመነ/ፀጋ)" if data["current_shift"] == "assistant" else "ባለቤት (ፋሲል)"
        bot.reply_to(message, f"🔄 ፈረቃ ተቀይሯል!\n👤 ተረኛው፦ <b>{target}</b>", parse_mode="HTML")
        
        # ✅ አስፈላጊ፦ ሽግግሩ እንደተቀየረ ግሩፕ ላይ ያለውን ሰሌዳ በራስ-ሰር አፕዴት ያደርጋል
        active_boards = [bid for bid, info in data["boards"].items() if info["active"]]
        for b_id in active_boards:
            update_group_board(b_id)
            
    else:
        bot.reply_to(message, "❌ ይህን ትዕዛዝ ለመጠቀም ባለቤት መሆን አለብዎት።")


# --- አውቶማቲክ ብሮድካስት (Broadcast System) ---
@bot.message_handler(commands=['post'])
def start_broadcast(message):
    if message.from_user.id in ADMIN_IDS:
        msg = bot.send_message(message.chat.id, "📢 ለመላክ የሚፈልጉትን መልዕክት (ጽሁፍ ወይም ፎቶ) አሁን ይላኩ፦")
        bot.register_next_step_handler(msg, send_to_all)
    else:
        bot.reply_to(message, "❌ ይህ ለባለቤቱ ብቻ የተፈቀደ ነው!")

def send_to_all(message):
    users = list(data["users"].keys())
    count = 0
    fail = 0
    bot.send_message(message.chat.id, f"⏳ ለ {len(users)} ተጠቃሚዎች በመላክ ላይ ነው...")
    for uid in users:
        try:
            if message.content_type == 'text':
                bot.send_message(uid, message.text)
            elif message.content_type == 'photo':
                bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption)
            count += 1
            time.sleep(0.05)
        except:
            fail += 1
    bot.send_message(message.chat.id, f"✅ ተጠናቋል!\n📤 የተላከላቸው፦ {count}\n🚫 ያልደረሳቸው፦ {fail}")

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id in ADMIN_IDS)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    stats = "".join([f"📍 ሰሌዳ {bid}: ({len(binfo['slots'])}/{binfo['max']})\n" for bid, binfo in data["boards"].items()])
    markup.add(types.InlineKeyboardButton("⚙️ ሰሌዳዎችን አስተካክል", callback_data="admin_manage"),
               types.InlineKeyboardButton("🔍 አሸናፊ ፈልግ", callback_data="lookup_winner"),
               types.InlineKeyboardButton("🔄 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset"))
    bot.send_message(message.chat.id, f"🛠 <b>የአድሚን ዳሽቦርድ</b>\n\n{stats}", reply_markup=markup)

# --- ከግሩፕ የሚላኩ ደረሰኞችን መቀበያ ---
@bot.message_handler(content_types=['photo'])
def handle_group_receipt(message):
    # 1. መልዕክቱ የመጣው ከተወሰነው ግሩፕ መሆኑን ማረጋገጥ
    if message.chat.id != GROUP_ID:
        return

    # 2. አድሚኑ ራሱ ግሩፕ ላይ ፎቶ ቢልክ ምንም አያድርግ
    if message.from_user.id in ADMIN_IDS:
        return 

    uid = str(message.from_user.id)
    name = message.from_user.first_name if message.from_user.first_name else "ተጫዋች"
    mid = message.message_id # የግሩፑ መልዕክት ID

    # ✅ ለአድሚን የሚላኩ በተኖች
    markup = types.InlineKeyboardMarkup(row_width=2)
    # ማሳሰቢያ፦ callback_data ውስጥ mid እና target_id በትክክል መያዛቸውን አረጋግጥ
    btn_approve = types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"g_app_{uid}_{mid}")
    btn_reject = types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"g_rej_{uid}_{mid}")
    markup.add(btn_approve, btn_reject)
    
    cap = (f"📩 <b>አዲስ ደረሰኝ ከግሩፕ</b>\n"
           f"━━━━━━━━━━━━━\n"
           f"👤 <b>ከ፦</b> {name}\n"
           f"🆔 <b>User ID፦</b> <code>{uid}</code>\n"
           f"📝 <b>ሁኔታ፦</b> ማረጋገጫ እየጠበቀ...")

    # ለአድሚኖች በሙሉ መላክ
    for adm in ADMIN_IDS:
        try:
            bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            print(f"ለአድሚን {adm} መላክ አልተቻለም፦ {e}")

# --- 2. በቦቱ (Private) የሚላኩ ፎቶዎችን መከልከል ---
@bot.message_handler(content_types=['photo', 'text'], func=lambda m: m.chat.type == 'private')
def block_private_receipts(message):
    # ✅ በጣም አስፈላጊ፦ አድሚን ከሆነ በቦቱ ውስጥ የሚጽፈው ነገር (ለምሳሌ 2-01 ወይም 50) 
    # እንደ ደረሰኝ እንዳይቆጠር ወዲያውኑ ስራውን ያቁም (Return)
    if message.from_user.id in ADMIN_IDS:
        return 

    # ተራ ተጫዋች ፎቶ ከላከ ብቻ "ግሩፕ ላይ ላክ" ይበለው
    if message.content_type == 'photo':
        bot.reply_to(message, "⚠️ <b>ደረሰኝ እዚህ አይቀበልም!</b>\nእባክዎ ግሩፕ ላይ ይላኩ።", parse_mode="HTML")


# ይህ ክፍል "ሰሌዳ አስተካክል" ሲነካ መልስ እንዲሰጥ ያደርጋል
@bot.callback_query_handler(func=lambda call: call.data in ["admin_manage", "manage_boards"] and call.from_user.id in ADMIN_IDS)
def admin_manage_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💵 በካሽ መዝግብ", callback_data="admin_cash"),
        types.InlineKeyboardButton("❌ ቁጥር ሰርዝ", callback_data="admin_delete")
    )
    # የሰሌዳዎቹን ዝርዝር እዚህ ጋር ጨምርላቸው
    for bid in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"⚙️ ሰሌዳ {bid} አስተካክል", callback_data=f"edit_{bid}"))
    
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_panel_back"))
    
    bot.edit_message_text("🛠 <b>የአድሚን ስራዎችን ይምረጡ፦</b>", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_cash")
def start_cash_reg(call):
    m = bot.send_message(call.from_user.id, "📝 <b>በካሽ ለመመዝገብ፦</b>\nሰሌዳ-ቁጥር ስም ይጻፉ\n\nምሳሌ፦ <code>1-05 አበበ</code>")
    bot.register_next_step_handler(m, process_cash_reg)

def process_cash_reg(message):
    try:
        text = message.text.strip()
        # መጀመሪያ በክፍተት ስሙን እና የሰሌዳውን ክፍል ይለያል
        if ' ' not in text:
            bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 1-05 አበበ")
            return
            
        board_info, name = text.split(' ', 1)
        
        if '-' not in board_info:
            bot.send_message(message.chat.id, "❌ ስህተት! በሰሌዳ እና ቁጥር መሀል ሰረዝ (-) ያድርጉ።")
            return
            
        bid, num = board_info.split('-', 1)
        
        if bid in data["boards"]:
            max_val = data["boards"][bid]["max"]
            if not num.isdigit() or int(num) > max_val or int(num) < 1:
                bot.send_message(message.chat.id, f"❌ ስህተት! በሰሌዳ {bid} ላይ ያሉት ቁጥሮች ከ1-{max_val} ብቻ ናቸው።")
                return

            data["boards"][bid]["slots"][num] = name[:15]
            save_data()
            update_group_board(bid)
            bot.send_message(message.chat.id, f"✅ ሰሌዳ {bid} ቁጥር {num} ለ {name} ተመዝግቧል!")
        else:
            bot.send_message(message.chat.id, f"❌ ሰሌዳ {bid} አልተገኘም!")
    except:
        bot.send_message(message.chat.id, "❌ ሲስተም ስህተት! አጻጻፍ፦ 1-05 አበበ")

def process_admin_delete(message):
    try:
        text = message.text.strip()
        if '-' not in text:
            bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 1-05")
            return
            
        bid, num = text.split('-', 1)
        if bid in data["boards"]:
            if num in data["boards"][bid]["slots"]:
                del data["boards"][bid]["slots"][num]
                save_data()
                update_group_board(bid)
                bot.send_message(message.chat.id, f"🗑 ሰሌዳ {bid} ቁጥር {num} ተሰርዟል!")
            else:
                bot.send_message(message.chat.id, "❌ ይህ ቁጥር ገና አልተመዘገበም!")
        else:
            bot.send_message(message.chat.id, "❌ ሰሌዳው አልተገኘም!")
    except:
        bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 1-05")

# --- 🟢 የአጽድቅ (Approve) Logic ---
# --- 1. አጽድቅ ሲጫን ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('g_app_'))
def approve_receipt_step(call):
    if call.from_user.id not in ADMIN_IDS: return
    try:
        # ✅ የቆዩ ትዕዛዞች ካሉ ማጽጃ (Sync ችግርን ይፈታል)
        bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
        
        _, _, target_id, receipt_mid = call.data.split('_')
        
        # 📝 ማሳሰቢያ፦ bot.delete_message እዚህ ጋር የለም፣ ስለዚህ ደረሰኙ አይጠፋም
        
        msg = bot.send_message(call.from_user.id, f"💰 ለ ID <code>{target_id}</code> የሚጨመረውን ብር ይጻፉ፦", parse_mode="HTML")
        
        # ብሩን ተቀብሎ ስራውን የሚጨርሰው ፈንክሽን
        bot.register_next_step_handler(msg, finalize_app, target_id)
    except Exception as e:
        print(f"Error: {e}")

# --- 2. ብሩን ተቀብሎ መጨረሻ ላይ የሚሰራው ---
def finalize_app(message, target_id):
    # አድሚን መሆኑን ማረጋገጥ
    if message.from_user.id not in ADMIN_IDS: return

    # የቆየውን ሂደት ማጽዳት (ይህ ሲጨመር ስህተት የሚለውን መልዕክት ያስቀረዋል)
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(message.chat.id, "❌ ስህተት! እባክዎ ቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, finalize_app, target_id)
        return

    try:
        amt = int(message.text.strip())
        uid = str(target_id)
        user = get_user(uid)
        user["wallet"] += amt
        save_data()
        
        # ... የተቀረው የኮድዎ ክፍል ...
        bot.send_message(message.chat.id, f"✅ {amt} ብር ለ {user['name']} ተጨምሯል።")

        # ንቁ ሰሌዳዎችን መፈለግ
        active_boards = [bid for bid, info in data["boards"].items() if info["active"]]
        markup = types.InlineKeyboardMarkup(row_width=5)
        
        # ✅ መስተካከያ፦ አንድ ሰሌዳ ብቻ ካለ በመጠቀም ሰሌዳውን መለየት
        if len(active_boards) == 1:
            bid = active_boards 
            board = data["boards"][bid]
            slots = board.get("slots", {})
            max_slots = board.get("max", 25)
            
            btns = []
            for i in range(1, max_slots + 1):
                if str(i) not in slots:
                    btns.append(types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}_{uid}"))
            
            markup.add(*btns)
            text = (f"✅ <b>ክፍያ ጸድቋል!</b>\n"
                    f"👤 <b>ተጫዋች፦</b> {user['name']}\n"
                    f"💰 <b>ሂሳብ፦</b> {user['wallet']} ብር\n\n"
                    f"👇 <b>እባክዎ ቁጥርዎን ይምረጡ፦</b>")
        
        # ሰሌዳ ከአንድ በላይ ከሆነ
        else:
            for b in active_boards:
                markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b}", callback_data=f"u_select_{uid}_{b}"))
            text = (f"✅ <b>ክፍያ ጸድቋል!</b>\n"
                    f"👤 <b>ተጫዋች፦</b> {user['name']}\n"
                    f"💰 <b>ሂሳብ፦</b> {user['wallet']} ብር\n\n"
                    f"👇 <b>እባክዎ መጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦</b>")

        # ግሩፕ ላይ መላክ
        bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")
        bot.send_message(message.chat.id, f"✅ ለ {user['name']} {amt} ብር ተጨምሮ ቁጥር መምረጫ ተልኳል።")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት ተከስቷል፦ {str(e)}")


# --- 🔴 የውድቅ (Reject) Logic ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('g_rej_'))
def reject_receipt_step(call):
    if call.from_user.id not in ADMIN_IDS: return
    try:
        # በተኑን ማጥፋት
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        _, _, target_id, _ = call.data.split('_')
        
        msg = bot.send_message(call.from_user.id, f"❌ ለ ID <code>{target_id}</code> ውድቅ የተደረገበትን ምክንያት ይጻፉ፦", parse_mode="HTML")
        # ምክንያቱን ተቀብሎ ለተጫዋቹ የሚልከው ፈንክሽን
        bot.register_next_step_handler(msg, finalize_rejection, target_id)
    except Exception as e:
        print(f"Error in reject: {e}")


@bot.callback_query_handler(func=lambda call: call.data == "admin_delete")
def start_admin_delete(call):
    m = bot.send_message(call.from_user.id, "🗑 <b>ቁጥር ለመሰረዝ፦</b>\nሰሌዳ-ቁጥር ይጻፉ\n\nምሳሌ፦ <code>1-05</code>")
    bot.register_next_step_handler(m, process_admin_delete)

def process_admin_delete(message):
    try:
        bid, num = message.text.split('-')
        if bid in data["boards"] and num in data["boards"][bid]["slots"]:
            del data["boards"][bid]["slots"][num]
            save_data()
            update_group_board(bid) # 👈 እዚህ ጋር ነው ዲዛይኑን ግሩፕ ላይ የሚያድሰው
            bot.send_message(message.chat.id, f"🗑 ሰሌዳ {bid} ቁጥር {num} ተሰርዟል!")
    except: bot.send_message(message.chat.id, "❌ ስህተት! (አጻጻፍ፦ 1-05)")


@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    uid = str(call.from_user.id)
    
    # 1. አድሚኑ ማፅደቂያ ሲነካ
    if call.data.startswith('approve_') and is_admin:
        target = call.data.split('_')
        m = bot.send_message(call.from_user.id, f"💵 ለ ID {target} የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_app, target)

    # 2. ውድቅ ማድረጊያ (Decline)
    elif call.data.startswith('decline_') and is_admin:
        target = call.data.split('_')
        bot.edit_message_caption("❌ ደረሰኙ ውድቅ ተደርጓል", call.message.chat.id, call.message.message_id, reply_markup=None)
        m = bot.send_message(call.from_user.id, "❌ ውድቅ የተደረገበትን ምክንያት ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_dec, target)

    # 3. ከብዙ ሰሌዳዎች አንዱን ሲመርጡ (u_select_)
    elif call.data.startswith('u_select_'):
        parts = call.data.split('_')
        target_id = parts
        bid = parts
        
        if uid != target_id:
            bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
            return
            
        markup = generate_picker_markup(uid, bid)
        text = (f"🎰 <b>ሰሌዳ {bid} ተመርጧል!</b>\n"
                f"💰 <b>ቀሪ ሂሳብ፦</b> {data['users'][uid]['wallet']} ብር\n"
                f"እባክዎ ቁጥር ይምረጡ፦")
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    # 4. ዝርግፍ ቁጥሮች ላይ ምርጫ ሲያደርጉ (p_)
    elif call.data.startswith('p_'):
        parts = call.data.split('_')
        target_id = parts
        bid = parts
        num = parts
        
        if uid != target_id:
            bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
            return
            
        # ወደ ዋናው የክፍያ ፈንክሽን መላክ (finalize_reg_inline ጋር ተመሳሳይ ስራ ይሰራል)
        call.data = f"pick_{bid}_{num}"
        finalize_reg_inline(call, bid, num)

    # 5. የተቀሩት የአድሚን እና የቦት ተግባራት
    elif call.data == "lookup_winner" and is_admin:
        m = bot.send_message(call.from_user.id, "አሸናፊ ለመፈለግ ሰሌዳ እና ቁጥር ይጻፉ (ለምሳሌ: 2-13)፦")
        bot.register_next_step_handler(m, process_lookup)
    elif call.data == "admin_manage" and is_admin: admin_manage_menu(call)
    elif call.data.startswith('edit_') and is_admin: edit_board(call)
    elif call.data.startswith('toggle_') and is_admin:
        bid = call.data.split('_')
        data["boards"][bid]["active"] = not data["boards"][bid]["active"]
        save_data(); edit_board(call)
    elif call.data == "admin_reset" and is_admin: reset_menu(call)
    elif call.data.startswith('doreset_') and is_admin:
        bid = call.data.split('_')
        data["boards"][bid]["slots"] = {}; data["pinned_msgs"][bid] = None
        save_data(); bot.answer_callback_query(call.id, "ሰሌዳው ጸድቷል!"); update_group_board(bid)
    elif call.data.startswith('select_'): handle_selection(call)
    elif call.data == "taken":
        bot.answer_callback_query(call.id, "❌ ይህ ቁጥር ተይዟል!")

def generate_picker_markup(uid, bid):
    board = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = []
    for i in range(1, board["max"] + 1):
        n_str = str(i)
        # ቁጥሩ ከተያዘ ❌ ያሳያል፣ ካልተያዘ ቁጥሩን ያሳያል
        if n_str not in board["slots"]:
            btns.append(types.InlineKeyboardButton(n_str, callback_data=f"p_{uid}_{bid}_{n_str}"))
        else:
            btns.append(types.InlineKeyboardButton("❌", callback_data="taken"))
    markup.add(*btns)
    return markup


def process_lookup(message):
    try:
        load_data()
        text = message.text.strip()
        
        if '-' not in text:
            bot.send_message(message.chat.id, "⚠️ አጻጻፍ ተሳስቷል! ለምሳሌ፦ <code>2-06</code>", parse_mode="HTML")
            return

        bid, num_raw = text.split('-')
        num = str(int(num_raw)) 

        if bid in data["boards"]:
            board_slots = data["boards"][bid].get("slots", {})
            winner_name = board_slots.get(num)
            
            if winner_name:
                # ✅ ትክክለኛውን የተጫዋች ID ብቻ መፈለጊያ (የግሩፕ IDን ችላ ይላል)
                winner_id = None
                for uid, info in data["users"].items():
                    if info.get("name") == winner_name and not uid.startswith('-'):
                        winner_id = uid
                        break
                
                res = f"🏆 <b>አሸናፊ ተገኝቷል!</b>\n\n"
                
                if winner_id:
                    # የተጫዋች አካውንት ሊንክ
                    res += f"👤 <b>ተጫዋች፦</b> <a href='tg://user?id={winner_id}'>{winner_name}</a>\n"
                    res += f"🆔 <b>User ID፦</b> <code>{winner_id}</code>\n"
                else:
                    # IDው ካልተገኘ (በካሽ የተመዘገበ)
                    res += f"👤 <b>ተጫዋች፦</b> {winner_name} (በካሽ የተመዘገበ)\n"
                
                res += f"🎰 <b>ሰሌዳ፦</b> {bid} | <b>ቁጥር፦</b> {num}\n"
                res += f"━━━━━━━━━━━━━━━━━━━━━\n"
                res += f"🔗 <i>ስሙን በመንካት በቀጥታ ማውራት ይችላሉ።</i>"
                
                bot.send_message(message.chat.id, res, parse_mode="HTML")
            else: 
                bot.send_message(message.chat.id, f"⚠️ በሰሌዳ {bid} ላይ ቁጥር {num} እስካሁን አልተያዘም!")
        else:
            bot.send_message(message.chat.id, f"⚠️ ሰሌዳ {bid} አልተገኘም!")
            
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ ስህተት! እባክዎ በትክክል ይጻፉ (ለምሳሌ: 2-13)")

def handle_selection(call):
    bid = call.data.split('_')[1]; user = get_user(call.message.chat.id)
    board = data["boards"][bid]
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True); return
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{bid}_{i}") for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
    markup.add(*btns)
    bot.edit_message_text(f"🎰 <b>ሰሌዳ {bid}</b>\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር\n\nቁጥር ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

def finalize_reg_inline(call, bid, num):
    uid = str(call.message.chat.id); user = get_user(uid); board = data["boards"][bid]
    if user["wallet"] < board["price"]: bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!"); return
    data["users"][uid]["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data(); update_group_board(bid); bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")
    
    # --- አውቶማቲክ ማሳሰቢያ ---
    remaining = board["max"] - len(board["slots"])
    milestones = [35, 20, 10, 5, 2]
    if remaining in milestones:
        msg = (f"🎰 <b>ሰሌዳ {bid} ሊሞላ ነው!</b>\n"
               f"━━━━━━━━━━━━━━━━━━━━━\n"
               f"🔥 ዕጣ ለመውጣት <b>{remaining}</b> ሰዎች ብቻ ቀረን!\n"
               f"🏃‍♂️ አሁኑኑ እድሎን ይሞክሩ!")
        try: bot.send_message(GROUP_ID, msg)
        except: pass

    if user["wallet"] >= board["price"]: handle_selection(call)
    else: bot.edit_message_text(f"✅ ምዝገባ ተጠናቋል።\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር", uid, call.message.message_id, reply_markup=main_menu_markup(uid))

def manage_menu(call):
    markup = types.InlineKeyboardMarkup()
    for bid in data["boards"]: markup.add(types.InlineKeyboardButton(f"ሰሌዳ {bid}", callback_data=f"edit_{bid}"))
    bot.edit_message_text("ሰሌዳ ይምረጡ፦", call.from_user.id, call.message.message_id, reply_markup=markup)

def edit_board(call):
    bid = call.data.split('_')[1]; b = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton(f"{'🟢 ክፍት' if b['active'] else '🔴 ዝግ'}", callback_data=f"toggle_{bid}"))
    markup.add(types.InlineKeyboardButton("🎫 ዋጋ", callback_data=f"set_price_{bid}"), types.InlineKeyboardButton("🎁 ሽልማት", callback_data=f"set_prize_{bid}"))
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
    bot.edit_message_text(f"📊 <b>ሰሌዳ {bid}</b>\n💰 መደብ፦ {b['price']}\n🏆 ሽልማት፦ {b['prize']}", call.from_user.id, call.message.message_id, reply_markup=markup)

# ✅ ብር ጨምሮ ግሩፕ ላይ Picker የሚልከው
def finalize_app(message, target_id):
    # 🕵️‍♂️ ሂደቱን መጀመሪያ እዚህ እናጽዳ (ስህተቱ እንዳይደጋገም)
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

    # ቁጥር መሆኑን ማረጋገጥ
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(message.chat.id, "❌ ስህተት! እባክዎ ቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, finalize_app, target_id)
        return

    try:
        amt = int(message.text.strip())
        uid = str(target_id)
        
        if uid not in data["users"]:
            data["users"][uid] = {"name": "ተጫዋች", "wallet": 0}
            
        data["users"][uid]["wallet"] += amt
        save_data()
        
        user_name = data["users"][uid]["name"]
        active_boards = [bid for bid, info in data["boards"].items() if info["active"]]
        
        # ✅ አንድ ሰሌዳ ብቻ ክፍት ከሆነ
        if len(active_boards) == 1:
            bid = active_boards # ዝርዝሩ ውስጥ ያለውን የመጀመሪያውን ሰሌዳ መውሰድ
            markup = generate_picker_markup(uid, bid) # እዚህ ጋር bid አሁን ቁጥር ነው
            text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n"
                    f"👤 <b>ተጫዋች፦</b> {user_name}\n"
                    f"💰 <b>ሂሳብ፦</b> {data['users'][uid]['wallet']} ብር\n"
                    f"🎰 <b>ሰሌዳ {bid}</b> - እባክዎ ቁጥር ይምረጡ፦")
            bot.send_message(GROUP_ID, text, reply_markup=markup)
            
        # ✅ ከአንድ በላይ ከሆኑ ምርጫ እንዲመጣ ይደረጋል
        elif len(active_boards) > 1:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for b in active_boards:
                price = data["boards"][b]["price"]
                markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b} ({price} ብር)", callback_data=f"u_select_{uid}_{b}"))
            
            text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n"
                    f"👤 <b>ተጫዋች፦</b> {user_name}\n"
                    f"💰 <b>ሂሳብ፦</b> {data['users'][uid]['wallet']} ብር\n\n"
                    f"❓ <b>እባክዎ መጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦</b>")
            bot.send_message(GROUP_ID, text, reply_markup=markup)
        
        else:
            bot.send_message(message.chat.id, "⚠️ ምንም ንቁ ሰሌዳ የለም።")
            return

        bot.send_message(message.chat.id, f"✅ {amt} ብር ተጨምሮ ማረጋገጫ ግሩፕ ላይ ተልኳል።")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት ተከስቷል፦ {e}")

# ❌ ለተጫዋቹ የውድቅ መልዕክት የሚልከው
def finalize_rejection(message, target_id):
    reason = message.text
    try:
        rej_text = f"❌ <b>ደረሰኝዎ ውድቅ ተደርጓል!</b>\n━━━━━━━━━━━━━\n📝 <b>ምክንያት፦</b> {reason}\n\n🙏 እባክዎ በትክክለኛ መረጃ በድጋሚ ግሩፕ ላይ ይላኩ።"
        bot.send_message(target_id, rej_text, parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ የውድቅ መልዕክት ለተጫዋቹ ተልኳል።")
    except:
        bot.send_message(message.chat.id, "⚠️ ለተጫዋቹ መልዕክት ማድረስ አልተቻለም (ቦቱን Start አላደረገም)።")

def reset_menu(call):
    markup = types.InlineKeyboardMarkup()
    for bid in data["boards"]: markup.add(types.InlineKeyboardButton(f"Reset {bid}", callback_data=f"doreset_{bid}"))
    bot.send_message(call.from_user.id, "የትኛው ሰሌዳ ይጽዳ?", reply_markup=markup)

def finalize_dec(message, target): bot.send_message(target, f"❌ ደረሰኝዎ ውድቅ ሆኗል። ምክንያት፦ {message.text}")

def update_board_value(message, bid, action):
    try:
        if action == "price": data["boards"][bid]["price"] = int(message.text)
        else: data["boards"][bid]["prize"] = message.text
        save_data(); bot.send_message(message.chat.id, "✅ ተቀይሯል!"); update_group_board(bid)
    except: bot.send_message(message.chat.id, "⚠️ ስህተት!")

@bot.message_handler(commands=['update'])
def force_update(message):
    if message.from_user.id in ADMIN_IDS:
        for bid in data["boards"]:
            update_group_board(bid)
        bot.send_message(message.chat.id, "✅ ሁሉም ሰሌዳዎች ግሩፕ ላይ ታድሰዋል!")
    
    
if __name__ == "__main__":
    # ለጊዜው ይህንን ጨምር (አንድ ጊዜ Deploy ካደረግክ በኋላ መልሰህ ብታጠፋው ይሻላል)
    save_data()
    
    keep_alive()
    # ... ሌላው የ bot.polling ኮድ ይቀጥላል
    bot.remove_webhook()
    while True:
        try: bot.polling(none_stop=True, interval=1, timeout=20)
        except: time.sleep(5)
