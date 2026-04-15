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
# 1. ዳታቤዝ ማውረጃ (Redis ተጠቅሞ)
def load_data():
    try:
        raw = redis.get("bdf_delivery_db")
        if raw: 
            return json.loads(raw)

        # መዋቅሩን ለደላላ ስልክ እና ዋሌት እንዲመች አድርገን እናስተካክለው
        initial_data = {
            "riders_list": {},     # ✅ አዲስ፡ ለደላላ ስልክ እና የሰራው ብር መመዝገቢያ
            "vendors_list": {},    # የድርጅቶች ዝርዝር
            "orders": {},          # የታዘዙ ትዕዛዞች
            "pending_items": {},   
            "categories": [],      
            "total_profit": 0,     
            "settings": {
                "base_delivery": 50, 
                "commission_rate": 10,
                "system_locked": False 
            }
        }
        return initial_data
    except Exception as e:
        print(f"❌ Database Load Error: {e}")
        # Error ቢመጣም ቦቱ እንዳይቆም ባዶውን riders_list እንላክ
        return {"riders_list": {}, "vendors_list": {}, "orders": {}, "categories": [], "settings": {"base_delivery": 50}}


def save_data(db):
    try:
        # ዳታውን ወደ Redis መላኪያ
        redis.set("bdf_delivery_db", json.dumps(db))
    except Exception as e:
        print(f"❌ Database Save Error: {e}")

# --- አዲሱ ክፍል እዚህ ጋር ይግባ ---
def notify_admins(text):
    """ለሦስቱም አድሚኖች የኦፕሬሽን መልዕክት መላኪያ"""
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"📢 **የBDF ኦፕሬሽን ማሳሰቢያ**\n\n{text}", parse_mode="Markdown")
        except Exception as e:
            print(f"ለአድሚን {admin_id} መላክ አልተቻለም: {e}")

# --------------------------------

# 2. አድሚን መሆኑን ማረጋገጫ (Check Admin)
def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True


# 3. አዲስ ምድብ መመዝገቢያ (Save Category)
def save_category(message):
    if not check_admin(message): return
    
    db = load_data()
    new_cat = message.text.strip()

    if not new_cat:
        return bot.send_message(message.chat.id, "⚠️ እባክዎ የምድብ ስም በትክክል ያስገቡ።")

    if "categories" not in db: db["categories"] = []

    if new_cat not in db["categories"]:
        db["categories"].append(new_cat)
        save_data(db) # ዳታ ሴቭ ማድረጊያ ፈንክሽን መኖሩን እርግጠኛ ሁን

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
        bot.send_message(message.chat.id, f"✅ ምድብ '{new_cat}' በሚገባ ተጨምሯል!", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "⚠️ ይህ ምድብ ቀድሞውኑ ተመዝግቧል።")

# 4. እቃ ሲመዘገብ ምድብ መምረጫ (Category Selector)
def process_item_name(message, photo_id):
    item_name = message.text.strip()
    db = load_data()
    
    # ድርጅቱ ዋስትና (Balance) እንዳለው እዚህ ጋር ቼክ ማድረግ ይቻላል
    v_id = str(message.from_user.id)
    if v_id in db['vendors_list']:
        if db['vendors_list'][v_id].get('deposit_balance', 0) <= 0:
            return bot.send_message(message.chat.id, "❌ ይቅርታ፣ የቀሪ ዋስትና ሂሳብዎ 0 ስለሆነ እቃ መመዝገብ አይችሉም። እባክዎ አድሚኑን ያነጋግሩ።")

    categories = db.get("categories", ["ሌሎች"])
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for cat in categories:
        # callback_data ላይ የፎቶውን ID እና ስሙን መያዝ ለቀጣይ ደረጃ ይረዳል
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"selcat_{cat}"))

    bot.send_message(message.chat.id, f"📂 የ '{item_name}' ምድብ ይምረጡ፦", reply_markup=markup)

