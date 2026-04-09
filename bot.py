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

def get_user(uid, name="user_name"):
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

        # 🎫 የቁጥሮች ዝርዝር (በመስመሮች መካከል ክፍተት ተጨምሯል)
    board_slots = board["slots"]
    for i in range(1, board["max"] + 1):
        n = str(i)
        if n in board_slots:
            # መጨረሻ ላይ \n\n በመጨመር ባዶ መስመር እንፈጥራለን
            text += f"<b>{i}👉</b> {board_slots[n]} ✅🏆🙏\n\n"
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
         
# --- 5. ዋና ዋና ትዕዛዞች (Admin Only Version) ---

@bot.message_handler(commands=['start'])
def welcome(message):
    uid = str(message.chat.id)
    
    # ተጠቃሚው አድሚን ካልሆነ ቦቱ ምንም ምላሽ አይሰጥም (ዝም ይላል)
    if int(uid) not in ADMIN_IDS:
        return 

    # አድሚን ከሆነ ግን ቀጥታ የቁጥጥር ፓነሉን ያገኘዋል
    user = get_user(uid, message.from_user.first_name)
    welcome_text = (
        f"👋 <b>ሰላም አድሚን {user['name']}!</b>\n\n"
        f"የቦቱ የቁጥጥር ማዕከል ውስጥ ገብተዋል። ከስር ያሉትን በተኖች በመጠቀም "
        f"ሰሌዳዎችን ማስተካከያ፣ ሂሳብ መመዝገብ እና ፈረቃ መቀየር ይችላሉ።"
    )
    bot.send_message(uid, welcome_text, reply_markup=main_menu_markup(uid), parse_mode="HTML")

@bot.message_handler(commands=['shift'])
def toggle_shift(message):
    # ይህ ትዕዛዝ የሚሰራው ለአድሚኖች ብቻ ነው
    if message.from_user.id in ADMIN_IDS:
        # አሁን ያለውን ፈረቃ መቀየር
        old_shift = data.get("current_shift", "me")
        new_shift = "assistant" if old_shift == "me" else "me"
        data["current_shift"] = new_shift
        save_data()
        
        # ተረኛው ማን እንደሆነ በግልጽ ማሳየት
        current_name = "ፋሲል (Me)" if new_shift == "me" else "ረዳት (Assistant)"
        bot.reply_to(message, f"🔄 <b>ፈረቃ ተቀይሯል!</b>\nአሁን ተረኛው፦ <code>{current_name}</code>", parse_mode="HTML")
    else:
        # ተራ ተጠቃሚ ከሆነ ዝም ይላል (ምንም ምላሽ አይሰጥም)
        return

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
    # አድሚን ፓነል በግል (Private) ብቻ እንዲከፈት
    if message.chat.type != 'private': return 
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    stats = "".join([f"📍 ሰሌዳ {bid}: ({len(binfo['slots'])}/{binfo['max']})\n" for bid, binfo in data["boards"].items()])
    markup.add(types.InlineKeyboardButton("⚙️ ሰሌዳዎችን አስተካክል", callback_data="admin_manage"),
               types.InlineKeyboardButton("🔍 አሸናፊ ፈልግ", callback_data="lookup_winner"),
               types.InlineKeyboardButton("🔄 ሰሌዳ አጽዳ (Reset)", callback_data="admin_reset"))
    bot.send_message(message.chat.id, f"🛠 <b>የአድሚን ዳሽቦርድ</b>\n\n{stats}", reply_markup=markup, parse_mode="HTML")

@bot.message_handler(content_types=['photo'])
def handle_group_receipts(message):
    # 1. ከግሩፕ ውጭ ወይም Private ከሆነ ዝም ይላል
    if message.chat.id != GROUP_ID: 
        return

    # 2. የተጫዋቹን መረጃ መመዝገብ (በኋላ ስም እንዳይጠየቅ)
    uid = str(message.from_user.id)
    user_name = message.from_user.first_name
    
    # ተጠቃሚው አዲስ ከሆነ ወይም ስሙ ከተቀየረ ዳታቤዙን ማደስ
    if uid not in data["users"]:
        data["users"][uid] = {"name": user_name, "wallet": 0}
    else:
        # ስሙን ሁልጊዜ ማዘመን (ለጥንቃቄ)
        data["users"][uid]["name"] = user_name
    
    save_data()
    
    mid = message.message_id # ለወደፊት Reply ለማድረግ

    # 3. ለአድሚኑ ደረሰኙን በተን ጨምሮ መላክ
    markup = types.InlineKeyboardMarkup()
    # callback_data ላይ የተጠቃሚውን ID እና የመልዕክቱን ID እንልካለን
    btn_approve = types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"app_{uid}_{mid}")
    btn_reject = types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"rej_{uid}_{mid}")
    markup.add(btn_approve, btn_reject)
    
    cap = (f"📩 <b>አዲስ ደረሰኝ (ከግሩፕ)</b>\n"
           f"━━━━━━━━━━━━━\n"
           f"👤 <b>ተጫዋች፦</b> {user_name}\n"
           f"🆔 <b>ID፦</b> <code>{uid}</code>")

    # ለአድሚኖች በግል (Private) መላክ
    for adm in ADMIN_IDS:
        try:
            bot.send_photo(adm, message.photo[-1].file_id, caption=cap, reply_markup=markup, parse_mode="HTML")
        except: 
            pass

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

