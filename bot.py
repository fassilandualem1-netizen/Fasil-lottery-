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
    
    # --- ምድብ 1: የፋይናንስ እና የዋስትና መቆጣጠሪያ ---
    finance_label = types.InlineKeyboardButton("--- 💰 ፋይናንስና ዋስትና ---", callback_data="none")
    btn_fund = types.InlineKeyboardButton("💳 ብር መሙያ (Fund)", callback_data="admin_add_funds")
    btn_balance = types.InlineKeyboardButton("📉 የሂሳብ ክትትል", callback_data="admin_monitor_balance")
    btn_profit = types.InlineKeyboardButton("💰 የኮሚሽን ትርፍ", callback_data="admin_profit_track")
    btn_low_credit = types.InlineKeyboardButton("⚠️ ዝቅተኛ ሂሳብ", callback_data="admin_low_credit")
    
    # --- ምድብ 2: የሽያጭ እና ኦፕሬሽን ---
    ops_label = types.InlineKeyboardButton("--- 📦 ኦፕሬሽን ---", callback_data="none")
    btn_live_orders = types.InlineKeyboardButton("📋 የቀጥታ ትዕዛዞች", callback_data="admin_live_orders")
    btn_pending = types.InlineKeyboardButton("📦 በመጠባበቅ ላይ ያሉ", callback_data="admin_pending_approvals")
    btn_cats = types.InlineKeyboardButton("📁 ምድቦች (Categories)", callback_data="admin_manage_cats")
    
    # --- ምድብ 3: ተሳታፊዎች እና ደህንነት ---
    security_label = types.InlineKeyboardButton("--- 🔐 ደህንነትና ተሳታፊዎች ---", callback_data="none")
    btn_vendors = types.InlineKeyboardButton("🏢 የአጋር ድርጅት", callback_data="admin_list_vendors")
    btn_riders = types.InlineKeyboardButton("🛵 የደላላዎች ሁኔታ", callback_data="admin_rider_status")
    btn_block = types.InlineKeyboardButton("🚫 አግድ/ፍቀድ", callback_data="admin_block_manager")
    btn_lock = types.InlineKeyboardButton("🔒 ሲስተም ዝጋ (Lock)", callback_data="admin_system_lock")
    
    # --- ምድብ 4: ድጋፍና ማስታወቂያ ---
    support_label = types.InlineKeyboardButton("--- 📣 ድጋፍና ማስታወቂያ ---", callback_data="none")
    btn_dispute = types.InlineKeyboardButton("💬 ቅሬታዎች", callback_data="admin_disputes")
    btn_reviews = types.InlineKeyboardButton("⭐ ግምገማዎች", callback_ደታ="admin_reviews")
    btn_broadcast = types.InlineKeyboardButton("📢 ማስታወቂያ ላክ", callback_data="admin_broadcast")
    
    # --- ምድብ 5: ሪፖርት ---
    report_label = types.InlineKeyboardButton("--- 📊 ሪፖርት ---", callback_data="none")
    btn_stats = types.InlineKeyboardButton("📈 ጠቅላላ ሪፖርት", callback_data="admin_full_stats")

    # በተኖቹን ወደ ማርክአፑ መጨመር
    markup.add(finance_label)
    markup.add(btn_fund, btn_balance)
    markup.add(btn_profit, btn_low_credit)
    
    markup.add(ops_label)
    markup.add(btn_live_orders, btn_pending)
    markup.add(btn_cats)
    
    markup.add(security_label)
    markup.add(btn_vendors, btn_riders)
    markup.add(btn_block, btn_lock)
    
    markup.add(support_label)
    markup.add(btn_dispute, btn_reviews)
    markup.add(btn_broadcast)
    
    markup.add(report_label)
    markup.add(btn_stats)
    
    return markup


# 2. የ /start ትዕዛዝ
@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        bot.clear_step_handler_by_chat_id(chat_id=user_id) # አዙሪቱን ይሰብራል
        
        # አድሚን ከሆነ
        if user_id in ADMIN_IDS:
            return bot.send_message(
                user_id, 
                "👑 **እንኳን ደህና መጡ የBDF አድሚን!**\nእባክዎ መቆጣጠሪያውን ይጠቀሙ፦", 
                reply_markup=get_admin_dashboard(), # ስሙ ተስተካክሏል
                parse_mode="Markdown"
            )

        # መደበኛ ተጠቃሚ ከሆነ
        welcome_text = f"ሰላም {message.from_user.first_name} 👋\nእንኳን ወደ BDF የዴሊቨሪ ቦት በደህና መጡ።"
        bot.send_message(user_id, welcome_text, reply_markup=get_main_menu())

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

