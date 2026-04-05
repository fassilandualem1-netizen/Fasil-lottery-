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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 ሰሌዳ ምረጥ", "👤 ፕሮፋይል", "🎫 የያዝኳቸው ቁጥሮች")
    if int(uid) in ADMIN_IDS: markup.add("⚙️ Admin Settings")
    return markup

# --- 4. የሰሌዳ ዲዛይን (Group View) ---
def update_group_board(b_id):
    b_id = str(b_id)
    board = data["boards"][b_id]
    current_shift = data.get("current_shift", "me")
    active_pay = PAYMENTS[current_shift]
    
    # 🎨 ራስጌ (Header)
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
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

                # 🎫 የቁጥሮች ዝርዝር (ስሙ Bold, Italic እና Code ሆኖ እንዲታይ)
    board_slots = board["slots"]
    for i in range(1, board["max"] + 1):
        n = str(i)
        if n in board_slots:
            # <b><i><code> ስሙን ይበልጥ ያጎላዋል
            text += f"<b>{i}👉</b> <b><i><code>{board_slots[n]}</code></i></b> ✅🏆🙏\n\n"
        else:
            text += f"<b>{i}👉</b> @@@@ ✅🏆🙏\n\n"
            
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += "🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ!</b> 🏟️\n"
    text += "<b>ስልክ ደውሎ ለማግኘት ከፈለጉ፦</b>\n"
    text += "         👇👇👇\n"
    text += "      👉 <code>0973416038</code>\n\n"
    
    text += "      <b>ገቢ ማስገቢያ አማራጮች</b>\n"
    text += "         👇👇👇👇👇\n"
    text += f"👉 <b>Telebirr:</b> <code>{active_pay['tele']}</code>\n"
    text += f"👉 <b>CBE:</b> <code>{active_pay['cbe']}</code>\n"
    text += f"\n🤖 <b>ለመጫወት እዚህ ይጫኑ፦</b> @{bot.get_me().username}"

        # --- ግሩፕ ላይ መልዕክቱን ማስተካከል (Edit) ---
    try:
        msg_id = data.get("pinned_msgs", {}).get(b_id)
        if msg_id:
            bot.edit_message_text(text, GROUP_ID, msg_id, parse_mode="HTML")
        else:
            m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
            if "pinned_msgs" not in data: data["pinned_msgs"] = {}
            data["pinned_msgs"][b_id] = m.message_id
            save_data()
    except Exception as e:
        print(f"Error: {e}")
        m = bot.send_message(GROUP_ID, text, parse_mode="HTML")
        if "pinned_msgs" not in data: data["pinned_msgs"] = {}
        data["pinned_msgs"][b_id] = m.message_id
        save_data()
         
# --- 5. ዋና ዋና ትዕዛዞች ---
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    user = get_user(uid, message.from_user.first_name)
    active_pay = PAYMENTS[data.get("current_shift", "me")]
    
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
        data["current_shift"] = "assistant" if data["current_shift"] == "me" else "me"
        save_data()
        bot.reply_to(message, f"🔄 ፈረቃ ተቀይሯል! አሁን ተረኛው፦ {data['current_shift']}")
    else:
        bot.reply_to(message, "❌ የባለቤትነት መብት የለዎትም።")

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

