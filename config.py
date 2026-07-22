import os
import json
import hmac
import hashlib
import urllib.parse
import datetime
import secrets
from functools import wraps
from flask import request, jsonify
import telebot
from werkzeug.security import generate_password_hash, check_password_hash

# ==========================================
# ⚙️ Configuration (ማዋቀሪያዎች)
# ==========================================
# Mock token for testing (not a real one)
TOKEN = "dummy_token_for_testing"
# Mock in-memory Redis for testing
class MockRedis:
    def __init__(self):
        self.data = {}
        # Pre-populate sample matches with real competitions
        sample_matches = [
            # Ethiopian Premier League
            {
                "fixture": {
                    "id": "ethiopian-1",
                    "teams": {
                        "home": {"name": "Saint George SC"},
                        "away": {"name": "Fasil Kenema SC"}
                    },
                    "league": "Ethiopian Premier League",
                    "time": "16:00",
                    "date": "2026-07-22"
                },
                "odds": {
                    "home": 2.1,
                    "draw": 3.2,
                    "away": 3.5,
                    "dc_1x": 1.35,
                    "dc_12": 1.42,
                    "dc_x2": 1.68
                }
            },
            {
                "fixture": {
                    "id": "ethiopian-2",
                    "teams": {
                        "home": {"name": "Bahir Dar Kenema"},
                        "away": {"name": "Mekelle 70 Enderta"}
                    },
                    "league": "Ethiopian Premier League",
                    "time": "18:30",
                    "date": "2026-07-22"
                },
                "odds": {
                    "home": 1.8,
                    "draw": 3.5,
                    "away": 4.2,
                    "dc_1x": 1.28,
                    "dc_12": 1.36,
                    "dc_x2": 1.92
                }
            },
            {
                "fixture": {
                    "id": "ethiopian-3",
                    "teams": {
                        "home": {"name": "Hawassa City"},
                        "away": {"name": "Adama City"}
                    },
                    "league": "Ethiopian Premier League",
                    "time": "20:00",
                    "date": "2026-07-23"
                },
                "odds": {
                    "home": 2.5,
                    "draw": 3.0,
                    "away": 2.8,
                    "dc_1x": 1.43,
                    "dc_12": 1.32,
                    "dc_x2": 1.44
                }
            },
            # UEFA Conference League Qualification
            {
                "fixture": {
                    "id": "ucl-1",
                    "teams": {
                        "home": {"name": "FC Basel"},
                        "away": {"name": "Viking Stavanger"}
                    },
                    "league": "UEFA Conference League - Qualification",
                    "time": "19:00",
                    "date": "2026-07-23"
                },
                "odds": {
                    "home": 1.95,
                    "draw": 3.4,
                    "away": 3.8,
                    "dc_1x": 1.32,
                    "dc_12": 1.38,
                    "dc_x2": 1.78
                }
            },
            {
                "fixture": {
                    "id": "ucl-2",
                    "teams": {
                        "home": {"name": "Rosenborg BK"},
                        "away": {"name": "HJK Helsinki"}
                    },
                    "league": "UEFA Conference League - Qualification",
                    "time": "20:00",
                    "date": "2026-07-23"
                },
                "odds": {
                    "home": 2.2,
                    "draw": 3.3,
                    "away": 3.25,
                    "dc_1x": 1.4,
                    "dc_12": 1.41,
                    "dc_x2": 1.62
                }
            },
            # UEFA Champions League Qualification
            {
                "fixture": {
                    "id": "ucl-3",
                    "teams": {
                        "home": {"name": "Celtic FC"},
                        "away": {"name": "FC Midtjylland"}
                    },
                    "league": "UEFA Champions League - Qualification",
                    "time": "20:45",
                    "date": "2026-07-23"
                },
                "odds": {
                    "home": 1.75,
                    "draw": 3.6,
                    "away": 4.5,
                    "dc_1x": 1.25,
                    "dc_12": 1.31,
                    "dc_x2": 2.0
                }
            },
            # English Premier League
            {
                "fixture": {
                    "id": "epl-1",
                    "teams": {
                        "home": {"name": "Arsenal"},
                        "away": {"name": "Brighton"}
                    },
                    "league": "English Premier League",
                    "time": "15:00",
                    "date": "2026-07-24"
                },
                "odds": {
                    "home": 1.85,
                    "draw": 3.5,
                    "away": 4.2,
                    "dc_1x": 1.3,
                    "dc_12": 1.35,
                    "dc_x2": 1.9
                }
            },
            # La Liga
            {
                "fixture": {
                    "id": "laliga-1",
                    "teams": {
                        "home": {"name": "Real Betis"},
                        "away": {"name": "Real Sociedad"}
                    },
                    "league": "La Liga",
                    "time": "17:00",
                    "date": "2026-07-24"
                },
                "odds": {
                    "home": 2.4,
                    "draw": 3.2,
                    "away": 3.0,
                    "dc_1x": 1.42,
                    "dc_12": 1.34,
                    "dc_x2": 1.55
                }
            }
        ]
        self.data["cached_real_sports_odds"] = json.dumps(sample_matches)
        # Pre-populate user balance
        self.data["users:balance"] = {"999999": 1000.0, "123456789": 500.0}
    def hget(self, key, field):
        if key not in self.data:
            return None
        if not isinstance(self.data[key], dict):
            return None
        return self.data[key].get(field)
    def hgetall(self, key):
        if key not in self.data:
            return {}
        if not isinstance(self.data[key], dict):
            return {}
        return self.data[key]
    def hset(self, key, field, value):
        if key not in self.data:
            self.data[key] = {}
        self.data[key][field] = value
    def hincrbyfloat(self, key, field, amount):
        if key not in self.data:
            self.data[key] = {}
        current = float(self.data[key].get(field, 0))
        self.data[key][field] = current + amount
    def lrange(self, key, start, end):
        if key not in self.data:
            return []
        lst = self.data[key]
        if end == -1:
            end = len(lst)
        return lst[start:end]
    def lpush(self, key, value):
        if key not in self.data:
            self.data[key] = []
        self.data[key].insert(0, value)
    def ltrim(self, key, start, end):
        if key in self.data:
            if end == -1:
                self.data[key] = self.data[key][start:]
            else:
                self.data[key] = self.data[key][start:end+1]
    def scard(self, key):
        return len(self.data.get(key, set()))
    def sismember(self, key, value):
        return value in self.data.get(key, set())
    def sadd(self, key, value):
        if key not in self.data:
            self.data[key] = set()
        self.data[key].add(value)
    def srem(self, key, value):
        if key in self.data:
            self.data[key].discard(value)
    def get(self, key):
        return self.data.get(key)
    def set(self, key, value):
        self.data[key] = value
    def delete(self, key):
        if key in self.data:
            del self.data[key]
    def eval(self, script, keys, args):
        # Mock deduct balance safely
        if len(keys) >= 2 and len(args) >= 1:
            balance_key = keys[0]
            user_id = keys[1]
            amount = float(args[0])
            current = float(self.hget(balance_key, user_id) or 0)
            if current >= amount:
                self.hincrbyfloat(balance_key, user_id, -amount)
                return "SUCCESS"
            else:
                return "INSUFFICIENT"
        return "SUCCESS"

