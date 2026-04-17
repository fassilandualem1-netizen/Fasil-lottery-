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


import json

def load_data():
    # መሠረታዊ የዳታቤዝ አወቃቀር (Default Structure)
    default_db = {
        "riders_list": {},     
        "vendors_list": {}, 
        "orders": {},          
        "carts": {},           # ለደንበኞች ቅርጫት የግድ ያስፈልጋል
        "pending_items": {},   
        "categories": [],      
        "total_profit": 0,     
        "user_list": [],       
        "settings": {
            "vendor_commission_p": 10,
            "rider_fixed_fee": 30,
            "customer_service_fee": 15,
            "base_delivery": 50,
            "system_locked": False 
        }
    }

    try:
        raw = redis.get("bdf_delivery_db")
        if raw: 
            loaded_db = json.loads(raw)
            
            # ዳታው ዝርዝር (list) ሳይሆን ዲክሽነሪ (dict) መሆኑን ማረጋገጫ
            if not isinstance(loaded_db, dict):
                loaded_db = default_db

            # አዳዲስ ቁልፎች (keys) በቆየው ዳታቤዝ ውስጥ ከሌሉ እንዲጨመሩ
            for key, value in default_db.items():
                if key not in loaded_db:
                    loaded_db[key] = value
            
            # vendors_list ሁሌም dict መሆኑን ማረጋገጥ
            if not isinstance(loaded_db.get('vendors_list'), dict):
                loaded_db['vendors_list'] = {}
                
            return loaded_db
            
        return default_db
    except Exception as e:
        print(f"❌ Database Load Error: {e}")
        return default_db


        # Error ቢመጣ እንኳን ቦቱ እንዳይቆም መሠረታዊ መዋቅሩን እንላክ
        return {
            "riders_list": {}, 
            "vendors_list": {}, 
            "orders": {}, 
            "categories": [], 
            "settings": {"vendor_commission_p": 10, "rider_fixed_fee": 30, "customer_service_fee": 15}
        }

def save_data(db):
    try:
        # ዳታውን ወደ Redis መላኪያ
        redis.set("bdf_delivery_db", json.dumps(db))
    except Exception as e:
        print(f"❌ Database Save Error: {e}")

# --- አዲሱ ክፍል እዚህ ጋር ይግባ ---
def notify_admins(text, reply_markup=None):
    """ለአድሚኖች መልዕክት እና በተኖችን መላኪያ"""
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                admin_id, 
                f"📢 **የBDF ኦፕሬሽን ማሳሰቢያ**\n\n{text}", 
                parse_mode="Markdown",
                reply_markup=reply_markup  # ✅ አዲሱ ጭማሪ እዚህ ነው
            )
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

def get_admin_dashboard(user_id):
    db = load_data()
    markup = types.InlineKeyboardMarkup(row_width=2)

    # --- በተኖቹን መፍጠር ---
    btn_dispute = types.InlineKeyboardButton("💬 ቅሬታዎች", callback_data="admin_disputes")
    btn_reviews = types.InlineKeyboardButton("⭐ ግምገማዎች", callback_data="admin_reviews")
    btn_broadcast = types.InlineKeyboardButton("📢 ማስታወቂያ", callback_data="admin_broadcast")
    
    btn_fund = types.InlineKeyboardButton("💳 ብር መሙያ", callback_data="admin_add_funds")
    btn_balance = types.InlineKeyboardButton("📉 ክትትል", callback_data="admin_monitor_balance")
    btn_profit = types.InlineKeyboardButton("💰 ትርፍ", callback_data="admin_profit_track")
    btn_low_credit = types.InlineKeyboardButton("⚠️ ዝቅተኛ ሂሳብ", callback_data="admin_low_credit")
    
    btn_live_orders = types.InlineKeyboardButton("📋 ቀጥታ ትዕዛዝ", callback_data="admin_live_orders")
    btn_pending = types.InlineKeyboardButton("📦 በመጠባበቅ", callback_data="admin_pending_approvals")
    btn_add_vendor = types.InlineKeyboardButton("➕ አዲስ ድርጅት", callback_data="admin_add_vendor")
    btn_add_rider = types.InlineKeyboardButton("➕ አዲስ driver", callback_data="admin_add_rider")
    btn_vendors = types.InlineKeyboardButton("🏢 ድርጅቶች", callback_data="admin_list_vendors")
    btn_view_cats = types.InlineKeyboardButton("📁 ምድቦች ማሳያ", callback_data="admin_view_categories")
    btn_add_cats = types.InlineKeyboardButton("➕ አዲስ ምድብ", callback_data="admin_manage_cats")
    btn_riders = types.InlineKeyboardButton("🛵 driver", callback_data="admin_rider_status")
    btn_set_commission = types.InlineKeyboardButton("⚙️ ኮሚሽን", callback_data="admin_set_commission")
    btn_block = types.InlineKeyboardButton("🚫 አግድ/ፍቀድ", callback_data="admin_block_manager")
    btn_lock = types.InlineKeyboardButton("🔒 ሲስተም ዝጋ", callback_data="admin_system_lock")
    btn_stats = types.InlineKeyboardButton("📈 ሪፖርት", callback_data="admin_full_stats")

    # --- ወደ Markup መጨመር (በሁለት ረድፍ) ---
    markup.add(btn_dispute, btn_reviews)
    markup.add(btn_broadcast) # ይህ ለብቻው ሰፋ ብሎ እንዲታይ (ወይም ከፈለግክ ሌላ ጨምርበት)
    
    markup.add(btn_fund, btn_balance)
    markup.add(btn_profit, btn_low_credit)
    
    markup.add(btn_live_orders, btn_pending)
    markup.add(btn_view_cats, btn_add_cats) 
    markup.add(btn_stats) 
    
    markup.add(btn_add_vendor, btn_add_rider)
    markup.add(btn_vendors, btn_riders)
    markup.add(btn_set_commission, btn_block)
    markup.add(btn_lock) # መዝጊያው ለብቻው ሰፋ ብሎ ለጥንቃቄ

    # --- ስዊች በተን (Switch Mode) ---
    uid_str = str(user_id)
    riders = db.get('riders_list', {})
    if uid_str in riders:
        btn_switch = types.InlineKeyboardButton("🔄 ወደ driver ቀይር (Rider Mode)", callback_data="switch_to_rider")
        markup.add(btn_switch)

    return markup


def get_vendor_dashboard(vendor_id):
    # መጀመሪያ ዳታቤዙን እናነባለን
    db = load_data()
    v_id_str = str(vendor_id)
    
    # የድርጅቱን መረጃ እናገኛለን፣ ከሌለ default True (ክፍት) እንሰጠዋለን
    vendor_info = db.get('vendors_list', {}).get(v_id_str, {})
    is_open = vendor_info.get('is_open', True) 
    
    markup = types.InlineKeyboardMarkup(row_width=2)

    # 🟢/🔴 የሁኔታ መግለጫ በተን (Toggle Button)
    status_text = "🟢 ክፍት ነኝ (Open)" if is_open else "🔴 ዝግ ነኝ (Closed)"
    btn_status = types.InlineKeyboardButton(status_text, callback_data="vendor_toggle_status")
    
    btn_add_item = types.InlineKeyboardButton("➕ አዲስ ዕቃ ጨምር", callback_data="vendor_add_item")
    btn_my_items = types.InlineKeyboardButton("📦 የኔ ዕቃዎች", callback_data="vendor_list_items")
    btn_orders = types.InlineKeyboardButton("📋 ትዕዛዞች", callback_data="vendor_view_orders")
    btn_wallet = types.InlineKeyboardButton("💰 ዋሌት", callback_data="vendor_wallet")
    btn_profile = types.InlineKeyboardButton("🏢 የድርጅት መረጃ", callback_data="vendor_profile")

    # አደራጃጀቱ፦ መጀመሪያ ሁኔታው ለብቻው፣ ቀጥሎ ሌሎቹ
    markup.add(btn_status)
    markup.add(btn_add_item, btn_my_items)
    markup.add(btn_orders, btn_wallet)
    markup.add(btn_profile)

    return markup


def get_customer_dashboard():
    # ከታች የሚቀመጡ ዋና ዋና በተኖች
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_order = types.KeyboardButton("🛍 ዕቃዎችን እዘዝ")
    btn_cart = types.KeyboardButton("🛒 የእኔ ቅርጫት")
    btn_history = types.KeyboardButton("📋 የትዕዛዝ ታሪክ")
    btn_profile = types.KeyboardButton("👤 መገለጫዬ/Profile")
    btn_support = types.KeyboardButton("📞 ድጋፍ")
    
    markup.add(btn_order)
    markup.add(btn_cart, btn_history)
    markup.add(btn_profile, btn_support)
    return markup

def get_rider_dashboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_orders = types.KeyboardButton("🛵 አዲስ ትዕዛዞች")
    btn_tasks = types.KeyboardButton("📋 የዛሬ ስራዎቼ")
    btn_earnings = types.KeyboardButton("💰 ገቢ")
    btn_status = types.KeyboardButton("🟢 ሁኔታዬ (Online/Offline)")
    
    markup.add(btn_orders)
    markup.add(btn_tasks, btn_earnings)
    markup.add(btn_status)
    return markup


# 1. መጀመሪያ ይህ መኖሩን አረጋግጥ
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🏢 አጋር ድርጅቶች", "📦 ትዕዛዞች", "📊 ሪፖርት", "⚙️ ሲስተም")
    return markup


def show_rider_menu(message):
    user_id = str(message.from_user.id)
    db = load_data()
    rider_info = db.get('riders_list', {}).get(user_id, {})
    
    # የደላላው ሁኔታ (Online/Offline)
    status_icon = "🟢" if rider_info.get('status') == "Active" else "🔴"
    rider_name = rider_info.get('name', "ደላላ")

    welcome_msg = (f"👋 ሰላም {rider_name}!\n"
                   f"የአሁኑ ሁኔታዎ፦ {status_icon} {rider_info.get('status', 'Active')}\n\n"
                   f"ከታች ያሉትን በተኖች በመጠቀም ስራዎችን ማስተዳደር ይችላሉ።")

    # get_rider_dashboard() ቀደም ብለን የሰራነው ነው
    bot.send_message(message.chat.id, welcome_msg, reply_markup=get_rider_dashboard())


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
            # እዚህ ጋር ስሙን 'get_vendor_dashboard' አድርገው
            return bot.send_message(user_id, f"እንኳን ደህና መጡ **{v_name}** 👋", 
                                   reply_markup=get_vendor_dashboard(uid_str), parse_mode="Markdown")

        # 3. drivers
        if uid_str in db.get('riders_list', {}):
            return show_rider_menu(message)

                    # ... (የአድሚን እና የቬንደር ቼክ እንደተጠበቀ ሆኖ) ...

    # 4. ለደንበኞች (ከላይ ያሉት ካልሆኑ እንደ ደንበኛ ይታያሉ)
        customers = db.get('customers', {})

        if user_id not in customers:
            # ገና ያልተመዘገበ አዲስ ደንበኛ
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add(types.KeyboardButton("📲 ስልክ ቁጥርዎን ያጋሩ", request_contact=True))
            
            welcome_text = (f"እንኳን ወደ **BDF Delivery** በደህና መጡ {message.from_user.first_name}! 👋\n\n"
                            f"ትዕዛዝ ለመጀመር መጀመሪያ ስልክ ቁጥርዎን ማጋራት አለብዎት።")
            bot.send_message(user_id, welcome_text, reply_markup=markup, parse_mode="Markdown")
        else:
            # ቀድሞ የተመዘገበ ደንበኛ
            welcome_text = f"እንኳን ደህና መጡ {message.from_user.first_name}! 👋\n\nምን ማዘዝ ይፈልጋሉ?"
            bot.send_message(user_id, welcome_text, reply_markup=get_customer_dashboard(), parse_mode="Markdown")

    except Exception as e:
        # ይህ ካልነበረ ነው ስህተት የሚሰጠው
        print(f"❌ Start Error: {e}")
        bot.send_message(message.chat.id, "ይቅርታ፣ ስህተት ተፈጥሯል። እባክዎ ጥቂት ቆይተው ይሞክሩ።")

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


@bot.message_handler(commands=['reset_pending'])
def reset_pending_data(message):
    # አድሚን መሆንህን ቼክ ለማድረግ (አማራጭ)
    # if str(message.chat.id) != "የአንተ_ID": return
    
    try:
        db = load_data()
        db['pending_items'] = {} 
        save_data(db)
        bot.reply_to(message, "✅ የቆዩ እና የተበላሹ 'pending_items' ዳታዎች በሙሉ ጸድተዋል! አሁን አዲስ ዕቃ መመዝገብ ትችላለህ።")
    except Exception as e:
        bot.reply_to(message, f"❌ ስህተት፦ {str(e)}")


@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def interrupt_handler(message):
    # ማንኛውም ኮማንድ ሲመጣ የቆየውን Next Step ይሰርዛል
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    
    # ከዚያ ወደ ትክክለኛው ኮማንድ ይልከዋል
    if message.text == '/start':
        start_command(message)
    elif message.text == '/admin':
        show_admin_panel(message)