# 1. "በካሽ መመዝገብ" - አድሚኑ መረጃ እንዲያስገባ መጠየቂያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_cash")
def start_cash_reg(call):
    msg = bot.send_message(call.from_user.id, 
        "📝 <b>በካሽ ለመመዝገብ መረጃውን እንዲህ ይጻፉ፦</b>\n\n"
        "<code>ሰሌዳ-ቁጥር ስም</code>\n\n"
        "ምሳሌ፦ <code>1-05 ፋሲል</code> (ሰሌዳ 1፣ ቁጥር 05 ለፋሲል)")
    bot.register_next_step_handler(msg, save_cash_registration)

# 2. በካሽ የተጻፈውን ዳታቤዝ ላይ ሴቭ ማድረጊያ
def save_cash_registration(message):
    try:
        # ለምሳሌ "1-05 ፋሲል" የሚለውን ይከፋፍላል
        board_part, name = message.text.split(' ', 1)
        bid, num = board_part.split('-')
        
        bid = str(bid) # ለደህንነት
        num = str(int(num)) # "05" ከሆነ "5" ያደርገዋል
        
        if bid in data["boards"]:
            data["boards"][bid]["slots"][num] = name
            # ሬዲስ ላይ ሴቭ እናደርጋለን
            redis.set("fasil_lotto_db", json.dumps(data))
            bot.send_message(message.chat.id, f"✅ ተመዝግቧል!\nሰሌዳ {bid} | ቁጥር {num} | ስም {name}")
        else:
            bot.send_message(message.chat.id, "❌ ስህተት፦ እንዲህ አይነት ሰሌዳ የለም።")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ ስህተት፦ አጻጻፍዎ ተሳስቷል። ምሳሌ፦ 1-05 ፋሲል")

# 3. "ቁጥር መሰረዝ" - የተሳሳተ ቁጥር ለማንሳት
@bot.callback_query_handler(func=lambda call: call.data == "admin_delete")
def start_delete_num(call):
    msg = bot.send_message(call.from_user.id, 
        "🗑 <b>ቁጥር ለመሰረዝ እንዲህ ይጻፉ፦</b>\n\n"
        "<code>ሰሌዳ-ቁጥር</code>\n\n"
        "ምሳሌ፦ <code>1-05</code> (ከሰሌዳ 1 ላይ ቁጥር 05ን ይሰርዛል)")
    bot.register_next_step_handler(msg, delete_num_logic)

def delete_num_logic(message):
    try:
        bid, num = message.text.split('-')
        bid, num = str(bid), str(int(num))
        
        if bid in data["boards"] and num in data["boards"][bid]["slots"]:
            del data["boards"][bid]["slots"][num]
            redis.set("fasil_lotto_db", json.dumps(data))
            bot.send_message(message.chat.id, f"🗑 ሰሌዳ {bid} ቁጥር {num} ተሰርዟል።")
        else:
            bot.send_message(message.chat.id, "❌ ቁጥሩ አልተገኘም ወይም ሰሌዳው የለም።")
    except:
        bot.send_message(message.chat.id, "❌ ስህተት፦ አጻጻፍዎ ተሳስቷል። ምሳሌ፦ 1-05")



