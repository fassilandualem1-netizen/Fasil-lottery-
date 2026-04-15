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

def get_admin_dashboard(user_id):
    db = load_data()
    markup = types.InlineKeyboardMarkup(row_width=2)

    # --- ምድብ 4 & 5: ድጋፍና ማስታወቂያ (ወደ ላይ ወጥቷል) ---
    support_label = types.InlineKeyboardButton("--- 📣 ድጋፍና ማስታወቂያ ---", callback_data="none")
    btn_dispute = types.InlineKeyboardButton("💬 ቅሬታዎች", callback_data="admin_disputes")
    btn_reviews = types.InlineKeyboardButton("⭐ ግምገማዎች", callback_data="admin_reviews")
    btn_broadcast = types.InlineKeyboardButton("📢 ማስታወቂያ ላክ", callback_data="admin_broadcast")

    # --- ምድብ 1: ፋይናንስና ዋስትና ---
    finance_label = types.InlineKeyboardButton("--- 💰 ፋይናንስና ዋስትና ---", callback_data="none")
    btn_fund = types.InlineKeyboardButton("💳 ብር መሙያ (Fund)", callback_data="admin_add_funds")
    btn_balance = types.InlineKeyboardButton("📉 የሂሳብ ክትትል", callback_data="admin_monitor_balance")
    btn_profit = types.InlineKeyboardButton("💰 የኮሚሽን ትርፍ", callback_data="admin_profit_track")
    btn_low_credit = types.InlineKeyboardButton("⚠️ ዝቅተኛ ሂሳብ", callback_data="admin_low_credit")

    # --- ምድብ 2: ኦፕሬሽን ---
    ops_label = types.InlineKeyboardButton("--- 📦 ኦፕሬሽን ---", callback_data="none")
    btn_live_orders = types.InlineKeyboardButton("📋 የቀጥታ ትዕዛዞች", callback_data="admin_live_orders")
    btn_pending = types.InlineKeyboardButton("📦 በመጠባበቅ ላይ ያሉ", callback_data="admin_pending_approvals")
    btn_cats = types.InlineKeyboardButton("📁 ምድቦች (Categories)", callback_data="admin_manage_cats")

    # --- ምድብ 3: ደህንነትና ተሳታፊዎች ---
    security_label = types.InlineKeyboardButton("--- 🔐 ደህንነትና ተሳታፊዎች ---", callback_data="none")
    btn_add_vendor = types.InlineKeyboardButton("➕ አዲስ ድርጅት", callback_data="admin_add_vendor")
    btn_add_rider = types.InlineKeyboardButton("➕ አዲስ ደላላ", callback_data="admin_add_rider") # ተጨምሯል
    btn_vendors = types.InlineKeyboardButton("🏢 የአጋር ድርጅቶች", callback_data="admin_list_vendors")
    btn_riders = types.InlineKeyboardButton("🛵 የደላላዎች ሁኔታ", callback_data="admin_rider_status")
    btn_set_commission = types.InlineKeyboardButton("⚙️ የኮሚሽን መጠን", callback_data="admin_set_commission")
    btn_block = types.InlineKeyboardButton("🚫 አግድ/ፍቀድ", callback_data="admin_block_manager")
    btn_lock = types.InlineKeyboardButton("🔒 ሲስተም ዝጋ (Lock)", callback_data="admin_system_lock")

    # --- ምድብ 6: ሪፖርት ---
    report_label = types.InlineKeyboardButton("--- 📊 ሪፖርት ---", callback_data="none")
    btn_stats = types.InlineKeyboardButton("📈 ጠቅላላ ሪፖርት", callback_data="admin_full_stats")

    # --- ወደ Markup መጨመር (ቅደም ተከተል) ---
    markup.add(support_label)
    markup.add(btn_dispute, btn_reviews)
    markup.add(btn_broadcast)

    markup.add(finance_label)
    markup.add(btn_fund, btn_balance)
    markup.add(btn_profit, btn_low_credit)

    markup.add(ops_label)
    markup.add(btn_live_orders, btn_pending)
    markup.add(btn_cats)

    markup.add(security_label)
    markup.add(btn_add_vendor, btn_add_rider) # ጎን ለጎን
    markup.add(btn_vendors, btn_riders)       # ጎን ለጎን
    markup.add(btn_set_commission)
    markup.add(btn_block, btn_lock)

    markup.add(report_label)
    markup.add(btn_stats)

        # --- አዲሱ የመቀያየሪያ ስዊች (Switch Mode) ---
    uid_str = str(user_id)
    if uid_str in db.get('riders_list', {}):
        # የአድሚን ገጹን ዘግቶ ወደ ደላላ ሜኑ የሚወስድ በተን
        btn_switch = types.InlineKeyboardButton("🔄 ወደ ደላላነት ቀይር (Rider Mode)", callback_mode="switch_to_rider")
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
        # ይህ መስመር ትክክለኛውን ስህተት በቦቱ ላይ ይልክልሃል
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