@bot.message_handler(func=lambda m: m.text == "🎮 ሰሌዳ ምረጥ")
def show_boards(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b_id, b_info in data["boards"].items():
        if b_info["active"]:
            markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} | 🎫 {b_info['price']} ብር", callback_data=f"select_{b_id}"))
    bot.send_message(message.chat.id, "<b>ለመጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦</b>", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎫 የያዝኳቸው ቁጥሮች")
def my_numbers(message):
    uid = str(message.chat.id)
    name = data["users"][uid]["name"]
    found = False
    text = "🎫 <b>የያዟቸው ቁጥሮች፦</b>\n\n"
    for bid, binfo in data["boards"].items():
        user_nums = [n for n, u in binfo["slots"].items() if u == name]
        if user_nums:
            found = True
            text += f"🎰 <b>ሰሌዳ {bid}:</b> {', '.join(user_nums)}\n"
    if not found: text = "⚠️ እስካሁን ምንም ቁጥር አልያዙም!"
    bot.send_message(uid, text)

@bot.message_handler(func=lambda m: m.text == "👤 ፕሮፋይል")
def show_profile(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, f"👤 <b>ፕሮፋይል</b>\n📛 ስም፦ {user['name']}\n💰 ቀሪ፦ {user['wallet']} ብር")

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Settings" and m.from_user.id in ADMIN_IDS)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    stats = "".join([f"📍 ሰሌዳ {bid}: ({len(binfo['slots'])}/{binfo['max']})\n" for bid, binfo in data["boards"].items()])
    markup.add(types.InlineKeyboardButton("⚙️ ሰሌዳዎችን አስተካክል", callback_data="admin_manage"),
               types.InlineKeyboardButton("🔍 አሸናፊ ፈልግ", callback_data="lookup_winner"),
               types.InlineKeyboardButton("🔄 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset"))
    
    # አዲስ ከመላክ ይልቅ መልዕክቱን ማደስ (Edit) ይሻላል
    bot.send_message(message.chat.id, f"🛠 <b>የአድሚን ዳሽቦርድ</b>\n\n{stats}", reply_markup=markup)

# --- 1. የፎቶ መቀበያ (ከግሩፕ ብቻ) ---
@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.id == GROUP_ID)
def handle_group_receipt(message):
    uid = str(message.from_user.id)
    name = message.from_user.first_name if message.from_user.first_name else "ተጫዋች"
    mid = message.message_id

    markup = types.InlineKeyboardMarkup()
    # እዚህ ጋር ስሙን (name) በ callback_data ውስጥ ጨምረነዋል
    markup.add(types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"g_app_{uid}_{mid}_{name}"))
    
    cap = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 <b>ከ፦</b> {name}\n🆔 <b>ID፦</b> <code>{uid}</code>"
    for adm in ADMIN_IDS:
        bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup)
    
    # በግል (Private) ለሚልኩ ተራ ተጠቃሚዎች
    elif message.chat.type == 'private' and message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⏳ ደረሰኝዎ ለባለቤቱ ተልኳል፣ እባክዎ ግሩፕ ላይ ይጠብቁ።")
        for adm in ADMIN_IDS:
            bot.send_photo(adm, message.photo[-1].file_id, caption=f"📩 <b>የውስጥ ደረሰኝ</b>\n👤 {message.from_user.first_name}\n🆔 <code>{uid}</code>", 
                           reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"g_app_{uid}_0")))