# --- ⚙️ የአድሚን እና የተጫዋች ድርጊቶች መቀበያ (Callback Handler) ---

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    uid = str(call.from_user.id)
    
    # 1. ተጫዋቹ ቁጥር ሲመርጥ (ከ generate_picker_markup የሚመጣ)
    if call.data.startswith('p_'):
        # ፎርማት፦ p_{uid}_{bid}_{num}
        parts = call.data.split('_')
        target_id = parts
        bid = parts
        num = parts
        
        # የሌላ ሰው ምርጫ እንዳይሆን መከልከል
        if uid != target_id:
            bot.answer_callback_query(call.id, "⚠️ ይህ የእርስዎ ምርጫ አይደለም!", show_alert=True)
            return

        # ወደ ምዝገባ ፈንክሽን መላክ
        finalize_reg_inline(call, bid, num)

    # 2. አሸናፊ ለመፈለግ
    elif call.data == "lookup_winner" and is_admin:
        m = bot.send_message(call.from_user.id, "🔍 አሸናፊ ለመፈለግ ሰሌዳ እና ቁጥር ይጻፉ (ለምሳሌ: 2-13)፦")
        bot.register_next_step_handler(m, process_lookup)

    # 3. የሰሌዳ አስተዳደር ሜኑ
    elif call.data == "admin_manage" and is_admin:
        admin_manage_menu(call)

    # 4. ሰሌዳ ለመቀየር/ለማስተካከል
    elif call.data.startswith('edit_') and is_admin:
        bid = call.data.split('_')
        edit_board(call, bid)

    # 5. ሰሌዳ ክፍት/ዝግ ለማድረግ (Active/Inactive)
    elif call.data.startswith('toggle_') and is_admin:
        bid = call.data.split('_')
        data["boards"][bid]["active"] = not data["boards"][bid]["active"]
        save_data()
        edit_board(call, bid)

    # 6. ሰሌዳ ለማጽዳት (Reset)
    elif call.data == "admin_reset" and is_admin:
        reset_menu(call)

    elif call.data.startswith('doreset_') and is_admin:
        bid = call.data.split('_')
        data["boards"][bid]["slots"] = {}
        data["pinned_msgs"][bid] = None
        save_data()
        bot.answer_callback_query(call.id, f"✅ ሰሌዳ {bid} ጸድቷል!")
        update_group_board(bid) # ግሩፕ ላይ ያለውን ሰሌዳ ያድሳል

    # 7. ተይዞ ያለ ቁጥር ሲነካ
    elif call.data == "taken":
        bot.answer_callback_query(call.id, "❌ ይህ ቁጥር ቀድሞ ተይዟል!")

# --- 🎰 የቁጥር መምረጫ በተኖች ማመንጫ (Picker Generator) ---

def generate_picker_markup(uid, bid):
    board = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=5)
    btns = []
    for i in range(1, board["max"] + 1):
        n_str = str(i)
        # ቁጥሩ ከተያዘ ❌ ያሳያል፣ ካልተያዘ ቁጥሩን ያሳያል
        if n_str not in board["slots"]:
            # callback_data ላይ የተጫዋቹን ID እና ሰሌዳውን እናያይዛለን
            btns.append(types.InlineKeyboardButton(n_str, callback_data=f"p_{uid}_{bid}_{n_str}"))
        else:
            btns.append(types.InlineKeyboardButton("❌", callback_data="taken"))
    markup.add(*btns)
    return markup



