import telebot
from telebot import types
import os, json, math, threading, time
from flask import Flask
from upstash_redis import Redis

# --- 1. ውቅረት ---
TOKEN = "8663228906:AAFsTC0fKqAVEWMi7rk59iSdfVD-1vlJA0Y"
REDIS_URL = "https://nice-kitten-98436.upstash.io"
REDIS_TOKEN = "gQAAAAAAAYCEAAIncDEyMWMyNjczNmZiNjM0NzlkODI4MmUyODAyZGIxNDI5N3AxOTg0MzY"
ADMIN_IDS = [5690096145, 7072611117,8488592165]
PORT = int(os.getenv("PORT", 8080)) # Render የራሱን Port እዚህ ይሰጥሃል

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__) # ስሙን 'app' ብንለው ይሻላል

@app.route('/')
def index():
    return "BDF Bot is running!"

def run_flask():
    # በ Render ላይ ስራ እንዲጀምር host እና port በትክክል መሰጠት አለባቸው
    app.run(host='0.0.0.0', port=PORT)

# --- 2. ዳታቤዝ ተግባራት ---
def load_data():
    try:
        raw = redis.get("beu_delivery_db")
        if raw: 
            return json.loads(raw)
        
        initial_data = {
            "vendors": {}, "vendors_list": {}, "orders": {}, 
            "items": {}, "pending": {}, "users": {}, 
            "categories": [], "promos": {}, "payment_logs": [], # አዳዲስ
            "riders": {}, "total_profit": 0, 
            "settings": {"base_delivery": 50, "commission_rate": 10} # ኮሚሽን ተጨምሯል
        }
        return initial_data
    except Exception as e:
        print(f"❌ Database Load Error: {e}")
        return {"vendors": {}, "vendors_list": {}, "orders": {}, "items": {}, "pending": {}, "users": {}, "categories": [], "settings": {"base_delivery": 50}}

def save_category(message):
    db = load_data()
    new_cat = message.text.strip()
    
    # categories የሚል ቁልፍ መኖሩን በድጋሚ ቼክ ማድረግ (ለጥንቃቄ)
    if "categories" not in db:
        db["categories"] = []
    
    if new_cat not in db["categories"]:
        db["categories"].append(new_cat)
        save_data(db)
        
        # ምድቡ ከተመዘገበ በኋላ ወደ አድሚን ዳሽቦርድ መመለሻ በተን
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ ተመለስ", callback_data="admin_main"))
        
        bot.send_message(message.chat.id, f"✅ ምድብ '{new_cat}' በሚገባ ተጨምሯል!", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "⚠️ ይህ ምድብ ቀድሞውኑ ተመዝግቧል።")

def process_item_name(message, photo_id):
    item_name = message.text
    db = load_data()
    categories = db.get("categories", ["ሌሎች"]) # አድሚኑ የጨመራቸውን ያመጣል
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        # እያንዳንዱን ምድብ በተን እናደርገዋለን
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"selcat_{cat}"))
    
    msg = bot.send_message(message.chat.id, f"📂 የ '{item_name}' ምድብ (Category) ይምረጡ፦", reply_markup=markup)
    # ማሳሰቢያ፦ እዚህ ጋር callback_handler ስለሚቀበለው register_next_step አያስፈልግም

