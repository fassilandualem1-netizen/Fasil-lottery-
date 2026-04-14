import telebot
from telebot import types
import os
import json
import math
from flask import Flask
import threading
from upstash_redis import Redis

# --- 1. ውቅረት (Configuration) ---
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
    return {"vendors": {}, "orders": {}, "total_profit": 0}

def save_data(data):
    redis.set("beu_delivery_db", json.dumps(data))

# --- 3. ርቀት ማሰያ (Haversine Formula) ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # በሜትር
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# --- 4. አዝራሮች (Keyboards) ---
def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🏬 አጋር ድርጅቶች", "📦 ትዕዛዞች", "📊 ሪፖርት")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "👑 <b>የአድሚን ፓነል</b>\nሰላም ሾፌር!", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, "👋 እንኳን ወደ BDF በደህና መጡ!")

# --- 1. የአጋር ድርጅቶች ኢንላይን ሜኑ ---
def vendor_inline_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ አዲስ መዝግብ", callback_data="add_vendor"),
        types.InlineKeyboardButton("🗑 ሱቅ ሰርዝ", callback_data="del_vendor"),
        types.InlineKeyboardButton("💳 ካዝና (Wallet)", callback_data="topup_wallet")
    )
    return markup

@bot.message_handler(func=lambda m: m.text == "🏬 አጋር ድርጅቶች")
def vendor_section(message):
    if message.from_user.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "የአጋር ድርጅቶች መቆጣጠሪያ፦", reply_markup=vendor_inline_menu())

# --- 2. ሱቅ መመዝገብ ---
@bot.callback_query_handler(func=lambda call: call.data == "add_vendor")
def start_add_vendor(call):
    msg = bot.send_message(call.message.chat.id, "📝 የሱቁን ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, process_v_name)

def process_v_name(message):
    v_name = message.text
    msg = bot.send_message(message.chat.id, f"📍 ለ '{v_name}' ሎኬሽን (Location) ይላኩ፦")
    bot.register_next_step_handler(msg, process_v_loc, v_name)

def process_v_loc(message, v_name):
    if not message.location:
        bot.send_message(message.chat.id, "❌ ስህተት፡ እባክዎ ሎኬሽን ይላኩ።")
        return
    db = load_data()
    v_id = str(len(db["vendors"]) + 1)
    db["vendors"][v_id] = {"name": v_name, "lat": message.location.latitude, "lon": message.location.longitude, "wallet": 0, "commission": 10}
    save_data(db)
    bot.send_message(message.chat.id, f"✅ {v_name} ተመዝግቧል!")

# --- 3. ካዝና መሙያ ---
@bot.callback_query_handler(func=lambda call: call.data == "topup_wallet")
def list_vendors_wallet(call):
    db = load_data()
    markup = types.InlineKeyboardMarkup()
    for vid, vinfo in db["vendors"].items():
        markup.add(types.InlineKeyboardButton(f"{vinfo['name']} ({vinfo['wallet']} ETB)", callback_data=f"deposit_{vid}"))
    bot.edit_message_text("ባላንስ ለመሙላት ሱቅ ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("deposit_"))
def ask_amount(call):
    vid = call.data.split("_")
    msg = bot.send_message(call.message.chat.id, "💰 የሚሞላውን የብር መጠን ያስገቡ፦")
    bot.register_next_step_handler(msg, process_deposit, vid)

def process_deposit(message, vid):
    if not message.text.isdigit(): return
    amount = int(message.text)
    db = load_data()
    if vid in db["vendors"]:
        db["vendors"][vid]["wallet"] += amount
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ባላንስ ተሞልቷል!")