@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def interrupt_handler(message):
    # ማንኛውም ኮማንድ ሲመጣ የቆየውን Next Step ይሰርዛል
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    
    # ከዚያ ወደ ትክክለኛው ኮማንድ ይልከዋል
    if message.text == '/start':
        start_command(message)
    elif message.text == '/admin':
        show_admin_panel(message)



@bot.callback_query_handler(func=lambda call: call.data.startswith(('admin_', 'switch_', 'approve_', 'reject_')))
def central_admin_handler(call):
    # 🔍 ይሄ ነው Debugging ኮዱ! 
    print(f"🔔 DEBUG: የተቀበለው ዳታ -> {call.data}")
    
    user_id = call.from_user.id
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    # ማንኛውንም የቆየ ግቤት (input) ያጸዳል
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)

    # 1. የስዊች ሎጂክ
    if call.data == "switch_to_rider":
        db = load_data()
        # አድሚኑ እንደ ደላላ መመዝገቡን እናረጋግጣለን
        if str(user_id) in db.get('riders_list', {}):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            show_rider_menu(call.message) # የደላላውን ሜኑ ይጠራል
        else:
            bot.answer_callback_query(call.id, "❌ ይቅርታ፣ እርስዎ እንደ ደላላ አልተመዘገቡም። መጀመሪያ 'አዲስ driver' በሚለው ይመዝገቡ።", show_alert=True)

    elif call.data == "switch_to_admin":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "👑 BDF አድሚን ዳሽቦርድ", reply_markup=get_admin_dashboard(user_id))
    

    # 2. የሪፖርትና መረጃ ማሳያ (ቀጥታ የሚሰሩ)
    elif call.data == "admin_full_stats":
        show_full_stats_logic(call.message)
        
    elif call.data == "admin_list_vendors":
        show_vendors_list_logic(call.message)
        
    elif call.data == "admin_live_orders":
        view_live_orders(call.message)
        
    elif call.data == "admin_monitor_balance":
        view_all_balances(call.message)
        
    elif call.data == "admin_rider_status":
        show_riders_report_logic(call.message) # ዋሌት ያለበት ሪፖርት
        
    elif call.data == "admin_disputes":
        view_disputes(call)
        
    elif call.data == "admin_reviews":
        view_reviews(call)
    
    elif call.data == "admin_view_categories":
        show_admin_categories(call.message)

    elif call.data == "admin_profit_track":
        view_total_profit(call)

    # 3. የአጽድቅ/ሰርዝ ሎጂክ (ስህተቱ የነበረበት ቦታ)
    elif call.data.startswith("approve_item_"):
        try:
            item_id = call.data.split("_")[-1]
            # ወደ ትክክለኛው approve_item ፈንክሽን እንልከዋለን
            # እዚህ ጋር call-ን በቀጥታ ማለፍ ይቻላል
            approve_item(call) 
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}")

    elif call.data.startswith("reject_item_"):
        try:
            item_id = call.data.split("_")[-1]
            # ውድቅ የማድረጊያ ሎጂክ
            db = load_data()
            if item_id in db.get('pending_items', {}):
                db['pending_items'].pop(item_id)
                save_data(db)
                bot.edit_message_caption("❌ ውድቅ ተደርጓል!", call.message.chat.id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "ዕቃው አልተገኘም")
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}")

    elif call.data == "admin_set_commission":
        start_commission_setting(call) # አዲሱን ሰንሰለት ይጀምራል

    elif call.data == "admin_low_credit":
        view_low_balances(call)
        
    elif call.data == "admin_pending_approvals":
        view_pending_items(call)

    # 3. ግቤት (Input/Next Step) የሚፈልጉ ስራዎች
    elif call.data == "admin_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 ማስታወቂያውን ይጻፉ (ለመሰረዝ /start ይበሉ)፦")
        bot.register_next_step_handler(msg, send_broadcast_logic)

    elif call.data == "admin_add_funds":
        # እዚህ ጋር ያሉት መስመሮች እኩል መግባት አለባቸው
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🏢 ለድርጅት", callback_data="add_fund_vendor"))
        markup.add(types.InlineKeyboardButton("➖ driver ዋሌት ቀንሥ", callback_data="admin_deduct_rider_wallet"))
        markup.add(types.InlineKeyboardButton("🛵 driver", callback_data="add_fund_rider"))
        bot.send_message(call.message.chat.id, "የማንን ሂሳብ መሙላት ይፈልጋሉ?", reply_markup=markup)

    elif call.data == "admin_add_vendor":
        msg = bot.send_message(call.message.chat.id, "➕ የአዲሱን ድርጅት ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, process_v_name)
        
    elif call.data == "admin_add_rider":
        msg = bot.send_message(call.message.chat.id, "🛵 የአዲሱን driver ሙሉ ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, process_rider_name)
        
    # 1. ያሉትን ምድቦች ለማየት
    elif call.data == "admin_view_categories":
        show_admin_categories(call.message)

    # 2. አዲስ ምድብ ለመጨመር
    elif call.data == "admin_manage_cats":
        msg = bot.send_message(call.message.chat.id, "📁 የአዲሱን ምድብ (Category) ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, add_category_logic)

        
    elif call.data == "admin_set_commission":
        msg = bot.send_message(call.message.chat.id, "🏢 **የሻጭ (Vendor) ኮሚሽን** በፐርሰንት ያስገቡ (ለምሳሌ 5 ወይም 10)፦")
        # ስሙን ከታች ካለው ፈንክሽን ጋር እናዛምደው
        bot.register_next_step_handler(msg, process_vendor_comm_step) 
        
    elif call.data == "admin_block_manager":
        msg = bot.send_message(call.message.chat.id, "🚫 ለማገድ/ለመፍቀድ የፈለጉትን User ID ያስገቡ፦")
        bot.register_next_step_handler(msg, process_block_logic)

    elif call.data == "admin_deduct_rider_wallet":
        msg = bot.send_message(call.message.chat.id, "🆔 ብር የሚቀነስለትን **ደላላ ID** ያስገቡ (ለምሳሌ፦ 8488592165)፦")
        bot.register_next_step_handler(msg, process_rider_deduct_id)


    # 4. ሲስተም ነክ
    elif call.data == "admin_system_lock":
        toggle_system_lock_logic(call.message)

    bot.answer_callback_query(call.id)



@bot.callback_query_handler(func=lambda call: call.data.startswith('v_accept_'))
def vendor_accept_order(call):
    # ውሂቡን መበለጥ (v_accept_{order_id}_{user_id})
    data = call.data.split('_')
    order_id = data
    user_id = data
    
    db = load_data()
    order = db.get('orders', {}).get(order_id)
    
    if not order:
        return bot.answer_callback_query(call.id, "ትዕዛዙ አልተገኘም!")

    # 1. የትዕዛዙን ሁኔታ መቀየር
    db['orders'][order_id]['status'] = "Accepted by Vendor"
    save_data(db)

    # 2. ለሻጩ ማረጋገጫ መስጠት (በፎቶው ላይ እንዳለው)
    bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ተቀብለዋል። እቃውን ማዘጋጀት ይጀምሩ።", 
                          call.message.chat.id, call.message.message_id)

    # 3. ለሁሉም ደላላዎች (Drivers) ማሳወቂያ መላክ (ዋናው ክፍል ይህ ነው!)
    notify_drivers_about_new_order(order_id, order)



@bot.callback_query_handler(func=lambda call: call.data.startswith('vendor_'))
def central_vendor_handler(call):
    # ማንኛውንም የቆየ ስራ ያጸዳል
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)

    if call.data == "vendor_add_item":
        msg = bot.send_message(call.message.chat.id, "📝 የዕቃውን **ስም** ያስገቡ (ለምሳሌ፦ በርገር)፦")
        bot.register_next_step_handler(msg, process_item_name)

    elif call.data == "vendor_wallet":
        db = load_data()
        v_id = str(call.from_user.id)
        vendor = db['vendors_list'].get(v_id, {})

        balance = vendor.get('balance', 0)
        total_sold = vendor.get('total_sold', 0)
        commission_rate = db['settings'].get('vendor_commission_p', 10)

        wallet_text = (f"💰 **የድርጅትዎ የሂሳብ መዝገብ**\n\n"
                       f"💵 ቀሪ ሂሳብ፦ `{balance} ETB`\n"
                       f"📊 አጠቃላይ ሽያጭ፦ `{total_sold} ETB`\n"
                       f"⚙️ ኮሚሽን፦ `{commission_rate}%` ")
        bot.send_message(call.message.chat.id, wallet_text, parse_mode="Markdown")

    elif call.data == "vendor_list_items":
        bot.answer_callback_query(call.id)
        show_my_items(call.message)

    elif call.data.startswith(('edit_item_', 'delete_item_', 'confirm_del_')):
        handle_item_management(call)


    elif call.data == "vendor_profile":
        db = load_data()
        v_id = str(call.from_user.id)
        v_info = db['vendors_list'].get(v_id, {})
        
        # የRating መረጃን ከዳታቤዝ እናምጣ (ከሌለ 0 ይሁን)
        rating = v_info.get('rating', 0.0)
        total_reviews = v_info.get('total_reviews', 0)
        
        # ለኮከብ ማሳያ (ለምሳሌ 4 ኮከብ ከሆነ ⭐⭐⭐⭐)
        star_icons = "⭐" * int(rating) if rating > 0 else "ገና አልተገመገመም"
        
        profile_text = (f"🏢 **የድርጅት መረጃ**\n\n"
                        f"📝 ስም፦ `{v_info.get('name', 'ያልተጠቀሰ')}`\n"
                        f"🆔 መለያ ቁጥር (ID)፦ `{v_id}`\n"
                        f"📍 ስልክ፦ `{v_info.get('phone', 'ያልተጠቀሰ')}`\n"
                        f"🌟 ደረጃ፦ {star_icons} `({rating})` \n"
                        f"👥 ጠቅላላ ግምገማ፦ `{total_reviews} ሰዎች` \n"
                        f"✅ ሁኔታ፦ `ንቁ (Active)`")
        
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, profile_text, parse_mode="Markdown")


    elif call.data == "vendor_view_orders":
        bot.send_message(call.message.chat.id, "📋 **የተላኩ ትዕዛዞች**\n\nአዲስ ትዕዛዝ ሲኖር እዚህ ጋር ይዘረዘራሉ...")

    elif call.data == "vendor_toggle_status":
        db = load_data()
        v_id = str(call.from_user.id)
        if v_id in db['vendors_list']:
            current_status = db['vendors_list'][v_id].get('is_open', True)
            new_status = not current_status
            db['vendors_list'][v_id]['is_open'] = new_status
            save_data(db)
            msg = "አሁን ክፍት ነዎት!" if new_status else "አሁን ዝግ ነዎት!"
            bot.answer_callback_query(call.id, msg, show_alert=True)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, 
                                          reply_markup=get_vendor_dashboard(v_id))


