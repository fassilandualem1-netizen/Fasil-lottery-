import os
import json
import hmac
import hashlib
import urllib.parse
import datetime
from functools import wraps
from flask import request, jsonify
import telebot
from upstash_redis import Redis

# ==========================================
# ⚙️ Configuration (ማዋቀሪያዎች)
# ==========================================
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com"
ADMIN_ID = 8488592165

bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

# ==========================================
# 🛡️ Security Decorator (የደህንነት ማረጋገጫ)
# ==========================================
def telegram_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        init_data = request.headers.get('X-Telegram-Init-Data')
        if not init_data:
            return jsonify({"status": "error", "message": "ያልተፈቀደ ሙከራ! (Missing Authorization)"}), 401
        try:
            parsed_data = urllib.parse.parse_qs(init_data)
            if 'hash' not in parsed_data:
                return jsonify({"status": "error", "message": "ያልተፈቀደ ሙከራ! (Missing Signature)"}), 401

            hash_from_tg = parsed_data.pop('hash')[0]
            data_check_string = "\n".join([f"{k}={v[0]}" for k, v in sorted(parsed_data.items())])

            secret_key = hmac.new("WebAppData".encode(), TOKEN.encode(), hashlib.sha256).digest()
            calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

            if calculated_hash != hash_from_tg:
                return jsonify({"status": "error", "message": "የደህንነት ማረጋገጫ አልተሳካም! (Invalid Token)"}), 401

            # የተረጋገጠውን ዳታ በ request object ላይ ማሰር
            request.telegram_data = parsed_data

        except Exception as e:
            return jsonify({"status": "error", "message": "በደህንነት ማጣሪያ ላይ ስህተት ተፈጥሯል"}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_user_id_from_request():
    """ከ Telegram init_data ውስጥ user_id ን የሚያወጣ"""
    try:
        user_json_str = request.telegram_data.get('user', ['{}'])[0]
        user_data = json.loads(user_json_str)
        return str(user_data.get('id'))
    except Exception:
        return None

# ==========================================
# 🛠️ Atomic Wallet & History Helpers
# ==========================================
def deduct_balance_safely(user_id: str, amount: float, game_mode: str = "real") -> str:
    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    lua_script = """
    local balance = tonumber(redis.call('HGET', KEYS[1], KEYS[2]) or "0")
    local amount = tonumber(ARGV[1])
    if balance < amount then
        return "INSUFFICIENT"
    end
    redis.call('HINCRBYFLOAT', KEYS[1], KEYS[2], -amount)
    return "SUCCESS"
    """
    try:
        return redis.eval(lua_script, [balance_key, user_id], [amount])
    except Exception as e:
        print(f"LUA Wallet Error: {e}")
        return "ERROR"


def add_to_history(user_id: str, entry: dict):
    try:
        # 1. የኢትዮጵያን ሰዓት (UTC+3) ማዘጋጀት
        ethiopia_tz = datetime.timezone(datetime.timedelta(hours=3))
        
        # 2. ከየትኛውም ቦታ የመጣውን ሰዓት ወደ ትክክለኛው የኢትዮጵያ ሰዓት መተካት
        entry["date"] = datetime.datetime.now(ethiopia_tz).strftime("%Y-%m-%d %H:%M")
        
        # 3. ወደ ዳታቤዝ ማስገባት
        history_key = f"history:{user_id}"
        redis.lpush(history_key, json.dumps(entry))
        redis.ltrim(history_key, 0, 19)
    except Exception as e:
        print(f"Add History Error: {e}")

def update_history_tx_status(user_id: str, tx_id: str, status: str):
    try:
        history_key = f"history:{user_id}"
        raw_history = redis.lrange(history_key, 0, -1) or []
        updated = False
        new_history = []

        for item_raw in raw_history:
            try:
                # ዳታው bytes ከሆነ ወደ string መቀየር
                if isinstance(item_raw, bytes):
                    item_raw = item_raw.decode('utf-8')
                
                item = json.loads(item_raw)
                
                # 'item' Dictionary መሆኑን ማረጋገጥ
                if isinstance(item, dict):
                    if item.get("tx_id") == tx_id:
                        item["status"] = status
                        updated = True
                    new_history.append(json.dumps(item))
            except Exception:
                continue # የተበላሸ መረጃ ካለ ዝለለው

        if updated and new_history:
            redis.delete(history_key)
            # አዲስ List ማስገባት
            for item_json in reversed(new_history):
                redis.lpush(history_key, item_json)
                
    except Exception as e:
        print(f"Update History Error: {e}")


def save_user_withdraw_details(user_id: str, info: dict):
    try:
        redis.hset("users:withdraw_info", user_id, json.dumps(info))
    except Exception as e:
        print(f"Save Withdraw Info Error: {e}")

def get_user_withdraw_details(user_id: str):
    try:
        data = redis.hget("users:withdraw_info", user_id)
        return json.loads(data) if data else None
    except Exception as e:
        return None