# 5. የርቀት ስሌት (Distance)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000 # በሜትር
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2-lat1)
    dlambda = math.radians(lon2-lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def get_admin_dashboard(user_id): # ✅ user_id እዚህ መግባቱን እርግጠኛ ሁን
    db = load_data() # ✅ ዳታውን መጫን ግዴታ ነው
    markup = types.InlineKeyboardMarkup(row_width=2)
    # ምድብ 1
    finance_label = types.InlineKeyboardButton("--- 💰 ፋይናንስና ዋስትና ---", callback_data="none")
    btn_fund = types.InlineKeyboardButton("💳 ብር መሙያ (Fund)", callback_data="admin_add_funds")
    btn_balance = types.InlineKeyboardButton("📉 የሂሳብ ክትትል", callback_data="admin_monitor_balance")
    btn_profit = types.InlineKeyboardButton("💰 የኮሚሽን ትርፍ", callback_data="admin_profit_track")
    btn_low_credit = types.InlineKeyboardButton("⚠️ ዝቅተኛ ሂሳብ", callback_data="admin_low_credit")

    # ምድብ 2
    ops_label = types.InlineKeyboardButton("--- 📦 ኦፕሬሽን ---", callback_data="none")
    btn_live_orders = types.InlineKeyboardButton("📋 የቀጥታ ትዕዛዞች", callback_data="admin_live_orders")
    btn_pending = types.InlineKeyboardButton("📦 በመጠባበቅ ላይ ያሉ", callback_data="admin_pending_approvals")
    btn_cats = types.InlineKeyboardButton("📁 ምድቦች (Categories)", callback_data="admin_manage_cats")

    # ምድብ 3
    security_label = types.InlineKeyboardButton("--- 🔐 ደህንነትና ተሳታፊዎች ---", callback_data="none")
    btn_add_vendor = types.InlineKeyboardButton("➕ አዲስ ድርጅት መመዝገቢያ", callback_data="admin_add_vendor")
    btn_vendors = types.InlineKeyboardButton("🏢 የአጋር ድርጅቶች", callback_data="admin_list_vendors")
    btn_add_rider = types.InlineKeyboardButton("➕ አዲስ driver መመዝገቢያ", callback_data="admin_add_rider")
    btn_phone = types.InlineKeyboardButton("📞 ስልክ መመዝገቢያ", callback_data="register_rider_phone")
    btn_set_commission = types.InlineKeyboardButton("⚙️ የኮሚሽን መጠን ቀይር", callback_data="admin_set_commission")
    btn_riders = types.InlineKeyboardButton("🛵 drivers ሁኔታ", callback_data="admin_rider_status")
    btn_block = types.InlineKeyboardButton("🚫 አግድ/ፍቀድ", callback_data="admin_block_manager")
    btn_lock = types.InlineKeyboardButton("🔒 ሲስተም ዝጋ (Lock)", callback_data="admin_system_lock")

    # ምድብ 4 & 5
    support_label = types.InlineKeyboardButton("--- 📣 ድጋፍና ማስታወቂያ ---", callback_data="none")
    btn_dispute = types.InlineKeyboardButton("💬 ቅሬታዎች", callback_data="admin_disputes")
    btn_reviews = types.InlineKeyboardButton("⭐ ግምገማዎች", callback_data="admin_reviews")
    btn_broadcast = types.InlineKeyboardButton("📢 ማስታወቂያ ላክ", callback_data="admin_broadcast")
    report_label = types.InlineKeyboardButton("--- 📊 ሪፖርት ---", callback_data="none")
    btn_stats = types.InlineKeyboardButton("📈 ጠቅላላ ሪፖርት", callback_data="admin_full_stats")

    
    # --- Adding to Markup ---
    markup.add(finance_label)
    markup.add(btn_fund, btn_balance)
    markup.add(btn_profit, btn_low_credit)
    markup.add(ops_label)
    markup.add(btn_live_orders, btn_pending)
    markup.add(btn_cats)
    markup.add(security_label)
    markup.add(btn_add_vendor, btn_add_rider) # Both registration buttons side by side
    markup.add(btn_vendors, btn_set_commission)
    markup.add(btn_riders)
    markup.add(btn_block, btn_lock)
    markup.add(support_label)
    markup.add(btn_dispute, btn_reviews)
    markup.add(btn_broadcast)
    markup.add(report_label)
    markup.add(btn_stats)
    markup.add(btn_phone)
    

    uid_str = str(user_id) 
    if uid_str in db.get('riders_list', {}):
        status = "🟢 Online" if db['riders_list'][uid_str].get('is_online') else "🔴 Offline"
        btn_rider = types.InlineKeyboardButton(f"🛵 ስራ: {status}", callback_data="rider_toggle_status")
        btn_phone = types.InlineKeyboardButton("📞 ስልክ መመዝገቢያ", callback_data="register_rider_phone")
        markup.add(btn_rider, btn_phone)

    return markup  

# 1. መጀመሪያ ይህ መኖሩን አረጋግጥ
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🏢 አጋር ድርጅቶች", "📦 ትዕዛዞች", "📊 ሪፖርት", "⚙️ ሲስተም")
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        uid_str = str(user_id)
        bot.clear_step_handler_by_chat_id(chat_id=user_id) 

        db = load_data() 

        # --- ተጠቃሚውን ወደ ሊስት መጨመሪያ ---
        if "user_list" not in db: db["user_list"] = []
        if user_id not in db["user_list"]:
            db["user_list"].append(user_id)
            save_data(db)

        # 1. ለአድሚኖች
        if user_id in ADMIN_IDS:
            # 💡 እዚህ ጋር ነው ስህተቱ የነበረው፦ user_id መጨመር አለበት
            markup = get_admin_dashboard(user_id) 
            
            # ⚠️ ማሳሰቢያ፦ የሪደር በተኑን ቀጥታ get_admin_dashboard ውስጥ ከጨመርከው 
            # እዚህ ጋር ድጋሚ markup.add ማድረግ አያስፈልግህም (ደራራቢ እንዳይሆን)
            
            return bot.send_message(user_id, "👑 **Welcome to BDF Admin Panel**", 
                                   reply_markup=markup, parse_mode="Markdown")

        # 2. ለድርጅቶች (Vendors)
        if uid_str in db.get('vendors_list', {}):
            v_name = db['vendors_list'][uid_str]['name']
            return bot.send_message(user_id, f"እንኳን ደህና መጡ **{v_name}** 👋", 
                                   reply_markup=get_vendor_menu(), parse_mode="Markdown")

        # 3. drivers
        if uid_str in db.get('riders_list', {}):
            return show_rider_menu(message)

        # 4. ለደንበኞች
        welcome_text = f"Welcome {message.from_user.first_name} to BDF Delivery! 👋\nYour ID: `{user_id}`"
        bot.send_message(user_id, welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

    except Exception as e:
        # Render Log ላይ Errorሩን በደንብ ለማየት ይረዳሃል
        print(f"❌ Error in start_command: {str(e)}")
        bot.send_message(message.chat.id, "⚠️ ቦቱ ላይ ትንሽ ችግር ተፈጥሯል፣ እባክዎ ደግመው ይሞክሩ።")

@bot.message_handler(commands=['admin'])
def show_admin_panel(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(
            message.chat.id, 
            "👑 **BDF አድሚን ዳሽቦርድ**",
            # ✅ እዚህ ጋር በቅንፍ ውስጥ ID መስጠት ግዴታ ነው
            reply_markup=get_admin_dashboard(message.from_user.id), 
            parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id, "❌ ፈቃድ የለዎትም።")


@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def interrupt_handler(message):
    # ማንኛውም ኮማንድ ሲመጣ የቆየውን Next Step ይሰርዛል
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    
    # ከዚያ ወደ ትክክለኛው ኮማንድ ይልከዋል
    if message.text == '/start':
        start_command(message)
    elif message.text == '/admin':
        show_admin_panel(message)


# --- 1. የሁሉም አድሚን በተኖች ማዕከላዊ መቆጣጠሪያ (Manager) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback_manager(call):
    # 🌟 ወሳኝ፦ ማንኛውንም የቆየ ስራ ያጸዳል (Overlap መከላከያ)
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    
    # ሀ. መረጃ መቀበል የሚፈልጉ (Next Step የሚጠቀሙ)
    if call.data == "admin_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 **ማስታወቂያ ይጻፉ፦**\n(ለማቋረጥ /start ይበሉ)")
        bot.register_next_step_handler(msg, send_broadcast_logic)

    elif call.data == "admin_add_vendor":
        msg = bot.send_message(call.message.chat.id, "🏢 **የድርጅቱን ስም ያስገቡ፦**")
        bot.register_next_step_handler(msg, process_v_name)

    elif call.data == "admin_add_funds":
        msg = bot.send_message(call.message.chat.id, "💳 **የድርጅት User ID ያስገቡ፦**")
        bot.register_next_step_handler(msg, process_fund_id)

    elif call.data == "admin_add_rider":
        msg = bot.send_message(call.message.chat.id, "🛵 ለመመዝገብ የሚፈልጉትን የደላላ User ID ያስገቡ፦")
        bot.register_next_step_handler(msg, process_admin_rider_id)


    elif call.data == "admin_manage_cats":
        msg = bot.send_message(call.message.chat.id, "📁 **የአዲሱን ምድብ ስም ያስገቡ፦**")
        bot.register_next_step_handler(msg, add_category_logic)

    elif call.data == "admin_block_manager":
        msg = bot.send_message(call.message.chat.id, "🚫 **የሚታገደውን ወይም የሚፈቀደውን User ID ያስገቡ፦**")
        bot.register_next_step_handler(msg, process_block_unblock)

    elif call.data == "admin_set_commission":
        msg = bot.send_message(call.message.chat.id, "⚙️ **አዲሱን የኮሚሽን መጠን ያስገቡ (%)፦**")
        bot.register_next_step_handler(msg, save_new_commission)

    # ለ. ቀጥታ ሪፖርት የሚያሳዩ (Next Step የማይፈልጉ)
    elif call.data == "admin_monitor_balance":
        view_all_balances(call)
    elif call.data == "admin_profit_track":
        view_total_profit(call)
    elif call.data == "admin_low_credit":
        view_low_balances(call)
    elif call.data == "admin_live_orders":
        view_live_orders(call)
    elif call.data == "admin_pending_approvals":
        view_pending_items(call)
    elif call.data == "admin_list_vendors":
        list_all_vendors(call)
    elif call.data == "admin_rider_status":
        view_rider_status(call)
    elif call.data == "admin_system_lock":
        toggle_system_lock(call)
    elif call.data == "admin_disputes":
        view_disputes(call)
    elif call.data == "admin_reviews":
        view_reviews(call)
    elif call.data == "admin_full_stats":
        show_full_stats(call)

# --- 2. እቃ የማጽደቅ/የመሰረዝ ስራ (ልዩ Callback) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_", "resolve_")))
def item_approval_manager(call):
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    if call.data.startswith("approve_"):
        approve_item(call)
    elif call.data.startswith("reject_"):
        reject_item(call)
    elif call.data.startswith("resolve_"):
        bot.answer_callback_query(call.id, "✅ ቅሬታው ተፈቷል ተብሎ ተመዝግቧል።")

# --- 3. መረጃ ተቀባይ ሎጂኮች (Logic Functions) ---

# ሀ. የድርጅት ምዝገባ ቅደም ተከተል
def process_v_name(message):
    v_name = message.text.strip()
    if v_name.startswith('/'): return start_command(message)
    msg = bot.send_message(message.chat.id, f"🆔 የ '{v_name}' ባለቤት User ID ያስገቡ፦")
    bot.register_next_step_handler(msg, process_v_id, v_name)

def process_v_id(message, v_name):
    v_id = message.text.strip()
    if v_id.startswith('/'): return start_command(message)
    if not v_id.isdigit():
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ User ID ቁጥር መሆን አለበት። እንደገና ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_v_id, v_name)
    msg = bot.send_message(message.chat.id, f"📍 የ '{v_name}' አድራሻ ያስገቡ፦")
    bot.register_next_step_handler(msg, process_v_address, v_name, v_id)

def process_v_address(message, v_name, v_id):
    address = message.text.strip()
    if address.startswith('/'): return start_command(message)
    db = load_data()
    v_id_str = str(v_id)
    if v_id_str in db['vendors_list']:
        return bot.send_message(message.chat.id, f"⚠️ ይህ ድርጅት (ID: {v_id}) ቀድሞውኑ አለ።")
    db['vendors_list'][v_id_str] = {
        "name": v_name, "address": address, "deposit_balance": 0,
        "total_sales": 0, "status": "active", "items": {},
        "registered_date": str(time.ctime())
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ **{v_name}** ተመዝግቧል!", reply_markup=get_admin_dashboard())

# ለ. ብር መሙያ ሎጂክ
def process_fund_id(message):
    v_id = message.text.strip()
    if v_id.startswith('/'): return start_command(message)
    db = load_data()
    if v_id not in db.get('vendors_list', {}):
        msg = bot.send_message(message.chat.id, "❌ ID አልተገኘም። ደግመው ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_fund_id)
    v_name = db['vendors_list'][v_id]['name']
    msg = bot.send_message(message.chat.id, f"💰 ለ '{v_name}' የሚሞላውን የብር መጠን ያስገቡ፦")
    bot.register_next_step_handler(msg, process_fund_amount, v_id, v_name)

def process_fund_amount(message, v_id, v_name):
    try:
        amount = float(message.text.strip())
        db = load_data()
        db['vendors_list'][v_id]['deposit_balance'] += amount
        save_data(db)
        bot.send_message(message.chat.id, f"✅ {amount} ብር ለ {v_name} ተሞልቷል።")
        try: bot.send_message(v_id, f"🔔 {amount} ETB ዋስትና ተሞልቶልዎታል።")
        except: pass
    except:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ ቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, process_fund_amount, v_id, v_name)

# ሐ. ኮሚሽን መቀየሪያ
def save_new_commission(message):
    try:
        new_rate = float(message.text.strip())
        db = load_data(); db['settings']['commission_rate'] = new_rate; save_data(db)
        bot.send_message(message.chat.id, f"✅ ኮሚሽን ወደ {new_rate}% ተቀይሯል።")
    except: bot.send_message(message.chat.id, "❌ ቁጥር ብቻ ያስገቡ።")

# 1. የሁሉንም ድርጅቶች ቀሪ ዋስትና ማሳያ
def view_all_balances(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    if not vendors:
        return bot.send_message(call.message.chat.id, "📭 እስካሁን የተመዘገበ ድርጅት የለም።")
    
    report = "📉 **የድርጅቶች ቀሪ የዋስትና ሂሳብ**\n\n"
    for vid, data in vendors.items():
        bal = data.get('deposit_balance', 0)
        report += f"🏢 ድርጅት፦ {data['name']}\n💰 ቀሪ ዋስትና፦ {bal} ETB\n"
        report += "------------------------\n"
    bot.send_message(call.message.chat.id, report, parse_mode="Markdown")

# 2. የቦቱን ጠቅላላ ትርፍ ማሳያ
def view_total_profit(call):
    db = load_data()
    profit = db.get("total_profit", 0)
    rate = db.get('settings', {}).get('commission_rate', 5)
    text = (f"📊 **የቦቱ ትርፍ ሪፖርት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📉 የኮሚሽን መጠን፦ **{rate}%**\n"
            f"💰 ጠቅላላ የተጣራ ትርፍ፦ **{profit:,.2f} ETB**\n"
            f"━━━━━━━━━━━━━━━")
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

# 3. ዋስትናቸው ሊያልቅ የደረሱ ድርጅቶች
def view_low_balances(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    limit = 200 # ማስጠንቀቂያ ጣሪያ
    low_list = [f"⚠️ {data['name']} - ቀሪ፦ {data.get('deposit_balance', 0)} ETB" 
                for vid, data in vendors.items() if data.get('deposit_balance', 0) < limit]
    
    text = "🚨 **ዋስትናቸው ሊያልቅ የደረሱ ድርጅቶች**\n\n" + "\n".join(low_list) if low_list else "✅ ሁሉም ድርጅቶች በቂ ዋስትና አላቸው።"
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

def process_admin_rider_id(message):
    try:
        rider_id = message.text.strip()
        db = load_data()
        
        if "riders_list" not in db: db["riders_list"] = {}
        
        # አዲስ ደላላ ሲመዘገብ የሚከተሉትን መረጃዎች መያዝ አለበት
        db['riders_list'][rider_id] = {
            "name": "Admin/Rider", 
            "phone": "ያልተመዘገበ",   # ስልኩ ገና ነው
            "is_online": False,
            "total_earned": 0,      # ✅ አዲስ፡ የሰራው ብር (Wallet) 0 ETB
            "completed_orders": 0   # ያደረሰው ትዕዛዝ ብዛት
        }
        
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ደላላ {rider_id} ተመዝግቧል።")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት፡ {e}")

# 4. የቀጥታ ትዕዛዞችን ማሳያ (Live Orders)
def view_live_orders(call):
    db = load_data()
    orders = db.get("orders", {})
    live_orders = {k: v for k, v in orders.items() if v['status'] in ["Pending", "On the way"]}
    
    if not live_orders:
        return bot.send_message(call.message.chat.id, "📭 በአሁኑ ሰዓት ምንም አይነት የቀጥታ ትዕዛዝ የለም።")
    
    text = "📋 **የቀጥታ ትዕዛዞች ዝርዝር**\n\n"
    for oid, odata in live_orders.items():
        text += (f"🆔 ትዕዛዝ: #{oid}\n🏢 ድርጅት: {odata['vendor_name']}\n"
                 f"👤 ደንበኛ: {odata['customer_name']}\n📍 ሁኔታ: {odata['status']}\n"
                 f"------------------------\n")
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

# 5. ድርጅቶችን ለማገድ ወይም ለመፍቀድ (Block Manager)
def process_block_unblock(message):
    target_id = message.text.strip()
    db = load_data()
    found = False
    for category in ['vendors_list', 'riders_list']:
        if target_id in db.get(category, {}):
            current_status = db[category][target_id].get('status', 'active')
            new_status = 'blocked' if current_status != 'blocked' else 'active'
            db[category][target_id]['status'] = new_status
            found = True; break
    if found:
        save_data(db)
        bot.send_message(message.chat.id, f"✅ የ ID {target_id} ሁኔታ ወደ **{new_status}** ተቀይሯል።")
    else:
        bot.send_message(message.chat.id, "❌ ስህተት፦ ይህ ID በሲስተሙ ላይ አልተገኘም።")

# 6. ሲስተሙን መቆለፊያ (System Lock)
def toggle_system_lock(call):
    db = load_data()
    db['settings']['system_locked'] = not db['settings'].get('system_locked', False)
    save_data(db)
    status_text = "🔒 ዝግ (Locked)" if db['settings']['system_locked'] else "🔓 ክፍት (Unlocked)"
    bot.send_message(call.message.chat.id, f"⚠️ የሲስተሙ ሁኔታ ተቀይሯል። አሁን ሲስተሙ፦ **{status_text}** ነው")

# 7. የማስታወቂያ መላኪያ ሎጂክ (Broadcast)
def send_broadcast_logic(message):
    if message.text and message.text.startswith('/'): return start_command(message)
    db = load_data(); all_users = db.get("user_list", [])
    if not all_users: return bot.send_message(message.chat.id, "⚠️ ተጠቃሚ የለም።")
    
    count = 0
    status_msg = bot.send_message(message.chat.id, "⏳ እየተላከ ነው...")
    for user_id in all_users:
        try:
            bot.send_message(user_id, f"🔔 **ማሳሰቢያ፦**\n\n{message.text}", parse_mode="Markdown")
            count += 1; time.sleep(0.05)
        except: continue
    bot.delete_message(message.chat.id, status_msg.message_id)
    bot.send_message(message.chat.id, f"✅ ለ {count} ተጠቃሚዎች ተልኳል።")

def list_all_vendors(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    
    if not vendors:
        return bot.send_message(call.message.chat.id, "🏢 እስካሁን የተመዘገበ ድርጅት የለም።")
    
    text = "🏢 **የአጋር ድርጅቶች ዝርዝር**\n\n"
    for vid, vdata in vendors.items():
        text += (f"🔹 **ስም:** {vdata['name']}\n"
                 f"🆔 **ID:** `{vid}`\n"
                 f"📍 **አድራሻ:** {vdata.get('address', 'ያልተገለጸ')}\n"
                 f"📈 **ጠቅላላ ሽያጭ:** {vdata.get('total_sales', 0)} ETB\n"
                 f"------------------------\n")
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")


def view_pending_items(call):
    db = load_data()
    pending = db.get("pending_items", {}) 
    
    if not pending:
        return bot.send_message(call.message.chat.id, "✅ በመጠባበቅ ላይ ያለ አዲስ እቃ የለም።")
    
    for item_id, idata in pending.items():
        text = (f"📦 **አዲስ እቃ ለመመዝገብ ቀርቧል**\n\n"
                f"🏢 ድርጅት: {idata['vendor_name']}\n"
                f"🛍 እቃ: {idata['item_name']}\n"
                f"💰 ዋጋ: {idata['price']} ETB")
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ ፍቀድ", callback_data=f"approve_{item_id}"),
            types.InlineKeyboardButton("❌ ሰርዝ", callback_data=f"reject_{item_id}")
        )
        bot.send_message(call.message.chat.id, text, reply_markup=markup)


def show_full_stats(call):
    db = load_data()
    orders = db.get("orders", {})
    total_sales = sum(o['total_price'] for o in orders.values() if o.get('status') == "Completed")
    
    text = (f"📊 **አጠቃላይ የቦቱ እንቅስቃሴ**\n\n"
            f"💰 ጠቅላላ ሽያጭ: {total_sales} ETB\n"
            f"📈 የተጣራ ትርፍ: {db.get('total_profit', 0)} ETB\n"
            f"📦 ጠቅላላ የታዘዙ እቃዎች: {len(orders)}\n"
            f"🏢 የተመዘገቡ ድርጅቶች: {len(db.get('vendors_list', {}))}\n"
            f"🛵 ንቁ ዴሊቨሪዎች: {len(db.get('riders_list', {}))}")
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

def view_disputes(call):
    db = load_data()
    disputes = db.get("disputes", {})
    if not disputes:
        return bot.send_message(call.message.chat.id, "✅ ምንም አይነት የደንበኛ ቅሬታ የለም።")
    
    for d_id, d_data in disputes.items():
        text = f"❗ **ቅሬታ**\n👤 ደንበኛ: {d_data['user_name']}\n📝 ጉዳዩ: {d_data['issue']}"
        bot.send_message(call.message.chat.id, text)

def view_reviews(call):
    db = load_data()
    reviews = db.get("reviews", [])
    if not reviews:
        return bot.send_message(call.message.chat.id, "⭐ እስካሁን የተሰጠ አስተያየት የለም።")
    
    text = "⭐ **የቅርብ ጊዜ አስተያየቶች**\n\n"
    for r in reviews[-5:]: # የመጨረሻዎቹን 5 ብቻ
        text += f"🏢 {r['vendor_name']} ➡️ {r['stars']}⭐\n💬 {r['comment']}\n---\n"
    bot.send_message(call.message.chat.id, text)

def view_rider_status(call):
    db = load_data()
    riders = db.get("riders_list", {})
    
    if not riders:
        return bot.send_message(call.message.chat.id, "🛵 እስካሁን የተመዘገበ ዴሊቨሪ የለም።")
    
    active_count = 0
    busy_count = 0
    report = "🛵 **የዴሊቨሪዎች ወቅታዊ ሁኔታ**\n\n"
    
    for rid, rdata in riders.items():
        status_icon = "🟢" if rdata['is_online'] else "🔴"
        work_status = "🏃 ስራ ላይ" if rdata['status'] == "Busy" else "⏳ ክፍት"
        
        if rdata['is_online']: active_count += 1
        if rdata['status'] == "Busy": busy_count += 1
        
        report += f"{status_icon} **{rdata['name']}**\n   - ሁኔታ፦ {work_status}\n   - ስልክ፦ {rdata['phone']}\n"
    
    summary = (f"\n📊 **ማጠቃለያ**\n"
               f"✅ ኦንላይን፦ {active_count}\n"
               f"🏃 ስራ ላይ፦ {busy_count}\n"
               f"💤 ኦፍላይን፦ {len(riders) - active_count}")
    
    bot.send_message(call.message.chat.id, report + summary)

def show_rider_menu(message):
    rider_id = str(message.from_user.id)
    db = load_data()
    
    # ደላላው በአድሚን የተመዘገበ መሆኑን ቼክ ያደርጋል
    if rider_id in db.get('riders_list', {}) and db['riders_list'][rider_id].get('is_authorized'):
        status = "ክፍት (Online)" if db['riders_list'][rider_id]['is_online'] else "ዝግ (Offline)"
        text = f"🛵 **የዴሊቨሪ ማእከል**\n\nየአሁኑ ሁኔታህ፦ **{status}**"
        
        markup = types.InlineKeyboardMarkup()
        btn_text = "🔴 ራስህን ዝጋ (Go Offline)" if db['riders_list'][rider_id]['is_online'] else "🟢 ራስህን ክፈት (Go Online)"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data="rider_toggle_status"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "⚠️ ይቅርታ፣ አንተ እንደ ደላላ አልተመዘገብክም። እባክህ አድሚኑን አነጋግር።")

def process_admin_rider_id(message):
    rider_id = message.text.strip()
    if rider_id.startswith('/'): return start_command(message)
    
    if not rider_id.isdigit():
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ User ID ቁጥር መሆን አለበት። ደግመው ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_admin_rider_id)

    msg = bot.send_message(message.chat.id, "👤 የደላላውን ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, process_admin_rider_name, rider_id)

def process_admin_rider_name(message, rider_id):
    rider_name = message.text.strip()
    db = load_data()
    
    if 'riders_list' not in db: db['riders_list'] = {}
    
    # ደላላውን በ IDው መመዝገብ (IDው ሁልጊዜ String መሆን አለበት)
    db['riders_list'][str(rider_id)] = {
        "name": rider_name,
        "phone": "ያልተመዘገበ",
        "status": "Idle",
        "is_online": False, 
        "earnings": 0,
        "total_deliveries": 0,
        "is_authorized": True 
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ ደላላ {rider_name} (ID: {rider_id}) በሚገባ ተመዝግቧል!")

def add_category_logic(message):
    if not check_admin(message): return
    
    db = load_data()
    new_cat = message.text.strip()

    if not new_cat:
        return bot.send_message(message.chat.id, "⚠️ እባክዎ የምድብ ስም በትክክል ያስገቡ።")

    if "categories" not in db: db["categories"] = []

    if new_cat not in db["categories"]:
        db["categories"].append(new_cat)
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ምጻብ '{new_cat}' ተጨምሯል።", reply_markup=get_admin_dashboard())
    else:
        bot.send_message(message.chat.id, "⚠️ ይህ ምድብ ቀድሞውኑ አለ።")

def approve_item(call):
    item_id = call.data.replace("approve_", "")
    db = load_data()
    
    if item_id in db.get('pending_items', {}):
        item_data = db['pending_items'].pop(item_id) # ከፔንዲንግ አውጣው
        vendor_id = str(item_data['vendor_id'])
        
        # ወደ ድርጅቱ እቃዎች ዝርዝር ጨምረው
        if vendor_id not in db['vendors_list']:
            return bot.send_message(call.message.chat.id, "❌ ድርጅቱ አልተገኘም።")
            
        db['vendors_list'][vendor_id]['items'][item_id] = item_data
        save_data(db)
        
        bot.edit_message_text(f"✅ እቃው ተፈቅዷል!\n📦 እቃ፦ {item_data['item_name']}", 
                              call.message.chat.id, call.message.message_id)
        
        # ለድርጅቱ ማሳወቂያ ላክ
        try: bot.send_message(vendor_id, f"🎉 እቃዎ '{item_data['item_name']}' በአድሚን ጸድቆ ለሽያጭ ቀርቧል።")
        except: pass
    else:
        bot.answer_callback_query(call.id, "❌ ይህ እቃ ቀድሞውኑ ተስተካክሏል።")

def reject_item(call):
    item_id = call.data.replace("reject_", "")
    db = load_data()
    
    if item_id in db.get('pending_items', {}):
        item_data = db['pending_items'].pop(item_id)
        save_data(db)
        
        bot.edit_message_text(f"❌ እቃው ተሰርዟል!\n📦 እቃ፦ {item_data['item_name']}", 
                              call.message.chat.id, call.message.message_id)
        
        # ለድርጅቱ ማሳወቂያ ላክ
        try: bot.send_message(item_data['vendor_id'], f"⚠️ ይቅርታ፣ ያቀረቡት እቃ '{item_data['item_name']}' በአድሚን ተቀባይነት አላገኘም።")
        except: pass

def get_admin_dashboard_with_rider(user_id, db):
    markup = get_admin_dashboard() # ዋናውን የአድሚን በተኖች ይጠራል
    
    uid_str = str(user_id)
    if uid_str in db.get('riders_list', {}):
        status = "🟢 Online" if db['riders_list'][uid_str].get('is_online') else "🔴 Offline"
        btn_rider = types.InlineKeyboardButton(f"🛵 ስራ: {status}", callback_data="rider_toggle_status")
        markup.add(btn_rider)
        
    return markup


# መጀመሪያ ፊልተሩን ሁሉንም እንዲቀበል እናስተካክለው (startswith የሚለውን እናስፋው)
@bot.callback_query_handler(func=lambda call: call.data.startswith(('admin_', 'rider_', 'accept_')))
def central_callback_manager(call):
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    db = load_data()
    uid = str(call.from_user.id)

    # 1. የአድሚን በተኖች
    if call.data.startswith('admin_'):
        if call.data == "admin_add_rider":
            msg = bot.send_message(call.message.chat.id, "🛵 የደላላ User ID ያስገቡ፦")
            bot.register_next_step_handler(msg, process_admin_rider_id)
        # ... ሌሎቹ የአድሚን elif እዚህ ይቀጥላሉ ...

    # 2. የደላላ (Rider) በተኖች (elif መጠቀም ትችላለህ)
    elif call.data == "rider_toggle_status":
        if uid in db.get('riders_list', {}):
            current = db['riders_list'][uid].get('is_online', False)
            db['riders_list'][uid]['is_online'] = not current
            save_data(db)
            new_status = "🟢 Online" if not current else "🔴 Offline"
            bot.answer_callback_query(call.id, f"ሁኔታዎ ወደ {new_status} ተቀይሯል")
            # ሜኑውን Update ለማድረግ
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, 
                                          reply_markup=get_admin_dashboard())
        else:
            bot.answer_callback_query(call.id, "⚠️ መጀመሪያ እንደ ደላላ መመዝገብ አለብዎት!", show_alert=True)

    # 3. የትዕዛዝ መቀበያ (Accept Order)
    elif call.data.startswith("accept_order_"):
        order_id = call.data.replace("accept_order_", "")
        if order_id in db['orders'] and db['orders'][order_id]['status'] == "Pending":
            db['orders'][order_id]['status'] = "On the way"
            db['orders'][order_id]['rider_id'] = uid
            save_data(db)
            bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} በ {call.from_user.first_name} ተይዟል!", 
                                  call.message.chat.id, call.message.message_id)
            notify_admins(f"🏃 አድሚን {call.from_user.first_name} ትዕዛዝ #{order_id}ን ይዞ ወጥቷል።")