# ሀ. በተኑ ሲጫን መጀመሪያ የድርጅቱን መለያ ይጠይቃል
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_funds")
def start_funding(call):
    # 1. መጀመሪያ የድርጅቱን ID ይጠይቃል
    msg = bot.send_message(call.message.chat.id, "🆔 እባክዎ ብር የሰጡትን የድርጅት User ID ያስገቡ፦")
    bot.register_next_step_handler(msg, process_fund_vendor_id)

def process_fund_vendor_id(message):
    vendor_id = message.text.strip()
    db = load_data()
    
    # ድርጅቱ መኖሩን ቼክ ያደርጋል
    if vendor_id in db.get("vendors_list", {}):
        msg = bot.send_message(message.chat.id, f"💵 ለድርጅት '{db['vendors_list'][vendor_id]['name']}' ስንት ብር ሰጡ?")
        bot.register_next_step_handler(msg, complete_funding, vendor_id)
    else:
        bot.send_message(message.chat.id, "❌ ስህተት፡ ይህ የድርጅት ID አልተመዘገበም።")

def complete_funding(message, vendor_id):
    try:
        amount = float(message.text)
        db = load_data()
        
        # ብሩን ይጨምራል (አንተ ለድርጅቱ የሰጠኸው ዋስትና)
        db['vendors_list'][vendor_id]['deposit_balance'] = db['vendors_list'][vendor_id].get('deposit_balance', 0) + amount
        
        # Redis ወይም ፋይል ላይ ሴቭ ያደርጋል
        save_data(db) 
        
        bot.send_message(message.chat.id, f"✅ ተሳክቷል!\n🏢 ድርጅት: {db['vendors_list'][vendor_id]['name']}\n💰 የታከለ ብር: {amount} ETB\n📉 አጠቃላይ ቀሪ ዋስትና: {db['vendors_list'][vendor_id]['deposit_balance']} ETB")
        
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ እባክዎ ቁጥር ብቻ ያስገቡ።")

@bot.callback_query_handler(func=lambda call: call.data == "admin_monitor_balance")
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


