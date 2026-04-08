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

# --- 📸 ደረሰኝ መቀበያ (ከግሩፕ ብቻ) ---
@bot.message_handler(content_types=['photo'])
def handle_group_receipt(message):
    if message.chat.id != GROUP_ID:
        return

    if message.from_user.id in ADMIN_IDS:
        return 

    uid = str(message.from_user.id)
    name = message.from_user.first_name if message.from_user.first_name else "ተጫዋች"
    mid = message.message_id 

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_approve = types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"g_app_{uid}_{mid}")
    btn_reject = types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"g_rej_{uid}_{mid}")
    markup.add(btn_approve, btn_reject)

    cap = (f"📩 <b>አዲስ ደረሰኝ ከግሩፕ</b>\n"
           f"━━━━━━━━━━━━━\n"
           f"👤 <b>ከ፦</b> {name}\n"
           f"🆔 <b>User ID፦</b> <code>{uid}</code>\n"
           f"📝 <b>ሁኔታ፦</b> ማረጋገጫ እየጠበቀ...")

    for adm in ADMIN_IDS:
        try:
            bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            print(f"Error sending to admin {adm}: {e}")

# --- ✅ የደረሰኝ ማጽደቂያ ወይም ውድቅ ማድረጊያ Logic ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("g_app_", "g_rej_")))
def handle_receipt_actions(call):
    data_parts = call.data.split("_")
    action = data_parts
    user_id = int(data_parts)
    msg_id = int(data_parts)

    if action == "app":
        bot.send_message(user_id, "✅ ደረሰኝዎ ተረጋግጧል! አሁን የሚፈልጉትን ቁጥር መምረጥ ይችላሉ።")
        bot.edit_message_caption("✅ ይህ ደረሰኝ ጸድቋል", call.message.chat.id, call.message.message_id)
    elif action == "rej":
        bot.send_message(user_id, "❌ ደረሰኝዎ ውድቅ ተደርጓል። እባክዎ ትክክለኛ መሆኑን አረጋግጠው በድጋሚ ይላኩ።")
        bot.edit_message_caption("❌ ይህ ደረሰኝ ውድቅ ተደርጓል", call.message.chat.id, call.message.message_id)

# --- 🛠 የአድሚን ማስተዳደሪያ ሰሌዳ ---
@bot.callback_query_handler(func=lambda call: call.data in ["admin_manage", "manage_boards", "admin_panel_back"] and call.from_user.id in ADMIN_IDS)
def admin_manage_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💵 በካሽ መዝግብ", callback_data="admin_cash"),
        types.InlineKeyboardButton("❌ ቁጥር ሰርዝ", callback_data="admin_delete")
    )
    
    for bid in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"⚙️ ሰሌዳ {bid} አስተካክል", callback_data=f"edit_{bid}"))

    bot.edit_message_text("🛠 <b>የአድሚን ስራዎችን ይምረጡ፦</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# --- 💵 በካሽ መመዝገቢያ ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_cash")
def start_cash_reg(call):
    m = bot.send_message(call.from_user.id, "📝 <b>በካሽ ለመመዝገብ፦</b>\nሰሌዳ-ቁጥር ስም ይጻፉ\n\nምሳሌ፦ <code>1-05 አበበ</code>", parse_mode="HTML")
    bot.register_next_step_handler(m, process_cash_reg)

def process_cash_reg(message):
    try:
        text = message.text.strip()
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
    except Exception as e:
        bot.send_message(message.chat.id, "❌ ሲስተም ስህተት! እባክዎ እንደገና ይሞክሩ።")

# --- 🗑 ቁጥር መሰረዣ ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_delete")
def start_admin_delete(call):
    m = bot.send_message(call.from_user.id, "🗑 <b>ቁጥር ለመሰረዝ፦</b>\nሰሌዳ-ቁጥር ይጻፉ\n\nምሳሌ፦ <code>1-05</code>", parse_mode="HTML")
    bot.register_next_step_handler(m, process_admin_delete)

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
    except Exception as e:
        bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 1-05")

# --- 🟢 የአጽድቅ (Approve) Logic ---

