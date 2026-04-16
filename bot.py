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

        # መዋቅሩን ለሁሉም ተዋናዮች (Vendor, Driver, Customer) እንዲመች አድርገን መጀመር
        initial_data = {
            "riders_list": {},     
            "vendors_list": {},    
            "orders": {},          
            "pending_items": {},   
            "categories": [],      
            "total_profit": 0,     
            "user_list": [],       # ሁሉንም ተጠቃሚዎች ለማስታወቂያ መያዣ
            "settings": {
                "vendor_commission_p": 10,   # ከድርጅቱ ሽያጭ የሚቀነስ (%)
                "rider_fixed_fee": 30,       # ለደላላው የሚከፈል ቋሚ ክፍያ (ETB)
                "customer_service_fee": 15,  # ከደንበኛው የሚወሰድ አገልግሎት ክፍያ (ETB)
                "base_delivery": 50,         # የመነሻ መላኪያ ዋጋ
                "system_locked": False 
            }
        }
        return initial_data
    except Exception as e:
        print(f"❌ Database Load Error: {e}")
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
    btn_cats = types.InlineKeyboardButton("📁 ምድቦች", callback_data="admin_manage_cats")
    
    btn_add_vendor = types.InlineKeyboardButton("➕ አዲስ ድርጅት", callback_data="admin_add_vendor")
    btn_add_rider = types.InlineKeyboardButton("➕ አዲስ driver", callback_data="admin_add_rider")
    btn_vendors = types.InlineKeyboardButton("🏢 ድርጅቶች", callback_data="admin_list_vendors")
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
    markup.add(btn_cats, btn_stats) # ሪፖርት እና ምድብ ጎን ለጎን
    
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
        # እነዚህ መስመሮች አሁን በትክክል ገባ ብለዋል
        error_msg = f"❌ Error: {str(e)}"
        print(error_msg)
        bot.send_message(message.chat.id, error_msg)

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


@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def interrupt_handler(message):
    # ማንኛውም ኮማንድ ሲመጣ የቆየውን Next Step ይሰርዛል
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    
    # ከዚያ ወደ ትክክለኛው ኮማንድ ይልከዋል
    if message.text == '/start':
        start_command(message)
    elif message.text == '/admin':
        show_admin_panel(message)



@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_') or call.data.startswith('switch_'))
def central_admin_handler(call):
    user_id = call.from_user.id
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
        
    elif call.data == "admin_profit_track":
        view_total_profit(call)
    
  
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

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def handle_pending_action(call):
    action, index = call.data.split('_')
    index = int(index)
    
    db = load_data()
    pending = db.get('pending_items', [])
    
    if index >= len(pending):
        return bot.answer_callback_query(call.id, "❌ ስህተት፦ ይህ እቃ ቀድሞ ተሰርዟል።")
    
    item = pending.pop(index) # ከፔንዲንግ ዝርዝር ውስጥ እናወጣዋለን
    
    if action == "approve":
        v_id = item['vendor_id']
        # እቃውን ወደ ድርጅቱ ዝርዝር ውስጥ እንጨምራለን
        if v_id in db['vendors_list']:
            if 'items' not in db['vendors_list'][v_id]:
                db['vendors_list'][v_id]['items'] = []
            
            db['vendors_list'][v_id]['items'].append({
                "name": item['item_name'],
                "price": item['price'],
                "category": item['category']
            })
            save_data(db)
            bot.send_message(call.message.chat.id, f"✅ '{item['item_name']}' ጸድቆ ለደንበኞች ክፍት ሆኗል።")
            # ለድርጅቱ ባለቤት ማሳወቂያ
            try: bot.send_message(v_id, f"🎉 ደስ የሚል ዜና! ያስገቡት ዕቃ '{item['item_name']}' በአድሚን ጸድቋል።")
            except: pass
            
    elif action == "reject":
        save_data(db) # የተቀነሰውን ዝርዝር ብቻ ሴቭ እናደርጋለን
        bot.send_message(call.message.chat.id, f"❌ '{item['item_name']}' ውድቅ ተደርጓል።")
        # ለድርጅቱ ባለቤት ማሳወቂያ
        try: bot.send_message(item['vendor_id'], f"⚠️ ይቅርታ፣ ያስገቡት ዕቃ '{item['item_name']}' በአድሚን ውድቅ ተደርጓል።")
        except: pass

    # መልዕክቱን እናጠፋዋለን (ወይም እናስተካክላለን)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id, "ተፈጽሟል!")


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
        
        # ለአድሚን የሚሄድ በተን ማዘጋጀት
        markup = types.InlineKeyboardMarkup()
        # እዚህ ጋር የደላላውን ID እና የብሩን መጠን በ callback_data እናሳልፋለን
        markup.add(
            types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"wd_approve_{uid}_{amount}"),
            types.InlineKeyboardButton("❌ ሰርዝ", callback_data=f"wd_reject_{uid}_{amount}")
        )

        admin_text = (f"💸 **አዲስ የገንዘብ ማውጫ ጥያቄ**\n\n"
                      f"👤 ስም፦ {r_name}\n"
                      f"🆔 ID፦ `{uid}`\n"
                      f"💰 መጠን፦ **{amount:,.2f} ETB**\n"
                      f"🏦 ቀሪ ሂሳብ፦ {balance:,.2f} ETB")
        
        # ለአድሚን መላክ (የአድሚን ግሩፕ ወይም ID ካለህ እሱን ተጠቀም)
        notify_admins(admin_text, reply_markup=markup) 

        bot.send_message(message.chat.id, f"✅ የ {amount} ብር ጥያቄ ለአድሚን ተልኳል። ሲጸድቅ እናሳውቅዎታለን።")

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

@bot.callback_query_handler(func=lambda call: call.data in ["add_fund_vendor", "add_fund_rider"])
def fund_selection_handler(call):
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    
    if call.data == "add_fund_vendor":
        msg = bot.send_message(call.message.chat.id, "🏢 ብር የሚሞላለትን **የድርጅት ID** ያስገቡ፦")
        bot.register_next_step_handler(msg, process_fund_id) # ያንተ ኮድ
        
    elif call.data == "add_fund_rider":
        msg = bot.send_message(call.message.chat.id, "🛵 ብር የሚሞላለትን **የደላላ (Driver) ID** ያስገቡ፦")
        bot.register_next_step_handler(msg, process_rider_fund_id) # አዲሱ ፈንክሽን


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
    profit = db.get("total_profit", 0)
    rate = db.get('settings', {}).get('commission_rate', 5)
    
    text = (f"💰 **የቦቱ ትርፍ ሪፖርት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📈 የኮሚሽን መጠን: {rate}%\n"
            f"💵 ጠቅላላ የተጣራ ትርፍ: **{profit:,.2f} ETB**\n"
            f"━━━━━━━━━━━━━━━")
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

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
