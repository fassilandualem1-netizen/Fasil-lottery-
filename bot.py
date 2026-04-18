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

CHANNEL_ID = -1003962139457

def backup_db_to_channel():
    try:
        with open('database.json', 'rb') as f:
            bot.send_document(CHANNEL_ID, f, caption=f"🔄 የዳታቤዝ ባካፕ\n📅 ቀን፦ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            print("📢 ዳታቤዝ ወደ ቻናል ተልኳል።")
    except Exception as e:
        print(f"❌ ባካፕ ሲደረግ ስህተት ተፈጠረ፦ {e}")

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

def process_automatic_settlement(order_id):
    db = load_data()
    order = db['orders'].get(order_id)
    
    v_id = str(order['vendor_id'])
    r_id = str(order['rider_id'])
    
    p = float(order['item_total'])   # የዕቃ ዋጋ
    d = float(order['delivery_fee']) # የማድረሻ ክፍያ
    
    # 📌 ኮሚሽን ተመኖች
    v_comm = p * 0.05  # 5% ከድርጅት
    r_comm = d * 0.10  # 10% ከደላላ ማድረሻ
    
    # 💳 የቬንደር ቅነሳ (Vendor Deduction)
    # አድሚኑ ቀድሞ ብር ስለሰጠው፡ (የእቃ ዋጋ + የቦት ኮሚሽን) ይቀነሳል
    db['vendors_list'][v_id]['wallet'] -= (p + v_comm)
    
    # 💳 የደላላ ቅነሳ (Driver Deduction)
    # ደላላው ከደንበኛው p+d ስለሚሰበስብ፡ (የእቃ ዋጋ + የቦት ኮሚሽን) ይቀነሳል
    db['riders_list'][r_id]['wallet'] -= (p + r_comm)
    
    # ትዕዛዙን መዝጋት
    db['orders'][order_id]['status'] = "Completed"
    save_data(db)
    
    # 📢 ማሳወቂያዎች
    bot.send_message(v_id, f"✅ ትዕዛዝ #{order_id} ተጠናቋል። ከዋሌትዎ {p + v_comm} ETB ተቀንሷል።")
    bot.send_message(r_id, f"🏁 ማድረስ ተጠናቋል። ከደንበኛው {p + d} ETB ተቀብለዋል። ሂሳብዎ ተቀናናሽ ተደርጓል።")


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
    db = load_data()
    # የቬንደሩን መረጃ ማግኘት
    vendor_data = db['vendors_list'].get(str(vendor_id), {})
    
    if not vendor_data:
        return "❌ የድርጅት መረጃ አልተገኘም። እባክዎ መጀመሪያ ይመዝገቡ።", None

    # መረጃዎችን መሰብሰብ
    wallet_balance = vendor_data.get('wallet', 0.0)
    items_count = len(vendor_data.get('items', {}))
    vendor_name = vendor_data.get('name', "ድርጅት")
    is_verified = "✅ የተረጋገጠ" if vendor_data.get('verified') else "⚠️ ያልተረጋገጠ"

    # የተጠቃሚ በይነገጽ (Inline Buttons)
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("➕ አዲስ ዕቃ ጨምር", callback_data="vendor_add_item"),
        types.InlineKeyboardButton(f"📦 የኔ ዕቃዎች ({items_count})", callback_data="vendor_list_items")
    )
    markup.add(
        types.InlineKeyboardButton("📋 ትዕዛዞች", callback_data="vendor_view_orders"),
        types.InlineKeyboardButton(f"💰 ዋሌት ({wallet_balance} ETB)", callback_data="vendor_wallet")
    )
    markup.add(
        types.InlineKeyboardButton("🏢 የድርጅት መረጃ", callback_data="vendor_profile")
    )

    text = (f"🏢 **{vendor_name} - ዳሽቦርድ**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"ሁኔታ፦ {is_verified}\n"
            f"💰 ቀሪ ሂሳብ፦ `{wallet_balance} ETB`\n"
            f"📦 ጠቅላላ ዕቃዎች፦ `{items_count}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"እባክዎ የሚፈልጉትን ተግባር ይምረጡ፦")
            
    return text, markup


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


# 🏢 የድርጅቱን ID መቀበያ
def process_fund_id(message):
    v_id = message.text.strip()
    
    # ተጠቃሚው በስህተት ኮማንድ ቢልክ (ለምሳሌ /start) ሂደቱን ያቋርጣል
    if v_id.startswith('/'): 
        return start_command(message)
    
    db = load_data()
    
    # IDው በvendors_list ውስጥ መኖሩን ቼክ ማድረግ
    if v_id not in db.get('vendors_list', {}):
        msg = bot.send_message(
            message.chat.id, 
            "❌ **ስህተት፦** ይህ የድርጅት ID አልተገኘም።\nእባክዎ በትክክል ያስገቡ ወይም በ 'ድርጅቶች' ዝርዝር ውስጥ IDውን ያረጋግጡ፦"
        )
        # IDው እስኪስተካከል ድረስ እዚሁ ፈንክሽን ላይ እንዲቆይ እናደርጋለን
        return bot.register_next_step_handler(msg, process_fund_id)
    
    v_name = db['vendors_list'][v_id].get('name', 'ድርጅት')
    
    msg = bot.send_message(
        message.chat.id, 
        f"🏢 ድርጅት፦ **{v_name}**\n💰 አሁን ያለው ቀሪ ሂሳብ፦ `{db['vendors_list'][v_id].get('deposit_balance', 0)} ETB`\n\n"
        f"እባክዎ የሚሞላውን **የብር መጠን** ያስገቡ፦"
    )
    # ወደ ቀጣዩ ደረጃ (ገንዘብ መቀበያ) ይልከዋል
    bot.register_next_step_handler(msg, process_vendor_fund_amount, v_id, v_name)






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




# 1. የመጀመሪያው ደረጃ - ስም መቀበል
@bot.callback_query_handler(func=lambda call: call.data == "vendor_add_item")
def start_add_item(call):
    msg = bot.send_message(call.message.chat.id, "🍎 **የእቃውን ስም ያስገቡ (ለምሳሌ፦ በርገር)፦**", parse_mode="Markdown")
    bot.register_next_step_handler(msg, get_item_name)

# 2. ስሙን ተቀብሎ ዋጋ መጠየቅ
def get_item_name(message):
    item_name = message.text
    msg = bot.send_message(message.chat.id, f"💰 የ **'{item_name}'** ዋጋ ስንት ነው? (ቁጥር ብቻ ያስገቡ)፦", parse_mode="Markdown")
    bot.register_next_step_handler(msg, get_item_price, item_name)

# 3. ዋጋውን ተቀብሎ ምድብ መጠየቅ
def get_item_price(message, item_name):
    try:
        price = float(message.text)
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        # በዳታቤዝህ ያሉትን ምድቦች እዚህ ጋር መዘርዘር ትችላለህ
        markup.add("ምግብ", "መጠጥ", "ኤሌክትሮኒክስ", "ሌላ")
        
        msg = bot.send_message(message.chat.id, "📁 የእቃውን ምድብ (Category) ይምረጡ፦", reply_markup=markup)
        bot.register_next_step_handler(msg, save_item_to_db, item_name, price)
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ (ለምሳሌ፦ 150)፦")
        bot.register_next_step_handler(msg, get_item_price, item_name)

# 4. ዳታውን በራስ-ሰር መመዝገብ እና ለአድሚን ሪፖርት መላክ
def save_item_to_db(message, item_name, price):
    category = message.text
    vendor_id = str(message.chat.id)
    db = load_data()
    
    # ለዕቃው ልዩ መለያ (Unique ID) መስጠት
    item_id = str(int(time.time()))
    
    new_item = {
        "name": item_name,
        "price": price,
        "category": category,
        "status": "Available",
        "created_at": str(datetime.now())
    }
    
    # በቬንደሩ ዝርዝር ውስጥ መጨመር
    if vendor_id not in db['vendors_list']:
        db['vendors_list'][vendor_id] = {"items": {}, "wallet": 0.0, "name": message.from_user.first_name}
        
    db['vendors_list'][vendor_id]['items'][item_id] = new_item
    save_data(db)
    
    # ለቬንደሩ ማረጋገጫ
    bot.send_message(vendor_id, f"✅ **{item_name}** በተሳካ ሁኔታ ተመዝግቧል። አሁን ለደንበኞች ይታያል!", reply_markup=types.ReplyKeyboardRemove())
    
    # ለአድሚኑ ሪፖርት መላክ (Automatic Report)
    admin_report = (f"📢 **አዲስ ዕቃ ተመዝግቧል!**\n\n"
                    f"🏢 ድርጅት፦ {db['vendors_list'][vendor_id].get('name')}\n"
                    f"🍎 ዕቃ፦ {item_name}\n"
                    f"💰 ዋጋ፦ {price} ETB\n"
                    f"📁 ምድብ፦ {category}")
    
    # ADMIN_ID አስቀድመህ የገለጽከው መሆን አለበት
    bot.send_message(ADMIN_ID, admin_report)



@bot.callback_query_handler(func=lambda call: call.data.startswith('v_edit_'))
def start_edit_price(call):
    item_id = call.data.replace("v_edit_", "")
    msg = bot.send_message(call.message.chat.id, "💰 አዲሱን ዋጋ ያስገቡ (ቁጥር ብቻ)፦")
    bot.register_next_step_handler(msg, save_new_price, item_id)

def save_new_price(message, item_id):
    v_id = str(message.chat.id)
    try:
        new_price = float(message.text)
        db = load_data()
        
        if item_id in db['vendors_list'][v_id]['items']:
            old_price = db['vendors_list'][v_id]['items'][item_id]['price']
            db['vendors_list'][v_id]['items'][item_id]['price'] = new_price
            save_data(db)
            
            bot.send_message(v_id, f"✅ ዋጋው በተሳካ ሁኔታ ተቀይሯል!\nቀድሞ፦ `{old_price}` | አሁን፦ `{new_price}` ETB", parse_mode="Markdown")
        else:
            bot.send_message(v_id, "❌ ዕቃው አልተገኘም።")
    except ValueError:
        msg = bot.send_message(v_id, "❌ ስህተት፦ እባክዎ ቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, save_new_price, item_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('v_del_'))
def delete_vendor_item(call):
    item_id = call.data.replace("v_del_", "")
    v_id = str(call.from_user.id)
    db = load_data()
    
    if item_id in db['vendors_list'][v_id]['items']:
        item_name = db['vendors_list'][v_id]['items'][item_id]['name']
        del db['vendors_list'][v_id]['items'][item_id]
        save_data(db)
        
        bot.answer_callback_query(call.id, f"🗑 {item_name} ተሰርዟል", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "❌ ዕቃው አልተገኘም።")


def create_new_order(customer_id, vendor_id, item_list, total_price, delivery_fee):
    db = load_data()
    order_id = f"ORD{int(time.time())}"
    
    new_order = {
        "order_id": order_id,
        "customer_id": customer_id,
        "vendor_id": vendor_id,
        "items": item_list,
        "item_total": total_price,
        "delivery_fee": delivery_fee,
        "status": "Pending", # ገና ለደላላ አልተሰጠም
        "timestamp": str(datetime.now())
    }
    
    db['orders'][order_id] = new_order
    save_data(db)
    
    # 🔔 ለቬንደሩ ኖቲፊኬሽን ብቻ (አንተ እንዳልከው Accept ማድረግ አይጠበቅበትም)
    items_desc = "\n".join([f"• {i['name']} (x{i['qty']})" for i in item_list])
    vendor_msg = (f"🔔 **አዲስ ትዕዛዝ ደርሶዎታል!**\n\n"
                  f"🆔 ID: `{order_id}`\n"
                  f"📦 ዝርዝር፦\n{items_desc}\n\n"
                  f"እባክዎ እቃውን ማዘጋጀት ይጀምሩ። ደላላ ሲመደብ እናሳውቅዎታለን።")
    bot.send_message(vendor_id, vendor_msg, parse_mode="Markdown")
    
    # ለደላላዎች ጥሪ ማስተላለፍ (Broadcast to Drivers)
    broadcast_to_drivers(order_id, total_price, delivery_fee)


@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_order_'))
def driver_accept_order(call):
    order_id = call.data.replace("accept_order_", "")
    driver_id = str(call.from_user.id)
    db = load_data()
    
    order = db['orders'].get(order_id)
    if order['status'] != "Pending":
        return bot.answer_callback_query(call.id, "❌ ይሄ ትዕዛዝ ቀድሞ ተወስዷል!", show_alert=True)

    # ትዕዛዙን ለደላላው መስጠት
    db['orders'][order_id]['status'] = "On the way"
    db['orders'][order_id]['rider_id'] = driver_id
    save_data(db)
    
    bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ተረክበዋል። አሁን ወደ ድርጅቱ ይሂዱ።", 
                          call.message.chat.id, call.message.message_id)
    
    # ለቬንደሩ ማሳወቅ
    bot.send_message(order['vendor_id'], f"🚚 ደላላው እቃውን ለመረከብ እየመጣ ነው። (ID: {driver_id})")


@bot.callback_query_handler(func=lambda call: call.data.startswith('finish_order_'))
def finalize_order(call):
    order_id = call.data.replace("finish_order_", "")
    db = load_data()
    order = db['orders'].get(order_id)
    
    v_id = str(order['vendor_id'])
    r_id = str(order['rider_id'])
    p = float(order['item_total'])
    d = float(order['delivery_fee'])
    
    # የኮሚሽን ተመኖች
    v_comm = p * 0.05 # 5%
    r_comm = d * 0.10 # 10%
    
    # 💰 አውቶማቲክ የዋሌት ቅነሳ (Automatic Settlement)
    # ለቬንደሩ፦ የእቃ ዋጋ (ቀድሞ ስለተከፈለው) + ኮሚሽን
    db['vendors_list'][v_id]['wallet'] -= (p + v_comm)
    
    # ለደላላው፦ ከደንበኛው p+d ስለሚቀበል፣ የእቃ ዋጋ (p) + ኮሚሽን
    db['riders_list'][r_id]['wallet'] -= (p + r_comm)
    
    db['orders'][order_id]['status'] = "Completed"
    save_data(db)
    
    # 📊 ለአድሚኑ የትርፍ ሪፖርት
    bot.send_message(ADMIN_ID, f"📈 **ትርፍ ተመዝግቧል!**\nትዕዛዝ፦ #{order_id}\nድምር ትርፍ፦ {v_comm + r_comm} ETB")
    
    bot.send_message(call.message.chat.id, "🏁 ትዕዛዙ ተጠናቋል። ሂሳቡ በራስ-ሰር ተሰልቷል።")


@bot.callback_query_handler(func=lambda call: call.data.endswith('_wallet'))
def view_wallet(call):
    user_id = str(call.from_user.id)
    db = load_data()
    
    # የትኛው አካል እንደሆነ መለየት
    if "vendor" in call.data:
        balance = db['vendors_list'].get(user_id, {}).get('wallet', 0.0)
    else:
        balance = db['riders_list'].get(user_id, {}).get('wallet', 0.0)
        
    text = (f"💰 **የእርስዎ ዋሌት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"ቀሪ ሂሳብ፦ `{balance} ETB`\n\n"
            f"💡 ሂሳብዎ ሲያልቅ አዳዲስ ትዕዛዞችን ማስተናገድ አይችሉም። ለመሙላት አድሚኑን ያነጋግሩ።")
            
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")


# ይህ ፈንክሽን በትዕዛዝ ማጠናቀቂያ (Finish Order) ውስጥ ይጠራል
def deduct_from_wallets(v_id, r_id, item_price, delivery_fee):
    db = load_data()
    
    # የኮሚሽን ተመኖች
    v_comm = item_price * 0.05  # 5%
    r_comm = delivery_fee * 0.10 # 10%
    
    # የቬንደር ቅነሳ (Price + Commission)
    db['vendors_list'][v_id]['wallet'] -= (item_price + v_comm)
    
    # የደላላ ቅነሳ (Price + Commission)
    db['riders_list'][r_id]['wallet'] -= (item_price + r_comm)
    
    save_data(db)


@bot.callback_query_handler(func=lambda call: call.data == "vendor_profile")
def view_vendor_profile(call):
    v_id = str(call.from_user.id)
    db = load_data()
    v_info = db['vendors_list'].get(v_id, {})
    
    status = "✅ የተረጋገጠ (Verified)" if v_info.get('verified') else "⚠️ ያልተረጋገጠ (Pending)"
    
    text = (f"🏢 **የድርጅት መረጃ ማስተዳደሪያ**\n\n"
            f"📍 **ስም፦** {v_info.get('name', 'ያልተጠቀሰ')}\n"
            f"📞 **ስልክ፦** {v_info.get('phone', 'ያልተጠቀሰ')}\n"
            f"🗺️ **አድራሻ፦** {v_info.get('address', 'ያልተጠቀሰ')}\n"
            f"🛡️ **ሁኔታ፦** {status}\n\n"
            f"ምን ማስተካከል ይፈልጋሉ?")
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 ስም ቀይር", callback_data="edit_v_name"),
        types.InlineKeyboardButton("📞 ስልክ ቀይር", callback_data="edit_v_phone"),
        types.InlineKeyboardButton("📍 ሎኬሽን አሻሽል", callback_data="edit_v_location")
    )
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")


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




