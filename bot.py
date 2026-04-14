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
    raw = r.get("beu_delivery_db")
    if raw: return json.loads(raw)
    return {"vendors": {}, "orders": {}, "items": {}, "pending": {}, "users": {}, "total_profit": 0, "settings": {"base_delivery": 50}}

def save_data(data):
    r.set("beu_delivery_db", json.dumps(data))

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def kb_admin_main():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🏬 አጋር ድርጅቶች", "📦 ትዕዛዞች", "📊 ሪፖርት", "👤 የኔ ፕሮፋይል", "⚙️ ሲስተም")
    return kb

@bot.message_handler(commands=['start'])
def start_command(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, f"👑 እንኳን ደህና መጡ አድሚን {message.from_user.first_name}!", reply_markup=kb_admin_main())
    else:
        # ለደንበኛው የሚሆን ሜኑ (ወደፊት የምንሰራው)
        bot.send_message(message.chat.id, "👋 እንኳን ወደ BDF በደህና መጡ!")

@bot.message_handler(func=lambda m: m.text == "👤 የኔ ፕሮፋይል")
def admin_personal_profile(message):
    if message.from_user.id not in ADMIN_IDS: return
    db = load_data()
    my_orders = [o for o in db["orders"].values() if o.get("driver_id") == message.from_user.id]
    completed = [o for o in my_orders if o["status"] == "Delivered"]
    
    total_cash = sum([o.get("total", 0) for o in completed])
    delivery_earnings = sum([o.get("delivery_fee", 0) for o in completed])
    
    text = (
        f"💳 **የአድሚን ፕሮፋይል**\n"
        f"👤 ስም፦ {message.from_user.first_name}\n"
        f"✅ ያደረሷቸው፦ {len(completed)}\n"
        f"💵 በእጅ ያለ ገንዘብ፦ {total_cash} ETB\n"
        f"🎁 የዴሊቨሪ ትርፍ፦ {delivery_earnings} ETB"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏬 አጋር ድርጅቶች")
def admin_vendor_menu(message):
    if message.from_user.id not in ADMIN_IDS: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ አዲስ ሱቅ መዝግብ", callback_data="admin_add_v"))
    markup.add(types.InlineKeyboardButton("📜 የሱቆች ዝርዝር/ሂሳብ", callback_data="admin_list_v"))
    bot.send_message(message.chat.id, "የአጋር ድርጅቶች መቆጣጠሪያ፦", reply_markup=markup)

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
    save_data(db)
    bot.send_message(message.chat.id, f"✅ {v_name} ተመዝግቧል!")


@bot.callback_query_handler(func=lambda call: call.data.startswith("claim_"))
def claim_order(call):
    oid = call.data.split("_")
    db = load_data()
    order = db["orders"][oid]
    
    if "driver_id" in order:
        return bot.answer_callback_query(call.id, "❌ ትዕዛዙ ተይዟል!")
    
    db["orders"][oid]["driver_id"] = call.from_user.id
    db["orders"][oid]["status"] = "On the way 🛵"
    save_data(db)
    
    addr = order["address_details"]
    details = f"📍 ኮንዶ፦ {addr['condo']}\n🧱 ብሎክ፦ {addr['block']} | 🚪 ቤት ቁጥር፦ {addr['house_no']}"
    
    bot.send_message(call.message.chat.id, f"✅ ትዕዛዝ #{oid} ተረክበዋል።\n{details}")
    bot.send_location(call.message.chat.id, order["location"]["lat"], order["location"]["lon"])

@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def finalize_order(call):
    oid = call.data.split("_")
    db = load_data()
    order = db["orders"][oid]
    
    if order["status"] == "Delivered": return

    # የኮሚሽን ስሌት
    db["total_profit"] += order["commission"]
    db["vendors"][order["vid"]]["wallet"] += (order["item_price"] - order["commission"])
    db["orders"][oid]["status"] = "Delivered"
    
    save_data(db)
    bot.edit_message_text(f"✅ ትዕዛዝ #{oid} ተጠናቋል። ሂሳብ ተሰልቷል።", call.message.chat.id, call.message.message_id)
    bot.send_message(order["customer_id"], "🎉 ትዕዛዝዎ ደርሷል! እናመሰግናለን።")



if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()
