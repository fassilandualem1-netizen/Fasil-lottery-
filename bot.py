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