# --- 1. አጽድቅ ሲጫን ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('g_app_'))
def approve_receipt_step(call):
    if call.from_user.id not in ADMIN_IDS: return
    try:
        # Sync ችግርን ለመከላከል የቆዩ ትዕዛዞችን ማጽጃ
        bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)

        # ዳታውን መበተን (g_app_uid_mid)
        data_parts = call.data.split('_')
        target_id = data_parts
        # receipt_mid = data_parts # አስፈላጊ ከሆነ መጠቀም ይቻላል

        msg = bot.send_message(call.from_user.id, f"💰 ለ ID <code>{target_id}</code> የሚጨመረውን ብር ይጻፉ፦", parse_mode="HTML")

        # ብሩን ተቀብሎ ስራውን የሚጨርሰው ፈንክሽን
        bot.register_next_step_handler(msg, finalize_app, target_id)
        
        # ለአድሚኑ ደረሰኙ ላይ ምልክት ማድረግ
        bot.edit_message_caption(f"⏳ ለ {target_id} ብር እየተጨመረ ነው...", call.message.chat.id, call.message.message_id)
        
    except Exception as e:
        print(f"Error in approve_receipt_step: {e}")

# --- 2. ብሩን ተቀብሎ መጨረሻ ላይ የሚሰራው ---
def finalize_app(message, target_id):
    # መጀመሪያ የቀድሞውን Step handler እናጽዳ
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

    val = message.text.strip() if message.text else ""
    if not val.isdigit():
        msg = bot.send_message(message.chat.id, "❌ ስህተት! እባክዎ ቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, finalize_app, target_id)
        return

    try:
        amt = int(val)
        uid = str(target_id)

        # የተጫዋች ዳታ ማረጋገጫ (ከሌለ መፍጠር)
        if "users" not in data: data["users"] = {}
        if uid not in data["users"]:
            data["users"][uid] = {"name": "ተጫዋች", "wallet": 0}

        data["users"][uid]["wallet"] += amt
        save_data()

        # 🟢 ንቁ ሰሌዳዎችን መፈለግ
        active_boards = [str(bid) for bid, info in data["boards"].items() if info.get("active", False)]

        if not active_boards:
            bot.send_message(message.chat.id, f"✅ {amt} ብር ለ {uid} ተጨምሯል። ነገር ግን በአሁኑ ሰዓት ምንም ክፍት ሰሌዳ የለም።")
            bot.send_message(uid, f"✅ {amt} ብር በwalletዎ ላይ ተጨምሯል። ክፍት ሰሌዳ ሲኖር ማሳወቂያ እንልካለን።")
            return

        # ✅ ማስተካከያ፦ አንድ ሰሌዳ ብቻ ካለ (active_boards በመጠቀም ከዝርዝር ማውጣት)
        if len(active_boards) == 1:
            bid = active_boards # ዝርዝሩን ሰብሮ የመጀመሪያውን ጽሁፍ ይወስዳል

            # generate_picker_markup በሌላው የኮድህ ክፍል መኖሩን እርግጠኛ ሁን
            markup = generate_picker_markup(uid, bid)
            text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n"
                    f"👤 <b>ተጫዋች፦</b> <a href='tg://user?id={uid}'>ተጫዋች</a>\n"
                    f"💰 <b>የአሁኑ ሂሳብ፦</b> {data['users'][uid]['wallet']} ብር\n\n"
                    f"🎰 <b>ሰሌዳ {bid}</b> - እባክዎ ቁጥር ይምረጡ፦")
            bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")

        # ✅ ከአንድ በላይ ክፍት ሰሌዳዎች ካሉ ምርጫ መስጠት
        else:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for b in active_boards:
                price = data["boards"][b].get("price", 0)
                markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b} ({price} ብር)", callback_data=f"u_select_{uid}_{b}"))

            text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n"
                    f"👤 <b>ተጫዋች፦</b> <a href='tg://user?id={uid}'>ተጫዋች</a>\n"
                    f"💰 <b>የአሁኑ ሂሳብ፦</b> {data['users'][uid]['wallet']} ብር\n\n"
                    f"❓ ብዙ ክፍት ሰሌዳዎች ስላሉ እባክዎ አንዱን ይምረጡ፦")
            bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")

        bot.send_message(message.chat.id, f"✅ ለ {uid} {amt} ብር ተጨምሮለታል።")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ የሲስተም ስህተት፦ {str(e)}")
        print(f"Finalize App Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_delete")