WEB_APP_URL = "https://sefer-bot.onrender.com"
ADMIN_ID = 8488592165
SPORTS_MATCHES_KEY = "sports:matches:list"

# Full list of sports markets
SPORTS_MARKETS = [
    {"key": "1", "label": "Home Win (1)"},
    {"key": "X", "label": "Draw (X)"},
    {"key": "2", "label": "Away Win (2)"},
    {"key": "1X", "label": "Double Chance: 1X (Home or Draw)"},
    {"key": "X2", "label": "Double Chance: X2 (Away or Draw)"},
    {"key": "12", "label": "Double Chance: 12 (Home or Away)"},
    {"key": "BTTS_YES", "label": "Both Teams to Score: Yes"},
    {"key": "BTTS_NO", "label": "Both Teams to Score: No"},
    {"key": "OVER_25", "label": "Total Goals Over 2.5"},
    {"key": "UNDER_25", "label": "Total Goals Under 2.5"},
    {"key": "OVER_15", "label": "Total Goals Over 1.5"},
    {"key": "UNDER_15", "label": "Total Goals Under 1.5"},
    {"key": "OVER_35", "label": "Total Goals Over 3.5"},
    {"key": "UNDER_35", "label": "Total Goals Under 3.5"},
    {"key": "DNB_1", "label": "Draw No Bet: Home Win"},
    {"key": "DNB_2", "label": "Draw No Bet: Away Win"},
    {"key": "FIRST_HALF_1", "label": "1st Half Home Win"},
    {"key": "FIRST_HALF_X", "label": "1st Half Draw"},
    {"key": "FIRST_HALF_2", "label": "1st Half Away Win"}
]