def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# 1. የአድሚን ኢንላይን (Inline) ዳሽቦርድ - ለዴሊቨሪ ስራ ብቻ
def admin_delivery_dashboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        types.InlineKeyboardButton("📊 ጠቅላላ ሪፖርት", callback_data="admin_stats"),
        types.InlineKeyboardButton("🏢 አዳዲስ ሱቆች", callback_data="admin_list_v"),
        types.InlineKeyboardButton("🛵 የደላላዎች ሁኔታ", callback_data="admin_riders"),
        types.InlineKeyboardButton("💰 የኮሚሽን ተመን", callback_data="admin_change_com"),
        types.InlineKeyboardButton("🎁 የማስተዋወቂያ ኮድ", callback_data="admin_promo"),
        types.InlineKeyboardButton("📦 በመጠባበቅ ላይ ያሉ", callback_data="admin_pending_items"),
        types.InlineKeyboardButton("🏆 ምርጥ ሻጮች", callback_data="admin_top_v"),
        types.InlineKeyboardButton("🧹 ዳታቤዝ አጽዳ", callback_data="admin_clear_db"),
        types.InlineKeyboardButton("💵 የክፍያ ታሪክ", callback_data="admin_pay_history"),
        types.InlineKeyboardButton("🗑 ትዕዛዝ ሰርዝ", callback_data="admin_cancel_order")
    ]
    # ምድብ ማደራጃውን ከፈለግከው እዚህ መሃል መጨመር ትችላለህ
    markup.add(types.InlineKeyboardButton("📁 ምድቦችን አደራጅ", callback_data="admin_manage_cats"))
    markup.add(*btns)
    return markup

# 2. የአድሚን ቋሚ የሪፕላይ (Reply) ኪቦርድ
def kb_admin_main():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🏬 አጋር ድርጅቶች", "📦 ትዕዛዞች", "📊 ሪፖርት", "⚙️ ሲስተም")
    return kb

# 4. ዋናው የ /start ፈንክሽን
@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        uid_str = str(user_id)
        db = load_data() 

        if user_id in ADMIN_IDS:
            return bot.send_message(user_id, "👑 እንኳን ደህና መጡ (የBDF አድሚን)!", reply_markup=kb_admin_main())

        vendors = db.get("vendors_list", {})
        if uid_str in vendors:
            v_name = vendors[uid_str].get("name", "ባለሱቅ")
            return bot.send_message(user_id, f"🏬 ሰላም {v_name} (ባለሱቅ)!", reply_markup=kb_vendor_main())

        bot.send_message(user_id, "👋 እንኳን ወደ BDF በደህና መጡ!", reply_markup=kb_customer_main())

    except Exception as e:
        print(f"❌ Error in start: {e}")

# --- አድሚኑ ከታች ያሉትን የሪፕላይ በተኖች ሲነካ የሚሰራ ---
@bot.message_handler(func=lambda message: message.text in ["🏬 አጋር ድርጅቶች", "📦 ትዕዛዞች", "📊 ሪፖርት", "⚙️ ሲስተም"])
def handle_admin_main_menu(message):
    if message.from_user.id not in ADMIN_IDS:
        return

    if message.text == "🏬 አጋር ድርጅቶች":
        # የአድሚን ዳሽቦርዱን (Inline Buttons) እዚህ ጋር ነው የምንጠራው
        bot.send_message(
            message.chat.id, 
            "የዴሊቨሪ ሲስተም መቆጣጠሪያ ዳሽቦርድ፦", 
            reply_markup=admin_delivery_dashboard() # ያዘጋጀኸውን ዳሽቦርድ ይጠራል
        )
    
    elif message.text == "📦 ትዕዛዞች":
        bot.send_message(message.chat.id, "የቅርብ ጊዜ ትዕዛዞች ዝርዝር...")
        # እዚህ ጋር የትዕዛዞችን ሎጂክ መጥራት ትችላለህ
        
    elif message.text == "📊 ሪፖርት":
        bot.send_message(message.chat.id, "ጠቅላላ የሽያጭ ሪፖርት...")
        
    elif message.text == "⚙️ ሲስተም":
        bot.send_message(message.chat.id, "የሲስተም ማስተካከያ ዝርዝር...")