def finalize_app(message, target_uid, mid):
    try:
        # 1. አድሚኑ የጻፈውን የብር መጠን ወደ ቁጥር መቀየር
        amt = int(message.text)
        uid = str(target_uid)
        
        # 2. የተጫዋቹን መረጃ ከዳታቤዝ ማግኘት (በ handle_receipts ተመዝግቧል)
        if uid not in data["users"]:
            data["users"][uid] = {"name": "ተጫዋች", "wallet": 0}
            
        data["users"][uid]["wallet"] += amt
        save_data()
        
        user_name = data["users"][uid].get("name", "ተጫዋች")
        # ክፍት የሆኑ ሰሌዳዎችን መለየት
        active_boards = [bid for bid, info in data["boards"].items() if info["active"]]
        
        if not active_boards:
            bot.send_message(message.chat.id, "⚠️ ማስጠንቀቂያ፦ በአሁኑ ሰዓት ምንም ክፍት ሰሌዳ የለም!")
            return

        # ✅ ሁኔታ 1፦ አንድ ሰሌዳ ብቻ ክፍት ከሆነ (ቀጥታ የቁጥር በተኖችን መላክ)
        if len(active_boards) == 1:
            bid = active_boards
            markup = generate_picker_markup(uid, bid)
            
            text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n"
                    f"━━━━━━━━━━━━━\n"
                    f"👤 <b>ተጫዋች፦</b> {user_name}\n"
                    f"💰 <b>የገባ ብር፦</b> {amt} ብር\n"
                    f"🎰 <b>ሰሌዳ {bid}</b> - እባክዎ ቁጥር ይምረጡ፦")
            
            # ግሩፕ ላይ ለደረሰኙ Reply በማድረግ ይልካል
            bot.send_message(GROUP_ID, text, reply_markup=markup, reply_to_message_id=mid, parse_mode="HTML")
            
        # ✅ ሁኔታ 2፦ ከአንድ በላይ ክፍት ሰሌዳዎች ካሉ (መጀመሪያ ሰሌዳ እንዲመርጥ መጠየቅ)
        else:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for b_id in active_boards:
                price = data["boards"][b_id]["price"]
                markup.add(types.InlineKeyboardButton(f"🎰 ሰሌዳ {b_id} ({price} ብር)", callback_data=f"u_select_{uid}_{b_id}"))
            
            text = (f"✅ <b>ክፍያ ተረጋግጧል!</b>\n"
                    f"━━━━━━━━━━━━━\n"
                    f"👤 <b>ተጫዋች፦</b> {user_name}\n"
                    f"💰 <b>የገባ ብር፦</b> {amt} ብር\n\n"
                    f"❓ <b>እባክዎ መጫወት የሚፈልጉትን ሰሌዳ ይምረጡ፦</b>")
            
            bot.send_message(GROUP_ID, text, reply_markup=markup, reply_to_message_id=mid, parse_mode="HTML")

        # ለአድሚኑ ማረጋገጫ መስጠት
        bot.send_message(message.chat.id, f"✅ ለ {user_name} የማረጋገጫ መልዕክት ግሩፕ ላይ ተልኳል።")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ የገንዘቡን መጠን በቁጥር ብቻ ይጻፉ (ለምሳሌ፦ 100)።")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ሲስተም ስህተት፦ {e}")

def process_lookup(message):
    try:
        # አጻጻፍ፦ ሰሌዳ-ቁጥር (ለምሳሌ 1-05)
        text = message.text.strip()
        if '-' not in text:
            bot.send_message(message.chat.id, "❌ ስህተት! አጻጻፍ፦ <code>ሰሌዳ-ቁጥር</code> (ምሳሌ፦ 1-05)", parse_mode="HTML")
            return
            
        bid, num = text.split('-', 1)
        
        # በዳታቤዙ ውስጥ መኖሩን ማረጋገጥ
        if bid in data["boards"] and num in data["boards"][bid]["slots"]:
            winner_name = data["boards"][bid]["slots"][num]
            
            # አሸናፊውን በስሙ ሳይሆን በ ID ለመፈለግ (ይበልጥ ትክክለኛ ነው)
            # ማሳሰቢያ፦ ይህ የሚሰራው ተጫዋቹ በደረሰኝ ጊዜ በ ID ተመዝግቦ ከሆነ ነው
            winner_id = None
            for u_id, info in data["users"].items():
                if info["name"] == winner_name:
                    winner_id = u_id
                    break
            
            if winner_id:
                # በሊንክ እንዲጠራ (Mention)
                mention = f'<a href="tg://user?id={winner_id}">{winner_name}</a>'
                res = (f"🏆 <b>አሸናፊ ተገኝቷል!</b>\n\n"
                       f"👤 <b>ስም፦</b> {mention}\n"
                       f"🎰 <b>ሰሌዳ፦</b> {bid} | <b>ቁጥር፦</b> {num}\n"
                       f"🆔 <b>User ID፦</b> <code>{winner_id}</code>")
            else:
                res = f"🏆 <b>አሸናፊ፦</b> {winner_name}\n⚠️ የዚህ ሰው ID በዳታቤዝ ውስጥ አልተገኘም።"
                
            bot.send_message(message.chat.id, res, parse_mode="HTML")
        else: 
            bot.send_message(message.chat.id, "⚠️ ይህ ቁጥር ገና አልተያዘም ወይም ሰሌዳው የለም!")
    except Exception as e: 
        bot.send_message(message.chat.id, f"❌ ስህተት ተከስቷል፦ {e}")


