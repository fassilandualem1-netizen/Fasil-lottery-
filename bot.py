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
        # 'r' ሳይሆን 'redis' መሆን አለበት
        raw = redis.get("beu_delivery_db")
        if raw: 
            return json.loads(raw)
        
        # ዳታቤዙ ባዶ ከሆነ መጀመሪያ የሚፈጠሩ ነገሮች
        initial_data = {
            "vendors": {}, 
            "vendors_list": {}, # ይህ ለባለሱቆች መለያ ያስፈልጋል
            "orders": {}, 
            "items": {}, 
            "pending": {}, 
            "users": {}, 
            "total_profit": 0, 
            "settings": {"base_delivery": 50}
        }
        return initial_data
    except Exception as e:
        print(f"❌ Database Load Error: {e}")
        return {"vendors": {}, "vendors_list": {}, "orders": {}, "items": {}, "pending": {}, "users": {}, "total_profit": 0, "settings": {"base_delivery": 50}}

def save_data(data):
    try:
        # 'r' ሳይሆን 'redis' መሆን አለበት
        redis.set("beu_delivery_db", json.dumps(data))
    except Exception as e:
        print(f"❌ Database Save Error: {e}")


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
        types.InlineKeyboardButton("📁 ምድቦችን አደራጅ", callback_data="admin_manage_cats"),
        types.InlineKeyboardButton("📊 ጠቅላላ ሪፖርት", callback_data="admin_stats"),
        types.InlineKeyboardButton("🏢 አጋር ሱቆች", callback_data="admin_list_v"),
        types.InlineKeyboardButton("🛵 የደላላዎች ሁኔታ", callback_data="admin_riders"),
        types.InlineKeyboardButton("💰 የኮሚሽን ተመን", callback_data="admin_change_com"),
        types.InlineKeyboardButton("📦 በመጠባበቅ ላይ ያሉ", callback_data="admin_pending_items"),
        types.InlineKeyboardButton("🧹 ዳታቤዝ አጽዳ", callback_data="admin_clear_db")
    ]
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




def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True



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