@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_cats")
def admin_manage_categories(call):
    db = load_data()
    # በዳታቤዝ ውስጥ "categories" የሚል ዝርዝር መኖሩን ማረጋገጥ
    categories = db.get("categories", ["ምግብ", "ኤሌክትሮኒክስ", "ልብስ"]) # መነሻ ምድቦች
    
    text = "📁 **ያሉ የምርት ምድቦች፦**\n\n"
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for cat in categories:
        text += f"🔹 {cat}\n"
        # እያንዳንዱን ምድብ ለመሰረዝ በተን ማዘጋጀት
        markup.add(types.InlineKeyboardButton(f"❌ {cat} ሰርዝ", callback_data=f"del_cat_{cat}"))
    
    markup.add(types.InlineKeyboardButton("➕ አዲስ ምድብ ጨምር", callback_data="add_new_cat"))
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- አዲስ ምድብ ለመጨመር ---
@bot.callback_query_handler(func=lambda call: call.data == "add_new_cat")
def ask_category_name(call):
    msg = bot.send_message(call.message.chat.id, "📝 አዲሱን የምድብ ስም ይጻፉ (ለምሳሌ፦ ኮስሞቲክስ)፦")
    bot.register_next_step_handler(msg, save_category)

def save_category(message):
    db = load_data()
    new_cat = message.text.strip()
    
    if "categories" not in db: db["categories"] = []
    
    if new_cat not in db["categories"]:
        db["categories"].append(new_cat)
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ምድብ '{new_cat}' በሚገባ ተጨምሯል።", reply_markup=kb_admin_main())
    else:
        bot.send_message(message.chat.id, "⚠️ ይህ ምድብ ቀድሞውኑ አለ።")

@bot.callback_query_handler(func=lambda call: call.data.startswith('selcat_'))
def handle_vendor_category_selection(call):
    selected_cat = call.data.replace('selcat_', '')
    # እዚህ ጋር ለጊዜው ዳታውን ለመያዝ (ለምሳሌ በ user state)
    msg = bot.send_message(call.message.chat.id, f"✅ ምድብ '{selected_cat}' ተመርጧል።\n\n📝 አሁን ስለ እቃው አጭር መግለጫ ይጻፉ፦")
    # ማሳሰቢያ፡ እዚህ ጋር selected_cat ለቀጣዩ ፈንክሽን ማስተላለፍ አለብህ
    bot.register_next_step_handler(msg, process_item_description, selected_cat)



