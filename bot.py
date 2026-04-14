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


from telebot import types

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
    btn_vendors = types.InlineKeyboardButton("🏢 የአጋር ሱቆች", callback_data="admin_list_vendors")
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

# አድሚኑ /admin ሲል የሚመጣ መልዕክት
@bot.message_handler(commands=['admin'])
def show_admin_panel(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(
            message.chat.id, 
            "👑 **እንኳን ወደ BDF አድሚን ዳሽቦርድ በደህና መጡ!**\nእባክዎ ከታች ካሉት አማራጮች አንዱን ይምረጡ፦",
            reply_markup=get_admin_dashboard(),
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(message, "❌ ይቅርታ፣ ይህንን ትዕዛዝ ለመጠቀም ፈቃድ የለዎትም።")



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