def handle_selection(call):
    # 1. መረጃውን መከፋፈል (u_select_{uid}_{bid})
    parts = call.data.split('_')
    target_uid = parts
    bid = parts
    
    # 2. ተጫዋቹን መለየት (በ ID)
    user = data["users"].get(target_uid)
    board = data["boards"].get(bid)
    
    if not user or not board:
        bot.answer_callback_query(call.id, "❌ ስህተት ተፈጥሯል!")
        return

    # 3. የገንዘብ መጠን ማረጋገጥ
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ ለዚህ ሰሌዳ በቂ ሂሳብ የሎትም!", show_alert=True)
        return

    # 4. የቁጥር መምረጫ በተኖችን (Picker) ማዘጋጀት
    # እዚህ ጋር generate_picker_markup መጠቀም ይሻላል (ኮድ ላለመደጋገም)
    markup = generate_picker_markup(target_uid, bid)
    
    text = (f"🎰 <b>ሰሌዳ {bid} ተመርጧል!</b>\n"
            f"👤 <b>ተጫዋች፦</b> {user['name']}\n"
            f"💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር\n\n"
            f"እባክዎ ቁጥር ይምረጡ፦")
            
    # ግሩፕ ላይ መልዕክቱን ማደስ
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def finalize_reg_inline(call, bid, num):
    # 1. ተጫዋቹን መለየት
    parts = call.data.split('_')
    target_uid = parts
    
    user = data["users"].get(target_uid)
    board = data["boards"].get(bid)
    
    if not user or not board:
        bot.answer_callback_query(call.id, "❌ ስህተት! ዳታው አልተገኘም።")
        return

    # 2. የገንዘብ መጠን ማረጋገጥ
    if user["wallet"] < board["price"]:
        bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የሎትም!", show_alert=True)
        return

    # 3. ክፍያ እና ምዝገባ
    data["users"][target_uid]["wallet"] -= board["price"]
    board["slots"][num] = user["name"]
    save_data()
    
    # ሰሌዳውን ማደስ (ግሩፕ ላይ)
    update_group_board(bid)
    bot.answer_callback_query(call.id, f"✅ ቁጥር {num} ተመርጧል!")

    # 4. ተከታታይ ጨዋታ ወይም መዝጊያ (ማሳሰቢያው ተወግዷል)
    if user["wallet"] >= board["price"]:
        new_markup = generate_picker_markup(target_uid, bid)
        text = (f"🎰 <b>ሰሌዳ {bid}</b>\n"
                f"👤 <b>ተጫዋች፦</b> {user['name']}\n"
                f"💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር\n\n"
                f"ቁጥር {num} ተይዟል! ሌላ ቁጥር ይምረጡ፦")
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=new_markup, parse_mode="HTML")
    else:
        final_text = (f"✅ <b>ምዝገባ ተጠናቋል።</b>\n"
                      f"👤 <b>ተጫዋች፦</b> {user['name']}\n"
                      f"🎰 <b>ሰሌዳ {bid}</b>\n"
                      f"💰 <b>ቀሪ ሂሳብ፦</b> {user['wallet']} ብር\n\n"
                      f"መልካም ዕድል! 🙏")
        bot.edit_message_text(final_text, call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode="HTML")