# ==========================================
# ⚽ Sports Match/Odds Helpers (for both web & Telegram bot)
# ==========================================
def get_all_sports_matches():
    """Get all stored sports matches, or default demo matches if none exist"""
    try:
        raw = redis.get(SPORTS_MATCHES_KEY)
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"Get matches failed: {e}")
    # Default demo matches (Ethiopian Premier League for local market)
    # Default odds helper
    def get_default_odds(base1=2.0, baseX=3.2, base2=2.8):
        return {
            "1": base1,
            "X": baseX,
            "2": base2,
            "1X": round(min(base1, baseX)*1.15, 2),
            "X2": round(min(baseX, base2)*1.15, 2),
            "12": round(min(base1, base2)*1.15, 2),
            "BTTS_YES": 1.85,
            "BTTS_NO": 1.95,
            "OVER_25": 1.75,
            "UNDER_25": 2.05,
            "OVER_15": 1.25,
            "UNDER_15": 3.5,
            "OVER_35": 2.5,
            "UNDER_35": 1.5,
            "DNB_1": round(base1*0.75, 2),
            "DNB_2": round(base2*0.75, 2),
            "FIRST_HALF_1": round(base1*1.3, 2),
            "FIRST_HALF_X": round(baseX*1.1, 2),
            "FIRST_HALF_2": round(base2*1.3, 2)
        }

    return [
        {
            "id": "match-1",
            "league": "Ethiopian Premier League",
            "home": "Saint George",
            "away": "Ethiopian Coffee",
            "start_time": int(time.time()) + 3600,
            "odds": get_default_odds(1.8, 3.4, 4.2),
            "active": True
        },
        {
            "id": "match-2",
            "league": "Ethiopian Premier League",
            "home": "Fasil Kenema",
            "away": "Bahir Dar Kenema",
            "start_time": int(time.time()) + 7200,
            "odds": get_default_odds(2.1, 3.2, 3.5),
            "active": True
        },
        {
            "id": "match-3",
            "league": "Ethiopian Premier League",
            "home": "Dedebit",
            "away": "Welayta Dicha",
            "start_time": int(time.time()) + 10800,
            "odds": get_default_odds(2.5, 3.1, 2.9),
            "active": True
        }
    ]


def save_sports_matches(matches):
    """Save sports matches to Redis"""
    try:
        redis.set(SPORTS_MATCHES_KEY, json.dumps(matches))
        return True
    except Exception as e:
        print(f"Save matches failed: {e}")
        return False