# ይህንን central_admin_handler ባለበት ወይም አዲስ Callback Handler ጋር ጨምረው
@bot.callback_query_handler(func=lambda call: call.data.startswith(('edit_item_', 'delete_item_', 'confirm_del_')))
def handle_item_management(call):
    db = load_data()
    user_id = str(call.from_user.id)
    
    # ዳታውን በትክክል መበለት
    if call.data.startswith("edit_item_"):
        item_id = call.data.replace("edit_item_", "")
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🔢 አዲሱን ዋጋ ያስገቡ (ለምሳሌ፦ 250)፦")
        bot.register_next_step_handler(msg, update_item_price_logic, item_id)

    elif call.data.startswith("delete_item_"):
        item_id = call.data.replace("delete_item_", "")
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ አዎ አጥፋው", callback_data=f"confirm_del_{item_id}"),
            types.InlineKeyboardButton("❌ ተመለስ", callback_data="vendor_list_items")
        )
        bot.answer_callback_query(call.id)
        try:
            bot.edit_message_caption("⚠️ ይህንን ዕቃ ለመሰረዝ እርግጠኛ ነዎት?", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except:
            bot.edit_message_text("⚠️ ይህንን ዕቃ ለመሰረዝ እርግጠኛ ነዎት?", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("confirm_del_"):
        item_id = call.data.replace("confirm_del_", "")
        if user_id in db['vendors_list'] and item_id in db['vendors_list'][user_id]['items']:
            del db['vendors_list'][user_id]['items'][item_id]
            save_data(db)
            bot.answer_callback_query(call.id, "✅ ዕቃው ተሰርዟል!", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ ዕቃው አልተገኘም!", show_alert=True)





@bot.callback_query_handler(func=lambda call: call.data.startswith('usercat_'))
def show_items_by_category(call):
    category_name = call.data.replace("usercat_", "")
    db = load_data()
    vendors = db.get('vendors_list', {})
    
    found_items = []
    
    # በሁሉም ድርጅቶች ውስጥ ያሉትን ዕቃዎች መፈተሽ
    for v_id, v_data in vendors.items():
        # ድርጅቱ ዝግ ካልሆነ ብቻ ዕቃዎችን አሳይ
        if v_data.get('is_open', True):
            items = v_data.get('items', {})
            for i_id, i_data in items.items():
                if i_data.get('category') == category_name:
                    # የድርጅቱን ስም ጭምር ለዕቃው ዳታ እንጨምርበታለን
                    i_data['vendor_id'] = v_id
                    i_data['vendor_name'] = v_data.get('name')
                    i_data['item_id'] = i_id
                    found_items.append(i_data)

    if not found_items:
        return bot.answer_callback_query(call.id, f"⚠️ በ '{category_name}' ምድብ ውስጥ አሁን ላይ የሚገኙ ዕቃዎች የሉም።", show_alert=True)

    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"📦 **በ '{category_name}' ምድብ የተገኙ ዕቃዎች፦**")

    for item in found_items:
        text = (f"🍎 **ዕቃ፦** {item['name']}\n"
                f"🏢 **ድርጅት፦** {item['vendor_name']}\n"
                f"💰 **ዋጋ፦** {item['price']} ETB\n"
                f"━━━━━━━━━━━━━━━")
        
        markup = types.InlineKeyboardMarkup()
        # ወደ ቅርጫት መጨመሪያ በተን
        markup.add(types.InlineKeyboardButton("🛒 ወደ ቅርጫት ጨምር", callback_data=f"addcart_{item['item_id']}_{item['vendor_id']}"))
        
        if item.get('photo'):
            bot.send_photo(call.message.chat.id, item['photo'], caption=text, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")







@bot.callback_query_handler(func=lambda call: call.data.startswith('r_take_'))
def rider_take_order(call):
    order_id = call.data.replace("r_take_", "")
    rider_id = str(call.from_user.id)
    db = load_data()
    
    # ትዕዛዙ በዳታቤዝ ውስጥ መኖሩን ማረጋገጥ
    if order_id not in db.get('orders', {}):
        return bot.answer_callback_query(call.id, "⚠️ ይቅርታ፣ ይህ ትዕዛዝ አልተገኘም!", show_alert=True)
    
    order_data = db['orders'][order_id]
    
    # ትዕዛዙ አስቀድሞ ተወስዶ ከሆነ መፈተሽ
    if order_data.get('rider_id'):
        return bot.answer_callback_query(call.id, "⚠️ ይህ ትዕዛዝ በሌላ ደላላ ተወስዷል!", show_alert=True)

    # ትዕዛዙን ለደላላው መመደብ
    db['orders'][order_id]['rider_id'] = rider_id
    db['orders'][order_id]['status'] = "Rider Assigned (ደላላ ተመድቧል)"
    save_data(db)

    # 1. ለደላላው ማረጋገጫ መስጠት
    bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ተረክበዋል። መልካም ስራ!", 
                          call.message.chat.id, call.message.message_id)
    
    # 2. ለደላላው የደንበኛውን መረጃ መላክ
    customer_id = order_data['user_id']
    address = order_data['address']
    
    details = (f"📍 **የማድረሻ ዝርዝር (# {order_id})**\n"
               f"━━━━━━━━━━━━━━\n"
               f"👤 **ደንበኛ፦** {customer_id}\n"
               f"🗺 **አድራሻ፦** {address}\n"
               f"━━━━━━━━━━━━━━")
    
    # ሁኔታውን ለማዘመን የሚሆኑ በተኖች
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📍 መነሻ ላይ ነኝ", callback_data=f"r_atvendor_{order_id}"))
    markup.add(types.InlineKeyboardButton("🚴 በመጓዝ ላይ", callback_data=f"r_ontheway_{order_id}"))
    markup.add(types.InlineKeyboardButton("✅ ደርሻለሁ (Delivered)", callback_data=f"r_delivered_{order_id}"))
    
    bot.send_message(rider_id, details, reply_markup=markup, parse_mode="Markdown")

    # 3. ለደንበኛው ማሳወቅ
    try:
        bot.send_message(customer_id, f"🛵 **ትዕዛዝዎ ተረክቧል!**\n\nደላላው {call.from_user.first_name} ትዕዛዝዎን ለማድረስ ጉዞ ጀምሯል።")
    except:
        pass





@bot.callback_query_handler(func=lambda call: call.data.startswith('r_delivered_'))
def rider_order_delivered(call):
    order_id = call.data.replace("r_delivered_", "")
    rider_id = str(call.from_user.id)
    db = load_data()
    
    if order_id not in db.get('orders', {}):
        return bot.answer_callback_query(call.id, "⚠️ ትዕዛዙ አልተገኘም!")

    order_data = db['orders'][order_id]
    
    # ትዕዛዙ ቀድሞ ተጠናቆ ከሆነ ለመፈተሽ
    if order_data.get('status') == "Completed":
        return bot.answer_callback_query(call.id, "✅ ይህ ትዕዛዝ አስቀድሞ ተጠናቋል!")

    # 1. የክፍያ ስሌት (ከቅድሙ ጋር ተመሳሳይ መሆን አለበት)
    # ማሳሰቢያ፡ እዚህ ጋር ርቀቱ አስቀድሞ ተሰልቶ በ order_data ውስጥ ቢቀመጥ ይመረጣል
    # ለጊዜው በቤዝ ፊው እናሰላው (ወይም በ order_data ውስጥ የተቀመጠ ካለ እሱን እንውሰድ)
    
    delivery_fee = order_data.get('delivery_fee', 50) # ትዕዛዙ ሲፈጠር የተቀመጠ ዋጋ ካለ
    rider_share = delivery_fee * 0.8 # 80% ለደላላው
    
    # 2. የደላላውን ገቢ ማሳደግ
    if 'riders_list' in db and rider_id in db['riders_list']:
        if 'earnings' not in db['riders_list'][rider_id]:
            db['riders_list'][rider_id]['earnings'] = 0
        
        db['riders_list'][rider_id]['earnings'] += rider_share
        db['riders_list'][rider_id]['total_deliveries'] = db['riders_list'][rider_id].get('total_deliveries', 0) + 1
    
    # 3. የትዕዛዝ ሁኔታን መቀየር
    db['orders'][order_id]['status'] = "Completed"
    db['orders'][order_id]['completed_at'] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    save_data(db)

    # 4. ለደላላው መልዕክት መላክ
    bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} በተሳካ ሁኔታ ደርሷል!\n💰 ገቢዎ፦ {rider_share} ETB በሂሳብዎ ላይ ተደምሯል።", 
                          call.message.chat.id, call.message.message_id)

    # 5. ለደንበኛው ማሳወቅ
    customer_id = order_data['user_id']
    try:
        completion_text = (f"🥳 **ትዕዛዝዎ ደርሷል!**\n\n"
                           f"ጥቅሉን ስለተቀበሉ እናመሰግናለን። በB.D.F Delivery አገልግሎት እንደተደሰቱ ተስፋ እናደርጋለን! 🙏")
        bot.send_message(customer_id, completion_text, parse_mode="Markdown")
    except:
        pass

    # 6. ለአድሚን ማሳወቅ (አማራጭ)
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"📢 **ትዕዛዝ ተጠናቀቀ!**\n🆔 #{order_id}\n🛵 ደላላ፦ {call.from_user.first_name}\n💵 ለደላላ የተከፈለ፦ {rider_share} ETB")
        except:
            pass






@bot.callback_query_handler(func=lambda call: call.data.startswith('addcart_'))
def add_to_cart_logic(call):
    # ዳታውን መበተን (item_id እና vendor_id)
    _, item_id, v_id = call.data.split('_')
    user_id = str(call.from_user.id)
    
    db = load_data()
    if 'carts' not in db: db['carts'] = {}
    if user_id not in db['carts']: db['carts'][user_id] = {}

    # ዕቃው ቀድሞ ቅርጫት ውስጥ ካለ ብዛቱን በ 1 ይጨምራል
    if item_id in db['carts'][user_id]:
        db['carts'][user_id][item_id]['qty'] += 1
    else:
        # አዲስ ከሆነ መረጃውን ይጨምራል
        vendor_items = db.get('vendors_list', {}).get(v_id, {}).get('items', {})
        item_info = vendor_items.get(item_id)
        
        if item_info:
            db['carts'][user_id][item_id] = {
                "name": item_info['name'],
                "price": item_info['price'],
                "vendor_id": v_id,
                "qty": 1
            }
        else:
            return bot.answer_callback_query(call.id, "⚠️ ይቅርታ ዕቃው አልተገኘም!", show_alert=True)

    save_data(db)
    bot.answer_callback_query(call.id, f"✅ {db['carts'][user_id][item_id]['name']} ወደ ቅርጫት ተጨምሯል!", show_alert=False)




@bot.callback_query_handler(func=lambda call: call.data.startswith('cartrem_'))
def remove_from_cart(call):
    item_id = call.data.replace("cartrem_", "")
    user_id = str(call.from_user.id)
    db = load_data()

    if user_id in db.get('carts', {}) and item_id in db['carts'][user_id]:
        if db['carts'][user_id][item_id]['qty'] > 1:
            db['carts'][user_id][item_id]['qty'] -= 1
        else:
            del db['carts'][user_id][item_id]
        
        save_data(db)
        bot.answer_callback_query(call.id, "ተቀንሷል!")
        # ቅርጫቱን በሪል ታይም አድስልኝ
        show_my_cart(call.message) 
    else:
        bot.answer_callback_query(call.id, "ዕቃው አልተገኘም!")





@bot.callback_query_handler(func=lambda call: call.data == "cart_checkout")
def start_checkout(call):
    user_id = str(call.from_user.id)
    db = load_data()
    user_cart = db.get('carts', {}).get(user_id, {})

    if not user_cart:
        return bot.answer_callback_query(call.id, "🛒 ቅርጫትዎ ባዶ ነው!", show_alert=True)

    # አድራሻ እንዲልክ መጠየቅ (በተን በመጠቀም)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    location_btn = types.KeyboardButton("📍 ያለሁበትን ቦታ ላክ (Send Location)", request_location=True)
    cancel_btn = types.KeyboardButton("❌ ተመለስ")
    markup.add(location_btn)
    markup.add(cancel_btn)

    msg = bot.send_message(call.message.chat.id, 
                     "🛵 **ትዕዛዙ እንዲደርሶት ያለሁበትን ቦታ ላክ የሚለውን በተን ይጫኑ ወይም በፅሁፍ አድራሻዎን ይላኩ፦**", 
                     reply_markup=markup, parse_mode="Markdown")
    
    # ደንበኛው የሚልከውን አድራሻ ለመቀበል 'register_next_step_handler' እንጠቀማለን
    bot.register_next_step_handler(msg, process_order_final)




@bot.callback_query_handler(func=lambda call: call.data.startswith('v_accept_'))
def vendor_accept_order(call):
    _, _, order_id, customer_id = call.data.split('_')
    
    # የትዕዛዙን ሁኔታ በዳታቤዝ መቀየር
    db = load_data()
    if order_id in db.get('orders', {}):
        db['orders'][order_id]['status'] = "Accepted (በዝግጅት ላይ)"
        save_data(db)
        
        # 1. ለሻጩ ማረጋገጫ
        bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ተቀብለዋል። እባክዎ ማዘጋጀት ይጀምሩ።", 
                              call.message.chat.id, call.message.message_id)
        
        # 2. ለደንበኛው ማሳወቅ
        try:
            bot.send_message(customer_id, f"🔔 **መልካም ዜና!**\n\nትዕዛዝ ቁጥር `#{order_id}` በሻጩ ተቀባይነት አግኝቷል። አሁን በዝግጅት ላይ ነው።")
        except:
            pass
    else:
        bot.answer_callback_query(call.id, "⚠️ ትዕዛዙ አልተገኘም!")





# --- 1. የደላላው ማዕከላዊ ትራፊክ (Callback Handler) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('rider_'))
def central_rider_handler(call):
    uid = str(call.from_user.id)
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)

    if call.data == "rider_toggle_status":
        toggle_rider_status(call)

    elif call.data == "rider_wallet":
        show_rider_wallet(call)

    # ✅ ስሙን አስተካክለነዋል - start_withdraw_flow መባል አለበት
    elif call.data == "rider_withdraw_request":
        start_withdraw_flow(call)

    elif call.data == "rider_view_orders":
        show_available_orders(call)

    elif call.data == "rider_history":
        show_rider_history(call)

    try:
        bot.answer_callback_query(call.id)
    except:
        pass


# --- 2. የደላላው ሁኔታ (Online/Offline) መቀያየሪያ ---
def toggle_rider_status(call):
    db = load_data()
    uid = str(call.from_user.id)
    
    current = db['riders_list'][uid].get('is_online', False)
    db['riders_list'][uid]['is_online'] = not current
    save_data(db)
    
    # በተኖቹን በለውጡ መሰረት ያድሳል
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, 
                                 reply_markup=get_rider_markup(uid, db))
    
    status_msg = "አሁን ኦንላይን ነዎት 🟢" if not current else "አሁን ኦፍላይን ነዎት 🔴"
    bot.answer_callback_query(call.id, status_msg)