# 1. ማዕከላዊ የ Callback አስተዳዳሪ
@bot.callback_query_handler(func=lambda call: call.data.startswith(('admin_', 'rider_', 'accept_')))
def central_callback_manager(call):
    # ማንኛውንም የተጀመረ Step-by-step ሂደት ያቋርጣል
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    db = load_data()
    uid = str(call.from_user.id)

    # --- ሀ. የአድሚን ተግባራት ---
    if call.data.startswith('admin_'):
        if call.data == "admin_add_rider":
            msg = bot.send_message(call.message.chat.id, "👤 የደላላውን ሙሉ ስም ያስገቡ፦")
            bot.register_next_step_handler(msg, get_rider_id)
        
        elif call.data == "admin_main":
            # ወደ ዋናው አድሚን ዳሽቦርድ ይመልሳል
            bot.edit_message_text("🛠 **የአድሚን ዳሽቦርድ**", call.message.chat.id, call.message.message_id, 
                                  reply_markup=get_admin_dashboard(call.from_user.id), parse_mode="Markdown")

    # --- ለ. የደላላ ተግባራት (ሁኔታ መቀያየሪያ) ---
    elif call.data == "rider_toggle_status":
        if uid in db.get('riders_list', {}):
            current = db['riders_list'][uid].get('is_online', False)
            db['riders_list'][uid]['is_online'] = not current
            save_data(db)
            
            new_label = "🟢 Online" if not current else "🔴 Offline"
            bot.answer_callback_query(call.id, f"ሁኔታዎ ወደ {new_label} ተቀይሯል")
            
            # ሜኑውን እዛው ላይ ያድሰዋል (ከአዲሱ የሪደር ስታተስ ጋር)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, 
                                          reply_markup=get_admin_dashboard_with_rider(call.from_user.id, db))
        else:
            bot.answer_callback_query(call.id, "⚠️ መጀመሪያ እንደ ደላላ መመዝገብ አለብዎት!", show_alert=True)

    # --- ሐ. የትዕዛዝ መቀበያ (Accept Order) ---
    elif call.data.startswith("accept_order_"):
        order_id = call.data.replace("accept_order_", "")
        if order_id in db.get('orders', {}) and db['orders'][order_id]['status'] == "Pending":
            db['orders'][order_id]['status'] = "On the way"
            db['orders'][order_id]['rider_id'] = uid
            save_data(db)
            
            bot.edit_message_text(f"✅ **ትዕዛዝ #{order_id} ተይዟል!**\n\n🛵 ደላላ፦ {call.from_user.first_name}\n📍 ሁኔታ፦ በማድረስ ላይ...", 
                                  call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            
            # ለደንበኛው ማሳወቅ (በጣም አስፈላጊ!)
            customer_id = db['orders'][order_id]['customer_id']
            bot.send_message(customer_id, f"🛵 **ትዕዛዝዎ በመንገድ ላይ ነው!**\nደላላ {call.from_user.first_name} እቃዎን እየያዘ መጥቷል።")

# --- መ. የደላላ ምዝገባ ቅደም ተከተል ---
def get_rider_id(message):
    rider_name = message.text.strip()
    msg = bot.send_message(message.chat.id, f"🆔 የ **{rider_name}** User ID ያስገቡ፦\n(ተጠቃሚው ቦቱ ላይ /id ብሎ የላከልህን ቁጥር)")
    bot.register_next_step_handler(msg, get_rider_phone, rider_name)

def get_rider_phone(message, rider_name):
    rider_id = message.text.strip()
    if not rider_id.isdigit():
        msg = bot.send_message(message.chat.id, "❌ ስህተት፡ ID ቁጥር ብቻ መሆን አለበት። ደግመው ያስገቡ፦")
        return bot.register_next_step_handler(msg, get_rider_phone, rider_name)
    
    msg = bot.send_message(message.chat.id, f"📞 የ **{rider_name}** ስልክ ቁጥር ያስገቡ፦")
    bot.register_next_step_handler(msg, save_full_rider, rider_name, rider_id)

def save_full_rider(message, rider_name, rider_id):
    phone = message.text.strip()
    db = load_data()
    
    # የሪደር ዳታቤዝ መዋቅር
    db['riders_list'][str(rider_id)] = {
        "name": rider_name,
        "phone": phone,
        "is_online": False,
        "status": "Idle",
        "earnings": 0,
        "is_authorized": True
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ **ምዝገባ ተጠናቋል!**\n\n👤 ስም፦ {rider_name}\n📞 ስልክ፦ {phone}\n🆔 ID፦ `{rider_id}`", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback_manager(call):
    # 🌟 የቆየ Next Step ካለ ያጸዳል
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    
    # --- 1. መረጃ መቀበል የሚፈልጉ (Next Step የሚጠቀሙ) ---
    if call.data == "admin_add_rider":
        msg = bot.send_message(call.message.chat.id, "👤 የደላላውን ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, get_rider_id) # ስም መቀበያ

    elif call.data == "admin_add_vendor":
        msg = bot.send_message(call.message.chat.id, "🏢 የድርጅቱን ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, process_v_name)

    elif call.data == "admin_add_funds":
        msg = bot.send_message(call.message.chat.id, "💳 የድርጅት User ID ያስገቡ፦")
        bot.register_next_step_handler(msg, process_fund_id)

    elif call.data == "admin_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 ማስታወቂያ ይጻፉ፦")
        bot.register_next_step_handler(msg, send_broadcast_logic)

    elif call.data == "admin_manage_cats":
        msg = bot.send_message(call.message.chat.id, "📁 የአዲሱን ምድብ ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, add_category_logic)

    elif call.data == "admin_set_commission":
        msg = bot.send_message(call.message.chat.id, "⚙️ አዲሱን የኮሚሽን መጠን ያስገቡ (%)፦")
        bot.register_next_step_handler(msg, save_new_commission)

    elif call.data == "admin_block_manager":
        msg = bot.send_message(call.message.chat.id, "🚫 የሚታገደውን ወይም የሚፈቀደውን User ID ያስገቡ፦")
        bot.register_next_step_handler(msg, process_block_unblock)

    # --- 2. ቀጥታ ሪፖርት የሚያሳዩ (Next Step የማይፈልጉ) ---
    elif call.data == "admin_monitor_balance": view_all_balances(call)
    elif call.data == "admin_profit_track": view_total_profit(call)
    elif call.data == "admin_low_credit": view_low_balances(call)
    elif call.data == "admin_live_orders": view_live_orders(call)
    elif call.data == "admin_full_stats": show_full_stats(call)
    elif call.data == "admin_pending_approvals": view_pending_items(call)
    elif call.data == "admin_list_vendors": list_all_vendors(call)
    elif call.data == "admin_rider_status": view_rider_status(call)
    elif call.data == "admin_system_lock": toggle_system_lock(call)
    elif call.data == "admin_disputes": view_disputes(call)
    elif call.data == "admin_reviews": view_reviews(call)



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

# --- 2. እቃ የማጽደቅ/የመሰረዝ/ቅሬታ የመፍታት ስራ (ልዩ Callback) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_", "resolve_")))
def item_approval_manager(call):
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    
    # 1. እቃዎችን ማጽደቂያ
    if call.data.startswith("approve_"):
        approve_item(call)
        
    # 2. እቃዎችን መሰረዣ
    elif call.data.startswith("reject_"):
        reject_item(call)
        
    # 3. ቅሬታዎችን መፍቻ (Resolve Dispute)
    elif call.data.startswith("resolve_"):
        dispute_id = call.data.replace("resolve_", "")
        db = load_data()
        
        if dispute_id in db.get('disputes', {}):
            # የቅሬታውን ሁኔታ መቀየር
            db['disputes'][dispute_id]['status'] = 'resolved'
            customer_id = db['disputes'][dispute_id].get('user_id')
            save_data(db)
            
            # አድሚኑ ጋር መልዕክቱን ማደስ
            bot.edit_message_text(f"✅ ቅሬታ ID `#{dispute_id}` ተፈቷል ተብሎ ተመዝግቧል።", 
                                  call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            
            # ደንበኛው ጋር ማሳወቂያ መላክ
            try:
                bot.send_message(customer_id, "🎉 **የቅሬታ መፍትሄ ማሳሰቢያ**\n\nያቀረቡት ቅሬታ በአድሚን ተመርምሮ ተፈቷል። ስለታገሱ እናመሰግናለን!")
            except:
                pass
        else:
            bot.answer_callback_query(call.id, "❌ ቅሬታው አልተገኘም ወይም ቀድሞ ተፈቷል።")

@bot.callback_query_handler(func=lambda call: call.data.startswith('switch_to_'))
def switch_mode_handler(call):
    user_id = call.from_user.id
    
    if call.data == "switch_to_rider":
        # አድሚን ዳሽቦርዱን አጥፍቶ የደላላውን ሜኑ ያመጣል
        bot.answer_callback_query(call.id, "አሁን በደላላነት ሁኔታ ላይ ነህ")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_rider_menu(call.message)

    elif call.data == "switch_to_admin":
        if user_id in ADMIN_IDS:
            # የደላላውን ሜኑ አጥፍቶ የአድሚን ዳሽቦርዱን ያመጣል
            bot.answer_callback_query(call.id, "ወደ አድሚን ዳሽቦርድ ተመልሰሃል")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "👑 **BDF አድሚን ዳሽቦርድ**", 
                             reply_markup=get_admin_dashboard(user_id), parse_mode="Markdown")

# --- 3. መረጃ ተቀባይ ሎጂኮች (Logic Functions) ---

# ሀ. የድርጅት ምዝገባ ቅደም ተከተል
def process_v_name(message):
    v_name = message.text.strip()
    if v_name.startswith('/'): return start_command(message)
    msg = bot.send_message(message.chat.id, f"🆔 የ '{v_name}' ባለቤት User ID ያስገቡ፦")
    bot.register_next_step_handler(msg, process_v_id, v_name)

def process_v_address(message, v_name, v_id):
    address = message.text.strip()
    if address.startswith('/'): return start_command(message)
    
    db = load_data()
    v_id_str = str(v_id)
    
    if v_id_str in db['vendors_list']:
        return bot.send_message(message.chat.id, f"⚠️ ይህ ድርጅት (ID: {v_id}) ቀድሞውኑ አለ።")
    
    db['vendors_list'][v_id_str] = {
        "name": v_name, 
        "address": address, 
        "deposit_balance": 0,
        "total_sales": 0, 
        "status": "active", 
        "items": {},
        "registered_date": str(time.ctime())
    }
    save_data(db)
    
    # ✅ እዚህ ጋር የ message.from_user.id መጨመር አለበት
    bot.send_message(
        message.chat.id, 
        f"✅ **{v_name}** ተመዝግቧል!", 
        reply_markup=get_admin_dashboard(message.from_user.id))


def process_fund_amount(message, v_id, v_name):
    # ተጠቃሚው ኮማንድ ከላከ ምዝገባውን ያቋርጣል
    if message.text and message.text.startswith('/'):
        return start_command(message)
        
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            msg = bot.send_message(message.chat.id, "⚠️ እባክዎ ከዜሮ በላይ የሆነ ቁጥር ያስገቡ፦")
            return bot.register_next_step_handler(msg, process_fund_amount, v_id, v_name)

        db = load_data()
        db['vendors_list'][v_id]['deposit_balance'] += amount
        save_data(db)

        # ወደ ዳሽቦርድ መመለሻ በተን
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))

        bot.send_message(message.chat.id, f"✅ {amount} ብር ለ **{v_name}** ተሞልቷል!", reply_markup=markup)
        
        # ለድርጅቱ ባለቤት ማሳወቂያ መላክ
        try:
            bot.send_message(v_id, f"🔔 **የሂሳብ ማሳሰቢያ**\n\nበ BDF አካውንትዎ ላይ {amount} ETB ዋስትና ተሞልቶልዎታል።")
        except:
            pass

    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ቁጥር ብቻ ያስገቡ (ለምሳሌ፦ 500)፦")
        bot.register_next_step_handler(msg, process_fund_amount, v_id, v_name)


# 1. ኮሚሽን መቀየሪያ
def save_new_commission(message):
    # ኮማንድ ከሆነ ምዝገባውን ያቋርጣል
    if message.text and message.text.startswith('/'):
        return start_command(message)
        
    try:
        new_rate = float(message.text.strip())
        # የኮሚሽን መጠኑ ከ 0 በታች ወይም ከ 100 በላይ እንዳይሆን መከላከል
        if 0 <= new_rate <= 100:
            db = load_data()
            db['settings']['commission_rate'] = new_rate
            save_data(db)
            bot.send_message(message.chat.id, f"✅ የቦቱ ኮሚሽን ወደ **{new_rate}%** ተቀይሯል።")
        else:
            msg = bot.send_message(message.chat.id, "⚠️ እባክዎ ከ 0 እስከ 100 ያለ ቁጥር ያስገቡ፦")
            bot.register_next_step_handler(msg, save_new_commission)
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ ቁጥር ብቻ ያስገቡ (ለምሳሌ፦ 10)፦")
        bot.register_next_step_handler(msg, save_new_commission)

# 2. የሁሉንም ድርጅቶች ቀሪ ዋስትና ማሳያ
def view_all_balances(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    
    if not vendors:
        return bot.send_message(call.message.chat.id, "📭 እስካሁን የተመዘገበ ድርጅት የለም።")
    
    report = "📉 **የድርጅቶች ቀሪ የዋስትና ሂሳብ**\n"
    report += "━━━━━━━━━━━━━━━\n"
    
    for vid, data in vendors.items():
        bal = data.get('deposit_balance', 0)
        # ሂሳባቸው ዝቅተኛ የሆኑትን በምልክት ለይቶ ማሳየት
        status_icon = "⚠️" if bal < 100 else "💰" 
        report += f"{status_icon} **{data['name']}**\n   └ ቀሪ፦ `{bal:,.2f} ETB`\n"
    
    report += "━━━━━━━━━━━━━━━"
    
    # ወደ ዳሽቦርድ መመለሻ በተን
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    
    bot.send_message(call.message.chat.id, report, reply_markup=markup, parse_mode="Markdown")

# 2. የቦቱን ጠቅላላ የተጣራ ትርፍ ማሳያ
def view_total_profit(call):
    db = load_data()
    profit = db.get("total_profit", 0)
    rate = db.get('settings', {}).get('commission_rate', 10)
    
    text = (f"📊 **የቦቱ የትርፍ ሪፖርት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📈 የወቅቱ የኮሚሽን መጠን፦ **{rate}%**\n"
            f"💰 ጠቅላላ የተጣራ ትርፍ፦ **{profit:,.2f} ETB**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 *ይህ ትርፍ ከእያንዳንዱ ትዕዛዝ ኮሚሽን የተጠራቀመ ነው።*")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")

# 3. ዋስትናቸው ሊያልቅ የደረሱ ድርጅቶች (Low Credit)
def view_low_balances(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    limit = 150 # የማስጠንቀቂያ ገደብ (threshold)
    
    low_list = []
    for vid, data in vendors.items():
        bal = data.get('deposit_balance', 0)
        if bal < limit:
            low_list.append(f"⚠️ **{data['name']}** (ID: `{vid}`)\n   └ ቀሪ፦ `{bal} ETB`")

    if not low_list:
        text = "✅ ሁሉም ድርጅቶች በቂ የዋስትና ሂሳብ አላቸው።"
    else:
        text = "🚨 **አስቸኳይ፦ ዋስትናቸው ሊያልቅ የደረሱ**\n\n" + "\n\n".join(low_list)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    
    bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

# 4. የቀጥታ ትዕዛዞች ክትትል (Live Orders)
def view_live_orders(call):
    db = load_data()
    orders = db.get("orders", {})
    
    # ሁኔታቸው "Pending" ወይም "On the way" የሆኑትን ብቻ መለየት
    active_orders = [f"🆔 `#{oid}` | 🏢 {o['vendor_name']} | 📍 {o['status']}" 
                     for oid, o in orders.items() if o['status'] in ["Pending", "On the way"]]

    if not active_orders:
        text = "📭 በአሁኑ ሰዓት ምንም አይነት የቀጥታ ትዕዛዝ የለም።"
    else:
        text = "📋 **በሂደት ላይ ያሉ ትዕዛዞች**\n\n" + "\n".join(active_orders)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 አድስ (Refresh)", callback_data="admin_live_orders"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")


# 2. የቦቱን ጠቅላላ ትርፍ ማሳያ
def view_total_profit(call):
    db = load_data()
    profit = db.get("total_profit", 0)
    rate = db.get('settings', {}).get('commission_rate', 5)
    
    text = (f"📊 **የቦቱ ትርፍ ሪፖርት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📉 የኮሚሽን መጠን፦ **{rate}%**\n"
            f"💰 ጠቅላላ የተጣራ ትርፍ፦ **{profit:,.2f} ETB**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 *ይህ ትርፍ ከእያንዳንዱ ሽያጭ ኮሚሽን የተሰበሰበ ነው።*")
            
    # ወደ ኋላ መመለሻ በተን
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))

    bot.answer_callback_query(call.id)
    try:
        # መልእክቱን እዛው ላይ ይቀይረዋል
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                              reply_markup=markup, parse_mode="Markdown")
    except:
        # ኤዲት ማድረግ ካልተቻለ አዲስ ይልካል
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")