@bot.callback_query_handler(func=lambda call: call.data.startswith('viewcat_'))
def list_category_items(call):
    category_name = call.data.replace("viewcat_", "")
    db = load_data()
    vendors = db.get('vendors_list', {})
    
    found_items = False
    bot.send_message(call.message.chat.id, f"📦 **በ '{category_name}' ምድብ ያሉ ዕቃዎች፦**")

    for v_id, v_info in vendors.items():
        items = v_info.get('items', {})
        for item_id, item_data in items.items():
            # እቃው የተመረጠው ምድብ ውስጥ መሆኑን ቼክ ማድረግ
            if item_data.get('category') == category_name:
                found_items = True
                
                # አድሚኑ እቃውን ማጥፋት እንዲችል "Delete" በተን እንጨምርለት
                markup = types.InlineKeyboardMarkup()
                btn_delete = types.InlineKeyboardButton("🗑 ሰርዝ (Admin Only)", callback_data=f"delitem_{v_id}_{item_id}")
                markup.add(btn_delete)

                caption = (f"🍎 **ዕቃ፦** {item_data['name']}\n"
                           f"💰 **ዋጋ፦** {item_data['price']} ETB\n"
                           f"🏢 **ድርጅት፦** {v_info['name']}")
                
                if item_data.get('photo'):
                    bot.send_photo(call.message.chat.id, item_data['photo'], caption=caption, reply_markup=markup)
                else:
                    bot.send_message(call.message.chat.id, caption, reply_markup=markup)

    if not found_items:
        bot.send_message(call.message.chat.id, f"😕 በዚህ ምድብ ውስጥ እስካሁን ምንም ዕቃ የለም።")






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