# --- 3. የዋሌት ማሳያ ሎጂክ ---
def show_rider_wallet(call):
    db = load_data()
    uid = str(call.from_user.id)
    balance = db['riders_list'][uid].get('wallet', 0)

    markup = types.InlineKeyboardMarkup()
    if balance > 100:
        markup.add(types.InlineKeyboardButton("💸 ብር አውጣ (Withdraw)", callback_data="rider_withdraw_request"))

    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="rider_main"))

    text = (f"💰 **የእርስዎ ዋሌት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💵 ጠቅላላ ቀሪ ሂሳብ፦ **{balance:,.2f} ETB**\n\n"
            f"ብር ለማውጣት በዋሌትዎ ውስጥ ከ 100 ETB በላይ ሊኖርዎት ይገባል።")

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")
    
    # ❌ እዚህ ስር የነበረውን "ትዕዛዝ የለም" የሚለውን ሜሴጅ አጥፍተነዋል






# ስልክ ቁጥር ሲላክ
@bot.message_handler(content_types=['contact'])
def handle_customer_contact(message):
    user_id = str(message.from_user.id)
    db = load_data()
    
    if 'customers' not in db: db['customers'] = {}
    
    # ስልኩን መመዝገብ
    db['customers'][user_id] = {
        "phone": message.contact.phone_number,
        "name": message.from_user.first_name,
        "location": None
    }
    save_data(db)
    
    # ቀጥሎ ሎኬሽን ይጠይቃል
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("📍 አሁን ያሉበትን ቦታ ይላኩ", request_location=True))
    
    bot.send_message(message.chat.id, "✅ ስልክዎ ተመዝግቧል። አሁን ደግሞ እቃው የሚመጣበትን ቦታ (Location) ይላኩ፦", reply_markup=markup)

# ሎኬሽን ሲላክ
@bot.message_handler(content_types=['location'])
def handle_customer_location(message):
    user_id = str(message.from_user.id)
    db = load_data()
    
    if user_id in db.get('customers', {}):
        # ሎኬሽኑን ሴቭ ማድረግ
        db['customers'][user_id]['location'] = {
            "latitude": message.location.latitude,
            "longitude": message.location.longitude
        }
        save_data(db)
        
        # ምዝገባ ተጠናቀቀ - ወደ ዳሽቦርድ
        bot.send_message(message.chat.id, "🎉 ምዝገባዎ በተሳካ ሁኔታ ተጠናቋል!", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(message.chat.id, "አሁን ማዘዝ ይችላሉ፦", reply_markup=get_customer_dashboard())




@bot.message_handler(func=lambda message: message.text == "🛍 ዕቃዎችን እዘዝ")
def show_customer_categories(message):
    db = load_data()
    categories = db.get('categories', [])
    
    if not categories:
        return bot.send_message(message.chat.id, "⚠️ ይቅርታ፣ በአሁኑ ሰዓት ምንም አይነት የምድብ ዝርዝር የለም።")

    markup = types.InlineKeyboardMarkup(row_width=2)
    # እያንዳንዱን ምድብ ወደ Inline Button መቀየር
    for cat in categories:
        # 'cat_' የሚል ቅጥያ እንጠቀማለን በቀጣይ callback ላይ ለመለየት
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"usercat_{cat}"))
    
    bot.send_message(message.chat.id, "📁 **የሚፈልጉትን የምድብ አይነት ይምረጡ፦**", reply_markup=markup, parse_mode="HTML")





@bot.message_handler(func=lambda message: message.text == "📋 የትዕዛዝ ታሪክ")
def order_history(message):
    user_id = str(message.from_user.id)
    db = load_data()
    all_orders = db.get('orders', {})
    
    # የዚህን ደንበኛ ትዕዛዞች ብቻ መለየት
    user_orders = {o_id: o_data for o_id, o_data in all_orders.items() if str(o_data.get('user_id')) == user_id}
    
    if not user_orders:
        return bot.send_message(message.chat.id, "📭 እስካሁን ምንም ያዘዙት ትዕዛዝ የለም።")

    history_msg = "📜 **የቅርብ ጊዜ ትዕዛዞችዎ፦**\n\n"
    # የመጨረሻዎቹን 5 ትዕዛዞች ብቻ ለማሳየት
    for o_id in list(user_orders.keys())[-5:]:
        order = user_orders[o_id]
        status = order.get('status', 'በጥበቃ ላይ')
        total = order.get('total', 0)
        history_msg += f"🆔 `#{o_id}` | 💰 {total} ETB\n📊 **ሁኔታ፦** {status}\n────────────────\n"
        
    bot.send_message(message.chat.id, history_msg, parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "💰 ገቢ")
def show_rider_earnings(message):
    rider_id = str(message.from_user.id)
    db = load_data()
    
    # ደላላው በዝርዝሩ ውስጥ መኖሩን ማረጋገጥ
    rider_info = db.get('riders_list', {}).get(rider_id)
    
    if not rider_info:
        return bot.send_message(message.chat.id, "❌ ይቅርታ፣ እርስዎ እንደ ደላላ አልተመዘገቡም።")

    earnings = rider_info.get('earnings', 0)
    total_tasks = rider_info.get('total_deliveries', 0)
    
    text = (f"💰 **የእርስዎ የገቢ መግለጫ**\n"
            f"━━━━━━━━━━━━━━\n"
            f"💵 **ጠቅላላ ገቢ፦** {earnings} ETB\n"
            f"📦 **ያከናወኑት ስራ፦** {total_tasks} ትዕዛዞች\n"
            f"━━━━━━━━━━━━━━\n"
            f"<i>ማሳሰቢያ፦ ክፍያ የሚፈጸመው በአስተዳዳሪው በኩል ነው።</i>")
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(func=lambda message: message.text == "🟢 ሁኔታዬ (Online/Offline)")
def toggle_status(message):
    rider_id = str(message.from_user.id)
    db = load_data()
    
    if rider_id not in db.get('riders_list', {}):
        return
        
    current_status = db['riders_list'][rider_id].get('status', 'Active')
    
    if current_status == "Active":
        db['riders_list'][rider_id]['status'] = "Offline"
        new_status = "🔴 ከመስመር ውጭ (Offline)"
    else:
        db['riders_list'][rider_id]['status'] = "Active"
        new_status = "🟢 መስመር ላይ (Online)"
    
    save_data(db)
    bot.send_message(message.chat.id, f"የእርስዎ ሁኔታ ወደ {new_status} ተቀይሯል።")


@bot.message_handler(func=lambda message: message.text == "📋 የዛሬ ስራዎቼ")
def show_active_tasks(message):
    rider_id = str(message.from_user.id)
    db = load_data()
    orders = db.get('orders', {})
    
    active_tasks = []
    for o_id, o_data in orders.items():
        if str(o_data.get('rider_id')) == rider_id and o_data.get('status') != "Completed":
            active_tasks.append(f"🆔 #{o_id} - {o_data['status']}")
            
    if not active_tasks:
        return bot.send_message(message.chat.id, "📭 በአሁኑ ሰዓት የጀመሩት ስራ የለም።")
    
    text = "📋 **አሁን በእጅዎ ያሉ ስራዎች፦**\n\n" + "\n".join(active_tasks)
    bot.send_message(message.chat.id, text)




@bot.message_handler(func=lambda message: message.text == "🛵 አዲስ ትዕዛዞች")
def check_new_orders(message):
    db = load_data()
    orders = db.get('orders', {})
    
    # ገና ያልተያዙ ትዕዛዞች (Rider የሌላቸው)
    available_orders = [o_id for o_id, o_data in orders.items() if not o_data.get('rider_id') and o_data.get('status') == "Accepted by Vendor"]
    
    if not available_orders:
        return bot.send_message(message.chat.id, "😴 በአሁኑ ሰዓት አዲስ ትዕዛዝ የለም።")
    
    bot.send_message(message.chat.id, f"🔔 በአሁኑ ሰዓት {len(available_orders)} ትዕዛዞች አሉ። ማሳወቂያዎችን ይጠብቁ።")





@bot.message_handler(func=lambda message: message.text == "📞 ድጋፍ")
def support_handler(message):
    support_text = ("👋 **እንኳን ወደ ድጋፍ ሰጪ ማዕከል በደህና መጡ!**\n\n"
                    "ማንኛውም ጥያቄ ወይም ቅሬታ ካለዎት ከታች ይጻፉልን። "
                    "የእኛ ባለሙያዎች መልዕክትዎን አይተው ምላሽ ይሰጡዎታል።")
    
    msg = bot.send_message(message.chat.id, support_text)
    bot.register_next_step_handler(msg, forward_to_admin)

def forward_to_admin(message):
    if message.text in ["🛍 ዕቃዎችን እዘዝ", "🛒 የእኔ ቅርጫት", "📋 የትዕዛዝ ታሪክ", "👤 መገለጫዬ/Profile", "📞 ድጋፍ"]:
        return # ደንበኛው ሌላ በተን ከተጫነ ስራውን እንዲያቆም

    admin_msg = (f"⚠️ **አዲስ የድጋፍ ጥያቄ!**\n\n"
                 f"👤 ከ፦ {message.from_user.first_name} (`{message.from_user.id}`)\n"
                 f"💬 መልዕክት፦ {message.text}")
    
    # ለሁሉም አድሚኖች መላክ
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, admin_msg)
        except:
            pass
            
    bot.send_message(message.chat.id, "✅ መልዕክትዎ ደርሶናል። በቅርቡ ምላሽ እንሰጥዎታለን።")


@bot.message_handler(func=lambda message: message.text == "👤 መገለጫዬ/Profile")
def show_user_profile(message):
    user_id = str(message.from_user.id)
    db = load_data()
    
    # በዳታቤዝ ውስጥ የተጠቃሚውን መረጃ መፈለግ
    user_info = None
    if 'user_list' in db:
        # በሊስት ውስጥ ያለን ተጠቃሚ በ ID መፈለግ
        for user in db['user_list']:
            if str(user.get('id')) == user_id:
                user_info = user
                break
    
    # መሠረታዊ መረጃዎች ከቴሌግራም መገለጫ
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name if message.from_user.last_name else ""
    username = f"@{message.from_user.username}" if message.from_user.username else "የለዎትም"
    
    # በዳታቤዝ ውስጥ ስልክ ቁጥር ካለ
    phone = user_info.get('phone', "ያልተመዘገበ") if user_info else "ያልተመዘገበ"
    role = user_info.get('role', "ደንበኛ") if user_info else "ደንበኛ"

    profile_text = (
        f"👤 <b>የእርስዎ መገለጫ (Profile)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>ሙሉ ስም፦</b> {first_name} {last_name}\n"
        f"📞 <b>ስልክ ቁጥር፦</b> <code>{phone}</code>\n"
        f"🔗 <b>Username፦</b> {username}\n"
        f"🆔 <b>የእርስዎ ID፦</b> <code>{user_id}</code>\n"
        f"🎭 <b>የአካውንት አይነት፦</b> {role}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>መረጃዎን ለመቀየር ከታች ያለውን በተን ይጠቀሙ።</i>"
    )
    
    markup = types.InlineKeyboardMarkup()
    btn_update = types.InlineKeyboardButton("📱 ስልክ ቁጥር ቀይር/አድስ", callback_data="update_phone")
    markup.add(btn_update)
    
    bot.send_message(message.chat.id, profile_text, reply_markup=markup, parse_mode="HTML")




@bot.message_handler(func=lambda message: message.text == "🛒 የእኔ ቅርጫት")
def show_my_cart(message):
    user_id = str(message.from_user.id)
    db = load_data()
    user_cart = db.get('carts', {}).get(user_id, {})

    if not user_cart:
        return bot.send_message(message.chat.id, "🛒 ቅርጫትዎ ባዶ ነው! እባክዎ መጀመሪያ ዕቃ ይምረጡ።")

    cart_text = "🛒 **የእርስዎ ቅርጫት ዝርዝር፦**\n━━━━━━━━━━━━━━━\n"
    total_bill = 0
    markup = types.InlineKeyboardMarkup()

    for i_id, i_info in user_cart.items():
        sub_total = i_info['price'] * i_info['qty']
        total_bill += sub_total
        cart_text += f"🔹 **{i_info['name']}**\n   {i_info['qty']} x {i_info['price']} = `{sub_total} ETB`\n---\n"
        
        # ለእያንዳንዱ ዕቃ መቀነሻ እና ማጥፊያ በተን
        markup.add(
            types.InlineKeyboardButton(f"➖ {i_info['name']}", callback_data=f"cartrem_{i_id}"),
            types.InlineKeyboardButton(f"➕ {i_info['name']}", callback_data=f"addcart_{i_id}_{i_info['vendor_id']}")
        )

    # የሰርቪስ ክፍያ መጨመር
    service_fee = db.get('settings', {}).get('customer_service_fee', 15)
    total_bill += service_fee

    cart_text += f"\n⚙️ ሰርቪስ ክፍያ፦ `{service_fee} ETB`"
    cart_text += f"\n💰 **አጠቃላይ ድምር፦ `{total_bill} ETB`**"

    # ትዕዛዙን ማጠቃለያ በተን
    markup.add(types.InlineKeyboardButton("✅ ትዕዛዙን አረጋግጥ (Checkout)", callback_data="cart_checkout"))
    markup.add(types.InlineKeyboardButton("🗑 ቅርጫቱን አጽዳ", callback_data="cart_clear_all"))

    bot.send_message(message.chat.id, cart_text, reply_markup=markup, parse_mode="Markdown")