def start_admin_delete(call):
    m = bot.send_message(call.from_user.id, "🗑 <b>ቁጥር ለመሰረዝ፦</b>\nሰሌዳ-ቁጥር ይጻፉ\n\nምሳሌ፦ <code>1-05</code>")
    bot.register_next_step_handler(m, process_admin_delete)

def process_admin_delete(message):
    try:
        text = message.text.strip()
        if '-' not in text:
            bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ 1-05")
            return
            
        # መረጃውን በትክክል መከፋፈል
        parts = text.split('-')
        bid = parts.strip()
        num = parts.strip()
        
        if bid in data["boards"]:
            if num in data["boards"][bid]["slots"]:
                del data["boards"][bid]["slots"][num]
                save_data()
                update_group_board(bid)
                bot.send_message(message.chat.id, f"🗑 ሰሌዳ {bid} ቁጥር {num} ተሰርዟል!")
            else:
                bot.send_message(message.chat.id, f"❌ ቁጥር {num} በሰሌዳ {bid} ላይ አልተመዘገበም!")
        else:
            bot.send_message(message.chat.id, f"❌ ሰሌዳ {bid} አልተገኘም!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት፦ {str(e)}")


@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    uid = str(call.from_user.id)

    # 1. አድሚኑ ማፅደቂያ ሲነካ
    if call.data.startswith('approve_') and is_admin:
        parts = call.data.split('_')
        target_id = parts # approve_uid -> index 1
        m = bot.send_message(call.from_user.id, f"💵 ለ ID <code>{target_id}</code> የሚጨመረውን ብር ይጻፉ፦", parse_mode="HTML")
        bot.register_next_step_handler(m, finalize_app, target_id)

    # 2. ውድቅ ማድረጊያ (Decline)
    elif call.data.startswith('decline_') and is_admin:
        parts = call.data.split('_')
        target_id = parts
        bot.edit_message_caption("❌ ደረሰኙ ውድቅ ተደርጓል", call.message.chat.id, call.message.message_id, reply_markup=None)
        m = bot.send_message(call.from_user.id, "❌ ውድቅ የተደረገበትን ምክንያት ይጻፉ፦")
        bot.register_next_step_handler(m, finalize_dec, target_id)

    # --- ተጫዋቹ ሰሌዳ ሲመርጥ ---
    elif call.data.startswith('u_select_'):
        parts = call.data.split('_')
        # u_select_uid_bid
        target_id = parts
        bid = parts

        if uid != target_id:
            bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
            return

        markup = generate_picker_markup(uid, bid)
        text = (f"🎰 <b>ሰሌዳ {bid} ተመርጧል!</b>\n"
                f"💰 <b>ቀሪ ሂሳብ፦</b> {data['users'][uid]['wallet']} ብር\n"
                f"እባክዎ ቁጥር ይምረጡ፦")
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # --- ተጫዋቹ ቁጥር ሲመርጥ ---
    elif call.data.startswith('p_'):
        parts = call.data.split('_')
        # p_uid_bid_num
        target_id = parts
        bid = parts
        num = parts

        if uid != target_id:
            bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
            return

        finalize_reg_inline(call, bid, num)

    # --- አድሚን ተግባራት ---
    elif call.data == "lookup_winner" and is_admin:
        m = bot.send_message(call.from_user.id, "አሸናፊ ለመፈለግ ሰሌዳ እና ቁጥር ይጻፉ (ለምሳሌ: 2-13)፦")
        bot.register_next_step_handler(m, process_lookup)
    
    elif call.data == "admin_manage" and is_admin: 
        admin_manage_menu(call)
    
    elif call.data.startswith('edit_') and is_admin: 
        edit_board(call)
    
    elif call.data.startswith('toggle_') and is_admin:
        bid = call.data.split('_')
        data["boards"][bid]["active"] = not data["boards"][bid].get("active", False)
        save_data()
        edit_board(call)
        bot.answer_callback_query(call.id, f"ሰሌዳ {bid} {'ተከፍቷል' if data['boards'][bid]['active'] else 'ተዘግቷል'}")

    elif call.data == "admin_reset" and is_admin: 
        reset_menu(call)
    
    elif call.data.startswith('doreset_') and is_admin:
        bid = call.data.split('_')
        data["boards"][bid]["slots"] = {}
        data["pinned_msgs"][bid] = None
        save_data()
        bot.answer_callback_query(call.id, "ሰሌዳው ጸድቷል!")
        update_group_board(bid)
        edit_board(call)

    elif call.data == "taken":
        bot.answer_callback_query(call.id, "❌ ይህ ቁጥር ተይዟል!", show_alert=False)

    # ዋጋ ለመቀየር
    elif call.data.startswith('set_price_') and is_admin:
        bid = call.data.split('_')
        msg = bot.send_message(call.from_user.id, f"🎫 ለሰሌዳ {bid} አዲስ ዋጋ ያስገቡ፦")
        bot.register_next_step_handler(msg, update_board_value, bid, "price")

    # ሽልማት ለመቀየር
    elif call.data.startswith('set_prize_') and is_admin:
        bid = call.data.split('_')
        msg = bot.send_message(call.from_user.id, f"🎁 ለሰሌዳ {bid} አዲስ የሽልማት ዝርዝር ያስገቡ፦")
        bot.register_next_step_handler(msg, update_board_value, bid, "prize")