# ሀ. በተኑ ሲነካ ስልክ እንዲጠይቅ
@bot.callback_query_handler(func=lambda call: call.data == "register_rider_phone")
def ask_for_phone(call):
    msg = bot.send_message(call.message.chat.id, "📞 እባክዎ ስልክ ቁጥርዎን ያስገቡ (ምሳሌ፦ 0911223344)፦")
    bot.register_next_step_handler(msg, save_rider_phone)

# ለ. ቁጥሩን ተቀብሎ ዳታቤዝ ውስጥ 'phone' በሚለው ቦታ ላይ እንዲያስቀምጥ
def save_rider_phone(message):
    db = load_data()
    uid = str(message.from_user.id)
    phone = message.text.strip()
    
    if phone.isdigit() and len(phone) >= 10:
        if uid in db.get('riders_list', {}):
            db['riders_list'][uid]['phone'] = phone
            save_data(db)
            bot.send_message(message.chat.id, f"✅ ስልክዎ {phone} ተመዝግቧል!")
        else:
            bot.send_message(message.chat.id, "❌ መጀመሪያ እንደ ደላላ መመዝገብ አለብዎት።")
    else:
        msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ ትክክለኛ ቁጥር ያስገቡ፦")
        bot.register_next_step_handler(msg, save_rider_phone)

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