import random
import string

def process_order_final(message):
    if message.text == "❌ ተመለስ":
        return bot.send_message(message.chat.id, "ትዕዛዙ ተሰርዟል።", reply_markup=get_customer_dashboard())

    user_id = str(message.from_user.id)
    db = load_data()
    user_cart = db.get('carts', {}).get(user_id, {})
    
    if not user_cart:
        return bot.send_message(message.chat.id, "🛒 ቅርጫትዎ ባዶ ነው!")

    # ልዩ የትዕዛዝ መለያ ቁጥር ማመንጨት (Order ID)
    order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    # የአድራሻ መረጃ መያዝ
    address = ""
    if message.location:
        address = f"Lat: {message.location.latitude}, Long: {message.location.longitude} (📍 ሎኬሽን)"
    else:
        address = message.text

    # ትዕዛዙን በየድርጅቱ (Vendor) መከፋፈል
    vendors_to_notify = {}
    total_price = 0

    for i_id, i_info in user_cart.items():
        v_id = i_info['vendor_id']
        if v_id not in vendors_to_notify:
            vendors_to_notify[v_id] = []
        vendors_to_notify[v_id].append(f"• {i_info['name']} ({i_info['qty']} ፍሬ)")
        total_price += i_info['price'] * i_info['qty']

    # 1. ለሻጮቹ (Vendors) መረጃ መላክ (ከነ በተኑ)
    for v_id, items in vendors_to_notify.items():
        vendor_msg = (f"🔔 <b>አዲስ ትዕዛዝ መጥቷል!</b>\n\n"
                      f"🆔 ትዕዛዝ ቁጥር: #{order_id}\n"
                      f"📝 ዝርዝር:\n" + "\n".join(items) + "\n\n"
                      f"📍 አድራሻ: {address}\n"
                      f"📞 የደንበኛ ID: {user_id}")
        
        # የሻጭ መቀበያ በተኖች እዚህ ጋር መግባት አለባቸው
        markup = types.InlineKeyboardMarkup()
        accept_btn = types.InlineKeyboardButton("✅ ትዕዛዙን ተቀበል", callback_data=f"v_accept_{order_id}_{user_id}")
        reject_btn = types.InlineKeyboardButton("❌ ሰርዝ", callback_data=f"v_reject_{order_id}_{user_id}")
        markup.add(accept_btn, reject_btn)
        
        try:
            bot.send_message(v_id, vendor_msg, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            print(f"ለድርጅት {v_id} መላክ አልተቻለም: {e}")

    # 2. ትዕዛዙን በዳታቤዝ 'orders' ውስጥ መመዝገብ
    if 'orders' not in db: db['orders'] = {}
    db['orders'][order_id] = {
        "user_id": user_id,
        "items": user_cart,
        "address": address,
        "status": "Pending (በጥበቃ ላይ)",
        "total": total_price
    }
    
    # 3. የደንበኛውን ቅርጫት ማጽዳት
    db['carts'][user_id] = {}
    save_data(db)

    # 4. ለደንበኛው ማረጋገጫ መላክ
    bot.send_message(message.chat.id, 
                     f"🎉 **ትዕዛዝዎ በተሳካ ሁኔታ ተልኳል!**\n\n"
                     f"🆔 የትዕዛዝ ቁጥር፦ `#{order_id}`\n"
                     f"💰 አጠቃላይ ዋጋ፦ `{total_price} ETB` + ሰርቪስ\n"
                     f"⏳ ድርጅቱ ትዕዛዙን ሲቀበል እናሳውቅዎታለን።", 
                     reply_markup=get_customer_dashboard(), parse_mode="Markdown")




def show_available_orders(call):
    # እዚህ ጋር ትዕዛዝ ካለ በዝርዝር ታሳያለህ፣ ከሌለ ግን፡
    text = "📦 በአሁኑ ሰዓት በአቅራቢያዎ የሚገኙ አዳዲስ ትዕዛዞች የሉም።"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="rider_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


# --- 5. የሥራ ታሪክ ማሳያ ---
def show_rider_history(call):
    db = load_data()
    uid = str(call.from_user.id)
    
    # ዳታው መኖሩን ቼክ እናድርግ (ለጥንቃቄ)
    rider_data = db.get('riders_list', {}).get(uid, {})
    deliveries = rider_data.get('total_deliveries', 0)
    
    # መነሻውን 0.0 እናድርገው
    rating = rider_data.get('rating', 0.0) 
    
    text = (f"📜 **የእርስዎ የሥራ ታሪክ**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✅ በስኬት ያደረሷቸው ትዕዛዞች፦ **{deliveries}**\n"
            f"⭐ አጠቃላይ ደረጃዎ፦ {rating:.1f}") # .1f ለአንድ ዲጂታል ነጥብ (ለምሳሌ 4.5)
            
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

# --- 6. የደላላው በተኖች ማደሻ (Helper) ---
def get_rider_markup(uid, db):
    rider_data = db['riders_list'].get(uid, {})
    status_icon = "🟢" if rider_data.get('is_online') else "🔴"
    status_text = "ኦንላይን" if rider_data.get('is_online') else "ኦፍላይን"
    wallet = rider_data.get('wallet', 0)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton(f"ሁኔታ፦ {status_icon} {status_text}", callback_data="rider_toggle_status"))
    markup.add(
        types.InlineKeyboardButton("📦 አዲስ ትዕዛዞች", callback_data="rider_view_orders"),
        types.InlineKeyboardButton(f"💰 ዋሌት ({wallet} ETB)", callback_data="rider_wallet")
    )
    markup.add(types.InlineKeyboardButton("📜 የታሪክ ማህደር", callback_data="rider_history"))
    markup.add(types.InlineKeyboardButton("👑 ወደ አድሚን ተመለስ", callback_data="switch_to_admin"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data == "rider_withdraw_request")
def start_withdraw_flow(call):
    uid = str(call.from_user.id)
    db = load_data()
    balance = db['riders_list'][uid].get('wallet', 0)
    
    if balance <= 100:
        return bot.answer_callback_query(call.id, "❌ ዝቅተኛው የማውጫ መጠን ከ 100 ብር በላይ መሆን አለበት።", show_alert=True)
    
    # edit_message_text በመጠቀም የድሮውን ሜኑ እናጠፋዋለን
    bot.edit_message_text(f"💰 የዋሌትዎ ቀሪ ሂሳብ፦ **{balance:,.2f} ETB**\n\n"
                         f"ማውጣት የሚፈልጉትን **የብር መጠን** ያስገቡ፦", 
                         call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    bot.register_next_step_handler(call.message, process_rider_withdraw_amount)

def process_rider_withdraw_amount(message):
    try:
        amount = float(message.text.strip())
        uid = str(message.from_user.id)
        db = load_data()
        balance = db['riders_list'][uid].get('wallet', 0)

        if amount < 50 or amount > balance:
            msg = bot.send_message(message.chat.id, "❌ ስህተት፦ መጠኑ ከ 50 ብር በታች ወይም ከዋሌትዎ በላይ ነው።")
            return

        r_name = db['riders_list'][uid].get('name', 'ደላላ')
        
        # 🟢 1. ለአድሚን የሚሆኑ በተኖችን እዚህ እንሰራለን
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"wd_approve_{uid}_{amount}"),
            types.InlineKeyboardButton("❌ ሰርዝ", callback_data=f"wd_reject_{uid}_{amount}")
        )

        # 🟢 2. መልዕክቱን እናዘጋጃለን
        admin_info = (f"💸 **አዲስ የገንዘብ ማውጫ ጥያቄ**\n\n"
                      f"👤 ስም፦ {r_name}\n"
                      f"💰 መጠን፦ **{amount:,.2f} ETB**\n"
                      f"🆔 ID፦ `{uid}`")

        # 🟢 3. አዲሱን notify_admins እንጠራለን (በተኑን ጨምረን)
        notify_admins(admin_info, reply_markup=markup)

        bot.send_message(message.chat.id, f"✅ የ {amount} ብር ጥያቄ ለአድሚን ተልኳል።")

    except ValueError:
        bot.send_message(message.chat.id, "❌ እባክዎ ቁጥር ብቻ ያስገቡ።")



@bot.callback_query_handler(func=lambda call: call.data.startswith('wd_'))
def handle_withdraw_decision(call):
    # ዳታውን መበተን (action, rider_id, amount)
    _, action, r_id, amount = call.data.split('_')
    amount = float(amount)
    
    db = load_data()
    rider_name = db['riders_list'].get(r_id, {}).get('name', 'ደላላ')

    if action == "approve":
        current_balance = db['riders_list'][r_id].get('wallet', 0)
        if current_balance >= amount:
            # ብሩን መቀነስ
            db['riders_list'][r_id]['wallet'] -= amount
            # ለድርጅቱ ትርፍ መዝገብ (ከተፈለገ)
            db['total_profit'] = db.get('total_profit', 0) # ማስተካከያ ካስፈለገ
            save_data(db)

            bot.edit_message_text(f"{call.message.text}\n\n✅ **ጸድቋል!** ብሩ ከዋሌቱ ተቀንሷል።", 
                                 call.message.chat.id, call.message.message_id)
            
            # ለደላላው ማሳወቂያ
            bot.send_message(r_id, f"🎉 የ {amount} ብር የማውጣት ጥያቄዎ ተቀባይነት አግኝቶ ከዋሌትዎ ተቀንሷል።")
        else:
            bot.answer_callback_query(call.id, "❌ ስህተት፦ በቂ ሂሳብ የለውም!", show_alert=True)

    elif action == "reject":
        bot.edit_message_text(f"{call.message.text}\n\n❌ **ውድቅ ተደርጓል!**", 
                             call.message.chat.id, call.message.message_id)
        
        # ለደላላው ማሳወቂያ
        bot.send_message(r_id, f"⚠️ ይቅርታ፣ የ {amount} ብር የማውጣት ጥያቄዎ በአድሚን ውድቅ ተደርጓል።")

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_item_"))
def approve_item(call):
    try:
        # 1. ID ማውጣት
        item_id = call.data.split("approve_item_")[-1]
        db = load_data()
        
        if item_id not in db.get('pending_items', {}):
            bot.answer_callback_query(call.id, "❌ ዕቃው አልተገኘም!", show_alert=True)
            return

        # 2. ዳታውን ማዘጋጀት
        item_data = db['pending_items'].pop(item_id)
        v_id = str(item_data['vendor_id'])

        # 3. የቬንደር መዋቅር ማረጋገጥ (ይህ ነው ዋናው መከላከያ)
        if 'vendors_list' not in db: db['vendors_list'] = {}
        
        # ቬንደሩ ከሌለ ወይም ዳታው Dictionary ካልሆነ (ሊስት ከሆነ) አዲስ ፍጠር
        if v_id not in db['vendors_list'] or not isinstance(db['vendors_list'][v_id], dict):
            db['vendors_list'][v_id] = {'name': item_data.get('vendor_name', 'Shop'), 'items': {}}
        
        # 'items' የግድ Dictionary መሆን አለበት (አንተ ኮድህ ላይ .append ትል ነበር፣ እሱ ስህተት ነው)
        if 'items' not in db['vendors_list'][v_id] or not isinstance(db['vendors_list'][v_id]['items'], dict):
            db['vendors_list'][v_id]['items'] = {}

        # 4. ዕቃውን በ Dictionary ቁልፍ (ID) መመዝገብ
        db['vendors_list'][v_id]['items'][item_id] = {
            "name": item_data['item_name'],
            "price": item_data['price'],
            "category": item_data['category'],
            "photo": item_data['photo']
        }

        save_data(db)
        
        # 5. መልዕክት ማደስ
        bot.edit_message_caption(
            caption=f"✅ ጸድቋል፦ {item_data['item_name']}\n🏢 ድርጅት፦ {item_data.get('vendor_name')}", 
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id
        )
        bot.send_message(v_id, f"🎉 ዕቃዎ '{item_data['item_name']}' በአድሚን ጸድቋል!")

    except Exception as e:
        print(f"❌ Approve Fix Error: {e}")
        bot.answer_callback_query(call.id, f"⚠️ ስህተት፦ {str(e)}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data in ["add_fund_vendor", "add_fund_rider"])
def fund_selection_handler(call):
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    
    if call.data == "add_fund_vendor":
        msg = bot.send_message(call.message.chat.id, "🏢 ብር የሚሞላለትን **የድርጅት ID** ያስገቡ፦")
        bot.register_next_step_handler(msg, process_fund_id) # ያንተ ኮድ
        
    elif call.data == "add_fund_rider":
        msg = bot.send_message(call.message.chat.id, "🛵 ብር የሚሞላለትን **የደላላ (Driver) ID** ያስገቡ፦")
        bot.register_next_step_handler(msg, process_rider_fund_id) # አዲሱ ፈንክሽን


# 🏢 የድርጅቱን ID መቀበያ
def process_fund_id(message):
    v_id = message.text.strip()
    # ኮማንድ ከሆነ ወደ መጀመሪያ ይመልሰው
    if v_id.startswith('/'): return start_command(message)
    
    db = load_data()
    # IDው በvendors_list ውስጥ መኖሩን ቼክ ማድረግ
    if v_id not in db.get('vendors_list', {}):
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ ይህ የድርጅት ID አልተገኘም። እባክዎ በትክክል ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_fund_id)
    
    v_name = db['vendors_list'][v_id].get('name', 'ድርጅት')
    msg = bot.send_message(message.chat.id, f"💰 ለ **'{v_name}'** የሚሞላውን የብር መጠን ያስገቡ፦")
    bot.register_next_step_handler(msg, process_vendor_fund_amount, v_id, v_name)