# --- አሸናፊ መፈለጊያ ---
def process_lookup(message):
    try:
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
                winner_id = None
                for u_id, info in data["users"].items():
                    if info.get("name") == winner_name and not u_id.startswith('-'):
                        winner_id = u_id
                        break

                res = f"🏆 <b>አሸናፊ ተገኝቷል!</b>\n\n"
                if winner_id:
                    res += f"👤 <b>ተጫዋች፦</b> <a href='tg://user?id={winner_id}'>{winner_name}</a>\n"
                    res += f"🆔 <b>User ID፦</b> <code>{winner_id}</code>\n"
                else:
                    res += f"👤 <b>ተጫዋች፦</b> {winner_name} (በካሽ)\n"

                res += f"🎰 <b>ሰሌዳ፦</b> {bid} | <b>ቁጥር፦</b> {num}\n"
                bot.send_message(message.chat.id, res, parse_mode="HTML")
            else: 
                bot.send_message(message.chat.id, f"⚠️ በሰሌዳ {bid} ላይ ቁጥር {num} አልተያዘም!")
        else:
            bot.send_message(message.chat.id, f"⚠️ ሰሌዳ {bid} አልተገኘም!")
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ ስህተት! እባክዎ በትክክል ይጻፉ (ለምሳሌ: 2-13)")


# --- 🎰 ተጫዋቹ ቁጥር እንዲመርጥ ማሳያ (Picker) ---
def handle_selection(call):
    try:
        bid = call.data.split('_')
        user = get_user(call.message.chat.id)
        board = data["boards"][bid]
        
        if user["wallet"] < board["price"]:
            bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True)
            return
            
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(str(i), callback_data=f"p_{call.message.chat.id}_{bid}_{i}") 
                for i in range(1, board["max"] + 1) if str(i) not in board["slots"]]
        markup.add(*btns)
        
        bot.edit_message_text(f"🎰 <b>ሰሌዳ {bid}</b>\n💰 ቀሪ ሂሳብ፦ {user['wallet']} ብር\n\nቁጥር ይምረጡ፦", 
                              call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"Error in handle_selection: {e}")

