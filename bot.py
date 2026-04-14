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
        
        # ዳታቤዙ ባዶ ከሆነ መጀመሪያ የሚፈጠሩ ነገሮች
        initial_data = {
            "vendors": {}, 
            "vendors_list": {}, 
            "orders": {}, 
            "items": {}, 
            "pending": {}, 
            "users": {}, 
            "categories": [], # <--- እዚህ ጋር ተጨምሯል
            "total_profit": 0, 
            "settings": {"base_delivery": 50}
        }
        return initial_data
    except Exception as e:
        print(f"❌ Database Load Error: {e}")
        # Error ቢፈጠር እንኳን ባዶ categories እንዲኖር ያደርጋል
        return {
            "vendors": {}, "vendors_list": {}, "orders": {}, 
            "items": {}, "pending": {}, "users": {}, 
            "categories": [], # <--- እዚህም መጨመር አለበት
            "total_profit": 0, "settings": {"base_delivery": 50}
        }

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