# 💰 የብሩን መጠን ተቀብሎ ዳታቤዝ ላይ መመዝገቢያ
def process_vendor_fund_amount(message, v_id, v_name):
    try:
        amount = float(message.text.strip())
        if amount <= 0: raise ValueError
        
        db = load_data()
        
        # 'balance' የሚለውን ኪይ ተጠቅመን እንደምርበታለን
        current_balance = db['vendors_list'][v_id].get('balance', 0)
        db['vendors_list'][v_id]['balance'] = current_balance + amount
        
        # ለክትትል እንዲመች deposit_balance ላይም እንጨምረው (ካለህ)
        db['vendors_list'][v_id]['deposit_balance'] = db['vendors_list'][v_id].get('deposit_balance', 0) + amount
        
        save_data(db)
        
        bot.send_message(message.chat.id, 
                         f"✅ **በተሳካ ሁኔታ ተሞልቷል!**\n\n"
                         f"🏢 ድርጅት፦ {v_name}\n"
                         f"💵 የተሞላው መጠን፦ {amount} ETB\n"
                         f"💰 አሁን ያለው ቀሪ ሂሳብ፦ {current_balance + amount} ETB", 
                         reply_markup=get_admin_dashboard(message.from_user.id))
        
        # ለድርጅቱ (Vendor) ማሳወቂያ መላክ
        try:
            bot.send_message(v_id, f"🔔 **የሂሳብ መሙያ ማሳወቂያ**\n\nበአድሚን በኩል `{amount} ETB` ሂሳብዎ ላይ ተጨምሯል።\n💰 የአሁኑ ቀሪ ሂሳብዎ፦ `{current_balance + amount} ETB` ነው")
        except:
            pass

    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ትክክለኛ የብር መጠን በቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, process_vendor_fund_amount, v_id, v_name)

# ሀ. የደላላውን ID መቀበያ
def process_rider_fund_id(message):
    r_id = message.text.strip()
    if r_id.startswith('/'): return start_command(message)
    
    db = load_data()
    if r_id not in db.get('riders_list', {}):
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ ይህ የደላላ ID አልተገኘም። እንደገና ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_rider_fund_id)
    
    r_name = db['riders_list'][r_id]['name']
    msg = bot.send_message(message.chat.id, f"💰 ለደላላ **'{r_name}'** የሚሞላውን የብር መጠን ያስገቡ፦")
    bot.register_next_step_handler(msg, process_rider_fund_amount, r_id, r_name)

# ለ. የብሩን መጠን መቀበያና ለደላላው ዋሌት ላይ መመዝገቢያ
def process_rider_fund_amount(message, r_id, r_name):
    try:
        amount = float(message.text.strip())
        if amount <= 0: raise ValueError
        
        db = load_data()
        # ለደላላው 'wallet' ውስጥ ይደመራል
        db['riders_list'][r_id]['wallet'] = db['riders_list'][r_id].get('wallet', 0) + amount
        save_data(db)
        
        bot.send_message(message.chat.id, f"✅ ተሳክቷል! ለደላላ {r_name} {amount} ETB ተሞልቷል።", 
                         reply_markup=get_admin_dashboard(message.from_user.id))
        
        # ለደላላው ማሳወቂያ መላክ
        bot.send_message(r_id, f"🔔 **የዋሌት ማሳወቂያ**\n\nበአድሚን በኩል {amount} ETB ዋሌትዎ ላይ ተሞልቶልዎታል።")
    except:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ትክክለኛ ቁጥር ያስገቡ፦")
        bot.register_next_step_handler(msg, process_rider_fund_amount, r_id, r_name)


# ድርጅት መመዝገቢያ 
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
    
    msg = bot.send_message(message.chat.id, f"📍 የ '{v_name}' አድራሻ (መንደር/ሰፈር) ያስገቡ፦")
    bot.register_next_step_handler(msg, process_v_address, v_name, v_id)

def process_v_address(message, v_name, v_id):
    address = message.text.strip()
    if address.startswith('/'): return start_command(message)

    db = load_data()
    # ዳታቤዙ ውስጥ መመዝገብ
    db['vendors_list'][v_id] = {
        "name": v_name,
        "address": address,
        "deposit_balance": 0,
        "total_sales": 0,
        "status": "active",
        "items": {}
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ ድርጅት '{v_name}' በትክክል ተመዝግቧል!", reply_markup=get_admin_dashboard(message.from_user.id))

# ምድብ logic
def add_category_logic(message):
    new_cat = message.text.strip()
    if new_cat.startswith('/'): return start_command(message)

    db = load_data()
    if "categories" not in db: db["categories"] = []
    
    if new_cat not in db["categories"]:
        db["categories"].append(new_cat)
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ምድብ '{new_cat}' ተጨምሯል!", reply_markup=get_admin_dashboard(message.from_user.id))
    else:
        bot.send_message(message.chat.id, "⚠️ ይህ ምድብ ቀድሞውኑ አለ።")


# ሀ. የድርጅት ኮሚሽን መቀበያ (ዲኮሬተሩ ጠፍቷል)
def start_commission_setting(call):
    # ማንኛውንም የቆየ ግቤት ያጸዳል
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    msg = bot.send_message(call.message.chat.id, "🏢 **ደረጃ 1/3**\n\nየድርጅት (Vendor) ኮሚሽን በ % ያስገቡ (ለምሳሌ 10)፦")
    bot.register_next_step_handler(msg, process_vendor_comm)

# ለ. የደላላውን ክፍያ ይጠይቃል
def process_vendor_comm(message):
    v_comm = message.text.strip()
    if v_comm.startswith('/'): return # ኮማንድ ከሆነ ይቁም
    
    msg = bot.send_message(message.chat.id, f"✅ የድርጅት ኮሚሽን፦ {v_comm}%\n\n**ደረጃ 2/3**\n\nለደላላ (Driver) የሚከፈለውን ቋሚ ክፍያ በብር ያስገቡ (ለምሳሌ 30)፦")
    bot.register_next_step_handler(msg, process_rider_fee, v_comm)

# ሐ. የደንበኛውን ሰርቪስ ፊ ይጠይቃል
def process_rider_fee(message, v_comm):
    r_fee = message.text.strip()
    if r_fee.startswith('/'): return
    
    msg = bot.send_message(message.chat.id, f"✅ የደላላ ክፍያ፦ {r_fee} ETB\n\n**ደረጃ 3/3**\n\nለደንበኛ (Customer) የሚታሰበውን የሰርቪስ ፊ በብር ያስገቡ (ለምሳሌ 15)፦")
    bot.register_next_step_handler(msg, save_all_fees, v_comm, r_fee)

# መ. ሁሉንም በአንድ ላይ ሴቭ ያደርጋል
def save_all_fees(message, v_comm, r_fee):
    c_fee = message.text.strip()
    try:
        db = load_data()
        # ቁጥሮቹን አስተካክሎ መመዝገብ
        db['settings']['vendor_commission_p'] = float(v_comm)
        db['settings']['rider_fixed_fee'] = float(r_fee)
        db['settings']['customer_service_fee'] = float(c_fee)
        save_data(db)
        
        bot.send_message(message.chat.id, 
                         "✅ **ሁሉም ዋጋዎች በትክክል ተመዝግበዋል!**\n\n"
                         f"🏢 ድርጅት፦ {v_comm}%\n"
                         f"🛵 driver፦ {r_fee} ETB\n"
                         f"👤 ደንበኛ፦ {c_fee} ETB", 
                         reply_markup=get_admin_dashboard(message.from_user.id))
    except ValueError:
        bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ቁጥር ብቻ ያስገቡ። ሂደቱ ተቋርጧል።")



#ማስታወቂያ 
def send_broadcast_logic(message):
    if message.text == '/start': return start_command(message)
    
    broadcast_text = message.text
    db = load_data()
    all_users = db.get("user_list", []) # ተጠቃሚዎች ሲገቡ ID-ያቸው እዚህ መመዝገብ አለበት
    
    if not all_users:
        return bot.send_message(message.chat.id, "⚠️ እስካሁን በቦቱ ላይ የተመዘገበ ተጠቃሚ የለም።")

    sent_count = 0
    status_msg = bot.send_message(message.chat.id, "⏳ መልዕክቱ እየተላከ ነው...")

    for user_id in all_users:
        try:
            bot.send_message(user_id, f"📢 **አዲስ ማስታወቂያ**\n\n{broadcast_text}")
            sent_count += 1
        except:
            continue # ቦቱን Block ካደረጉት ዝለላቸው
    
    bot.delete_message(message.chat.id, status_msg.message_id)
    bot.send_message(message.chat.id, f"✅ መልዕክቱ ለ {sent_count} ተጠቃሚዎች ደርሷል።", reply_markup=get_admin_dashboard(message.from_user.id))

#ረፖርት 
def show_full_stats_logic(message):
    db = load_data()
    vendors = db.get('vendors_list', {})
    total_sales = sum(v.get('total_sales', 0) for v in vendors.values())
    total_profit = db.get('total_profit', 0) # ኮሚሽን ሲሰበሰብ እዚህ ይደመራል
    
    text = (f"📊 **አጠቃላይ የቦቱ ሪፖርት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🏢 አጋር ድርጅቶች፦ {len(vendors)}\n"
            f"🛵 ንቁ driver፦ {len(db.get('riders_list', {}))}\n"
            f"💰 ጠቅላላ ሽያጭ፦ {total_sales:,.2f} ETB\n"
            f"📈 የተጣራ ትርፍ፦ {total_profit:,.2f} ETB\n"
            f"━━━━━━━━━━━━━━━")
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


def update_vendor_rating(vendor_id, new_star):
    db = load_data()
    vendor = db['vendors_list'][str(vendor_id)]
    
    current_rating = vendor.get('rating', 0.0)
    total_reviews = vendor.get('total_reviews', 0)
    
    # አዲሱን አማካይ ማስላት (Average formula)
    # አዲስ አማካይ = ((የድሮ አማካይ * የድሮ ብዛት) + አዲስ ኮከብ) / (የድሮ ብዛት + 1)
    new_rating = ((current_rating * total_reviews) + new_star) / (total_reviews + 1)
    
    vendor['rating'] = round(new_rating, 1) # እስከ አንድ ዲጂት (ለምሳሌ 4.5)
    vendor['total_reviews'] = total_reviews + 1
    
    save_data(db)



def show_admin_categories(message):
    db = load_data()
    categories = db.get('categories', [])
    
    if not categories:
        return bot.send_message(message.chat.id, "📁 እስካሁን ምንም አይነት የምድብ ዝርዝር አልተመዘገበም።")
    
    text = "📁 **የBDF የዕቃ ምድቦች (Categories)**\n"
    text += "━━━━━━━━━━━━━━━\n"
    for i, cat in enumerate(categories, 1):
        text += f"{i}. {cat}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ አዲስ ምድብ ጨምር", callback_data="admin_manage_cats"))
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="switch_to_admin"))
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")


# system lock
def toggle_system_lock_logic(message):
    db = load_data()
    if 'settings' not in db: db['settings'] = {}
    
    # የነበረውን ይገለብጠዋል (True ከሆነ False...)
    current_status = db['settings'].get('system_locked', False)
    db['settings']['system_locked'] = not current_status
    save_data(db)
    
    new_status = "🔒 ዝግ (Locked)" if db['settings']['system_locked'] else "🔓 ክፍት (Open)"
    bot.send_message(message.chat.id, f"⚠️ የሲስተሙ ሁኔታ ተቀይሯል።\nአሁን ቦቱ፦ **{new_status}** ነው")

def process_rider_name(message):
    r_name = message.text.strip()
    if r_name.startswith('/'): return start_command(message)
    msg = bot.send_message(message.chat.id, f"📞 የ '{r_name}' **ስልክ ቁጥር** ያስገቡ፦")
    bot.register_next_step_handler(msg, process_rider_phone, r_name)

# ሐ. ስልክ ተቀብሎ User ID ይጠይቃል
def process_rider_phone(message, r_name):
    r_phone = message.text.strip()
    msg = bot.send_message(message.chat.id, f"🆔 የ '{r_name}' የቴሌግራም **User ID** ያስገቡ፦")
    bot.register_next_step_handler(msg, process_rider_id, r_name, r_phone)