@bot.callback_query_handler(func=lambda call: call.data == "admin_profit_track")
def view_total_profit(call):
    db = load_data()
    profit = db.get("total_profit", 0)
    
    text = (f"💰 **ጠቅላላ የኮሚሽን ትርፍ**\n\n"
            f"ቦቱ ከሽያጮች የሰበሰበው ጠቅላላ ትርፍ፦\n"
            f"✨ **{profit} ETB** ✨")
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "admin_low_credit")
def view_low_balances(call):
    db = load_data()
    vendors = db.get("vendors_list", {})
    limit = 200 # ማስጠንቀቂያ የሚሰጥበት ጣሪያ
    
    low_list = []
    for vid, data in vendors.items():
        bal = data.get('deposit_balance', 0)
        if bal < limit:
            low_list.append(f"⚠️ {data['name']} - ቀሪ፦ {bal} ETB")
            
    if low_list:
        text = "🚨 **ዋስትናቸው ሊያልቅ የደረሱ ድርጅቶች**\n\n" + "\n".join(low_list)
    else:
        text = "✅ ሁሉም ድርጅቶች በቂ የዋስትና ሂሳብ አላቸው።"
        
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "admin_live_orders")
def view_live_orders(call):
    db = load_data()
    orders = db.get("orders", {})
    
    # "Pending" (ገና ያልተረከበ) ወይም "On the way" (መንገድ ላይ ያለ) የሆኑትን ብቻ መለየት
    live_orders = {k: v for k, v in orders.items() if v['status'] in ["Pending", "On the way"]}
    
    if not live_orders:
        return bot.send_message(call.message.chat.id, "📭 በአሁኑ ሰዓት ምንም አይነት የቀጥታ ትዕዛዝ የለም።")
    
    text = "📋 **የቀጥታ ትዕዛዞች ዝርዝር**\n\n"
    for oid, odata in live_orders.items():
        text += (f"🆔 ትዕዛዝ ቁጥር: #{oid}\n"
                 f"🏢 ድርጅት: {odata['vendor_name']}\n"
                 f"👤 ደንበኛ: {odata['customer_name']}\n"
                 f"📍 ሁኔታ: {odata['status']}\n"
                 f"------------------------\n")
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "admin_pending_approvals")
def view_pending_items(call):
    db = load_data()
    pending = db.get("pending_items", {}) 
    
    if not pending:
        return bot.send_message(call.message.chat.id, "✅ በመጠባበቅ ላይ ያለ አዲስ እቃ የለም።")
    
    for item_id, idata in pending.items():
        text = (f"📦 **አዲስ እቃ ለመመዝገብ ቀርቧል**\n\n"
                f"🏢 ድርጅት: {idata['vendor_name']}\n"
                f"🛍 እቃ: {idata['item_name']}\n"
                f"💰 ዋጋ: {idata['price']} ETB\n"
                f"📝 መግለጫ: {idata['description']}")
        
        # ለማጽደቅ ወይም ለመሰረዝ በተኖች
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ ፍቀድ (Approve)", callback_data=f"approve_{item_id}"),
            types.InlineKeyboardButton("❌ ሰርዝ (Reject)", callback_data=f"reject_{item_id}")
        )
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_cats")
def manage_categories(call):
    msg = bot.send_message(call.message.chat.id, "📁 ለመጨመር የሚፈልጉትን አዲስ ምድብ ስም ያስገቡ፦\n(ለምሳሌ፦ ፋርማሲ፣ ምግብ ቤት፣ ልብስ ቤት...)")
    bot.register_next_step_handler(msg, add_category_logic)

def add_category_logic(message):
    new_cat = message.text
    db = load_data()
    
    if "categories" not in db:
        db["categories"] = []
    
    if new_cat not in db["categories"]:
        db["categories"].append(new_cat)
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ምድብ '{new_cat}' በሚገባ ተጨምሯል!")
    else:
        bot.send_message(message.chat.id, "⚠️ ይህ ምድብ ቀድሞውኑ አለ።")


@bot.callback_query_handler(func=lambda call: call.data == "admin_list_vendors")
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

@bot.callback_query_handler(func=lambda call: call.data == "admin_rider_status")
def view_rider_status(call):
    db = load_data()
    riders = db.get("riders_list", {})
    
    active_riders = [r for r in riders.values() if r['is_online']]
    busy_riders = [r for r in riders.values() if r['status'] == "Busy"]
    
    text = (f"🛵 **የዴሊቨሪዎች ወቅታዊ ሁኔታ**\n\n"
            f"✅ ክፍት (Online): {len(active_riders)}\n"
            f"⏳ ስራ ላይ (Busy): {len(busy_riders)}\n"
            f"❌ ዝግ (Offline): {len(riders) - len(active_riders)}\n\n"
            f"ጠቅላላ የተመዘገቡ፦ {len(riders)}")
    
    bot.send_message(call.message.chat.id, text)

@bot.callback_query_handler(func=lambda call: call.data == "admin_block_manager")
def block_manager_start(call):
    msg = bot.send_message(call.message.chat.id, "🚫 ለማገድ ወይም ለመፍቀድ የሚፈልጉትን የሰው/የድርጅት User ID ያስገቡ፦")
    bot.register_next_step_handler(msg, process_block_unblock)

def process_block_unblock(message):
    target_id = message.text
    db = load_data()
    
    # መጀመሪያ ድርጅቶች ውስጥ ይፈልጋል፣ ካልሆነ ዴሊቨሪዎች ውስጥ
    found = False
    for category in ['vendors_list', 'riders_list']:
        if target_id in db.get(category, {}):
            current_status = db[category][target_id].get('status', 'active')
            new_status = 'blocked' if current_status != 'blocked' else 'active'
            db[category][target_id]['status'] = new_status
            found = True
            break
    
    if found:
        save_data(db)
        bot.send_message(message.chat.id, f"✅ የ ID {target_id} ሁኔታ ወደ **{new_status}** ተቀይሯል።")
    else:
        bot.send_message(message.chat.id, "❌ ስህተት፦ ይህ ID በሲስተሙ ላይ አልተገኘም።")