# --- 2. ሁሉንም Callback በአንድ ላይ የሚይዝ (The Master Listener) ---
@bot.callback_query_handler(func=lambda call: True)
def master_callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    data_split = call.data.split('_')
    cmd = data_split

    # ✅ ማጽደቂያ (Approve)
    if call.data.startswith('g_app_') and is_admin:
        target_id = data_split
        receipt_mid = data_split
        msg = bot.send_message(call.from_user.id, f"💰 ለ <code>{target_id}</code> የሚጨመረውን ብር ይጻፉ፦")
        bot.register_next_step_handler(msg, send_picker_to_group, target_id, receipt_mid)

    # ❌ ውድቅ ማድረጊያ
    elif call.data.startswith('g_rej_') and is_admin:
        bot.send_message(data_split, "❌ ይቅርታ፣ የላኩት ደረሰኝ ተቀባይነት አላገኘም።")
        bot.answer_callback_query(call.id, "ደረሰኙ ውድቅ ተደርጓል!")

    # 🎰 ቁጥር መምረጫ (p_ID_BID_NUM)
    elif cmd == 'p':
        allowed_id = data_split
        bid = data_split
        num = data_split
        
        if str(call.from_user.id) != str(allowed_id):
            bot.answer_callback_query(call.id, "⚠️ ይቅርታ! ይህ የሌላ ሰው ምርጫ ነው!", show_alert=True)
            return
        
        # ምዝገባ እና ቼክ እዚህ ይገባል (አንተ ከላይ በጻፍከው handle_secure_pick Logic መሰረት)
        process_secure_pick(call, allowed_id, bid, num)

    # ⚙️ አድሚን ዳሽቦርድ ማስተካከያ
    elif call.data == "admin_manage" and is_admin:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("💵 በካሽ መዝግብ", callback_data="admin_cash"),
                   types.InlineKeyboardButton("❌ ቁጥር ሰርዝ", callback_data="admin_delete"))
        for b_id in data["boards"]:
            markup.add(types.InlineKeyboardButton(f"⚙️ ሰሌዳ {b_id} አስተካክል", callback_data=f"edit_{b_id}"))
        markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="back_to_admin"))
        bot.edit_message_text("🛠 <b>የአድሚን ስራዎችን ይምረጡ፦</b>", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "admin_cash" and is_admin:
        m = bot.send_message(call.from_user.id, "📝 <b>በካሽ መዝግብ፦</b> 1-05 አበበ")
        bot.register_next_step_handler(m, process_cash_reg)

    elif call.data == "admin_delete" and is_admin:
        m = bot.send_message(call.from_user.id, "🗑 <b>ቁጥር ሰርዝ፦</b> 1-05")
        bot.register_next_step_handler(m, process_admin_delete)

    elif call.data.startswith('edit_') and is_admin:
        edit_board(call)

    elif call.data == "back_to_admin" and is_admin:
        # ወደ ዋናው አድሚን ፔጅ ይመልሰዋል
        admin_panel(call.message)
        bot.delete_message(call.message.chat.id, call.message.message_id)

# --- 3. ለብቻው የወጣ የቁጥር መመዝገቢያ Logic ---
def process_secure_pick(call, uid, bid, num):
    user = get_user(uid)
    board = data["boards"][bid]
    
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "❌ ሂሳብዎ በቂ አይደለም!", show_alert=True)
        bot.delete_message(GROUP_ID, call.message.message_id)
        return

    # ምዝገባ
    data["users"][uid]["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data()
    update_group_board(bid)
    
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")

    # ገና የሚቀረው ብር ካለ መልሶ ምርጫውን ያሳየዋል
    if data["users"][uid]["wallet"] >= board["price"]:
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(str(i), callback_data=f"p_{uid}_{bid}_{i}") if str(i) not in board["slots"] else types.InlineKeyboardButton("❌", callback_data="t") for i in range(1, board["max"] + 1)]
        markup.add(*btns)
        
        new_text = (f"♻️ <b>ተጨማሪ ቁጥር ይምረጡ!</b>\n👤 <b>ተጫዋች፦</b> <b><i><code>{user['name']}</code></i></b>\n💰 <b>ቀሪ፦</b> {data['users'][uid]['wallet']} ብር")
        bot.edit_message_text(new_text, GROUP_ID, call.message.message_id, reply_markup=markup)
    else:
        bot.delete_message(GROUP_ID, call.message.message_id)
        bot.send_message(GROUP_ID, f"🎉 <b>{user['name']}</b> መርጠው ጨርሰዋል መልካም ዕድል!")

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
    
            if call.data.startswith('g_app_') and is_admin:
        # 1. ዳታውን በ '_' እንበታትነዋለን
        parts = call.data.split('_')
        
        # 2. እያንዳንዱን መረጃ ለየብቻ እናወጣለን
        target_id = parts      # የተጫዋቹ ID (ለምሳሌ 5122026260)
        receipt_mid = parts    # የደረሰኙ መለያ (ለምሳሌ 206)
        
        # 3. አሁን ስሙን ከደረሰኙ ላይ በቀጥታ እንውሰድ (ከላይ በነገርኩህ መሰረት ካደረግከው)
        # አራተኛው ክፍል (index 4) ላይ ስሙ ይኖራል
        user_name = parts if len(parts) > 4 else "ተጫዋች"

        # 4. መልዕክቱን ሲልክ ['g', 'app'...] የሚለውን እንዳያመጣ እንዲህ እናደርጋለን
        msg = bot.send_message(call.message.chat.id, f"💰 ለ <b>{user_name}</b> የሚጨመረውን ብር ይጻፉ፦")
        
        # 5. መረጃዎቹን ለሚቀጥለው ፈንክሽን እናስተላልፋለን
        bot.register_next_step_handler(msg, send_picker_to_group, target_id, receipt_mid, user_name)

    
    elif call.data.startswith('u_pick_'):
        allowed_id = call.data.split('_')
        if str(call.from_user.id) != str(allowed_id):
            bot.answer_callback_query(call.id, "❌ ይቅርታ፣ ይህ በተን ለእርስዎ አልተፈቀደም!", show_alert=True)
            return
        # በተኑን አንዴ ስለተጠቀመበት እናጠፋዋለን
        bot.delete_message(GROUP_ID, call.message.message_id)
        show_boards(call.message)
    # -----------------------------------

    elif call.data.startswith('select_'): handle_selection(call)
    # ... የቀረው ኮድህ ይቀጥላል ...
    elif call.data.startswith('pick_'):
        _, bid, num = call.data.split('_')
        finalize_reg_inline(call, bid, num)
    elif call.data == "lookup_winner" and is_admin:
        m = bot.send_message(call.from_user.id, "አሸናፊ ለመፈለግ ሰሌዳ እና ቁጥር ይጻፉ (ለምሳሌ: 2-13)፦")
        bot.register_next_step_handler(m, process_lookup)
    elif call.data == "admin_manage" and is_admin: manage_menu(call)
    elif call.data.startswith('edit_') and is_admin: edit_board(call)
    elif call.data.startswith('toggle_') and is_admin:
        bid = call.data.split('_')[1]
        data["boards"][bid]["active"] = not data["boards"][bid]["active"]
        save_data(); edit_board(call)
    elif call.data.startswith('set_') and is_admin:
        _, action, bid = call.data.split('_')
        m = bot.send_message(call.from_user.id, f"የሰሌዳ {bid} አዲስ ዋጋ/ሽልማት ይጻፉ፦")
        bot.register_next_step_handler(m, update_board_value, bid, action)
    elif call.data == "admin_reset" and is_admin: reset_menu(call)
    elif call.data.startswith('doreset_') and is_admin:
        bid = call.data.split('_')[1]
        data["boards"][bid]["slots"] = {}; data["pinned_msgs"][bid] = None
        save_data(); bot.answer_callback_query(call.id, "ሰሌዳው ጸድቷል!"); update_group_board(bid)