# መ. ሁሉንም መረጃ ዳታቤዝ ውስጥ ይከታል (Wallet ጨምሮ)
def process_rider_id(message, r_name, r_phone):
    r_id = message.text.strip()
    if not r_id.isdigit():
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ ID ቁጥር መሆን አለበት። እንደገና ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_rider_id, r_name, r_phone)
    
    db = load_data()
    if 'riders_list' not in db: db['riders_list'] = {}
    
    # process_rider_id ውስጥ ይሄን ተካ
    db['riders_list'][r_id] = {
        "name": r_name,
        "phone": r_phone,
        "wallet": 0,
        "is_online": False,
        "status": "active",
        "total_deliveries": 0,
        "rating": 0.0  # ✅ ከ 5.0 ወደ 0.0 ተቀይሯል
    }

    save_data(db)
    bot.send_message(message.chat.id, f"✅ driver'{r_name}' በስልክ {r_phone} ተመዝግቧል!", reply_markup=get_admin_dashboard(message.from_user.id))

def show_riders_report_logic(message):
    db = load_data()
    riders = db.get('riders_list', {})
    if not riders:
        return bot.send_message(message.chat.id, "🛵 እስካሁን የተመዘገበ driver የለም።")

    text = "🛵 **driver ወቅታዊ ሁኔታና ዋሌት**\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    for rid, rdata in riders.items():
        status = "🟢" if rdata.get('is_online') else "🔴"
        wallet = rdata.get('wallet', 0)
        phone = rdata.get('phone', 'የሌለው')
        
        text += (f"{status} **{rdata['name']}**\n"
                 f"📞 ስልክ፦ {phone}\n"
                 f"💰 ዋሌት፦ **{wallet:,.2f} ETB**\n"
                 f"🆔 ID፦ `{rid}`\n"
                 f"------------------------\n")
        
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# ኮሚሽን መተመኛ ምርጫ
def set_commission_choice(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏢 የሻጭ ኮሚሽን (%)", callback_data="set_vendor_comm"))
    markup.add(types.InlineKeyboardButton("🛵 የደላላ ክፍያ (ETB)", callback_data="set_rider_fee"))
    bot.send_message(message.chat.id, "የትኛውን ዋጋ መተመን ይፈልጋሉ?", reply_markup=markup)


# ሀ. መጀመሪያ የሻጩን ይቀበላል
def process_vendor_comm_step(message):
    try:
        v_rate = float(message.text.strip())
        # የደላላውን ክፍያ ለመጠየቅ ወደ ቀጣይ ደረጃ ያልፋል
        msg = bot.send_message(message.chat.id, f"✅ የሻጭ ኮሚሽን {v_rate}% ተይዟል።\n\n🛵 አሁን ደግሞ **የደላላውን የአገልግሎት ክፍያ** በብር ያስገቡ (ለምሳሌ 0 ወይም 5)፦")
        bot.register_next_step_handler(msg, process_rider_fee_step, v_rate)
    except:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, process_vendor_comm_step)

# ለ. ከዚያ የደላላውን ተቀብሎ ሁለቱንም በአንድ ላይ ሴቭ ያደርጋል
def process_rider_fee_step(message, v_rate):
    try:
        r_fee = float(message.text.strip())
        db = load_data()
        if 'settings' not in db: db['settings'] = {}
        
        # ሁለቱንም ዳታቤዝ ውስጥ ማስቀመጥ
        db['settings']['vendor_commission_percent'] = v_rate
        db['settings']['rider_fixed_fee'] = r_fee
        save_data(db)
        
        text = (f"✅ **ዋጋዎች በትክክል ተመዝግበዋል!**\n\n"
                f"🏢 የሻጭ ኮሚሽን፦ {v_rate}%\n"
                f"🛵 የደላላ ክፍያ፦ {r_fee} ETB")
        bot.send_message(message.chat.id, text, reply_markup=get_admin_dashboard(message.from_user.id))
    except:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, process_rider_fee_step, v_rate)

def apply_wallet_deduction(rider_id, vendor_id, item_price):
    db = load_data()
    rider_id = str(rider_id)
    vendor_id = str(vendor_id)
    
    # --- 1. የሻጭ ኮሚሽን ተቀናሽ ---
    if vendor_id in db.get('vendors_list', {}):
        v_rate = db.get('settings', {}).get('vendor_commission_percent', 5)
        vendor_cut = (item_price * v_rate) / 100
        db['vendors_list'][vendor_id]['deposit_balance'] -= vendor_cut
    else:
        vendor_cut = 0 # ድርጅቱ ካልተገኘ

    # --- 2. የደላላ ተቀናሽ (ዕቃ + ቋሚ ክፍያ) ---
    if rider_id in db.get('riders_list', {}):
        r_fee = db.get('settings', {}).get('rider_fixed_fee', 0)
        rider_total_deduct = item_price + r_fee
        db['riders_list'][rider_id]['wallet'] -= rider_total_deduct
        
        # ደላላው ሂሳቡ ካለቀበት ማሳወቂያ መላክ
        if db['riders_list'][rider_id]['wallet'] < 50:
            try:
                bot.send_message(rider_id, "⚠️ **ማሳሰቢያ፦** የዋሌት ሂሳብዎ ከ 50 ETB በታች ዝቅ ብሏል። እባክዎ በቅርቡ ሂሳብዎን ይሙሉ!")
            except: pass
    else:
        r_fee = 0 # ደላላው ካልተገኘ

    # --- 3. የአድሚን ትርፍ መመዝገብ ---
    # ትርፍህ ከሻጩ የወሰድከው ኮሚሽን + ከደላላው የወሰድከው የአገልግሎት ክፍያ ነው
    admin_gain = vendor_cut + r_fee
    db['total_profit'] = db.get('total_profit', 0) + admin_gain
    
    save_data(db)
    print(f"💰 Deduction Complete: Admin gained {admin_gain} ETB")



#የአጋር ድርጅቶች ዝርዝር
def show_vendors_list_logic(message):
    db = load_data()
    vendors = db.get("vendors_list", {})
    if not vendors:
        return bot.send_message(message.chat.id, "🏢 እስካሁን የተመዘገበ ድርጅት የለም።")
    
    text = "🏢 **የአጋር ድርጅቶች ዝርዝር**\n\n"
    for vid, vdata in vendors.items():
        text += (f"🔹 **{vdata['name']}**\n"
                 f"🆔 ID: `{vid}` | 📍 {vdata.get('address', 'አድራሻ የለም')}\n"
                 f"💰 ሽያጭ: {vdata.get('total_sales', 0)} ETB\n"
                 f"------------------------\n")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

#ድርጅቶችን/ደላላዎችን ማገጃ
def process_block_logic(message):
    target_id = message.text.strip()
    db = load_data()
    found = False
    for cat in ['vendors_list', 'riders_list']:
        if target_id in db.get(cat, {}):
            status = db[cat][target_id].get('status', 'active')
            new_status = 'blocked' if status != 'blocked' else 'active'
            db[cat][target_id]['status'] = new_status
            found = True; save_data(db)
            bot.send_message(message.chat.id, f"✅ የ ID {target_id} ሁኔታ ወደ **{new_status}** ተቀይሯል።")
            break
    if not found: bot.send_message(message.chat.id, "❌ ይህ ID አልተገኘም።")

#ቀጥታ ትዕዛዞች እና ቅሬታዎች
def view_live_orders(message):
    bot.send_message(message.chat.id, "📑 በአሁኑ ሰዓት ንቁ ትዕዛዞች የሉም (ከዳታቤዝ ጋር ገና ይገናኛል)።")

def view_disputes(call):
    bot.answer_callback_query(call.id, "ምንም ቅሬታ የለም", show_alert=True)

#የቅሬታዎች መከታተያ
def view_disputes(call):
    db = load_data()
    disputes = db.get("disputes", {})
    if not disputes:
        return bot.answer_callback_query(call.id, "✅ ምንም አይነት ቅሬታ የለም።", show_alert=True)
    
    text = "❗ **የደንበኞች ቅሬታ ዝርዝር**\n\n"
    for d_id, d_data in disputes.items():
        text += f"🆔 ትዕዛዝ: #{d_data['order_id']}\n👤 ደንበኛ: {d_data['user_name']}\n📝 ቅሬታ: {d_data['issue']}\n---\n"
    bot.send_message(call.message.chat.id, text)

#የደንበኞች ግምገማ
def view_reviews(call):
    db = load_data()
    reviews = db.get("reviews", [])
    if not reviews:
        return bot.answer_callback_query(call.id, "⭐ እስካሁን የተሰጠ አስተያየት የለም።", show_alert=True)
    
    text = "⭐ **የቅርብ ጊዜ አስተያየቶች**\n\n"
    for r in reviews[-5:]: # የመጨረሻዎቹን 5 ብቻ
        text += f"🏢 {r['vendor_name']} ➡️ {r['stars']}⭐\n💬 {r['comment']}\n---\n"
    bot.send_message(call.message.chat.id, text)

#የተጣራ ትርፍ ክትትል
def view_total_profit(call):
    db = load_data()
    profit = db.get('total_profit', 0)
    v_comm = db['settings'].get('vendor_commission_p', 0)
    c_fee = db['settings'].get('customer_service_fee', 0)
    
    text = (f"📈 **የቦቱ አጠቃላይ የትርፍ ሪፖርት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 ጠቅላላ የተጣራ ትርፍ፦ **{profit:,.2f} ETB**\n\n"
            f"⚙️ **አሁን እየሰሩ ያሉ መተመኛዎች፦**\n"
            f"• የድርጅት ኮሚሽን፦ {v_comm}%\n"
            f"• የደንበኛ አገልግሎት ክፍያ፦ {c_fee} ETB")
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")






def complete_order_logic(order_id):
    db = load_data()
    order = db['orders'][order_id]
    item_price = float(order['price'])
    
    # 🟢 ከሴቲንግ ላይ የትኩስ ኮሚሽን ዋጋዎችን ማንበብ
    v_comm_percent = db['settings'].get('vendor_commission_p', 10)
    service_fee = db['settings'].get('customer_service_fee', 15)
    
    # ትርፉን ማስላት
    vendor_commission_amount = item_price * (v_comm_percent / 100)
    total_order_profit = vendor_commission_amount + service_fee
    
    # 🟢 በጠቅላላ ትርፍ ላይ መደመር
    db['total_profit'] = db.get('total_profit', 0) + total_order_profit
    save_data(db)