# ሱቅ መመዝገቢያ ሎጂክ
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_v")
def start_add_v(call):
    msg = bot.send_message(call.message.chat.id, "📝 የሱቁን ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, process_v_name)

def process_v_name(message):
    v_name = message.text
    msg = bot.send_message(message.chat.id, f"🔢 የ '{v_name}' ባለቤት የቴሌግራም ID ቁጥር ያስገቡ፦")
    bot.register_next_step_handler(msg, process_v_id, v_name)

def process_v_id(message, v_name):
    v_id = message.text.strip()
    if not v_id.isdigit():
        bot.send_message(message.chat.id, "❌ ስህተት፦ ID ቁጥር ብቻ መሆን አለበት። እንደገና ይሞክሩ።")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📍 የሱቁን ሎኬሽን ላክ", request_location=True))
    msg = bot.send_message(message.chat.id, f"📍 ለ '{v_name}' ሎኬሽን ይላኩ፦", reply_markup=markup)
    bot.register_next_step_handler(msg, finalize_v_reg, v_name, v_id)

def finalize_v_reg(message, v_name, v_id):
    if not message.location:
        bot.send_message(message.chat.id, "❌ ሎኬሽን አልተላከም፣ ምዝገባው ተቋርጧል።", reply_markup=kb_admin_main())
        return
    
    db = load_data()
    if "vendors_list" not in db: db["vendors_list"] = {}
    
    db["vendors_list"][str(v_id)] = {
        "name": v_name,
        "lat": message.location.latitude,
        "lon": message.location.longitude,
        "balance": 0,
        "shop_status": "Open 🟢"
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ ሱቅ '{v_name}' በሚገባ ተመዝግቧል!", reply_markup=kb_admin_main())


@bot.callback_query_handler(func=lambda call: call.data == "set_del_fee")
def change_delivery_fee(call):
    msg = bot.send_message(call.message.chat.id, "💰 አዲሱን የማድረሻ መነሻ ዋጋ በቁጥር ብቻ ያስገቡ (ለምሳሌ፦ 50)፦")
    bot.register_next_step_handler(msg, save_new_fee)

def save_new_fee(message):
    try:
        new_fee = int(message.text)
        db = load_data()
        if "settings" not in db: db["settings"] = {}
        db["settings"]["base_delivery"] = new_fee
        save_data(db)
        bot.send_message(message.chat.id, f"✅ የማድረሻ መነሻ ዋጋ ወደ {new_fee} ETB ተቀይሯል።")
    except:
        bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ቁጥር ብቻ ያስገቡ!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_cat_"))
def delete_category(call):
    db = load_data()
    cat_to_del = call.data.replace("del_cat_", "")
    
    if "categories" in db and cat_to_del in db["categories"]:
        db["categories"].remove(cat_to_del)
        save_data(db)
        bot.answer_callback_query(call.id, f"✅ {cat_to_del} ተሰርዟል", show_alert=True)
        # ገጹን ሪፍሬሽ ለማድረግ የድሮውን ፈንክሽን መልሰህ ጥራው
        admin_manage_categories(call) 
    else:
        bot.answer_callback_query(call.id, "❌ ምድቡ አልተገኘም")



@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_")))
def handle_item_approval(call):
    db = load_data()
    action, item_id = call.data.split("_")
    
    # እቃውን ከ pending ውስጥ ፈልጎ ማውጣት
    item = db.get("pending", {}).pop(item_id, None)
    
    if not item:
        return bot.edit_message_caption("❌ ይህ እቃ ቀድሞውኑ ተሰርዟል ወይም የለም።", call.message.chat.id, call.message.message_id)

    if action == "approve":
        # ወደ ዋናው የዕቃዎች ዝርዝር (items) መጨመር
        if "items" not in db: db["items"] = {}
        item["status"] = "Active"
        db["items"][item_id] = item
        save_data(db)
        
        bot.edit_message_caption(f"✅ እቃው '{item['name']}' ጸድቋል! ለደንበኞች ይታያል።", call.message.chat.id, call.message.message_id)
        # ለባለሱቁ ሜሴጅ መላክ (ካስፈለገ)
    
    else: # Reject ከሆነ
        save_data(db)
        bot.edit_message_caption(f"🔴 እቃው '{item['name']}' ውድቅ ተደርጓል።", call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_settings")
def change_delivery_fee(call):
    msg = bot.send_message(call.message.chat.id, "💰 እባክዎ መነሻ የዴሊቨሪ ዋጋ በቁጥር ብቻ ይጻፉ (ለምሳሌ፦ 60)፦")
    bot.register_next_step_handler(msg, save_delivery_settings)

def save_delivery_settings(message):
    try:
        new_fee = float(message.text)
        db = load_data()
        db["settings"]["base_delivery"] = new_fee
        save_data(db)
        bot.send_message(message.chat.id, f"✅ የዴሊቨሪ ዋጋ ወደ {new_fee} ETB ተቀይሯል።")
    except:
        bot.send_message(message.chat.id, "⚠️ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ።")

@bot.callback_query_handler(func=lambda call: call.data == "admin_promo")
def create_promo(call):
    msg = bot.send_message(call.message.chat.id, "🎟 አዲስ የማስተዋወቂያ ኮድ ይጻፉ (ለምሳሌ: SAVE10)፦")
    bot.register_next_step_handler(msg, set_promo_amount)

def set_promo_amount(message):
    promo_code = message.text.upper().strip()
    msg = bot.send_message(message.chat.id, f"💰 ለ '{promo_code}' ስንት ብር ቅናሽ ይደረግ? (በቁጥር ብቻ)፦")
    bot.register_next_step_handler(msg, save_promo, promo_code)

def save_promo(message, promo_code):
    try:
        amount = float(message.text)
        db = load_data()
        if "promos" not in db: db["promos"] = {}
        db["promos"][promo_code] = amount
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ኮድ '{promo_code}' ለ {amount} ብር ቅናሽ ተመዝግቧል።")
    except:
        bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ቁጥር ብቻ ያስገቡ።")

@bot.callback_query_handler(func=lambda call: call.data == "admin_pay_history")
def view_payments(call):
    db = load_data()
    payments = db.get("payment_logs", [])
    if not payments:
        return bot.answer_callback_query(call.id, "📅 እስካሁን የተመዘገበ የክፍያ ታሪክ የለም።", show_alert=True)
    
    text = "💳 **የክፍያ ታሪክ፦**\n\n"
    for p in payments[-10:]: # የመጨረሻዎቹን 10 ብቻ ለማሳየት
        text += f"👤 ሱቅ፦ {p['v_name']}\n💰 መጠን፦ {p['amount']} ETB\n📅 ቀን፦ {p['date']}\n----------\n"
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")



@bot.callback_query_handler(func=lambda call: call.data == "admin_cancel_order")
def ask_order_id_to_cancel(call):
    msg = bot.send_message(call.message.chat.id, "🚫 ለመሰረዝ የትዕዛዝ መለያ ቁጥሩን (Order ID) ያስገቡ፦")
    bot.register_next_step_handler(msg, execute_order_cancel)

def execute_order_cancel(message):
    oid = message.text.strip()
    db = load_data()
    if oid in db.get("orders", {}):
        db["orders"][oid]["status"] = "Cancelled"
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ትዕዛዝ #{oid} ተሰርዟል።")
    else:
        bot.send_message(message.chat.id, "❌ ትዕዛዙ አልተገኘም።")


@bot.callback_query_handler(func=lambda call: call.data == "admin_top_v")
def show_top_vendors(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    # በሽያጭ መጠን (balance) መሰረት ሱቆችን ቶፕ 5 መለየት
    sorted_v = sorted(vendors.items(), key=lambda x: x.get('balance', 0), reverse=True)[:5]
    
    text = "🏆 **ምርጥ አቅራቢዎች (Top 5)፦**\n\n"
    for i, (vid, vdata) in enumerate(sorted_v, 1):
        text += f"{i}. {vdata['name']} - {vdata.get('balance', 0)} ETB\n"
    
    bot.send_message(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "admin_rider_status")
def view_riders(call):
    db = load_data()
    riders = db.get("riders", {})
    if not riders:
        return bot.answer_callback_query(call.id, "🚫 ምንም የተመዘገበ ዴሊቨሪ የለም።", show_alert=True)
    
    text = "🛵 **የዴሊቨሪዎች ሁኔታ፦**\n\n"
    for rid, rdata in riders.items():
        status = "🟢 Online" if rdata.get("is_online") else "🔴 Offline"
        # ዴሊቨሪው ትዕዛዝ ላይ ከሆነ ደግሞ እንዲህ ይታያል
        on_duty = "⚠️ በትዕዛዝ ላይ" if rdata.get("on_order") else "✅ ስራ አልያዘም"
        
        text += f"👤 ስም፦ {rdata['name']}\n📱 ስልክ፦ {rdata['phone']}\n🚦 ሁኔታ፦ {status}\n💼 ስራ፦ {on_duty}\n----------\n"
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "admin_commission")
def set_comm_rate(call):
    msg = bot.send_message(call.message.chat.id, "📈 የኮሚሽን ተመን በፐርሰንት (%) ያስገቡ (ለምሳሌ 10 ካሉ ከሽያጭ 10% ይቆረጣል)፦")
    bot.register_next_step_handler(msg, save_commission)

def save_commission(message):
    try:
        rate = float(message.text)
        db = load_data()
        db["settings"]["commission_rate"] = rate
        save_data(db)
        bot.send_message(message.chat.id, f"✅ የኮሚሽን ተመን ወደ {rate}% ተቀይሯል።")
    except:
        bot.send_message(message.chat.id, "❌ እባክዎ ቁጥር ብቻ ያስገቡ!")

@bot.callback_query_handler(func=lambda call: call.data == "admin_pending_items")
def view_pending_items(call):
    db = load_data()
    pending_dict = db.get("pending", {})
    
    if not pending_dict:
        return bot.answer_callback_query(call.id, "✅ ምንም በመጠባበቅ ላይ ያለ እቃ የለም።", show_alert=True)
    
    bot.answer_callback_query(call.id, "እቃዎቹን በማምጣት ላይ...")
    
    for item_id, item in pending_dict.items():
        # ለእያንዳንዱ እቃ ማጽደቂያ እና መሰረዣ በተን ማዘጋጀት
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ ፍቀድ (Approve)", callback_data=f"approve_it_{item_id}"),
            types.InlineKeyboardButton("❌ ሰርዝ (Reject)", callback_data=f"reject_it_{item_id}")
        )
        
        caption = (
            f"📦 **አዲስ እቃ ማረጋገጫ**\n\n"
            f"🆔 መለያ ቁጥር፦ `{item_id}`\n"
            f"📂 ምድብ፦ {item.get('category', 'ያልተጠቀሰ')}\n"
            f"🏬 ሱቅ፦ {item.get('v_name', 'ያልታወቀ')}\n"
            f"📝 ስም፦ {item.get('name')}\n"
            f"💰 ዋጋ፦ {item.get('price')} ETB\n"
            f"📖 መግለጫ፦ {item.get('description', '-')}"
        )
        
        # እቃው ፎቶ ካለው ከነፎቶው ይልካል
        if item.get('photo'):
            bot.send_photo(call.message.chat.id, item['photo'], caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_it_", "reject_it_")))
def handle_pending_action(call):
    data_parts = call.data.split("_")
    action = data_parts # approve ወይም reject
    item_id = data_parts
    
    db = load_data()
    # እቃውን ከ pending ውስጥ መፈለግ
    item = db.get("pending", {}).pop(item_id, None)
    
    if not item:
        return bot.edit_message_caption("⚠️ ይህ እቃ ቀድሞውኑ ተስተካክሏል ወይም አልተገኘም።", call.message.chat.id, call.message.message_id)

    if action == "approve":
        # ወደ ዋናው የዕቃዎች ዝርዝር መጨመር
        if "items" not in db: db["items"] = {}
        item["status"] = "Active"
        db["items"][item_id] = item
        save_data(db)
        
        bot.edit_message_caption(f"✅ እቃው '{item['name']}' ጸድቋል! አሁን ለደንበኞች ይታያል።", 
                                 call.message.chat.id, call.message.message_id)
        
        # ለባለሱቁ ማሳወቂያ መላክ (ካስፈለገ)
        # vendor_id = item.get('vendor_id')
        # bot.send_message(vendor_id, f"🎉 እንኳን ደስ አለዎት! '{item['name']}' የተባለው እቃዎ በአድሚን ጸድቋል።")

    elif action == "reject":
        save_data(db) # እቃው ከ pending ተወግዷል
        bot.edit_message_caption(f"🔴 እቃው '{item['name']}' ውድቅ ተደርጓል (ተሰርዟል)።", 
                                 call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_order_"))
def broadcast_to_riders(call):
    order_id = call.data.replace("broadcast_order_", "")
    db = load_data()
    order = db['orders'][order_id]
    
    riders = db.get("riders", {})
    online_riders = [rid for rid, rdata in riders.items() if rdata.get("is_online") and not rdata.get("on_duty")]
    
    if not online_riders:
        return bot.answer_callback_query(call.id, "⚠️ በአሁኑ ሰዓት ክፍት የሆነ ዴሊቨሪ የለም።", show_alert=True)

    rider_text = (f"📦 **አዲስ የዴሊቨሪ ስራ!**\n\n"
                  f"📍 መነሻ (ሱቅ)፦ {order['vendor_address']}\n"
                  f"🏁 መድረሻ፦ {order['address']}\n"
                  f"💵 የዴሊቨሪ ክፍያ፦ {order['delivery_fee']} ETB\n")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ ስራውን ተቀበል", callback_data=f"accept_order_{order_id}"))

    for rider_id in online_riders:
        bot.send_message(rider_id, rider_text, reply_markup=markup)
    
    bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ለ {len(online_riders)} ዴሊቨሪዎች ተልኳል", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_order_"))
def rider_accept_order(call):
    order_id = call.data.replace("accept_order_", "")
    rider_id = str(call.from_user.id)
    db = load_data()
    
    order = db['orders'].get(order_id)
    
    if order.get('status') != "Pending Assignment":
        return bot.answer_callback_query(call.id, "❌ ይቅርታ፣ ይህ ትዕዛዝ በሌላ ሰው ተወስዷል።", show_alert=True)

    # ትዕዛዙን ለዴሊቨሪው መመደብ
    order['status'] = "On the way"
    order['rider_id'] = rider_id
    db['riders'][rider_id]['on_duty'] = True
    save_data(db)

    bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ተረክበዋል። መልካም ጉዞ!", call.message.chat.id, call.message.message_id)
    
    # ለደንበኛው ማሳወቅ
    bot.send_message(order['customer_id'], f"🚀 ትዕዛዝዎ ተረክቧል! ዴሊቨሪ {call.from_user.first_name} በቅርቡ ይደርሰዎታል።")



@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_dashboard_handler(call):
    db = load_data()
    
    # 1. ጠቅላላ ሪፖርት
    if call.data == "admin_stats":
        orders = db.get("orders", {})
        delivered = [o for o in orders.values() if o.get('status') == 'Delivered']
        total_sales = sum([o.get('total', 0) for o in delivered])
        text = f"📊 **አጠቃላይ ሪፖርት**\n\n✅ የተጠናቀቁ ትዕዛዞች: {len(delivered)}\n💰 ጠቅላላ ሽያጭ: {total_sales} ETB"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    # 2. አዳዲስ ሱቆች (የሱቆች ዝርዝር)
    elif call.data == "admin_list_v":
        vendors = db.get("vendors_list", {})
        if not vendors:
            return bot.answer_callback_query(call.id, "❌ ምንም የተመዘገበ ሱቅ የለም", show_alert=True)
        text = "🏪 **የአጋር ሱቆች ዝርዝር፦**\n\n"
        for vid, v in vendors.items():
            text += f"🔹 {v['name']} (ID: `{vid}`)\n"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    # 3. የደላላዎች (Riders) ሁኔታ
    elif call.data == "admin_riders":
        riders = db.get("riders", {})
        text = "🛵 **የዴሊቨሪዎች ሁኔታ፦**\n\n"
        if not riders:
            text += "ምንም ዴሊቨሪ የለም"
        for r in riders.values():
            status = "🟢 Online" if r.get("is_online") else "🔴 Offline"
            text += f"👤 {r['name']} - {status}\n"
        bot.send_message(call.message.chat.id, text)

    # 4. የኮሚሽን ተመን
    elif call.data == "admin_change_com":
        msg = bot.send_message(call.message.chat.id, "📈 አዲሱን የኮሚሽን ተመን (%) ያስገቡ፦")
        bot.register_next_step_handler(msg, save_commission)

    # 5. የማስተዋወቂያ ኮድ (Promo)
    elif call.data == "admin_promo":
        msg = bot.send_message(call.message.chat.id, "🎟 አዲስ የፕሮሞ ኮድ ይጻፉ፦")
        bot.register_next_step_handler(msg, set_promo_amount)

    # 6. በመጠባበቅ ላይ ያሉ (Pending)
    elif call.data == "admin_pending_items":
        # ይህ ከላይ የሰራነውን የፎቶ መላኪያ ሎጂክ ይጠራል
        view_pending_items(call) 

    # 7. ምርጥ ሻጮች
    elif call.data == "admin_top_v":
        vendors = db.get("vendors_list", {})
        top = sorted(vendors.items(), key=lambda x: x.get('balance', 0), reverse=True)[:5]
        text = "🏆 **ምርጥ 5 ሻጮች፦**\n\n"
        for i, (vid, v) in enumerate(top, 1):
            text += f"{i}. {v['name']} ({v.get('balance', 0)} ETB)\n"
        bot.send_message(call.message.chat.id, text)

    # 8. ዳታቤዝ አጽዳ
    elif call.data == "admin_clear_db":
        # ማረጋገጫ የሚጠይቀውን ፈንክሽን ይጠራል
        confirm_clear_db(call)

    # 9. የክፍያ ታሪክ
    elif call.data == "admin_pay_history":
        payments = db.get("payment_logs", [])
        text = "💳 **የክፍያ ታሪክ፦**\n\n"
        if not payments: text += "ምንም ታሪክ የለም"
        for p in payments[-10:]:
            text += f"📅 {p['date']} | {p['v_name']} | {p['amount']} ETB\n"
        bot.send_message(call.message.chat.id, text)

    # 10. ትዕዛዝ ሰርዝ
    elif call.data == "admin_cancel_order":
        msg = bot.send_message(call.message.chat.id, "🚫 ለመሰረዝ የትዕዛዝ ቁጥር (ID) ያስገቡ፦")
        bot.register_next_step_handler(msg, execute_order_cancel)

    # ወደ ኋላ መመለሻ
    elif call.data == "admin_main":
        bot.edit_message_text("የዴሊቨሪ ሲስተም መቆጣጠሪያ ዳሽቦርድ፦", 
                              call.message.chat.id, call.message.message_id, 
                              reply_markup=admin_delivery_dashboard())



def notify_admin_new_order(order_id):
    db = load_data()
    order = db['orders'][order_id]
    
    text = (f"🔔 **አዲስ ትዕዛዝ መጥቷል!**\n\n"
            f"🆔 ትዕዛዝ ቁጥር፦ #{order_id}\n"
            f"👤 ደንበኛ፦ {order['customer_name']}\n"
            f"📞 ስልክ፦ {order['customer_phone']}\n"
            f"📍 አድራሻ፦ {order['address']}\n"
            f"🛍 እቃ፦ {order['item_name']}\n"
            f"💰 ጠቅላላ ዋጋ፦ {order['total']} ETB\n\n"
            f"እባክዎ ትዕዛዙን ለዴሊቨሪ ይምድቡ ወይም ለሁሉም ክፍት ያድርጉት።")
    
    markup = types.InlineKeyboardMarkup()
    # ትዕዛዙን ለዴሊቨሪዎች ክፍት የሚያደርግ በተን
    markup.add(types.InlineKeyboardButton("🛵 ለዴሊቨሪዎች ላክ", callback_data=f"broadcast_order_{order_id}"))
    
    for admin_id in ADMIN_IDS:
        bot.send_message(admin_id, text, reply_markup=markup, parse_mode="Markdown")




def finalize_order_payment(order_id):
    db = load_data()
    order = db["orders"][order_id]
    item_price = order["item_price"]
    
    # ኮሚሽን ማስላት
    comm_rate = db["settings"].get("commission_rate", 10) # ካልተገኘ በ 10% አስላ
    commission_amount = (item_price * comm_rate) / 100
    
    # ለሱቁ የሚሰጠው (ከኮሚሽን የተረፈው)
    vendor_share = item_price - commission_amount
    
    # በዳታቤዝ ውስጥ ገቢዎችን መመዝገብ
    db["total_profit"] += commission_amount # የአድሚኑ ትርፍ
    
    # የሱቁን ሂሳብ መጨመር
    vid = order["vendor_id"]
    if vid in db["vendors_list"]:
        db["vendors_list"][vid]["balance"] += vendor_share
        
    save_data(db)





if __name__ == "__main__":
    # 1. የ Flask ሰርቨርን በ Background ያስነሳል
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. የቆየ ግንኙነትን ያጸዳል
    bot.remove_webhook()
    time.sleep(1) # ለደህንነት 1 ሰከንድ መጠበቅ
    
    # 3. ቦቱን ያስነሳል
    print(f"🚀 ቦቱ በ Port {PORT} ላይ ስራ ጀምሯል...")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            print(f"⚠️ ስህተት፦ {e}")
            time.sleep(5)
