import os
import json
import hmac
import hashlib
import urllib.parse
from functools import wraps
from flask import Flask, request, jsonify
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

# የ Flask አፕሊኬሽን ማስነሻ
app = Flask(__name__)

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
            
            # የተረጋገጠውን ዳታ በ request object ላይ ማሰር (ለ APIዎቹ እንዲጠቅም)
            request.telegram_data = parsed_data
            
        except Exception as e:
            return jsonify({"status": "error", "message": "በደህንነት ማጣሪያ ላይ ስህተት ተፈጥሯል"}), 401
        return f(*args, **kwargs)
    return decorated_function

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
        result = redis.eval(lua_script, [balance_key, user_id], [amount])
        return result
    except Exception as e:
        print(f"LUA Wallet Error: {e}")
        return "ERROR"

def add_to_history(user_id: str, entry: dict):
    try:
        history_key = f"history:{user_id}"
        redis.lpush(history_key, json.dumps(entry))
        redis.ltrim(history_key, 0, 19)
    except Exception as e:
        print(f"Add History Error: {e}")

# ==========================================
# 🌐 API Routes (የፍላስክ ራውቶች)
# ==========================================

def get_user_id_from_request():
    """ከ Telegram init_data ውስጥ user_id ን የሚያወጣ አጭር ፋንክሽን"""
    try:
        user_json_str = request.telegram_data.get('user', ['{}'])[0]
        user_data = json.loads(user_json_str)
        return str(user_data.get('id'))
    except Exception:
        return None

# ለባላንስ የሚጠይቅ API (GET request)
@app.route('/api/get-balance', methods=['GET'])
@telegram_auth_required
def get_user_balance():
    user_id = get_user_id_from_request()
    if not user_id:
         return jsonify({"status": "error", "message": "የተጠቃሚ መረጃ አልተገኘም"}), 400
    
    # Redis ላይ ቼክ ማድረግ
    balance = redis.hget("users:balance", user_id) or "0"
    
    return jsonify({
        "status": "success",
        "balance": float(balance)
    })

# ለገንዘብ ማውጣት (Withdrawal) የሚጠይቅ API (POST request)
@app.route('/api/withdraw', methods=['POST'])
@telegram_auth_required
def withdraw():
    data = request.json
    amount = data.get('amount')
    
    # ⚠️ ሴኪዩሪቲ: user_id ን ከ ፎርም (frontend) ከመቀበል ይልቅ ከ Telegram መረጃ ማውጣት ይመረጣል!
    user_id = get_user_id_from_request()
    
    if not user_id or not amount:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400
    
    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({"status": "error", "message": "የተሳሳተ የገንዘብ መጠን"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "የገንዘብ መጠኑ ቁጥር መሆን አለበት"}), 400

    # የደህንነት ቼክ እና የሒሳብ ቅነሳ
    result = deduct_balance_safely(user_id, amount, "real")
    
    if result == "SUCCESS":
        # ታሪክ ውስጥ መመዝገብ
        add_to_history(user_id, {"action": "withdraw", "amount": amount, "status": "pending"})
        return jsonify({"status": "success", "message": "የማውጣት ጥያቄዎ ተቀባይነት አግኝቷል"})
    elif result == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ገንዘብ የለዎትም"})
    else:
        return jsonify({"status": "error", "message": "በሲስተሙ ላይ ችግር አጋጥሟል፣ እባክዎ ትንሽ ቆይተው ይሞክሩ"})

# ==========================================
# 🚀 ሰርቨሩን ለማስነሳት
# ==========================================
if __name__ == '__main__':
    # በ Render ወይም Heroku ላይ ፖርት አሳይን እንዲያደርግ
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