# --- ✅ ቁጥር ምርጫን ማጠናቀቂያ ---
def finalize_reg_inline(call, bid, num):
    uid = str(call.from_user.id) # call.message.chat.id ፈንታ call.from_user.id መጠቀም የተሻለ ነው
    user = get_user(uid)
    board = data["boards"][bid]
    
    if user["wallet"] < board["price"]: 
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True)
        return
        
    # ሂሳብ መቀነስ እና ቁጥሩን መመዝገብ
    data["users"][uid]["wallet"] -= board["price"]
    board["slots"][str(num)] = user["name"]
    save_data()
    update_group_board(bid)
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")

        # --- የነበረው አውቶማቲክ ማሳሰቢያ ተወግዷል ---
    # የቀረው ቁጥር መቁጠሪያ ብቻ (አስፈላጊ ከሆነ)
    remaining = board["max"] - len(board["slots"])

    # ተጫዋቹ አሁንም ብር ካለው በዚያው እንዲቀጥል Picker ማሳየት
    if data["users"][uid]["wallet"] >= board["price"]:
        markup = generate_picker_markup(uid, bid)
        bot.edit_message_text(f"✅ ቁጥር {num} ተመዝግቧል!\n💰 ቀሪ ሂሳብ፦ {data['users'][uid]['wallet']} ብር\n\nሌላ ቁጥር ይጨምሩ፦", 
                              call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.edit_message_text(f"✅ ምዝገባ ተጠናቋል።\n💰 ቀሪ ሂሳብ፦ {data['users'][uid]['wallet']} ብር", 
                              call.message.chat.id, call.message.message_id, parse_mode="HTML")

# --- 📊 የአድሚን ሰሌዳ ማስተካከያ ---
def edit_board(call):
    bid = call.data.split('_')
    b = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    status_text = "🟢 ክፍት" if b.get('active') else "🔴 ዝግ"
    markup.add(types.InlineKeyboardButton(status_text, callback_data=f"toggle_{bid}"))
    markup.add(types.InlineKeyboardButton("🎫 ዋጋ", callback_data=f"set_price_{bid}"), 
               types.InlineKeyboardButton("🎁 ሽልማት", callback_data=f"set_prize_{bid}"))
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
    
    bot.edit_message_text(f"📊 <b>ሰሌዳ {bid} ማስተካከያ</b>\n━━━━━━━━━━━━━\n💰 መደብ፦ {b['price']} ብር\n🏆 ሽልማት፦ {b['prize']}\n📝 ሁኔታ፦ {'ክፍት' if b.get('active') else 'ዝግ'}", 
                          call.from_user.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# --- 💰 ብር ጨምሮ Picker የሚልክ ---
def finalize_app(message, target_id):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

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
        active_boards = [bid for bid, info in data["boards"].items() if info.get("active")]

        if len(active_boards) == 1:
            bid = active_boards # የሊስቱ የመጀመሪያውን ኤለመንት መውሰድ
            markup = generate_picker_markup(uid, bid)
            text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n"
                    f"👤 <b>ተጫዋች፦</b> {user_name}\n"
                    f"💰 <b>ሂሳብ፦</b> {data['users'][uid]['wallet']} ብር\n\n"
                    f"🎰 <b>ሰሌዳ {bid}</b> - እባክዎ ቁጥር ይምረጡ፦")
            bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")

        elif len(active_boards) > 1:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for b in active_boards:
                price = data["boards"][b]["price"]
                markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b} ({price} ብር)", callback_data=f"u_select_{uid}_{b}"))

            text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n"
                    f"👤 <b>ተጫዋች፦</b> {user_name}\n"
                    f"💰 <b>ሂሳብ፦</b> {data['users'][uid]['wallet']} ብር\n\n"
                    f"❓ <b>እባክዎ መጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦</b>")
            bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "⚠️ ብሩ ተጨምሯል ግን ምንም ንቁ ሰሌዳ የለም።")
            return

        bot.send_message(message.chat.id, f"✅ {amt} ብር ለ {uid} ተጨምሮ ማረጋገጫ ግሩፕ ላይ ተልኳል።")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት ተከስቷል፦ {e}")

# --- ❌ ውድቅ ማድረጊያ ---
def finalize_dec(message, target):
    try:
        reason = message.text
        rej_text = (f"❌ <b>ደረሰኝዎ ውድቅ ተደርጓል!</b>\n"
                    f"━━━━━━━━━━━━━\n"
                    f"📝 <b>ምክንያት፦</b> {reason}\n\n"
                    f"🙏 እባክዎ በትክክለኛ መረጃ በድጋሚ ግሩፕ ላይ ይላኩ።")
        bot.send_message(target, rej_text, parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ የውድቅ መልዕክት ለተጫዋቹ ተልኳል።")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ ስህተት፦ {e}")