# Mock bot for testing
class MockBot:
    def __init__(self):
        pass
    def message_handler(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator
    def callback_query_handler(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator
    def reply_to(self, *args, **kwargs):
        pass
    def send_message(self, *args, **kwargs):
        pass
    def send_photo(self, *args, **kwargs):
        pass
    def edit_message_text(self, *args, **kwargs):
        pass
    def edit_message_caption(self, *args, **kwargs):
        pass
    def answer_callback_query(self, *args, **kwargs):
        pass
    def remove_webhook(self):
        pass
    def set_webhook(self, *args, **kwargs):
        pass

bot = MockBot()
redis = MockRedis()

# ==========================================
# 🛡️ Security Decorator (የደህንነት ማረጋገጫ)
# ==========================================
def telegram_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For testing: skip real auth and use mock user data
        request.telegram_data = {
            'user': ['{"id": 123456789, "first_name": "Test User"}']
        }
        return f(*args, **kwargs)
    return decorated_function

def get_user_id_from_request():
    """ከ Telegram initData ውስጥ user_id ን የሚያወጣ"""
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
    redis.call('HINCRBYFLOAT', KEYS[1], KEYS[2], -amount)
    return "SUCCESS"
    """
    try:
        return redis.eval(lua_script, [balance_key, user_id], [amount])
    except Exception as e:
        print(f"LUA Wallet Error: {e}")
        return "ERROR"


def get_balance_safely(user_id: str, game_mode: str = "real") -> float:
    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    try:
        balance_str = redis.hget(balance_key, user_id)
        return float(balance_str) if balance_str else 0.0
    except Exception as e:
        print(f"Get Balance Error: {e}")
        return 0.0


def add_balance_safely(user_id: str, amount: float, reason: str = "deposit", game_mode: str = "real") -> str:
    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    try:
        redis.hincrbyfloat(balance_key, user_id, amount)
        add_to_history(user_id, {
            "type": "deposit" if amount > 0 else "withdraw",
            "game": reason,
            "amount": abs(amount)
        })
        return "SUCCESS"
    except Exception as e:
        print(f"Add Balance Error: {e}")
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


# ==========================================
# 🔐 User Authentication (የተጠቃሚ ማረጋገጫ)
# ==========================================
def register_user(username: str, password: str, telegram_id: str = None, initial_balance: float = 0.0):
    """Register a new user with username/password, optional Telegram ID"""
    try:
        # Check if username already exists
        existing_user = redis.hget("users:by_username", username.lower())
        if existing_user:
            return {"status": "error", "message": "Username already exists"}
        
        # Create user data
        user_id = secrets.token_urlsafe(16)  # Generate unique user ID
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        
        user_data = {
            "id": user_id,
            "username": username.lower(),
            "password_hash": password_hash,
            "telegram_id": telegram_id,
            "created_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).isoformat(),
            "balance": initial_balance,
            "demo_balance": 0.0
        }
        
        # Save user
        redis.hset("users:by_id", user_id, json.dumps(user_data))
        redis.hset("users:by_username", username.lower(), user_id)
        
        if telegram_id:
            redis.hset("users:by_telegram_id", telegram_id, user_id)
        
        # Set initial balance
        redis.hset("users:balance", user_id, initial_balance)
        
        return {"status": "success", "user": user_data}
    except Exception as e:
        print(f"Register User Error: {e}")
        return {"status": "error", "message": "Registration failed"}


def login_user(username: str, password: str):
    """Login user with username/password"""
    try:
        # Get user ID from username
        user_id = redis.hget("users:by_username", username.lower())
        if not user_id:
            return {"status": "error", "message": "Invalid credentials"}
        
        # Get user data
        user_data_raw = redis.hget("users:by_id", user_id)
        if not user_data_raw:
            return {"status": "error", "message": "Invalid credentials"}
        
        user_data = json.loads(user_data_raw)
        
        # Check password
        if not check_password_hash(user_data.get("password_hash", ""), password):
            return {"status": "error", "message": "Invalid credentials"}
        
        # Check balance exists, add if missing
        current_balance = float(redis.hget("users:balance", user_id) or 0)
        
        # Update user data with latest balance
        user_data["balance"] = current_balance
        
        return {"status": "success", "user": user_data}
    except Exception as e:
        print(f"Login User Error: {e}")
        return {"status": "error", "message": "Login failed"}


def get_or_create_telegram_user(telegram_id: str, user_name: str = None, initial_balance: float = 100.0):
    """Get existing Telegram user or create new one"""
    try:
        # Check if user exists
        user_id = redis.hget("users:by_telegram_id", telegram_id)
        
        if user_id:
            # Get existing user
            user_data_raw = redis.hget("users:by_id", user_id)
            if user_data_raw:
                user_data = json.loads(user_data_raw)
                user_data["balance"] = float(redis.hget("users:balance", user_id) or 0)
                return {"status": "success", "user": user_data}
        
        # Create new user
        username = f"telegram_{telegram_id}"
        return register_user(username, secrets.token_urlsafe(16), telegram_id, initial_balance)
    except Exception as e:
        print(f"Get/Create Telegram User Error: {e}")
        return {"status": "error", "message": "Failed to get user"}


def request_password_reset(username: str):
    """Create password reset code"""
    try:
        user_id = redis.hget("users:by_username", username.lower())
        if not user_id:
            return {"status": "success", "message": "If username exists, a reset code has been generated"}
        
        # Generate reset code (expires after 1 hour)
        reset_code = secrets.token_urlsafe(16)
        reset_data = {"user_id": user_id, "expires_at": (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))) + datetime.timedelta(hours=1)).isoformat()}
        
        redis.hset("password_reset_codes", reset_code, json.dumps(reset_data))
        redis.expire(f"password_reset:{reset_code}", 3600)
        
        # In a real app, send this via email/SMS! For now, we'll just return it for testing
        print(f"[PASSWORD RESET] Code for {username}: {reset_code}")
        return {"status": "success", "message": "Reset code generated (check console for testing)", "reset_code": reset_code}
    except Exception as e:
        print(f"Request Password Reset Error: {e}")
        return {"status": "error", "message": "Failed to request reset"}


def confirm_password_reset(reset_code: str, new_password: str):
    """Confirm password reset with code"""
    try:
        reset_data_raw = redis.hget("password_reset_codes", reset_code)
        if not reset_data_raw:
            return {"status": "error", "message": "Invalid or expired reset code"}
        
        reset_data = json.loads(reset_data_raw)
        
        # Check expiration
        expires_at = datetime.datetime.fromisoformat(reset_data["expires_at"])
        if datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))) > expires_at:
            redis.hdel("password_reset_codes", reset_code)
            return {"status": "error", "message": "Reset code has expired"}
        
        # Get user data
        user_id = reset_data["user_id"]
        user_data_raw = redis.hget("users:by_id", user_id)
        if not user_data_raw:
            return {"status": "error", "message": "User not found"}
        
        user_data = json.loads(user_data_raw)
        
        # Update password
        user_data["password_hash"] = generate_password_hash(new_password, method='pbkdf2:sha256')
        redis.hset("users:by_id", user_id, json.dumps(user_data))
        
        # Delete used reset code
        redis.hdel("password_reset_codes", reset_code)
        
        return {"status": "success", "message": "Password reset successful"}
    except Exception as e:
        print(f"Confirm Password Reset Error: {e}")
        return {"status": "error", "message": "Failed to reset password"}
