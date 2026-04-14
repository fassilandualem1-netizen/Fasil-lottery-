import telebot
from telebot import types
import os, json, math, threading
from flask import Flask
from upstash_redis import Redis

# --- 1. ውቅረት ---
TOKEN = "8663228906:AAFsTC0fKqAVEWMi7rk59iSdfVD-1vlJA0Y"
REDIS_URL = "https://nice-kitten-98436.upstash.io"
REDIS_TOKEN = "gQAAAAAAAYCEAAIncDEyMWMyNjczNmZiNjM0NzlkODI4MmUyODAyZGIxNDI5N3AxOTg0MzY"
ADMIN_IDS = [5690096145, 7072611117,8488592165]
PORT = int(os.getenv("PORT", 8080))

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
server = Flask(__name__)

# --- 2. ዳታቤዝ ተግባራት ---
def load_data():
    raw = redis.get("beu_delivery_db")
    if raw: return json.loads(raw)
    return {"vendors": {}, "orders": {}, "items": {}, "pending": {}, "users": {}, "total_profit": 0}

def save_data(data):
    redis.set("beu_delivery_db", json.dumps(data))

# --- 3. ርቀት ማሰያ ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def kb_admin_main():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🏬 አጋር ድርጅቶች", "📦 ትዕዛዞች", "📊 ሪፖርት")
    return kb

def kb_vendor_main():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ እቃ ጨምር", "📉 የኔ ሽያጭ")
    return kb

def kb_customer_main():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🏪 ሱቆችን ተመልከት", "🛍 የኔ ትዕዛዞች")
    return kb

@bot.message_handler(commands=['start'])
def start_command(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "👑 <b>የአድሚን ፓነል</b>", reply_markup=kb_admin_main())
    else:
        bot.send_message(message.chat.id, "👋 እንኳን ወደ BDF በደህና መጡ!", reply_markup=kb_customer_main())


# --- ሱቅ መመዝገቢያ ---
@bot.message_handler(func=lambda m: m.text == "🏬 አጋር ድርጅቶች")
def admin_vendor_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ አዲስ ሱቅ መዝግብ", callback_data="admin_add_v"),
               types.InlineKeyboardButton("💳 ካዝና ሙላ", callback_data="admin_topup_v"))
    bot.send_message(message.chat.id, "ምን ማድረግ ይፈልጋሉ?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_v")
def start_add_v(call):
    msg = bot.send_message(call.message.chat.id, "📝 የሱቁን ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, save_v_name)

def save_v_name(message):
    v_name = message.text
    msg = bot.send_message(message.chat.id, f"📍 ለ '{v_name}' ሎኬሽን ይላኩ፦")
    bot.register_next_step_handler(msg, save_v_loc, v_name)

def save_v_loc(message, v_name):
    if not message.location: return
    db = load_data()
    v_id = str(len(db["vendors"]) + 1)
    db["vendors"][v_id] = {"name": v_name, "lat": message.location.latitude, "lon": message.location.longitude, "wallet": 0, "commission": 10}
    save_data(db); bot.send_message(message.chat.id, f"✅ {v_name} ተመዝግቧል!")

# --- እቃ መጨመር (ሻጭ) ---
@bot.message_handler(func=lambda m: m.text == "➕ እቃ ጨምር")
def vendor_add_item(message):
    db = load_data()
    markup = types.InlineKeyboardMarkup()
    for vid, v in db["vendors"].items():
        markup.add(types.InlineKeyboardButton(v['name'], callback_data=f"v_item_{vid}"))
    bot.send_message(message.chat.id, "የትኛው ሱቅ ነው?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_item_"))
def step_photo(call):
    vid = call.data.split("_")
    msg = bot.send_message(call.message.chat.id, "📷 የእቃውን ፎቶ ይላኩ፦")
    bot.register_next_step_handler(msg, step_details, vid)

def step_details(message, vid):
    if not message.photo: return
    p_id = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "📝 ስምና ዋጋ ይላኩ (ምሳሌ፦ በርገር - 250)፦")
    bot.register_next_step_handler(msg, send_approval, vid, p_id)

def send_approval(message, vid, p_id):
    try:
        name, price = message.text.split("-")
        db = load_data(); iid = str(len(db["pending"]) + 100)
        db["pending"][iid] = {"vid": vid, "name": name.strip(), "price": int(price.strip()), "photo": p_id}
        save_data(db)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ ፍቀድ (Approve)", callback_data=f"appr_{iid}"))
        for admin in ADMIN_IDS:
            bot.send_photo(admin, p_id, caption=f"🔔 ማረጋገጫ\nሱቅ፦ {db['vendors'][vid]['name']}\nእቃ፦ {name}\nዋጋ፦ {price}", reply_markup=markup)
        bot.send_message(message.chat.id, "⏳ ተልኳል! አድሚን ፍቃድ እየጠበቅን ነው...")
    except: bot.send_message(message.chat.id, "❌ ስህተት! 'ስም - ዋጋ' መሆኑን ያረጋግጡ።")


# --- ሱቆችን ማሳያ ---
@bot.message_handler(func=lambda m: m.text == "🏪 ሱቆችን ተመልከት")
def customer_vendors(message):
    db = load_data()
    markup = types.InlineKeyboardMarkup()
    for vid, v in db["vendors"].items():
        markup.add(types.InlineKeyboardButton(v['name'], callback_data=f"showitems_{vid}"))
    bot.send_message(message.chat.id, "የትኛው ሱቅ ማዘዝ ይፈልጋሉ?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("showitems_"))
def show_items(call):
    vid = call.data.split("_"); db = load_data()
    for iid, item in db.get("items", {}).items():
        if item["vid"] == vid:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"🛒 አዝዝ ({item['price']} ETB)", callback_data=f"buy_{iid}"))
            bot.send_photo(call.message.chat.id, item["photo"], caption=f"<b>{item['name']}</b>\nዋጋ፦ {item['price']} ETB", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def get_loc(call):
    iid = call.data.split("_")
    msg = bot.send_message(call.message.chat.id, "📍 ያሉበትን ቦታ (Location) ይላኩ፦")
    bot.register_next_step_handler(msg, calc_final, iid)

def calc_final(message, iid):
    if not message.location: return
    db = load_data(); item = db["items"][iid]; v = db["vendors"][item["vid"]]
    dist = calculate_distance(message.location.latitude, message.location.longitude, v['lat'], v['lon'])
    delivery = 50 if dist <= 1000 else 50 + ((dist - 1000) // 500) * 10
    total = item["price"] + delivery
    order_id = str(len(db["orders"]) + 1)
    db["orders"][order_id] = {"customer_id": message.from_user.id, "item_name": item["name"], "total": total, "status": "Pending"}
    save_data(db)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ ትዕዛዙን አረጋግጥ", callback_data=f"confirm_{order_id}"))
    bot.send_message(message.chat.id, f"💰 <b>ጠቅላላ ክፍያ፦ {total} ETB</b>\n(እቃ፦ {item['price']} + ማድረሻ፦ {delivery})\nማዘዝ ይፈልጋሉ?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("appr_"))
def admin_approve(call):
    iid = call.data.split("_"); db = load_data()
    if iid in db["pending"]:
        db["items"][iid] = db["pending"].pop(iid)
        save_data(db); bot.edit_message_caption("✅ እቃው ጸድቋል!", call.message.chat.id, call.message.message_id)

# --- Server Setup ---
@server.route('/')
def home(): return "Bot is Running", 200
def run(): server.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()