@bot.callback_query_handler(func=lambda call: call.data == "rider_view_orders")
def rider_view_orders(call):
    user_id = str(call.from_user.id)
    db = load_data()
    
    # ደላላው ኦፍላይን ከሆነ ትዕዛዝ ማየት የለበትም
    if not db['riders_list'].get(user_id, {}).get('is_online'):
        return bot.answer_callback_query(call.id, "⚠️ ትዕዛዝ ለማየት መጀመሪያ 'ኦንላይን' ይሁኑ!", show_alert=True)

    orders = db.get('orders', {})
    # ማንም ያልተረከባቸው (Pending) ትዕዛዞችን መፈለግ
    available_orders = {k: v for k, v in orders.items() if v.get('status') == 'Pending'}

    if not available_orders:
        return bot.answer_callback_query(call.id, "📭 በአሁኑ ሰዓት አዲስ ትዕዛዝ የለም።", show_alert=True)

    bot.send_message(call.message.chat.id, "🚴 **አዳዲስ ትዕዛዞች ዝርዝር፦**")

    for o_id, o_data in available_orders.items():
        markup = types.InlineKeyboardMarkup()
        # ትዕዛዙን ለመቀበል (Accept)
        btn_accept = types.InlineKeyboardButton("✅ ትዕዛዙን ተቀበል", callback_data=f"accept_order_{o_id}")
        markup.add(btn_accept)
        
        text = (f"🆔 **ትዕዛዝ ቁጥር:** `#{o_id}`\n"
                f"🏢 **ድርጅት:** {o_data.get('vendor_name')}\n"
                f"📍 **መዳረሻ:** {o_data.get('delivery_address')}\n"
                f"💰 **የአገልግሎት ክፍያ:** {o_data.get('delivery_fee')} ETB\n"
                f"💵 **ጠቅላላ ዋጋ:** {o_data.get('total')} ETB")
        
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")