def manage_menu(call):
    # አድሚን ፓነል የግድ በ DM (Private) መሆን አለበት
    if call.message.chat.type != 'private': return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for bid in data["boards"]: 
        markup.add(types.InlineKeyboardButton(f"⚙️ ሰሌዳ {bid}", callback_data=f"edit_{bid}"))
    
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_panel_back"))
    bot.edit_message_text("🛠 <b>ሰሌዳ ይምረጡ፦</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def edit_board(call, bid=None):
    # bid ከሌለ ከ callback_data ውስጥ ይወስዳል
    if bid is None:
        bid = call.data.split('_')
        
    b = data["boards"][bid]
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # የሰሌዳ ሁኔታ (ክፍት/ዝግ)
    status_text = "🟢 ክፍት" if b['active'] else "🔴 ዝግ"
    markup.add(types.InlineKeyboardButton(status_text, callback_data=f"toggle_{bid}"))
    
    # ዋጋ እና ሽልማት ማስተካከያ
    markup.add(
        types.InlineKeyboardButton("💵 ዋጋ ቀይር", callback_data=f"set_price_{bid}"), 
        types.InlineKeyboardButton("🎁 ሽልማት ቀይር", callback_data=f"set_prize_{bid}")
    )
    
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
    
    text = (f"📊 <b>የሰሌዳ {bid} አስተዳደር</b>\n"
            f"━━━━━━━━━━━━━\n"
            f"💰 <b>መደብ (Price)፦</b> {b['price']} ብር\n"
            f"🏆 <b>ሽልማት (Prize)፦</b> {b['prize']} ብር\n"
            f"🚦 <b>ሁኔታ፦</b> {status_text}")
            
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# --- 1. ሰሌዳን የማጽጃ ሜኑ (Reset Menu) ---
def reset_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for bid in data["boards"]: 
        markup.add(types.InlineKeyboardButton(f"🧹 Reset ሰሌዳ {bid}", callback_data=f"doreset_{bid}"))
    
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_manage"))
    bot.edit_message_text("⚠️ <b>የትኛው ሰሌዳ ይጽዳ?</b>\n(Reset ሲያደርጉ የነበሩት ስሞች በሙሉ ይጠፋሉ!)", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# --- 2. ደረሰኝ ውድቅ ሲደረግ (Decline) ---
def finalize_dec(message, target_uid, mid):
    # target_uid = የተጫዋቹ ID
    # mid = የተጫዋቹ ደረሰኝ መልዕክት ID (ግሩፕ ላይ Reply ለማድረግ)
    
    reason = message.text
    text = (f"❌ <b>ደረሰኝዎ ውድቅ ሆኗል!</b>\n"
            f"━━━━━━━━━━━━━\n"
            f"👤 <b>ተጫዋች፦</b> <a href='tg://user?id={target_uid}'>ተጫዋች</a>\n"
            f"📝 <b>ምክንያት፦</b> {reason}\n\n"
            f"እባክዎ እንደገና በትክክል ይላኩ። 🙏")
            
    # ግሩፕ ላይ ለደረሰኙ Reply በማድረግ ለተጫዋቹ ማሳወቅ
    bot.send_message(GROUP_ID, text, reply_to_message_id=mid, parse_mode="HTML")
    bot.send_message(message.chat.id, "✅ ለተጫዋቹ ውድቅ መደረጉ ተገልጾለታል።")

# --- 3. የሰሌዳ ዋጋ ወይም ሽልማት መቀየሪያ ---
def update_board_value(message, bid, action):
    try:
        val = message.text.strip()
        if action == "price":
            # ዋጋ የግድ ቁጥር መሆን አለበት
            data["boards"][bid]["price"] = int(val)
            msg = f"✅ የሰሌዳ {bid} መደብ (Price) ወደ <b>{val} ብር</b> ተቀይሯል!"
        else:
            # ሽልማት ጽሁፍም ሊሆን ይችላል (ለምሳሌ "ባጃጅ")
            data["boards"][bid]["prize"] = val
            msg = f"✅ የሰሌዳ {bid} ሽልማት (Prize) ወደ <b>{val}</b> ተቀይሯል!"
            
        save_data()
        bot.send_message(message.chat.id, msg, parse_mode="HTML")
        
        # ግሩፕ ላይ ያለውን Pin የተደረገ ሰሌዳ እንዲታደስ ማድረግ
        update_group_board(bid)
        
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ ስህተት! እባክዎ ለዋጋ (Price) ቁጥር ብቻ ይጻፉ።")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ ስህተት፦ {e}")

@bot.message_handler(commands=['update'])
def force_update(message):
    # አድሚን መሆንህን ማረጋገጥ
    if message.from_user.id in ADMIN_IDS:
        # አድሚኑ መጠበቅ እንዳለበት እንዲያውቅ አጭር መልዕክት መላክ
        status_msg = bot.send_message(message.chat.id, "🔄 ሰሌዳዎች እየታደሱ ነው...")
        
        try:
            for bid in data["boards"]:
                # እያንዳንዱን ሰሌዳ ግሩፕ ላይ ማደስ
                update_group_board(bid)
            
            # ስራው ሲያልቅ የቆየውን መልዕክት ማስተካከያ (Edit)
            bot.edit_message_text("✅ ሁሉም ሰሌዳዎች ግሩፕ ላይ ታድሰዋል!", message.chat.id, status_msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ ስህተት ተፈጥሯል፦ {e}", message.chat.id, status_msg.message_id)
    else:
        # አድሚን ካልሆነ ዝም ይላል ወይም ማስጠንቀቂያ ይሰጣል
        bot.reply_to(message, "⚠️ ይህ ትዕዛዝ ለአድሚን ብቻ ነው!")

    
if __name__ == "__main__":
    # ለጊዜው ይህንን ጨምር (አንድ ጊዜ Deploy ካደረግክ በኋላ መልሰህ ብታጠፋው ይሻላል)
    save_data()
    
    keep_alive()
    # ... ሌላው የ bot.polling ኮድ ይቀጥላል
    bot.remove_webhook()
    while True:
        try: bot.polling(none_stop=True, interval=1, timeout=20)
        except: time.sleep(5)