@bot.callback_query_handler(func=lambda call: call.data == "admin_system_lock")
def toggle_system_lock(call):
    db = load_data()
    # የነበረውን ሁኔታ ይገለብጠዋል (True ከሆነ False፣ False ከሆነ True)
    db['settings']['system_locked'] = not db['settings'].get('system_locked', False)
    save_data(db)
    
    status_text = "🔒 ዝግ (Locked)" if db['settings']['system_locked'] else "🔓 ክፍት (Unlocked)"
    bot.send_message(call.message.chat.id, f"⚠️ የሲስተሙ ሁኔታ ተቀይሯል። አሁን ሲስተሙ፦ **{status_text}** ነው")

# ደንበኛው ትዕዛዝ ሲጀምር የሚደረግ ቼክ (Logic)
# if db['settings']['system_locked']:
#     bot.send_message(user_id, "❌ ይቅርታ፣ ሲስተሙ ለጥገና ለጊዜው ተዘግቷል።")


@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def start_broadcast(call):
    msg = bot.send_message(call.message.chat.id, "📢 ለሁሉም ተጠቃሚዎች የሚተላለፈውን መልዕክት ይጻፉ፦")
    bot.register_next_step_handler(msg, send_broadcast_logic)

def send_broadcast_logic(message):
    db = load_data()
    all_users = db.get("user_list", []) # በቦቱ /start ያሉትን ሁሉ ID መያዝ አለበት
    
    count = 0
    for user_id in all_users:
        try:
            bot.send_message(user_id, f"🔔 **ከአድሚን የተላከ መልዕክት፦**\n\n{message.text}", parse_mode="Markdown")
            count += 1
        except:
            continue # ቦቱን Block ያደረጉ ካሉ ዝለላቸው
            
    bot.send_message(message.chat.id, f"✅ ማስታወቂያው ለ {count} ተጠቃሚዎች ተልኳል።")

@bot.callback_query_handler(func=lambda call: call.data == "admin_disputes")
def view_disputes(call):
    db = load_data()
    disputes = db.get("disputes", {})
    
    if not disputes:
        return bot.send_message(call.message.chat.id, "✅ ምንም አይነት የደንበኛ ቅሬታ የለም።")
    
    for d_id, d_data in disputes.items():
        text = (f"❗ **አዲስ ቅሬታ**\n"
                f"👤 ደንበኛ: {d_data['user_name']}\n"
                f"🆔 ትዕዛዝ: #{d_data['order_id']}\n"
                f"📝 ቅሬታ: {d_data['issue']}")
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ ተፈቷል", callback_data=f"resolve_{d_id}"))
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_reviews")
def view_reviews(call):
    db = load_data()
    reviews = db.get("reviews", [])
    
    if not reviews:
        return bot.send_message(call.message.chat.id, "⭐ እስካሁን የተሰጠ አስተያየት የለም።")
    
    text = "⭐ **የቅርብ ጊዜ አስተያየቶች**\n\n"
    for r in reviews[-5:]: # የመጨረሻዎቹን 5 ብቻ ለማሳየት
        text += f"🏢 {r['vendor_name']} ➡️ {r['stars']}⭐\n💬 {r['comment']}\n---\n"
        
    bot.send_message(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "admin_full_stats")
def show_full_stats(call):
    db = load_data()
    orders = db.get("orders", {})
    
    total_sales = sum(o['total'] for o in orders.values() if o['status'] == "Completed")
    total_orders = len(orders)
    profit = db.get("total_profit", 0)
    
    text = (f"📊 **አጠቃላይ የቦቱ እንቅስቃሴ**\n\n"
            f"💰 ጠቅላላ ሽያጭ: {total_sales} ETB\n"
            f"📈 የተጣራ ትርፍ (Commission): {profit} ETB\n"
            f"📦 ጠቅላላ የታዘዙ እቃዎች: {total_orders}\n"
            f"🏢 የተመዘገቡ ድርጅቶች: {len(db.get('vendors_list', {}))}\n"
            f"🛵 ንቁ ዴሊቨሪዎች: {len(db.get('riders_list', {}))}")
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")



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