@bot.callback_query_handler(func=lambda call: call.data == "rider_toggle_status")
def rider_toggle_status(call):
    user_id = str(call.from_user.id)
    db = load_data()
    
    if user_id in db.get('riders_list', {}):
        # ሁኔታውን መገልበጥ (True -> False / False -> True)
        current_status = db['riders_list'][user_id].get('is_online', False)
        new_status = not current_status
        db['riders_list'][user_id]['is_online'] = new_status
        save_data(db)
        
        status_msg = "አሁን ኦንላይን ነዎት 🟢" if new_status else "አሁን ኦፍላይን ነዎት 🔴"
        bot.answer_callback_query(call.id, status_msg)
        
        # ሜኑውን በለውጡ መሰረት ማደስ (Refresh)
        # አዲስ መልዕክት ከመላክ ይልቅ የድሮውን edit ማድረግ ይሻላል
        # ማሳሰቢያ፦ የ show_rider_menu ኮድህ መልዕክት የሚልክ ስለሆነ እዚህ ጋር ራሱን መጥራት ይቻላል
        show_rider_menu(call.message) 
    else:
        bot.answer_callback_query(call.id, "❌ የደላላ አካውንት አልተገኘም።", show_alert=True)



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



def show_items_by_category(message):
    db = load_data()
    categories = db.get('categories', [])
    
    if not categories:
        return bot.send_message(message.chat.id, "📁 እስካሁን ምንም ምድብ አልተፈጠረም።")

    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        # እያንዳንዱን ምድብ በ callback_data እንልካለን
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"viewcat_{cat}"))
    
    bot.send_message(message.chat.id, "📂 ማየት የሚፈልጉትን ምድብ ይምረጡ፦", reply_markup=markup)



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
    db = load_data()
    orders = db.get('orders', {})
    
    # በሂደት ላይ ያሉ ትዕዛዞችን ብቻ መለየት (Completed እና Cancelled ያልሆኑትን)
    live_orders = {
        o_id: o_data for o_id, o_data in orders.items() 
        if o_data.get('status') not in ['Completed', 'Cancelled']
    }
    
    if not live_orders:
        return bot.send_message(message.chat.id, "📭 በአሁኑ ሰዓት ምንም ንቁ ትዕዛዝ የለም።")

    text = "📑 **ንቁ ትዕዛዞች (Live Orders)**\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    for o_id, o_data in live_orders.items():
        # የድርጅት ስም እና የደላላ ስም መፈለግ
        v_id = str(o_data.get('vendor_id'))
        r_id = str(o_data.get('rider_id'))
        
        v_name = db.get('vendors_list', {}).get(v_id, {}).get('name', 'ያልታወቀ ድርጅት')
        r_name = db.get('riders_list', {}).get(r_id, {}).get('name', 'ደላላ አልተመደበም')
        
        status = o_data.get('status', 'በጥበቃ ላይ')
        total = o_data.get('total', 0)
        
        text += (f"🆔 **ID:** `#{o_id}`\n"
                 f"🏢 **ድርጅት:** {v_name}\n"
                 f"🛵 **ደላላ:** {r_name}\n"
                 f"💰 **ዋጋ:** {total} ETB\n"
                 f"📊 **ሁኔታ:** {status}\n"
                 f"------------------------\n")

    # ረጅም መልዕክት ከሆነ እንዲያሳጥር (Scrollable እንዲሆን)
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