# --- ⚙️ ዋጋ/ሽልማት ማስተካከያ ---
def update_board_value(message, bid, action):
    try:
        val = message.text.strip()
        if action == "price":
            if not val.isdigit():
                bot.send_message(message.chat.id, "❌ ስህተት! እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ።")
                return
            data["boards"][bid]["price"] = int(val)
        else:
            data["boards"][bid]["prize"] = val

        save_data()
        update_group_board(bid)
        bot.send_message(message.chat.id, f"✅ ሰሌዳ {bid} በትክክል ተስተካክሏል!")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ ስህተት፦ {e}")

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

# --- ❌ ለተጫዋቹ የውድቅ መልዕክት የሚልከው ---
def finalize_rejection(message, target_id):
    # መጀመሪያ የቆዩ step_handlerዎችን እናጽዳ
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    
    reason = message.text if message.text else "ምክንያት አልተጠቀሰም"
    try:
        rej_text = (f"❌ <b>ደረሰኝዎ ውድቅ ተደርጓል!</b>\n"
                    f"━━━━━━━━━━━━━\n"
                    f"📝 <b>ምክንያት፦</b> {reason}\n\n"
                    f"🙏 እባክዎ በትክክለኛ መረጃ በድጋሚ ግሩፕ ላይ ይላኩ።")
        
        # target_id string መሆኑን እናረጋግጥ
        bot.send_message(str(target_id), rej_text, parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ የውድቅ መልዕክት ለተጫዋቹ ተልኳል።")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ ለተጫዋቹ መልዕክት ማድረስ አልተቻለም (ቦቱን Start አላደረገም ወይም ብሎክ አድርጓል)።")

# --- 🧹 ሰሌዳ መጥረጊያ ሜኑ ---
def reset_menu(call):
    if call.from_user.id not in ADMIN_IDS: return
    
    markup = types.InlineKeyboardMarkup()
    for bid in data["boards"]:
        markup.add(types.InlineKeyboardButton(f"🗑 ሰሌዳ {bid} አጽዳ (Reset)", callback_data=f"doreset_{bid}"))
    
    bot.send_message(call.from_user.id, "የትኛው ሰሌዳ እንዲጸዳ ይፈልጋሉ?", reply_markup=markup)

# --- ⚙️ የሰሌዳ ዋጋ እና ሽልማት ማስተካከያ ---
def update_board_value(message, bid, action):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    try:
        val = message.text.strip() if message.text else ""
        if not val:
            bot.send_message(message.chat.id, "❌ ባዶ መረጃ ማስገባት አይቻልም!")
            return

        if action == "price":
            if not val.isdigit():
                bot.send_message(message.chat.id, "❌ ስህተት! እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ።")
                return
            data["boards"][bid]["price"] = int(val)
            msg = f"✅ የሰሌዳ {bid} ዋጋ ወደ {val} ብር ተቀይሯል!"
        else:
            data["boards"][bid]["prize"] = val
            msg = f"✅ የሰሌዳ {bid} ሽልማት ተስተካክሏል!"
            
        save_data()
        update_group_board(bid) # ግሩፑ ላይ ያለውን ሰሌዳ ወዲያው ያድሳል
        bot.send_message(message.chat.id, msg)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ ስህተት ተከስቷል፦ {e}")

# --- 🔄 ሰሌዳዎችን በሃይል ማደሻ (Force Update) ---
@bot.message_handler(commands=['update'])
def force_update(message):
    if message.from_user.id in ADMIN_IDS:
        try:
            for bid in data["boards"]:
                update_group_board(bid)
            bot.send_message(message.chat.id, "✅ ሁሉም ሰሌዳዎች ግሩፕ ላይ ታድሰዋል!")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ ማደስ አልተቻለም፦ {e}")

# --- 🚀 ቦቱን ማስነሻ ---
if __name__ == "__main__":
    # ዳታውን መጀመሪያ ሴቭ ማድረጉ ፋይሉ መኖሩን ያረጋግጣል
    save_data()
    
    # keep_alive() # Flask/UptimeRobot የምትጠቀም ከሆነ ይሄ መቆየት አለበት
    
    print("🤖 ቦቱ ስራ ጀምሯል...")
    
    # ቦቱ ሳይቆራረጥ እንዲሰራ (Error Handling Loop)
    bot.remove_webhook()
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            print(f"Bot Polling Error: {e}")
            time.sleep(5) # ስህተት ሲፈጠር ለ5 ሰከንድ አርፎ እንዲነሳ