def send_picker_to_group(message, target_id, receipt_mid):
    try:
        amt = int(message.text)
        # 1. የተጫዋቹን መረጃ ከቴሌግራም ሰርቨር ላይ በትክክል መሳብ
        user_info = bot.get_chat(target_id)
        
        # ስሙ ካለው ስሙን፣ ካልሆነ ደግሞ "ተጫዋች" እንዲል
        raw_name = user_info.first_name if user_info.first_name else "ተጫዋች"
        # ስሙን Bold እና Italic አድርገን ለሰሌዳው እናዘጋጃለን (እስከ 5 ፊደል)
        clean_name = raw_name[:5] 

        # 2. ዳታቤዝ ላይ ስሙን "ደንበኛ" በሚለው ፋንታ በቴሌግራም ስሙ መተካት
        if str(target_id) not in data["users"]:
            data["users"][str(target_id)] = {"name": clean_name, "wallet": 0}
        else:
            # የቆየ ስም ካለውም በቅርብ ስሙ እንዲታደስ
            data["users"][str(target_id)]["name"] = clean_name
            
        data["users"][str(target_id)]["wallet"] += amt
        save_data()

        # 3. ክፍት ሰሌዳ መምረጥ
        active_board = None
        for b_id, b_info in data["boards"].items():
            if b_info["active"] and b_info["price"] <= amt:
                active_board = b_id
                break
        
        if not active_board:
            bot.send_message(message.chat.id, "❌ ክፍት ሰሌዳ የለም!")
            return

        board = data["boards"][active_board]
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = []
        for i in range(1, board["max"] + 1):
            n_str = str(i)
            if n_str not in board["slots"]:
                btns.append(types.InlineKeyboardButton(n_str, callback_data=f"p_{target_id}_{active_board}_{n_str}"))
            else:
                btns.append(types.InlineKeyboardButton("❌", callback_data="taken"))
        markup.add(*btns)
        
        # 4. ግልጽ የሆነ Bold እና Italic ስም በመልዕክቱ ላይ
        text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n"
                f"👤 <b>ተጫዋች፦</b> <b><i><code>{clean_name}</code></i></b>\n"
                f"💰 <b>ቀሪ ሂሳብ፦</b> <b>{data['users'][str(target_id)]['wallet']} ብር</b>\n\n"
                f"🎰 <b>ሰሌዳ {active_board} - ቁጥርዎን ይምረጡ፦</b>")
        
        bot.send_message(GROUP_ID, text, reply_to_message_id=receipt_mid, reply_markup=markup)
        bot.send_message(message.chat.id, f"✅ ለ {clean_name} ሰሌዳ {active_board} ተዘርግቷል።")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት! {e}")


def finalize_app(message, target):
    try:
        amt = int(message.text)
        data["users"][str(target)]["wallet"] += amt
        save_data()
        bot.send_message(target, f"✅ <b>{amt} ብር ተጨምሯል!</b>")
        m = bot.send_message(target, "አሁን በሰሌዳ ላይ የሚወጣውን ስምዎን (እስከ 5 ፊደል) ይጻፉ፦")
        bot.register_next_step_handler(m, save_name, target)
    except: bot.send_message(message.chat.id, "⚠️ ስህተት! ቁጥር ብቻ ይጻፉ።")

def save_name(message, uid):
    data["users"][str(uid)]["name"] = message.text[:5]
    save_data()
    bot.send_message(uid, f"✅ ስምዎ '{message.text[:5]}' ተብሎ ተመዝግቧል!", reply_markup=main_menu_markup(uid))
    show_boards(message)

def process_lookup(message):
    try:
        bid, num = message.text.split('-')
        winner_name = data["boards"][bid]["slots"].get(num)
        if winner_name:
            winner_id = next((u for u, i in data["users"].items() if i["name"] == winner_name), None)
            res = f"🏆 <b>አሸናፊ ተገኝቷል!</b>\n\n👤 ስም፦ {winner_name}\n🎰 ሰሌዳ፦ {bid} | ቁጥር፦ {num}\n"
            if winner_id: res += f"🔗 <b>ሊንክ፦</b> <a href='tg://user?id={winner_id}'>ወደ አካውንቱ ሂድ</a>"
            bot.send_message(message.chat.id, res)
        else: bot.send_message(message.chat.id, "⚠️ ይህ ቁጥር አልተያዘም!")
    except: bot.send_message(message.chat.id, "⚠️ ስህተት! (ለምሳሌ: 1-5)")

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