def view_reviews(call):
    db = load_data()
    # ቅሬታ ሳይሆን 'reviews' የሚለውን ዳታ እናነባለን
    reviews = db.get("reviews", {}) 
    
    if not reviews:
        return bot.answer_callback_query(call.id, "📊 እስካሁን ምንም ግምገማ አልተሰጠም።", show_alert=True)
    
    text = "🌟 **የአገልግሎት ግምገማዎች**\n\n"
    for r_id, r_data in reviews.items():
        stars = "⭐" * int(r_data.get('rating', 0))
        text += (f"👤 **ደንበኛ:** {r_data.get('user_name')}\n"
                f"📝 **አስተያየት:** {r_data.get('comment')}\n"
                f"📉 **ውጤት:** {stars}\n"
                f"━━━━━━━━━━━━━━━\n")
    
    bot.send_message(call.message.chat.id, text)


#የቅሬታዎች መከታተያ
def view_disputes(call):
    db = load_data()
    disputes = db.get("disputes", {})
    
    if not disputes:
        return bot.answer_callback_query(call.id, "✅ ምንም አይነት ቅሬታ የለም።", show_alert=True)
    
    bot.send_message(call.message.chat.id, "❗ **የደንበኞች ቅሬታ ዝርዝር**")

    for d_id, d_data in disputes.items():
        markup = types.InlineKeyboardMarkup()
        # ቅሬታውን ለመፍታት ወይም ውድቅ ለማድረግ
        btn_resolve = types.InlineKeyboardButton("✅ ተፈትቷል", callback_data=f"resolve_{d_id}")
        btn_view_order = types.InlineKeyboardButton("🔍 ትዕዛዙን እይ", callback_data=f"v_order_{d_data['order_id']}")
        markup.add(btn_view_order, btn_resolve)
        
        text = (f"🆔 **የቅሬታ ID:** `{d_id}`\n"
                f"📦 **ትዕዛዝ ቁጥር:** `#{d_data['order_id']}`\n"
                f"👤 **ደንበኛ:** {d_data.get('user_name', 'ያልታወቀ')}\n"
                f"📝 **የቅሬታው ምክንያት:**\n_{d_data['issue']}_")
        
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

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



# ይህ ለምሳሌ ያህል ነው - እቃ መመዝገቢያህ መጨረሻ ላይ እንዲህ አድርገው
def final_save_item(v_id, item_data):
    db = load_data()
    if v_id in db['vendors_list']:
        item_id = str(int(time.time())) # ልዩ መለያ ቁጥር
        db['vendors_list'][v_id]['items'][item_id] = item_data
        save_data(db)
        return True
    return False

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
