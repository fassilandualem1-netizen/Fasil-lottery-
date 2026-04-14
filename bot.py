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

# --- 4. ዋና ዋና ቁልፎች ---
def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🏬 አጋር ድርጅቶች", "📦 ትዕዛዞች", "📊 ሪፖርት", "➕ እቃ ጨምር")
    return markup

def get_customer_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🏪 ሱቆችን ተመልከት", "🛍 የኔ ትዕዛዞች")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "👑 <b>የአድሚን ፓነል</b>\nሰላም ሾፌር!", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, "👋 እንኳን ወደ Beu-Style በደህና መጡ!", reply_markup=get_customer_keyboard())


# --- 1. ሱቅ መመዝገቢያ ---
@bot.callback_query_handler(func=lambda call: call.data == "add_vendor")
def add_v_start(call):
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

# --- 2. እቃ መጨመር (ሻጭ ይልካል -> አድሚን ያጸድቃል) ---
@bot.message_handler(func=lambda m: m.text == "➕ እቃ ጨምር")
def vendor_add_item(message):
    db = load_data()
    markup = types.InlineKeyboardMarkup()
    for vid, v in db["vendors"].items():
        markup.add(types.InlineKeyboardButton(v['name'], callback_data=f"it_to_{vid}"))
    bot.send_message(message.chat.id, "እቃው የትኛው ሱቅ ነው?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("it_to_"))
def step_photo(call):
    vid = call.data.split("_")
    msg = bot.send_message(call.message.chat.id, "📷 የእቃውን ፎቶ ይላኩ፦")
    bot.register_next_step_handler(msg, step_caption, vid)

def step_caption(message, vid):
    if not message.photo: return
    p_id = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "📝 ስምና ዋጋ ይላኩ (ምሳሌ፦ በርገር - 250)፦")
    bot.register_next_step_handler(msg, send_to_admin, vid, p_id)

def send_to_admin(message, vid, p_id):
    name, price = message.text.split("-")
    db = load_data(); iid = str(len(db["pending"]) + 100)
    db["pending"][iid] = {"vid": vid, "name": name.strip(), "price": int(price.strip()), "photo": p_id}
    save_data(db)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ ፍቀድ (Approve)", callback_data=f"ap_{iid}"))
    for admin in ADMIN_IDS:
        bot.send_photo(admin, p_id, caption=f"🔔 ማረጋገጫ\nሱቅ፦ {db['vendors'][vid]['name']}\nእቃ፦ {name}\nዋጋ፦ {price}", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ ለላኩት እቃ አድሚን ፍቃድ እየጠበቅን ነው...")


# --- 1. አድሚን ሲያጸድቅ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("ap_"))
def approve_final(call):
    iid = call.data.split("_"); db = load_data()
    if iid in db["pending"]:
        db["items"][iid] = db["pending"].pop(iid)
        save_data(db); bot.edit_message_caption("✅ እቃው ጸድቋል!", call.message.chat.id, call.message.message_id)

# --- 2. የደንበኛ ስልክ መቀበያ ---
@bot.message_handler(content_types=['contact'])
def contact_reg(message):
    db = load_data()
    db["users"][str(message.from_user.id)] = {"phone": message.contact.phone_number, "name": message.from_user.first_name}
    save_data(db); bot.send_message(message.chat.id, "✅ ተመዝግቧል!", reply_markup=get_customer_keyboard())

# --- 3. ትዕዛዝ ማጠናቀቂያ (Completed) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("finish_"))
def order_complete(call):
    oid = call.data.split("_"); db = load_data()
    if oid in db["orders"]:
        order = db["orders"][oid]; vid = order["vendor_id"]
        price = order["item_price"]; comm = (db["vendors"][vid]["commission"]/100) * price
        db["vendors"][vid]["wallet"] -= price; db["total_profit"] += comm
        order["status"] = "Completed"; save_data(db)
        bot.edit_message_text(f"✅ ተጠናቋል! ትርፍ፦ {comm} ETB", call.message.chat.id, call.message.message_id)

# --- 4. ሪፖርት ---
@bot.message_handler(func=lambda m: m.text == "📊 ሪፖርት")
def show_rep(message):
    if message.from_user.id in ADMIN_IDS:
        db = load_data(); txt = f"📊 ትርፍ፦ {db['total_profit']} ETB\n"
        for vid, v in db["vendors"].items(): txt += f"• {v['name']}፦ {v['wallet']} ETB\n"
        bot.send_message(message.chat.id, txt)

# --- 5. ቦቱን ማስነሻ ---
@server.route('/')
def h(): return "Active", 200
def run(): server.run(host='0.0.0.0', port=PORT)
if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()