#ዝቅተኛ የዋስትና ሂሳብ
def view_low_balances(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    low_limit = 200 # ከ 200 በታች ሲሆን እንዲያሳውቅ
    
    low_list = [f"⚠️ {v['name']} (ቀሪ: {v['deposit_balance']} ETB)" 
                for v in vendors.values() if v.get('deposit_balance', 0) < low_limit]
    
    if not low_list:
        return bot.answer_callback_query(call.id, "✅ ሁሉም ድርጅቶች በቂ ዋስትና አላቸው።", show_alert=True)
    
    text = "🚨 **የዋስትና ሂሳባቸው ዝቅተኛ የሆኑ ድርጅቶች**\n\n" + "\n".join(low_list)
    bot.send_message(call.message.chat.id, text)

#በመጠባበቅ ላይ ያሉ
def view_pending_items(call):
    db = load_data()
    pending = db.get('pending_items', [])
    
    if not pending:
        return bot.answer_callback_query(call.id, "✅ በመጠባበቅ ላይ ያለ አዲስ ዕቃ የለም።", show_alert=True)
    
    bot.send_message(call.message.chat.id, "📦 **ጸደቃ የሚጠብቁ ዕቃዎች ዝርዝር፦**")
    
    for index, item in enumerate(pending):
        markup = types.InlineKeyboardMarkup()
        # እያንዳንዱን እቃ በ index ቁጥሩ እንለየዋለን
        btn_approve = types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approve_{index}")
        btn_reject = types.InlineKeyboardButton("❌ ሰርዝ", callback_data=f"reject_{index}")
        markup.add(btn_approve, btn_reject)
        
        text = (f"🏢 ድርጅት፦ {item['vendor_name']}\n"
                f"🍎 ዕቃ፦ {item['item_name']}\n"
                f"💰 ዋጋ፦ {item['price']} ETB\n"
                f"📁 ምድብ፦ {item['category']}")
        
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

#የክትትል ሎጂክ
def view_all_balances(message):
    db = load_data()
    vendors = db.get('vendors_list', {})
    
    if not vendors:
        return bot.send_message(message.chat.id, "❌ እስካሁን ምንም የተመዘገበ ድርጅት የለም።")
    
    text = "📉 **የድርጅቶች የሂሳብ ክትትል**\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    for vid, vdata in vendors.items():
        balance = vdata.get('deposit_balance', 0)
        # ሂሳቡ ከ 100 በታች ከሆነ ቀይ ምልክት እንዲያሳይ
        status_icon = "🔴" if balance < 100 else "🟢"
        text += f"{status_icon} **{vdata['name']}**\n   ቀሪ ሂሳብ፦ `{balance:,.2f} ETB`\n"
    
    text += "━━━━━━━━━━━━━━━"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

#የደላላው ሜኑ (Rider Menu)
def show_rider_menu(message):
    user_id = message.chat.id
    db = load_data()
    rider_data = db['riders_list'].get(str(user_id), {})
    
    # driverሁኔታ (Online/Offline)
    status_text = "🟢 ኦንላይን" if rider_data.get('is_online') else "🔴 ኦፍላይን"
    wallet = rider_data.get('wallet', 0)

    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn_status = types.InlineKeyboardButton(f"ሁኔታ፦ {status_text}", callback_data="rider_toggle_status")
    btn_orders = types.InlineKeyboardButton("📦 አዲስ ትዕዛዞች", callback_data="rider_view_orders")
    btn_wallet = types.InlineKeyboardButton(f"💰 ዋሌት ({wallet} ETB)", callback_data="rider_wallet")
    btn_history = types.InlineKeyboardButton("📜 የታሪክ ማህደር", callback_data="rider_history")
    
    # ወደ አድሚንነት መመለሻ በተን
    btn_back_admin = types.InlineKeyboardButton("👑 ወደ አድሚን ተመለስ", callback_data="switch_to_admin")
    
    markup.add(btn_status)
    markup.add(btn_orders, btn_wallet)
    markup.add(btn_history)
    markup.add(btn_back_admin)

    text = (f"🛵 **driverማኔጅመንት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 ስም፦ {rider_data.get('name', 'Driver')}\n"
            f"📞 ስልክ፦ {rider_data.get('phone', '-')}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"ትዕዛዝ ለመቀበል 'ኦንላይን' መሆንዎን ያረጋግጡ።")
            
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

def process_rider_deduct_id(message):
    r_id = message.text.strip()
    db = load_data()
    if r_id not in db.get('riders_list', {}):
        return bot.send_message(message.chat.id, "❌ ID አልተገኘም።")
    
    r_name = db['riders_list'][r_id]['name']
    curr_balance = db['riders_list'][r_id].get('wallet', 0)
    msg = bot.send_message(message.chat.id, f"👤 ደላላ፦ {r_name}\n💰 አሁኑ ዋሌት፦ {curr_balance} ETB\n\nከዋሌቱ ላይ **የሚቀነሰውን መጠን** ያስገቡ (ሙሉውን ከሆነ {curr_balance})፦")
    bot.register_next_step_handler(msg, process_rider_deduct_amount, r_id)

def process_rider_deduct_amount(message, r_id):
    try:
        amount = float(message.text.strip())
        db = load_data()
        db['riders_list'][r_id]['wallet'] -= amount # ዋሌቱን መቀነስ
        save_data(db)
        
        bot.send_message(message.chat.id, f"✅ ተሳክቷል! ከ {r_id} ዋሌት ላይ {amount} ETB ተቀንሷል።")
        bot.send_message(r_id, f"💸 **የክፍያ ማሳወቂያ**\n\nየጠየቁት {amount} ETB ተከፍሎዎ ከዋሌትዎ ላይ ተቀንሷል። ስለሰሩ እናመሰግናለን!")
    except:
        bot.send_message(message.chat.id, "❌ ስህተት ተፈጥሯል።")



import uuid

# 1. የዕቃ ስም መቀበያ
def process_item_name(message):
    if message.text == "/start": return start_cmd(message)
    
    item_name = message.text.strip()
    db = load_data()
    categories = db.get('categories', [])
    
    if not categories:
        return bot.send_message(message.chat.id, "❌ አድሚኑ መጀመሪያ የምድብ ዝርዝር (Categories) መፍጠር አለበት።")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for cat in categories:
        markup.add(cat)
    
    msg = bot.send_message(message.chat.id, f"📁 የ **'{item_name}'** ምድብ ይምረጡ፦", reply_markup=markup)
    bot.register_next_step_handler(msg, process_item_category, item_name)

# 2. ምድብ መቀበያ
def process_item_category(message, item_name):
    if message.text == "/start": return start_cmd(message)
    
    category = message.text.strip()
    # ቀጣይ ዋጋ እንዲያስገባ መጠየቅ
    msg = bot.send_message(message.chat.id, f"💰 የ **'{item_name}'** ዋጋ በብር ያስገቡ፦", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_item_price, item_name, category)

# 3. ዋጋ መቀበያ (ከነ ስህተት ማረሚያው)
def process_item_price(message, item_name, category):
    if message.text == "/start": return start_cmd(message)
    
    try:
        # ዋጋውን ወደ ቁጥር መቀየር
        price = float(message.text.strip())
        msg = bot.send_message(message.chat.id, f"📸 የ **'{item_name}'** ፎቶ ይላኩ፦")
        bot.register_next_step_handler(msg, process_item_photo, item_name, category, price)
    except ValueError:
        # ቁጥር ካልሆነ ድጋሚ እንዲያስገባ መጠየቅ
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ (ለምሳሌ፦ 150)፦")
        bot.register_next_step_handler(msg, process_item_price, item_name, category)

# 4. ፎቶ መቀበያ እና ለአድሚን መላኪያ (ይህ ክፍል ባለፈው በሰጠሁህ ይቀጥላል)

        

# 4. ፎቶውን ተቀብሎ በጊዜያዊነት ያከማቻል
def process_item_photo(message, item_name, category, price):
    # ፎቶ መሆኑን ማረጋገጥ
    if message.content_type != 'photo':
        msg = bot.send_message(message.chat.id, "⚠️ እባክዎ የዕቃውን ፎቶ ይላኩ (ጽሁፍ አይቀበልም)፦")
        bot.register_next_step_handler(msg, process_item_photo, item_name, category, price)
        return

    try:
        db = load_data()
        v_id = str(message.from_user.id)
        # የቬንደሩን ስም ከዳታቤዝ ፈልጎ ማውጣት
        v_name = db.get('vendors_list', {}).get(v_id, {}).get('name', 'ያልታወቀ ድርጅት')

        # ለዕቃው ልዩ መለያ ID መፍጠር (String መሆኑን እናረጋግጥ)
        temp_id = str(uuid.uuid4())[:8]
        
        item_data = {
            "vendor_name": v_name,
            "vendor_id": message.chat.id,
            "item_name": item_name, 
            "price": price,
            "category": category,
            "photo": message.photo[-1].file_id 
        }
        
        # ዳታውን በpending_items ውስጥ ማስቀመጥ
        if "pending_items" not in db:
            db["pending_items"] = {}
            
        db["pending_items"][temp_id] = item_data
        save_data(db)
        
        # ለአድሚን መላክ
        process_item_finish(message, item_data, temp_id)
        
    except Exception as e:
        print(f"Photo processing error: {e}")
        bot.send_message(message.chat.id, "❌ ፎቶውን ስንመዘግብ ስህተት ተፈጥሯል።")

# 5. ለአድሚን በፎቶ እና በበተን መልክ ይልካል
import traceback

def process_item_finish(message, item_data, temp_id):
    print("\n--- 🕵️ DEBUG: STARTING ADMIN NOTIFICATION ---")
    
    # 1. መረጃዎቹ በትክክል መኖራቸውን ቼክ እናድርግ
    photo_id = item_data.get('photo')
    print(f"DEBUG: Photo ID to be sent: {photo_id}")
    print(f"DEBUG: Temp ID: {temp_id}")

    markup = types.InlineKeyboardMarkup(row_width=2)
    # Callback data ርዝመቱ ከ 64 bytes መብለጥ የለበትም
    btn_approve = types.InlineKeyboardButton("✅ እቀበላለሁ", callback_data=f"approve_item_{temp_id}")
    btn_reject = types.InlineKeyboardButton("❌ አልቀበልም", callback_data=f"reject_item_{temp_id}")
    markup.add(btn_approve, btn_reject)

    admin_text = (
        "🆕 **አዲስ የዕቃ ማጽደቂያ ጥያቄ**\n"
        "━━━━━━━━━━━━━━━\n"
        f"🏢 ድርጅት፦ {item_data.get('vendor_name', 'ያልታወቀ')}\n"
        f"🍎 ዕቃ፦ {item_data.get('item_name', 'ያልታወቀ')}\n"
        f"💰 ዋጋ፦ {item_data.get('price', 0)} ETB\n"
        f"📁 ምድብ፦ {item_data.get('category', 'ያልታወቀ')}"
    )

    target_admin = 8488592165 

    try:
        # 2. ፎቶውን ለመላክ መሞከር
        if photo_id:
            bot.send_photo(
                chat_id=target_admin, 
                photo=photo_id, 
                caption=admin_text, 
                reply_markup=markup,
                parse_mode="Markdown"
            )
            print("✅ DEBUG: Photo sent successfully!")
        else:
            print("⚠️ DEBUG: Photo ID is missing! Sending text only.")
            bot.send_message(target_admin, f"⚠️ ፎቶው አልተገኘም!\n\n{admin_text}", reply_markup=markup)

        bot.send_message(message.chat.id, "✅ ዕቃው ለቁጥጥር ተልኳል!")

    except Exception as e:
        # 3. ስህተቱን በዝርዝር ማውጣት
        print("❌ DEBUG: CRITICAL ERROR IN SENDING TO ADMIN!")
        print(traceback.format_exc()) # ይህ መስመር ስህተቱ የቱ ጋር እንደሆነ ይነግረናል
        
        bot.send_message(message.chat.id, "⚠️ መረጃው ተመዝግቧል ግን ለአድሚን መላክ አልተቻለም።")
    
    print("--- 🕵️ DEBUG: END --- \n")

def update_item_price_logic(message, item_id):
    user_id = str(message.from_user.id)
    try:
        new_price = float(message.text.strip())
        db = load_data()
        
        if user_id in db.get('vendors_list', {}) and item_id in db['vendors_list'][user_id].get('items', {}):
            db['vendors_list'][user_id]['items'][item_id]['price'] = new_price
            save_data(db)
            
            bot.send_message(message.chat.id, f"✅ ዋጋው በትክክል ተቀይሯል! አዲሱ ዋጋ፦ **{new_price} ETB**", parse_mode="Markdown")
            # ወደ ዝርዝሩ እንዲመለስ
            show_my_items(message)
        else:
            bot.send_message(message.chat.id, "❌ ስህተት፦ ዕቃው አልተገኘም።")
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, update_item_price_logic, item_id)


def show_my_items(message):
    db = load_data()
    v_id = str(message.chat.id)
    # የቬንደሩን ዳታ ፈልግ
    vendor_data = db.get('vendors_list', {}).get(v_id, {})
    items = vendor_data.get('items', {}) # Dictionary መሆኑን ልብ በል

    if not items:
        bot.send_message(message.chat.id, "📦 እስካሁን ምንም ዕቃ የለዎትም።")
        return

    bot.send_message(message.chat.id, "📂 **የእርስዎ ዕቃዎች ዝርዝር፦**")
    
    # items አሁን Dictionary ስለሆነ በ .items() እናነባለን
    for item_id, item in items.items():
        text = f"🍎 ዕቃ፦ {item['name']}\n💰 ዋጋ፦ {item['price']} ETB\n📁 ምድብ፦ {item['category']}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✏️ ዋጋ ቀይር", callback_data=f"edit_item_{item_id}"),
            types.InlineKeyboardButton("🗑 ሰርዝ", callback_data=f"delete_item_{item_id}")
        )
        
        if item.get('photo'):
            bot.send_photo(message.chat.id, item['photo'], caption=text, reply_markup=markup)
        else:
            bot.send_message(message.chat.id, text, reply_markup=markup)



def notify_drivers_about_new_order(order_id, order_data):
    db = load_data()
    riders = db.get('riders_list', {})
    
    # የዲሊቨሪ ዋጋውንና ርቀቱን እዚህ ጋር እናስላ (ወይም ቋሚ ዋጋ ካለህ)
    delivery_fee = order_data.get('total', 0) * 0.1 # ለምሳሌ 10% ከሆነ
    
    msg_text = (f"🛵 **አዲስ የዲሊቨሪ ትዕዛዝ!**\n"
                f"━━━━━━━━━━━━━━\n"
                f"🆔 ትዕዛዝ ቁጥር፦ #{order_id}\n"
                f"💰 ጠቅላላ ክፍያ፦ {order_data.get('total')} ETB\n"
                f"📍 አድራሻ፦ {order_data.get('address')}\n"
                f"━━━━━━━━━━━━━━")
    
    markup = types.InlineKeyboardMarkup()
    # ቀደም ብለን የሰራነው የመረከቢያ logic (r_take_)
    markup.add(types.InlineKeyboardButton("✅ ትዕዛዙን ተቀበል", callback_data=f"r_take_{order_id}"))

    for r_id, r_info in riders.items():
        # ደላላው "Active" (Online) ከሆነ ብቻ ይላክለት
        if r_info.get('status') == "Active":
            try:
                bot.send_message(r_id, msg_text, reply_markup=markup)
            except:
                continue




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