# 3. ዋስትናቸው ሊያልቅ የደረሱ ድርጅቶች
def view_low_balances(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    limit = 200 # ማስጠንቀቂያ ጣሪያ
    
    low_list = [f"⚠️ {data['name']} - ቀሪ፦ {data.get('deposit_balance', 0)} ETB" 
                for vid, data in vendors.items() if data.get('deposit_balance', 0) < limit]
    
    text = "🚨 **ዋስትናቸው ሊያልቅ የደረሱ ድርጅቶች**\n\n" + "\n".join(low_list) if low_list else "✅ ሁሉም ድርጅቶች በቂ ዋስትና አላቸው።"
    
    # ወደ ዳሽቦርድ መመለሻ
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    
    # ቦቱ መልእክቱን Edit እንዲያደርገው ብናደርገው ዳሽቦርዱ ጽዱ ይሆናል
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")


# 4. የቀጥታ ትዕዛዞችን ማሳያ (Live Orders)
# 4. የቀጥታ ትዕዛዞችን ማሳያ (Live Orders)
def view_live_orders(call):
    db = load_data()
    orders = db.get("orders", {})
    
    # ሁኔታቸው ገና ያልተጠናቀቁትን ብቻ መለየት
    live_orders = {k: v for k, v in orders.items() if v['status'] in ["Pending", "On the way"]}
    
    if not live_orders:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 አድስ (Refresh)", callback_data="admin_live_orders"))
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
        return bot.edit_message_text("📭 በአሁኑ ሰዓት ምንም አይነት የቀጥታ ትዕዛዝ የለም።", 
                                     call.message.chat.id, call.message.message_id, 
                                     reply_markup=markup)
    
    text = "📋 **የቀጥታ ትዕዛዞች ዝርዝር**\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    for oid, odata in live_orders.items():
        # ሁኔታውን በኢሞጂ ለይቶ ማሳየት
        status_icon = "⏳" if odata['status'] == "Pending" else "🛵"
        text += (f"🆔 **ትዕዛዝ:** `#{oid}`\n"
                 f"🏢 **ድርጅት:** {odata['vendor_name']}\n"
                 f"👤 **ደንበኛ:** {odata['customer_name']}\n"
                 f"{status_icon} **ሁኔታ:** {odata['status']}\n"
                 f"------------------------\n")
    
    markup = types.InlineKeyboardMarkup()
    # አድሚኑ ገጹን ሳይዘጋ አዳዲስ ትዕዛዞችን እንዲያይ
    markup.add(types.InlineKeyboardButton("🔄 አድስ (Refresh)", callback_data="admin_live_orders"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")

# 5. ድርጅቶችን ወይም ደላላዎችን ለማገድ/ለመፍቀድ
def process_block_unblock(message):
    # ተጠቃሚው ኮማንድ ከላከ ይቋረጣል
    if message.text and message.text.startswith('/'):
        return start_command(message)

    target_id = message.text.strip()
    db = load_data()
    found = False
    target_category = ""

    # መጀመሪያ IDው በየትኛው ዝርዝር ውስጥ እንዳለ መለየት
    for category in ['vendors_list', 'riders_list']:
        if target_id in db.get(category, {}):
            target_category = category
            found = True
            break
            
    if found:
        current_status = db[target_category][target_id].get('status', 'active')
        new_status = 'blocked' if current_status != 'blocked' else 'active'
        db[target_category][target_id]['status'] = new_status
        save_data(db)
        
        # ምላሹን በሚያምር ሁኔታ ማሳየት
        status_text = "🚫 ታግዷል" if new_status == 'blocked' else "✅ ተፈቅዷል"
        bot.send_message(message.chat.id, f"👤 **ተሳታፊ፦** {db[target_category][target_id]['name']}\n🆔 **ID:** `{target_id}`\n⚙️ **ወቅታዊ ሁኔታ፦** {status_text}", 
                         parse_mode="Markdown", reply_markup=get_admin_dashboard(message.from_user.id))
        
        # ለታገደው/ለተፈቀደው ሰው ማሳወቂያ መላክ
        try:
            msg_to_user = "⚠️ መለያዎ በሲስተም አስተዳዳሪ ታግዷል።" if new_status == 'blocked' else "🎉 መለያዎ እንዲሰራ ተፈቅዷል። አሁን መጠቀም ይችላሉ።"
            bot.send_message(target_id, msg_to_user)
        except:
            pass # ተጠቃሚው ቦቱን Block ካደረገው Error እንዳይሰጥ
    else:
        bot.send_message(message.chat.id, "❌ ስህተት፦ ይህ ID በሲስተሙ ላይ አልተገኘም። እባክዎ በትክክል ያረጋግጡ።")

# 6. ሲስተሙን መቆለፊያ (System Lock)
def toggle_system_lock(call):
    db = load_data()
    # ያለውን ሁኔታ መቀልበስ (True ከሆነ False፣ False ከሆነ True ያደርገዋል)
    db['settings']['system_locked'] = not db['settings'].get('system_locked', False)
    save_data(db)
    
    current_lock = db['settings']['system_locked']
    status_text = "🔒 የታሸገ (Locked)" if current_lock else "🔓 ክፍት (Unlocked)"
    alert_msg = "ሲስተሙ ተዘግቷል! አሁን አዳዲስ ትዕዛዞችን መቀበል አይቻልም።" if current_lock else "ሲስተሙ ተከፍቷል! አሁን ትዕዛዞችን መቀበል ይቻላል።"

    # ወደ ዳሽቦርድ መመለሻ በተን
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))

    # አድሚኑ ሁኔታው መቀየሩን በ Popup እንዲያይ
    bot.answer_callback_query(call.id, f"የሲስተም ሁኔታ፦ {status_text}")
    
    bot.edit_message_text(f"⚠️ **የሲስተም መቆለፊያ ማሳወቂያ**\n\nአሁን ሲስተሙ፦ **{status_text}** ነው\n\n{alert_msg}", 
                          call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")

def process_order(message):
    db = load_data()
    if db['settings'].get('system_locked', False):
        return bot.send_message(message.chat.id, "🚫 **ይቅርታ!**\nሲስተሙ ለጊዜው ስለተቆለፈ አዳዲስ ትዕዛዞችን መቀበል አንችልም። እባክዎ ቆይተው ይሞክሩ።")
    
    # ... ሌላው የትዕዛዝ ሎጂክ እዚህ ይቀጥላል ...


# 7. የማስታወቂያ መላኪያ ሎጂክ (Broadcast)
def send_broadcast_logic(message):
    if message.text and message.text.startswith('/'): 
        return start_command(message)
    
    db = load_data()
    all_users = db.get("user_list", [])
    
    if not all_users: 
        return bot.send_message(message.chat.id, "⚠️ እስካሁን በቦቱ የተመዘገበ ተጠቃሚ የለም።")
    
    count = 0
    status_msg = bot.send_message(message.chat.id, "⏳ ማስታወቂያው ለሁሉም ተጠቃሚዎች እየተላከ ነው...")
    
    for user_id in all_users:
        try:
            bot.send_message(user_id, f"🔔 **ከ BDF የተላከ ማሳሰቢያ**\n\n{message.text}", parse_mode="Markdown")
            count += 1
            # ቴሌግራም እንዳያግደን ትንሽ ፍጥነት እንቀንሳለን
            time.sleep(0.40) 
        except:
            continue
    
    # የላክነውን የ "እየተላከ ነው" መልዕክት እናጠፋለን
    bot.delete_message(message.chat.id, status_msg.message_id)
    
    # ውጤቱን ማሳያና መመለሻ በተን
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ ተመለስ", callback_data="admin_main"))
    
    bot.send_message(message.chat.id, f"✅ ማስታወቂያው በሚገባ ተልኳል!\n\n📊 ጠቅላላ የደረሳቸው ተጠቃሚዎች፦ **{count}**", 
                     parse_mode="Markdown", reply_markup=markup)


def list_all_vendors(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    
    if not vendors:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
        return bot.edit_message_text("🏢 እስካሁን የተመዘገበ ድርጅት የለም።", 
                                     call.message.chat.id, 
                                     call.message.message_id, 
                                     reply_markup=markup)
    
    text = "🏢 **የአጋር ድርጅቶች ዝርዝር**\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    for vid, vdata in vendors.items():
        status = "✅" if vdata.get('status') == 'active' else "🚫"
        text += (f"{status} **ስም:** {vdata['name']}\n"
                 f"🆔 **ID:** `{vid}`\n"
                 f"📍 **አድራሻ:** {vdata.get('address', 'ያልተገለጸ')}\n"
                 f"📈 **ጠቅላላ ሽያጭ:** {vdata.get('total_sales', 0):,.2f} ETB\n"
                 f"------------------------\n")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    
    # መልዕክቱ በጣም ረጅም ከሆነ (ከ 4096 ካራክተር በላይ) እንዳይቆረጥ መጠንቀቅ ያስፈልጋል
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                              reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")


def view_pending_items(call):
    db = load_data()
    pending = db.get("pending_items", {}) 
    
    if not pending:
        # አድሚኑን ግራ እንዳይጋባ Popup መልዕክት ያሳየዋል
        return bot.answer_callback_query(call.id, "✅ በመጠባበቅ ላይ ያለ አዲስ እቃ የለም።", show_alert=True)
    
    for item_id, idata in pending.items():
        text = (f"📦 **አዲስ እቃ ለመመዝገብ ቀርቧል**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🏢 **ድርጅት:** {idata['vendor_name']}\n"
                f"🛍 **እቃ:** {idata['item_name']}\n"
                f"💰 **ዋጋ:** {idata['price']:,} ETB\n"
                f"📝 **መግለጫ:** {idata.get('description', 'የለም')}")
        
        markup = types.InlineKeyboardMarkup()
        # ማጽደቂያና መሰረዣ በተኖች
        markup.add(
            types.InlineKeyboardButton("✅ ፍቀድ", callback_data=f"approve_{item_id}"),
            types.InlineKeyboardButton("❌ ሰርዝ", callback_data=f"reject_{item_id}")
        )
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

def show_full_stats(call):
    db = load_data()
    orders = db.get("orders", {})
    
    # ሁኔታቸው "Completed" የሆኑትን ብቻ ሽያጭ መደመር
    total_sales = sum(o.get('total_price', 0) for o in orders.values() if o.get('status') == "Completed")
    
    # ተጨማሪ ጠቃሚ ቁጥሮችን ማውጣት
    total_vendors = len(db.get('vendors_list', {}))
    total_riders = len(db.get('riders_list', {}))
    active_riders = len([r for r in db.get('riders_list', {}).values() if r.get('is_online')])
    net_profit = db.get('total_profit', 0)

    text = (f"📊 **አጠቃላይ የቦቱ እንቅስቃሴ ሪፖርት**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 **ጠቅላላ ሽያጭ፦** `{total_sales:,.2f} ETB`\n"
            f"📈 **የቦቱ የተጣራ ትርፍ፦** `{net_profit:,.2f} ETB`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📦 **ጠቅላላ ትዕዛዞች፦** {len(orders)}\n"
            f"🏢 **የአጋር ድርጅቶች፦** {total_vendors}\n"
            f"🛵 **ጠቅላላ ደላላዎች፦** {total_riders} ({active_riders} ንቁ)\n"
            f"━━━━━━━━━━━━━━━")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                              reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")


def view_disputes(call):
    db = load_data()
    disputes = db.get("disputes", {})
    
    if not disputes:
        # አድሚኑን በ Popup ማሳወቅ
        return bot.answer_callback_query(call.id, "✅ ምንም አይነት የደንበኛ ቅሬታ የለም።", show_alert=True)
    
    for d_id, d_data in disputes.items():
        # የቅሬታውን ሁኔታ (Status) መፈተሽ (ለምሳሌ Pending ከሆነ)
        if d_data.get('status') == 'resolved':
            continue

        text = (f"❗ **አዲስ የደንበኛ ቅሬታ**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"👤 **ደንበኛ፦** {d_data['user_name']}\n"
                f"🆔 **የደንበኛ ID፦** `{d_data['user_id']}`\n"
                f"📦 **የትዕዛዝ ቁጥር፦** `#{d_data.get('order_id', 'ያልተጠቀሰ')}`\n\n"
                f"📝 **ጉዳዩ፦**\n_{d_data['issue']}_\n"
                f"━━━━━━━━━━━━━━━")
        
        markup = types.InlineKeyboardMarkup()
        # ለቅሬታው ምላሽ ለመስጠትና ለመዝጋት
        markup.add(
            types.InlineKeyboardButton("💬 ምላሽ ስጥ", callback_data=f"reply_dispute_{d_data['user_id']}"),
            types.InlineKeyboardButton("✅ ተፈቷል (Resolve)", callback_data=f"resolve_dispute_{d_id}")
        )
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

# መመለሻ በተን ለብቻው እንዲመጣ (ከተፈለገ)
    markup_back = types.InlineKeyboardMarkup()
    markup_back.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    bot.send_message(call.message.chat.id, "ከላይ ያሉትን ቅሬታዎች መርምረው እርምጃ ይውሰዱ።", reply_markup=markup_back)

def view_rider_status(call):
    db = load_data()
    riders = db.get("riders_list", {})
    
    if not riders:
        # አድሚኑን በ Popup ማሳወቅ ይቻላል
        return bot.answer_callback_query(call.id, "🛵 እስካሁን የተመዘገበ ዴሊቨሪ የለም።", show_alert=True)
    
    active_count = 0
    busy_count = 0
    report = "🛵 **የዴሊቨሪዎች ወቅታዊ ሁኔታ**\n"
    report += "━━━━━━━━━━━━━━━\n"
    
    for rid, rdata in riders.items():
        # ዳታው ባዶ ቢሆን እንኳ እንዳይቋረጥ .get() መጠቀም ይመረጣል
        is_online = rdata.get('is_online', False)
        status_icon = "🟢" if is_online else "🔴"
        
        current_work = rdata.get('status', 'Idle')
        work_status = "🏃 ስራ ላይ" if current_work == "Busy" else "⏳ ዝግጁ"
        
        if is_online: active_count += 1
        if current_work == "Busy": busy_count += 1
        
        report += (f"{status_icon} **{rdata.get('name', 'ያልታወቀ')}**\n"
                   f"   └ ሁኔታ፦ {work_status}\n"
                   f"   └ ስልክ፦ `{rdata.get('phone', 'የለም')}`\n"
                   f"------------------------\n")
    
    summary = (f"\n📊 **ማጠቃለያ**\n"
               f"✅ ኦንላይን፦ **{active_count}**\n"
               f"🏃 ስራ ላይ፦ **{busy_count}**\n"
               f"💤 ኦፍላይን፦ **{len(riders) - active_count}**")
    
    # መመለሻ በተን መጨመር
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
    
    bot.edit_message_text(report + summary, call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")


# 1. የደላላው ዋና ሜኑ
def show_rider_menu(message):
    # message.from_user.id የሚሰራው ከ message handler ሲመጣ ነው
    # ከ callback ሲመጣ ግን message.chat.id መጠቀም ይመረጣል
    user_id = message.from_user.id if hasattr(message, 'from_user') else message.chat.id
    rider_id = str(user_id)
    
    db = load_data()
    riders = db.get('riders_list', {})
    
    if rider_id in riders and riders[rider_id].get('status') != 'blocked':
        is_online = riders[rider_id].get('is_online', False)
        status_text = "🟢 ክፍት (Online)" if is_online else "🔴 ዝግ (Offline)"
        
        text = (f"🛵 **የዴሊቨሪ ማእከል**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"👤 ሰላም **{riders[rider_id].get('name')}**\n"
                f"📊 የወቅቱ ሁኔታህ፦ **{status_text}**\n"
                f"━━━━━━━━━━━━━━━")
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # 1. ሁኔታ መቀያየሪያ በተን
        toggle_label = "🔴 ራስህን ዝጋ (Offline)" if is_online else "🟢 ስራ ጀምር (Online)"
        markup.add(types.InlineKeyboardButton(toggle_label, callback_data="rider_toggle_status"))
        
        # 2. 💡 አዲሱ በተን፦ አድሚን ከሆነ ብቻ የሚታይ (Switch Back)
        if int(rider_id) in ADMIN_IDS:
            markup.add(types.InlineKeyboardButton("🔄 ወደ አድሚንነት ተመለስ", callback_data="switch_to_admin"))
        
        # 3. ሌሎች የደላላ ተግባራት
        markup.add(types.InlineKeyboardButton("📋 የእኔ ትዕዛዞች", callback_data="rider_my_orders"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "⚠️ **ይቅርታ!**\nአንተ እንደ ደላላ አልተመዘገብክም ወይም መለያህ ታግዷል።")

# 2. ሁኔታውን የሚቀይር የ Callback ሎጂክ
# ይህ በ callback_query_handler ውስጥ መካተት አለበት
@bot.callback_query_handler(func=lambda call: call.data == "rider_toggle_status")
def rider_status_manager(call):
    rider_id = str(call.from_user.id)
    db = load_data()
    
    if rider_id in db.get('riders_list', {}):
        # ሁኔታውን መቀልበስ (True ከሆነ False...)
        current = db['riders_list'][rider_id].get('is_online', False)
        db['riders_list'][rider_id]['is_online'] = not current
        save_data(db)
        
        new_status = not current
        status_msg = "አሁን ኦንላይን ነህ። ትዕዛዞች ይደርሱሃል!" if new_status else "አሁን ኦፍላይን ነህ። ትዕዛዝ አይላክልህም።"
        
        # Popup ማሳወቂያ
        bot.answer_callback_query(call.id, status_msg)
        
        # ሜኑውን እዛው ላይ ማደስ (Refresh)
        show_rider_menu(call.message) # ማሳሰቢያ፡ ይህ message object ይፈልጋል
        # ወይም ደግሞ edit_message_text መጠቀም ይቻላል





def add_category_logic(message):
    # 1. ኮማንድ ከሆነ ምዝገባውን ያቋርጣል
    if message.text and message.text.startswith('/'):
        return start_command(message)
    
    db = load_data()
    new_cat = message.text.strip()

    if not new_cat:
        msg = bot.send_message(message.chat.id, "⚠️ እባክዎ የምድብ ስም በትክክል ያስገቡ፦")
        return bot.register_next_step_handler(msg, add_category_logic)

    if "categories" not in db: 
        db["categories"] = []

    # 2. ተመሳሳይ ስም እንዳይደገም (Case-insensitive ቢሆን ይመረጣል)
    if new_cat not in db["categories"]:
        db["categories"].append(new_cat)
        save_data(db)
        
        # 3. አድሚን ዳሽቦርድን ከ user_id ጋር መጥራት
        bot.send_message(
            message.chat.id, 
            f"✅ ምድብ **'{new_cat}'** በሚገባ ተጨምሯል!", 
            reply_markup=get_admin_dashboard(message.from_user.id),
            parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id, f"⚠️ '{new_cat}' የሚባል ምድብ ቀድሞውኑ አለ።")


# 1. የድርጅት ምዝገባ ሂደት (የጠፋው ክፍል)
def process_v_id(message, v_name):
    v_id = message.text.strip()
    if not v_id.isdigit():
        msg = bot.send_message(message.chat.id, "❌ ስህተት፡ ID ቁጥር መሆን አለበት። ደግመው ይሞክሩ፦")
        return bot.register_next_step_handler(msg, process_v_id, v_name)
    
    msg = bot.send_message(message.chat.id, f"📍 የ '{v_name}' አድራሻ ያስገቡ፦")
    bot.register_next_step_handler(msg, process_v_address, v_name, v_id)

# 2. የተሻሻለ የ Callback አስተዳዳሪ (ሁሉንም የአድሚን ተግባራት በአንድ ላይ)
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def final_admin_manager(call):
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    uid = str(call.from_user.id)
    
    # 📝 መረጃ መቀበል የሚፈልጉ (Next Steps)
    if call.data == "admin_add_vendor":
        msg = bot.send_message(call.message.chat.id, "🏢 የድርጅቱን ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, process_v_name)
    elif call.data == "admin_add_rider":
        msg = bot.send_message(call.message.chat.id, "👤 የደላላውን ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, get_rider_id)
    elif call.data == "admin_manage_cats":
        msg = bot.send_message(call.message.chat.id, "📁 የአዲሱን ምድብ ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, add_category_logic)

    # 📊 ሪፖርትና ዝርዝር ማሳያዎች
    elif call.data == "admin_list_vendors": list_all_vendors(call)
    elif call.data == "admin_rider_status": view_rider_status(call)
    elif call.data == "admin_pending_approvals": view_pending_items(call)
    elif call.data == "admin_main":
        bot.edit_message_text("👑 **BDF አድሚን ዳሽቦርድ**", call.message.chat.id, call.message.message_id, 
                              reply_markup=get_admin_dashboard(call.from_user.id), parse_mode="Markdown")

def approve_item(call):
    item_id = call.data.replace("approve_", "")
    db = load_data()
    
    # 1. እቃው በፔንዲንግ ውስጥ መኖሩን ማረጋገጥ
    pending_items = db.get('pending_items', {})
    if item_id in pending_items:
        item_data = pending_items.pop(item_id) # ከፔንዲንግ አውጣው
        vendor_id = str(item_data['vendor_id'])
        
        # 2. ድርጅቱ በሲስተሙ መኖሩን ማረጋገጥ
        if vendor_id not in db.get('vendors_list', {}):
            return bot.answer_callback_query(call.id, "❌ ድርጅቱ በሲስተሙ ላይ አልተገኘም!", show_alert=True)
            
        # 3. ለድርጅቱ የእቃ መያዣ (items) ከሌለው መፍጠር
        if 'items' not in db['vendors_list'][vendor_id]:
            db['vendors_list'][vendor_id]['items'] = {}
            
        # እቃውን ወደ ድርጅቱ ዝርዝር መመዝገብ
        db['vendors_list'][vendor_id]['items'][item_id] = item_data
        save_data(db)
        
        # 4. ለአድሚኑ ማረጋገጫ መስጠት
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
        
        bot.edit_message_text(
            f"✅ **እቃው ጸድቋል!**\n\n"
            f"📦 **እቃ፦** {item_data['item_name']}\n"
            f"🏢 **ድርጅት፦** {item_data['vendor_name']}\n"
            f"💰 **ዋጋ፦** {item_data['price']:,} ETB", 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        # 5. ለድርጅቱ (ባለቤቱ) ማሳወቂያ መላክ
        try:
            bot.send_message(vendor_id, f"🎉 ደስ የሚል ዜና! እቃዎ **'{item_data['item_name']}'** በአድሚን ተመርምሮ ጸድቋል። አሁን ለሽያጭ ቀርቧል።")
        except:
            pass
    else:
        # እቃው ቀድሞ ተጸድቆ ከሆነ ወይም ከተሰረዘ
        bot.answer_callback_query(call.id, "⚠️ ይህ እቃ ቀድሞውኑ ተስተካክሏል።", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)


def reject_item(call):
    item_id = call.data.replace("reject_", "")
    db = load_data()
    
    # 1. እቃው በፔንዲንግ ውስጥ መኖሩን ማረጋገጥ
    pending_items = db.get('pending_items', {})
    if item_id in pending_items:
        # እቃውን ከፔንዲንግ ዝርዝር ውስጥ ማጥፋት
        item_data = pending_items.pop(item_id)
        save_data(db)
        
        # 2. ለአድሚኑ ማረጋገጫ መስጠት (ከመመለሻ በተን ጋር)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main"))
        
        bot.edit_message_text(
            f"❌ **እቃው ውድቅ ተደርጓል**\n\n"
            f"📦 **እቃ፦** {item_data['item_name']}\n"
            f"🏢 **ድርጅት፦** {item_data['vendor_name']}\n"
            f"📉 **ሁኔታ፦** ከዝርዝር ተሰርዟል", 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        # 3. ለድርጅቱ (ባለቤቱ) ማሳወቂያ መላክ
        try:
            bot.send_message(
                item_data['vendor_id'], 
                f"⚠️ **ማሳሰቢያ**\n\nያቀረቡት እቃ **'{item_data['item_name']}'** በአድሚን ተቀባይነት አላገኘም (ውድቅ ተደርጓል)። "
                f"እባክዎ መረጃዎችን አስተካክለው በድጋሚ ይሞክሩ።"
            )
        except:
            pass
    else:
        # እቃው ቀድሞ ተሰርዞ ከሆነ
        bot.answer_callback_query(call.id, "⚠️ ይህ እቃ ቀድሞውኑ ተሰርዟል።", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

def get_admin_dashboard_with_rider(user_id, db):
    # 1. መጀመሪያ ዋናውን የአድሚን ዳሽቦርድ በተኖች እናመጣለን
    # ማሳሰቢያ፡ get_admin_dashboard(user_id) ብለህ መጥራትህን እርግጠኛ ሁን
    markup = get_admin_dashboard(user_id) 
    
    uid_str = str(user_id)
    riders = db.get('riders_list', {})
    
    # 2. አድሚኑ በደላላነትም ተመዝግቦ ከሆነ የደላላ መቆጣጠሪያ በተን እንጨምራለን
    if uid_str in riders:
        is_online = riders[uid_str].get('is_online', False)
        status_label = "🟢 ስራ ላይ (Online)" if is_online else "🔴 ስራ ዝግ (Offline)"
        
        # የደላላውን ሁኔታ የሚቀይር በተን
        btn_rider_toggle = types.InlineKeyboardButton(f"🛵 {status_label}", callback_data="rider_toggle_status")
        
        # አድሚኑ ወደ ደላላ ሜኑ መግቢያ በተን (አማራጭ)
        btn_rider_menu = types.InlineKeyboardButton("📋 የደላላ ተግባራት", callback_data="rider_main_menu")
        
        # በተኖቹን በሁለተኛ ረድፍ እንጨምራቸዋለን
        markup.add(btn_rider_toggle, btn_rider_menu)
        
    return markup




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
