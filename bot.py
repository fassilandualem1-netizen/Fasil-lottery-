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

        # መዋቅሩን ለፋይናንስ ቁጥጥር እንዲመች አድርገን እናስተካክለው
        initial_data = {
            "vendors_list": {},    # የድርጅቶች ዝርዝር (Wallet እዚህ ይገባል)
            "orders": {},          # የታዘዙ ትዕዛዞች
            "pending_items": {},   # አድሚን ያላጸደቃቸው እቃዎች
            "categories": [],      # የምድብ ዝርዝር
            "total_profit": 0,     # የአድሚን የተጣራ ኮሚሽን
            "settings": {
                "base_delivery": 50, 
                "commission_rate": 10,
                "system_locked": False # ሲስተሙን መዝጊያ
            }
        }
        return initial_data
    except Exception as e:
        print(f"❌ Database Load Error: {e}")
        return {"vendors_list": {}, "orders": {}, "categories": [], "settings": {"base_delivery": 50}}

def save_data(db):
    try:
        # ዳታውን ወደ Redis መላኪያ
        redis.set("bdf_delivery_db", json.dumps(db))
    except Exception as e:
        print(f"❌ Database Save Error: {e}")

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

def get_admin_dashboard():
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
    btn_set_commission = types.InlineKeyboardButton("⚙️ የኮሚሽን መጠን ቀይር", callback_data="admin_set_commission")
    btn_riders = types.InlineKeyboardButton("🛵 የደላላዎች ሁኔታ", callback_data="admin_rider_status")
    btn_block = types.InlineKeyboardButton("🚫 አግድ/ፍቀድ", callback_data="admin_block_manager")
    btn_lock = types.InlineKeyboardButton("🔒 ሲስተም ዝጋ (Lock)", callback_data="admin_system_lock")

    # ምድብ 4 & 5
    support_label = types.InlineKeyboardButton("--- 📣 ድጋፍና ማስታወቂያ ---", callback_data="none")
    btn_dispute = types.InlineKeyboardButton("💬 ቅሬታዎች", callback_data="admin_disputes")
    btn_reviews = types.InlineKeyboardButton("⭐ ግምገማዎች", callback_data="admin_reviews")
    btn_broadcast = types.InlineKeyboardButton("📢 ማስታወቂያ ላክ", callback_data="admin_broadcast")
    report_label = types.InlineKeyboardButton("--- 📊 ሪፖርት ---", callback_data="none")
    btn_stats = types.InlineKeyboardButton("📈 ጠቅላላ ሪፖርት", callback_data="admin_full_stats")

    # --- ወደ Markup መጨመር ---
    markup.add(finance_label)
    markup.add(btn_fund, btn_balance)
    markup.add(btn_profit, btn_low_credit)
    markup.add(ops_label)
    markup.add(btn_live_orders, btn_pending)
    markup.add(btn_cats)
    markup.add(security_label)
    markup.add(btn_add_vendor)
    markup.add(btn_vendors, btn_set_commission) # እዚህ ተስተካክሏል
    markup.add(btn_riders)
    markup.add(btn_block, btn_lock)
    markup.add(support_label)
    markup.add(btn_dispute, btn_reviews)
    markup.add(btn_broadcast)
    markup.add(report_label)
    markup.add(btn_stats)

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

        # --- ተጠቃሚውን ወደ ሊስት መጨመሪያ (እዚህ ቦታ መሆኑ ወሳኝ ነው) ---
        if "user_list" not in db: db["user_list"] = []
        if user_id not in db["user_list"]:
            db["user_list"].append(user_id)
            save_data(db)
        # --------------------------------------------------------

        if user_id in ADMIN_IDS:
            return bot.send_message(user_id, "👑 **እንኳን ደህና መጡ የBDF አድሚን!**", 
                                   reply_markup=get_admin_dashboard(), parse_mode="Markdown")

        if uid_str in db.get('vendors_list', {}):
            v_name = db['vendors_list'][uid_str]['name']
            return bot.send_message(user_id, f"እንኳን ደህና መጡ **{v_name}** 👋", 
                                   reply_markup=get_vendor_menu(), parse_mode="Markdown")

        welcome_text = f"ሰላም {message.from_user.first_name} 👋\nየመለያ ቁጥርዎ፦ `{user_id}`"
        bot.send_message(user_id, welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

    except Exception as e:
        print(f"❌ Error in start_command: {e}")




@bot.message_handler(commands=['admin'])
def show_admin_panel(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(
            message.chat.id, 
            "👑 **BDF አድሚን ዳሽቦርድ**",
            reply_markup=get_admin_dashboard(), # አሁን በላይኛው ፈንክሽን ይጠራል
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
