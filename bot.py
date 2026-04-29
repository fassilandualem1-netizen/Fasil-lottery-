import telebot
from telebot import types
import os, json, math, threading, time
from flask import Flask
from upstash_redis import Redis



# --- 1. ውቅረት ---
TOKEN = "8663228906:AAFsTC0fKqAVEWMi7rk59iSdfVD-1vlJA0Y"
CHANNEL_ID = -1003962139457 
REDIS_URL = "https://nice-kitten-98436.upstash.io"
REDIS_TOKEN = "gQAAAAAAAYCEAAIncDEyMWMyNjczNmZiNjM0NzlkODI4MmUyODAyZGIxNDI5N3AxOTg0MzY"
ADMIN_IDS = [5690096145, 7072611117,8488592165]
PORT = int(os.getenv("PORT", 8080)) # Render የራሱን Port እዚህ ይሰጥሃል

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__) # ስሙን 'app' ብንለው ይሻላል

# --- 1. ጊዜያዊ ዳታ መያዣዎች (ከኮድህ መጀመሪያ ላይ ይሁኑ) ---
item_creation_data = {} 
temp_topup_data = {}
admin_temp_registration = {}


# --- 2. ሁሉንም ነገር Reset ማድረጊያ ፋንክሽን ---
def reset_user_state(user_id):
    """
    ተጠቃሚው ሂደቱን ሲያቋርጥ ወይም ኮማንድ ሲልክ 
    ጊዜያዊ መረጃዎችን ለማጽዳት ያገለግላል።
    """
    user_id_str = str(user_id)
    
    # ቴሌግራም የሚጠብቃቸውን ጥያቄዎች (Next Step Handlers) ያጸዳል
    bot.clear_step_handler_by_chat_id(chat_id=user_id)
    
    # የቬንደር እቃ መመዝገቢያ ዳታን ያጸዳል
    if user_id_str in item_creation_data:
        del item_creation_data[user_id_str]
    
    # የገንዘብ መሙያ (Top-up) ዳታን ያጸዳል
    if user_id in temp_topup_data:
        del temp_topup_data[user_id]
        
    print(f"🧹 State for {user_id} has been cleaned.")



@app.route('/')
def index():
    return "BDF Bot is running!"

def run_flask():
    # በ Render ላይ ስራ እንዲጀምር host እና port በትክክል መሰጠት አለባቸው
    app.run(host='0.0.0.0', port=PORT)

import json
from datetime import datetime
import threading
import time

# የዳታቤዝ መቆለፊያ (ለ Race Condition መከላከያ)
db_lock = threading.Lock()

def load_data():
    default_db = {
        "users": {},
        "riders_list": {},     
        "vendors_list": {}, 
        "orders": {},          
        "carts": {},           
        "categories": [],      
        "total_profit": 0,     
        "user_list": [],       
        "stats": {
            "total_vendor_comm": 0.0,
            "total_rider_comm": 0.0,
            "total_customer_comm": 0.0,
            "total_orders": 0
        },
        "settings": {
            "vendor_commission_p": 5,    
            "rider_commission_fixed": 5,
            "service_fee": 8,
            "rider_fixed_fee": 30,       
            "base_delivery": 50,
            "rain_mode": False,   # ✅ አዲስ የታከለ
            "rain_val": 25,       # ✅ አዲስ የታከለ
            "night_mode": False,  # ✅ አዲስ የታከለ
            "night_val": 15,      # ✅ አዲስ የታከለ
            "system_locked": False 
        }
    }

    try:
        raw = redis.get("bdf_delivery_db")
        if raw: 
            loaded_db = json.loads(raw)
            if not isinstance(loaded_db, dict):
                loaded_db = default_db

            # 🛠 ወሳኝ ክፍል፡ አዳዲስ ቁልፎች (እንደ stats ያሉት) በቆየው ዳታቤዝ ውስጥ 
            # ከሌሉ እንዲጨመሩ (Merge) ያደርጋል
            for key, value in default_db.items():
                if key not in loaded_db:
                    loaded_db[key] = value
                
                # በ settings ውስጥ ያሉ ንዑስ ቁልፎችንም ቼክ ለማድረግ
                if key == "settings":
                    for s_key, s_val in default_db["settings"].items():
                        if s_key not in loaded_db["settings"]:
                            loaded_db["settings"][s_key] = s_val
                            
            return loaded_db

        return default_db
    except Exception as e:
        print(f"❌ Database Load Error: {e}")
        return default_db


def save_data(db):
    """ዳታውን ወደ Redis ያስቀምጣል"""
    try:
        redis.set("bdf_delivery_db", json.dumps(db))
    except Exception as e:
        print(f"❌ Database Save Error: {e}")



SUB_CATEGORIES = {
    "🍴ምግብ ቤት": [
        "የፍስክ ምግቦች", "የፆም ምግቦች", "ፈጣን ምግቦች (በርገር/ፒዛ)", 
        "ፓስታና መኮሮኒ", "የባህል ምግቦች", "ቁርስ", "መጠጥ"
    ],
    "​🛍️ ሱፐርማርኬት": [
        "አትክልትና ፍራፍሬ", "የታሸጉ ምግቦች (ዘይት/ፓስታ)", "የወተት ተዋጽኦ", 
        "የንጽህና እቃዎች", "ጣፋጭና ብስኩት", "ቅመማ ቅመም", "የቤት እቃዎች"
    ],
    "🍹መጠጥ": [
        "ቢራ (ዳሽን/ሀበሻ/ጊዮርጊስ)", "ለስላሳ መጠጦች", 
        "ወይንና ውስኪ", "ጁስና የታሸገ ውሃ", "ሀገር በቀል መጠጦች"
    ],
    "💊 ፋርማሲ": [
        "የህመም ማስታገሻ", "የህጻናት እቃዎች (ዳይፐር/ወተት)", 
        "የመጀመሪያ እርዳታ", "ቪታሚኖችና ማሟያዎች", "የሴቶች ንጽህና መጠበቂያ"
    ],
    "💄ኮስሞቲክስ": [
        "ሽቶ", "ሜካፕ", "የቆዳ እንክብካቤ", 
        "የፀጉር እቃዎች", "የወንዶች መዋቢያ (Shaving)"
    ],
    "👕 ቡቲክ": [
        "የወንድ ልብስ", "የሴት ልብስ", "የህጻናት ልብስ", 
        "ጫማዎች", "ቦርሳና መለዋወጫዎች"
    ]
}

# ቬንደሩ መረጃውን ሞልቶ እስኪጨርስ በጊዜያዊነት የምንይዝበት
item_creation_temp = {}  



db = load_data()
v_id = "8443303643" # የአንተ ID
vendor_info = db.get('vendors_list', {}).get(v_id, {})
print(f"የተመዘገበው ምድብ፦ {vendor_info.get('category')}")
print(f"የዳታ አይነት፦ {type(vendor_info.get('category'))}")


import math
import json
from datetime import datetime

# --- 1. የዳታቤዝ ባካፕ (Backup Logic) ---
def backup_db_to_channel():
    """የሪዲዝ ዳታቤዝን ፋይል አድርጎ ወደ ቴሌግራም ቻናል ይልካል"""
    try:
        db = load_data()
        file_path = 'database_backup.json'
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
            
        with open(file_path, 'rb') as f:
            bot.send_document(
                CHANNEL_ID, 
                f, 
                caption=f"🔄 **BDF Delivery Backup**\n📅 ቀን፦ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
    except Exception as e:
        print(f"❌ Backup Error: {e}")

# --- 2. የርቀት ስሌት (Distance Calculation in KM) ---
def calculate_distance(lat1, lon1, lat2, lon2):
    """
    በሁለት ነጥቦች መካከል ያለውን ርቀት በ KM ያሰላል።
    ለመንገድ መታጠፊያዎች 30% (1.3x) ተጨማሪ ርቀት ይጨምራል።
    """
    try:
        if None in [lat1, lon1, lat2, lon2]:
            return -1
        
        # የምድር ራዲየስ በ KM
        R = 6371 
        
        dlat = math.radians(float(lat2) - float(lat1))
        dlon = math.radians(float(lon2) - float(lon1))
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # ቀጥታ ርቀት (Air Distance)
        air_dist = R * c
        
        # 📌 የመሬት ላይ መንገድ ማስተካከያ (1.3x Multiplier)
        road_distance = air_dist * 1.3
        
        return round(road_distance, 2) 

    except (ValueError, TypeError, ZeroDivisionError):
        return -1


def command_breaker(func):
    def wrapper(message, *args, **kwargs):
        # ማንኛውም መልዕክት ሲመጣ መጀመሪያ ትዕዛዝ መሆኑን ያያል
        if message.text and message.text.startswith('/'):
            bot.clear_step_handler_by_chat_id(message.chat.id)
            return send_welcome(message) # ወደ start ይወስደዋል
        
        # ትዕዛዝ ካልሆነ ግን ዋናውን ፋንክሽን ያሰራዋል
        return func(message, *args, **kwargs)
    return wrapper


@command_breaker
def save_commissions(message):
    try:
        # 1. ጽሁፉን በኮማ መከፋፈል እና ማጽዳት
        input_data = [x.strip() for x in message.text.split(",")]

        # 2. 3 ቁጥሮች መኖራቸውን ማረጋገጥ
        if len(input_data) != 3:
            msg = bot.reply_to(message, "⚠️ ስህተት፦ እባክዎ 3 ቁጥሮችን በኮማ በመለየት ያስገቡ።\nምሳሌ፦ 3, 5, 8")
            bot.register_next_step_handler(msg, save_commissions)
            return

        # 3. ቁጥሮቹን ወደ float መቀየር እና መመደብ
        v_comm, r_comm, c_comm = map(float, input_data)
        
        db = load_data()
        if 'settings' not in db: db['settings'] = {}
        
        # 4. ዳታቤዝ ላይ ማስቀመጥ
        db['settings']['vendor_commission_p'] = v_comm
        db['settings']['rider_commission_fixed'] = r_comm
        db['settings']['service_fee'] = c_comm
        
        save_data(db)
        
        # 5. ለአድሚኑ መልስ መላክ
        response = (
            f"✅ **ኮሚሽን በትክክል ተቀምጧል!**\n\n"
            f"🏢 ድርጅት፦ `{v_comm}%` \n"
            f"🛵 ራይደር፦ `{r_comm} ETB` \n"
            f"👤 ሰርቪስ፦ `{c_comm} ETB`"
        )
        bot.send_message(message.chat.id, response, parse_mode="Markdown")

        # 6. ወደ ቻናሉ መረጃ መላክ (Log)
        log_msg = (
            f"⚙️ **የኮሚሽን ለውጥ ተደርጓል!**\n\n"
            f"🏢 **የድርጅት፦** {v_comm}%\n"
            f"🛵 **የራይደር፦** {r_comm} ETB\n"
            f"👤 **ሰርቪስ ፊ፦** {c_comm} ETB"
        )
        try:
            bot.send_message(CHANNEL_ID, log_msg, parse_mode="Markdown")
        except Exception as e:
            print(f"ቻናል ላይ ሎግ መላክ አልተቻለም: {e}")

    except ValueError:
        msg = bot.reply_to(message, "❌ ስህተት፦ እባክዎ ቁጥሮችን ብቻ ያስገቡ (ለምሳሌ፦ 3, 5, 8)")
        bot.register_next_step_handler(msg, save_commissions)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት ተፈጥሯል፦ {e}")


def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True

def calculate_dynamic_delivery_fee(u_lat, u_lon, v_lat, v_lon):
    db = load_data()
    s = db.get('settings', {})

    # 1. ርቀቱን በ KM እናሰላለን (ከክፍል 4 ፋንክሽን የሚመጣ)
    dist_km = calculate_distance(u_lat, u_lon, v_lat, v_lon)
    
    if dist_km == -1: return 0, "ርቀት ሊታወቅ አልቻለም"

    # 2. የዋጋ መለኪያዎች (ከ Settings የሚመጡ)
    base_fee = float(s.get('base_delivery', 25))    # መነሻ (ለምሳሌ እስከ 1.5 ኪሜ)
    free_distance = float(s.get('free_km', 1.5))    # በመነሻው የሚሸፈን ርቀት
    per_km_fee = float(s.get('extra_per_km', 10))   # ከዛ በላይ ለሚጨምር በየ 1 ኪሜው
    
    # 3. የርቀት ዋጋ ስሌት (ተለዋዋጭ)
    if dist_km <= free_distance:
        distance_fee = base_fee
    else:
        # ለተጨማሪው ርቀት ብቻ ማስላት
        extra_distance = dist_km - free_distance
        distance_fee = base_fee + (extra_distance * per_km_fee)

    # 4. የአየር ሁኔታ እና የምሽት ክፍያ
    rain_extra = float(s.get('rain_val', 25)) if s.get('rain_mode') else 0
    night_extra = float(s.get('night_val', 15)) if s.get('night_mode') else 0

    total = distance_fee + rain_extra + night_extra

    # 5. ዝርዝር ማብራሪያ ለደንበኛው
    details = f"({distance_fee:.1f} ETB ርቀት [{dist_km}km]"
    if rain_extra > 0: details += f" + 🌧️{rain_extra:.0f}"
    if night_extra > 0: details += f" + 🌙{night_extra:.0f}"
    details += ")"

    return round(total, 2), details


def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True

from telebot import types

# ቦቱ ሲነሳ ሜኑ በተኑን እንዲያስተካክል
def set_bot_menu(bot):
    main_menu_commands = [
        types.BotCommand("start", "ቦቱን ለመጀመር / Reset"),
        types.BotCommand("help", "እርዳታ ለማግኘት")
    ]
    bot.set_my_commands(main_menu_commands)

# ቦቱን በምታነሳበት ጊዜ ጥራው
set_bot_menu(bot)



def get_admin_dashboard(user_id):
    try:
        db = load_data()
        markup = types.InlineKeyboardMarkup(row_width=2)

        # --- 1. በተኖቹን መፍጠር ---
        btn_broadcast = types.InlineKeyboardButton("📢 ማስታወቂያ", callback_data="admin_broadcast")
        btn_fund = types.InlineKeyboardButton("💳 ብር መሙያ", callback_data="admin_add_funds")
        btn_balance = types.InlineKeyboardButton("📉 ክትትል", callback_data="admin_monitor_balance")
        btn_profit = types.InlineKeyboardButton("💰 ትርፍ", callback_data="admin_profit_track")
        btn_system_reset = types.InlineKeyboardButton("🗑 Reset System", callback_data="admin_system_reset")
        btn_live_orders = types.InlineKeyboardButton("📋 ቀጥታ ትዕዛዝ", callback_data="admin_live_orders")
        btn_add_vendor = types.InlineKeyboardButton("➕ አዲስ ድርጅት", callback_data="admin_add_vendor")
        btn_add_rider = types.InlineKeyboardButton("➕ አዲስ driver", callback_data="admin_add_rider")
        btn_vendors = types.InlineKeyboardButton("🏢 ድርጅቶች", callback_data="admin_list_vendors")
        btn_view_cats = types.InlineKeyboardButton("📁 ምድቦች ማሳያ", callback_data="admin_view_categories")
        btn_add_cats = types.InlineKeyboardButton("➕ አዲስ ምድብ", callback_data="admin_manage_cats")
        btn_riders = types.InlineKeyboardButton("🛵 driver", callback_data="admin_rider_status")
        btn_set_commission = types.InlineKeyboardButton("⚙️ ኮሚሽን", callback_data="admin_set_commission")
        btn_delivery_settings = types.InlineKeyboardButton("🚚 ዴሊቨሪ ዋጋ/ሁኔታ", callback_data="admin_delivery_mgmt")
        btn_block = types.InlineKeyboardButton("🚫 አግድ/ፍቀድ", callback_data="admin_block_manager")
        btn_lock = types.InlineKeyboardButton("🔒 ሲስተም ዝጋ", callback_data="admin_system_lock")
        btn_stats = types.InlineKeyboardButton("📈 ሪፖርት", callback_data="admin_full_stats")
        
        # --- 2. ወደ ዋናው ሜኑ መመለሻ በተን ---
        btn_back_to_main = types.InlineKeyboardButton("🏠 ወደ ዋናው ሜኑ", callback_data="go_to_main_start")

        # --- 3. ወደ Markup መጨመር (በተዋረድ) ---
        markup.add(btn_broadcast)
        markup.add(btn_fund, btn_balance)
        markup.add(btn_profit, btn_system_reset)
        markup.add(btn_live_orders)
        
        # የዴሊቨሪ መቆጣጠሪያው
        markup.add(btn_delivery_settings) 
        
        markup.add(btn_view_cats, btn_add_cats) 
        markup.add(btn_stats) 
        markup.add(btn_add_vendor, btn_add_rider)
        markup.add(btn_vendors, btn_riders)
        markup.add(btn_set_commission, btn_block)
        markup.add(btn_lock)
        
        # መመለሻው ሁልጊዜ መጨረሻ ላይ እንዲሆን
        markup.add(btn_back_to_main)

        return markup

    except Exception as e:
        print(f"Error building dashboard: {e}")
        return None



def get_vendor_dashboard_elements(user_id):
    db = load_data()
    user_id_str = str(user_id)
    v_info = db.get('vendors_list', {}).get(user_id_str, {})
    
    v_name = v_info.get('name', 'ያልታወቀ ድርጅት')
    v_balance = float(v_info.get('deposit_balance', 0.0))
    v_rating = v_info.get('rating', 0.0)
    
    # 1. የባላንስ ማሳያ
    if v_balance < 0:
        balance_display = f"⚠️ አድሚኑ ሊከፍልዎት የሚገባ፦ {v_balance:,.2f} ETB"
    elif v_balance > 0:
        balance_display = f"💰 ቀሪ የቅድሚያ ክፍያ፦ {v_balance:,.2f} ETB"
    else:
        balance_display = f"💰 ባላንስ፦ 0.00 ETB"

    # 2. የእቃዎች ብዛት
    all_items = db.get('items', [])
    v_items_count = len([i for i in all_items if str(i.get('vendor_id')) == user_id_str])
    
    # 3. ንቁ ትዕዛዞች (Pending, Accepted ወይም Picked_up የሆኑትን ብቻ ይቆጥራል)
    all_orders = db.get('orders', [])
    active_orders = len([o for o in all_orders if str(o.get('vendor_id')) == user_id_str and o.get('status') in ['pending', 'accepted', 'picked_up']])

    # 4. የድርጅቱ ክፍት/ዝግ መሆን ሁኔታ
    is_open = v_info.get('is_open', True)
    status_text = "🟢 ክፍት (ለደንበኞች ይታያል)" if is_open else "🔴 ተዘግቷል (ትዕዛዝ አይቀበልም)"

    text = (
        f"🏠 **የድርጅት ዳሽቦርድ፦ {v_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌟 ደረጃ፦ {'ገና አልተሰጠም' if v_rating == 0 else f'⭐ {v_rating}'}\n"
        f"💰 ሁኔታ፦ {balance_display}\n"
        f"🔔 ንቁ ትዕዛዞች፦ `{active_orders}`\n"
        f"🛍️ ጠቅላላ እቃዎች፦ `{v_items_count}`\n"
        f"📊 ሁኔታ፦ {status_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 ስራ ለመጀመር ከታች ያሉትን በተኖች ይጠቀሙ፦"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # በተኖችን መጨመር
    markup.add(
        types.InlineKeyboardButton("🔔 አዲስ ትዕዛዞች", callback_data="vendor_view_orders"),
        types.InlineKeyboardButton("➕ እቃ ጨምር", callback_data="vendor_add_item")
    )
    markup.add(
        types.InlineKeyboardButton("📦 የእኔ እቃዎች", callback_data="vendor_my_items"),
        types.InlineKeyboardButton("📈 የሽያጭ ታሪክ", callback_data="vendor_sales_history")
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ መቆጣጠሪያ", callback_data="vendor_settings"),
        types.InlineKeyboardButton("🔄 አድስ", callback_data="vendor_refresh")
    )
    markup.add(types.InlineKeyboardButton("🏠 ወደ ዋናው ሜኑ", callback_data="go_to_main_start"))
    
    return text, markup



@bot.callback_query_handler(func=lambda call: call.data in ["vendor_refresh", "go_to_main_start"])
def vendor_dashboard_fast_fix(call):
    user_id = call.from_user.id
    user_id_str = str(user_id)
    
    # 1. መዘግየቱን ለማጥፋት (Clock ምልክቱን ለማንሳት)
    bot.answer_callback_query(call.id)
    
    # 2. የቆየ ጥያቄ ካለ ማጽዳት
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    reset_user_state(user_id)
    
    # 3. ዳታውን መጫን
    text, markup = get_vendor_dashboard_elements(user_id)
    
    try:
        # መጀመሪያ የነበረውን መልዕክት ለመቀየር ይሞክራል (ፈጣን ነው)
        bot.edit_message_text(text, user_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        # 'edit' ካልሰራ (ለምሳሌ ፎቶ የነበረበት መልዕክት ከሆነ) የድሮውን አጥፍቶ አዲስ ይልካል
        bot.delete_message(user_id, call.message.message_id)
        bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")


# --- 1. ሁሉንም ጊዜያዊ ዳታዎች ማጽጃ ፋንክሽን (መጀመሪያ ይሄ ይግባ) ---
def reset_user_state(user_id):
    user_id_str = str(user_id)
    # የቆዩ የ step handler (ጥያቄዎችን) ያጸዳል
    bot.clear_step_handler_by_chat_id(chat_id=user_id)

    # እቃ እየመዘገበ ከሆነ ዳታውን ያጠፋል
    if user_id_str in item_creation_data:
        del item_creation_data[user_id_str]

    # የገንዘብ መሙያ ዳታ ካለ ማጽዳት
    if user_id in temp_topup_data:
        del temp_topup_data[user_id]

    print(f"🧹 State for {user_id} has been cleaned.")

# --- 2. መመለሻ Handler (ይህንን ለብቻው ጨርሰው) ---
@bot.callback_query_handler(func=lambda call: call.data == "go_to_main_start")
def back_to_main_handler(call):
    # መጀመሪያ ሁኔታውን Reset እናደርጋለን
    reset_user_state(call.from_user.id)
    # ከዛ ወደ ዋናው ሜኑ እንወስደዋለን
    # እዚህ ጋር ሜኑህን የሚመልስ ኮድ ጨምር (ለምሳሌ send_welcome የሚለውን መጥራት)
    bot.answer_callback_query(call.id, "ወደ ዋናው ሜኑ ተመልሰዋል!")
    # ለምሳሌ፡ bot.edit_message_text("ዋና ሜኑ", call.message.chat.id, call.message.message_id)

# 1. መጀመሪያ ማንኛውንም ትዕዛዝ ሰብሮ የሚገባው Interceptor
@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'), content_types=['text'])
def handle_interrupt_commands(message):
    user_id = message.from_user.id
    # ማንኛውንም ቀጣይ ስቴፕ ሰብሮ ያጠፋል
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    reset_user_state(user_id)

    # ትዕዛዙ /start ከሆነ ወደ ዋናው ዳሽቦርድ ይልከዋል
    if message.text == '/start':
        return send_welcome(message)
    
    # ሌላ ኮማንድ ካለህ እዚህ መጨመር ትችላለህ (ለምሳሌ /help)

# 2. ዋናው የ /start እና የዳሽቦርድ ክፍል
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_id_str = str(user_id)
    db = load_data()

    # ሁሉንም ጊዜያዊ ዳታ እና Step Handler ያጸዳል
    reset_user_state(user_id)

    # 1. አድሚን ከሆነ
    if user_id in ADMIN_IDS:
        markup = get_admin_dashboard(user_id)
        return bot.send_message(user_id, "👋 ሰላም ጌታዬ! የ BDF መቆጣጠሪያ ፓነል ዝግጁ ነው።", reply_markup=markup, parse_mode="Markdown")

    # 2. ቬንደር (ድርጅት) መሆኑን ቼክ ማድረግ
    vendors_list = db.get('vendors_list', {})
    if user_id_str in vendors_list:
        v_info = vendors_list[user_id_str]
        if 'lat' not in v_info or 'lon' not in v_info:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(types.KeyboardButton("📍 የድርጅቱን መገኛ ላክ", request_location=True))
            return bot.send_message(user_id, 
                f"ሰላም {v_info.get('name')}! 👋\n\nእባክዎ መጀመሪያ የድርጅቱን ትክክለኛ መገኛ (Location) በመጫን ይላኩ።", 
                reply_markup=markup)
        text, markup = get_vendor_dashboard_elements(user_id)
        return bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")

    # 3. ሾፌር መሆኑን ቼክ ማድረግ
    drivers_list = db.get('drivers_list', {})
    if user_id_str in drivers_list:
        text, markup = get_driver_dashboard_elements(user_id) 
        return bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")

    # 4. ደንበኛ ከሆነ
    else:
        if is_user_complete(user_id_str):
            bot.send_message(user_id, "እንኳን ደህና መጡ! ምን ማዘዝ ይፈልጋሉ?", reply_markup=get_customer_main_markup())
        else:
            bot.send_message(user_id, "ወደ BDF በደህና መጡ! ለመመዝገብ ስልክና ሎኬሽን ያጋሩ።", reply_markup=get_customer_registration_markup())




@bot.message_handler(content_types=['location'])
def handle_vendor_location(message):
    user_id = message.from_user.id
    user_id_str = str(user_id)
    db = load_data()

    # 1. ቬንደር ከሆነ
    if user_id_str in db.get('vendors_list', {}):
        db['vendors_list'][user_id_str]['lat'] = message.location.latitude
        db['vendors_list'][user_id_str]['lon'] = message.location.longitude
        save_data(db)

        # እዚህ ጋር ReplyKeyboardRemove() ስላከልን ከታች ያለው ትልቅ በተን ይጠፋል
        bot.send_message(user_id, "✅ የድርጅቱ መገኛ በትክክል ተመዝግቧል!", 
                         reply_markup=types.ReplyKeyboardRemove())

        # 2. አሁን ዳሽቦርዱን እናሳየዋለን
        text, markup = get_vendor_dashboard_elements(user_id)
        bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")

    # 3. ደንበኛ ከሆነ
    elif user_id_str in db.get('users', {}):
        db['users'][user_id_str]['lat'] = message.location.latitude
        db['users'][user_id_str]['lon'] = message.location.longitude
        save_data(db)
        
        bot.send_message(user_id, "✅ መገኛዎ ተመዝግቧል።", 
                         reply_markup=types.ReplyKeyboardRemove())
        # የደንበኛ ሜኑ ካለህ እዚህ መጥራት ትችላለህ





@bot.message_handler(content_types=['photo'])
def get_photo_id(message):
    # ቦቱ የፎቶውን ID ይልክልሃል
    photo_id = message.photo[-1].file_id
    bot.reply_to(message, f"የዚህ ፎቶ File ID፦\n\n`{photo_id}`", parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "vendor_refresh")
def vendor_refresh_handler(call):
    user_id = call.from_user.id
    db = load_data()
    
    # አዳዲስ መረጃዎችን ከዳታቤዝ እናመጣለን
    text, markup = get_vendor_dashboard_elements(user_id)
    
    try:
        # ሜሴጁን edit እናደርገዋለን
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        # ለተጠቃሚው ትንሽ ማሳወቂያ ከላይ እንዲመጣለት
        bot.answer_callback_query(call.id, "🔄 መረጃው ታድሷል!")
        
    except Exception as e:
        # ለውጥ ከሌለ edit ማድረግ ስለማይችል የሚመጣውን error ለመከላከል
        bot.answer_callback_query(call.id, "ምንም አዲስ ለውጥ የለም።")



@bot.callback_query_handler(func=lambda call: call.data == "vendor_settings")
def vendor_settings_handler(call):
    db = load_data()
    v_id = str(call.from_user.id)
    v_info = db.get('vendors_list', {}).get(v_id, {})
    
    # ሁኔታውን ማረጋገጥ (ክፍት/ዝግ)
    is_open = v_info.get('is_open', True)
    status_text = "🟢 ክፍት (ትዕዛዝ ይቀበላል)" if is_open else "🔴 ዝግ (ትዕዛዝ አይቀበልም)"
    toggle_btn_text = "🔴 ድርጅቱን ዝጋ" if is_open else "🟢 ድርጅቱን ክፈት"

    text = (
        f"⚙️ **የድርጅት መቆጣጠሪያ፦ {v_info.get('name')}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 የአሁኑ ሁኔታ፦ {status_text}\n"
        f"📍 መገኛ (Location)፦ ተመዝግቧል ✅\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"ምን ማስተካከል ይፈልጋሉ?"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(toggle_btn_text, callback_data="vendor_toggle_open"),
        types.InlineKeyboardButton("📍 መገኛ (Location) ቀይር", callback_data="vendor_update_loc"),
        types.InlineKeyboardButton("📝 ስም ቀይር", callback_data="vendor_change_name"),
        types.InlineKeyboardButton("🏠 ወደ ዳሽቦርድ", callback_data="go_to_main_start")
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")



@bot.callback_query_handler(func=lambda call: call.data == "vendor_toggle_open")
def toggle_vendor_open(call):
    db = load_data()
    v_id = str(call.from_user.id)
    
    if v_id in db['vendors_list']:
        # ሁኔታውን ይገለብጠዋል
        current_status = db['vendors_list'][v_id].get('is_open', True)
        db['vendors_list'][v_id]['is_open'] = not current_status
        save_data(db)
        
        new_status = "ተከፍቷል" if not current_status else "ተዘግቷል"
        bot.answer_callback_query(call.id, f"✅ ድርጅቱ {new_status}!", show_alert=True)
        
        # ገጹን አፕዴት እናድርገው
        vendor_settings_handler(call)



@bot.callback_query_handler(func=lambda call: call.data == "vendor_update_loc")
def vendor_update_loc_start(call):
    # ኪቦርዱን እንዲልክለት እንጠይቃለን
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📍 አዲሱን መገኛ ላክ", request_location=True))
    
    msg = bot.send_message(call.message.chat.id, "እባክዎ አዲሱን የድርጅቱን መገኛ በተኑን በመጫን ይላኩ፦", reply_markup=markup)
    # ይህንን የሚቀበለው ከላይ በሰራኸው የ Location Handler ውስጥ ነው



@bot.callback_query_handler(func=lambda call: call.data == "vendor_sales_history")
def vendor_sales_history_handler(call):
    db = load_data()
    v_id = str(call.from_user.id)
    
    completed_orders = [o for o in db.get('orders', []) 
                        if str(o.get('vendor_id')) == v_id and o.get('status') == 'completed']
    
    if not completed_orders:
        return bot.answer_callback_query(call.id, "📊 እስካሁን የተጠናቀቀ ሽያጭ የለም።", show_alert=True)

    # የሽያጭ ማጠቃለያ
    total_sales = sum(float(o['total_price']) for o in completed_orders)
    total_net = sum(float(o.get('net_to_vendor', o['total_price'])) for o in completed_orders)

    report_text = (
        f"📈 **የሽያጭ ታሪክ ሪፖርት (GC)**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛍️ ጠቅላላ ትዕዛዞች፦ `{len(completed_orders)}`\n"
        f"💰 ጠቅላላ የሽያጭ ዋጋ፦ `{total_sales:,.2f} ETB`\n"
        f"💵 ለርስዎ የሚገባው (Net)፦ `{total_net:,.2f} ETB`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📜 **የመጨረሻዎቹ ዝርዝሮች፦**\n\n"
    )

    # የመጨረሻዎቹን 5 ዝርዝሮች ማሳየት
    for o in completed_orders[-5:]:
        report_text += (
            f"🆔 #{o['order_id']} | 📅 {o.get('completed_at', 'N/A')}\n"
            f"💵 ዋጋ፦ {o['total_price']} ETB\n"
            f"📉 ኮሚሽን፦ -{o.get('commission_taken', 0):,.2f}\n"
            f"💳 ሁኔታ፦ {'✅ የተከፈለ' if o.get('payment_status') == 'Paid' else '⏳ ያልተከፈለ'}\n"
            f"--------------------------\n"
        )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 ወደ ዳሽቦርድ", callback_data="go_to_main_start"))
    
    bot.edit_message_text(report_text, call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")




from datetime import datetime

def complete_order_and_record_sales(order_id):
    db = load_data()
    # ትዕዛዙን መፈለግ
    for order in db.get('orders', []):
        if str(order['order_id']) == str(order_id):
            if order['status'] == 'completed': return # አስቀድሞ ከተጠናቀቀ

            total = float(order['total_price'])
            # 1. ኮሚሽን ማስላት (ለምሳሌ 10%)
            commission_rate = 0.10 
            commission_amount = total * commission_rate
            
            # 2. ሰዓቱን በፈረንጅ (GC) መመዝገብ
            order['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            order['commission_taken'] = commission_amount
            order['net_to_vendor'] = total - commission_amount
            order['payment_status'] = 'Pending' # አድሚኑ ገና ለቬንደሩ አልከፈለውም
            order['status'] = 'completed'
            
            # 3. የቬንደሩን ባላንስ መቀነስ (አሁን ኔጋቲቭ ይሆናል)
            v_id = str(order['vendor_id'])
            current_bal = float(db['vendors_list'][v_id].get('deposit_balance', 0))
            db['vendors_list'][v_id]['deposit_balance'] = current_bal - total
            
            save_data(db)
            break







# 1. የቬንደር እቃዎችን በዝርዝር ማሳያ

@bot.callback_query_handler(func=lambda call: call.data == "vendor_my_items")
def view_vendor_categories(call):
    db = load_data()
    v_id = str(call.from_user.id)

    # የዚህ ቬንደር የሆኑ እቃዎችን መለየት
    my_items = [i for i in db.get('items', []) if str(i.get('vendor_id')) == v_id]

    if not my_items:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ እቃ ጨምር", callback_data="vendor_add_item"))
        markup.add(types.InlineKeyboardButton("⬅️ ወደ ዳሽቦርድ", callback_data="go_to_vendor_dashboard"))
        return bot.edit_message_text("📦 እስካሁን ምንም የተመዘገበ እቃ የለም።", 
                                    call.message.chat.id, call.message.message_id, reply_markup=markup)

    # እቃዎቹ ያሉባቸውን ምድቦች ብቻ ለይቶ ማውጣት
    categories = sorted(list(set(i.get('category', 'ያልተመደበ') for i in my_items)))

    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        markup.add(types.InlineKeyboardButton(f"📁 {cat}", callback_data=f"v_view_cat_{cat}"))

    markup.add(types.InlineKeyboardButton("⬅️ ወደ ዳሽቦርድ", callback_data="go_to_vendor_dashboard"))

    bot.edit_message_text("📍 እቃዎችን ለማየት ምድብ ይምረጡ፦", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup)




@bot.callback_query_handler(func=lambda call: call.data.startswith("v_view_cat_"))
def show_items_in_category(call):
    selected_cat = call.data.replace("v_view_cat_", "")
    db = load_data()
    v_id = str(call.from_user.id)
    
    # በምድቡ ስር ያሉትን እቃዎች ብቻ መለየት
    cat_items = [i for i in db.get('items', []) 
                 if str(i.get('vendor_id')) == v_id and i.get('category') == selected_cat]

    bot.delete_message(call.message.chat.id, call.message.message_id)

    for item in cat_items:
        item_id = item['id']
        is_active = item.get('status', 'active') == 'active'
        status_icon = "🟢" if is_active else "🔴"
        toggle_label = "🔴 አልቋል በል" if is_active else "🟢 አለ በል"

        caption = (
            f"🛍️ **እቃ፦ {item['name']}**\n"
            f"💰 ዋጋ፦ {item['price']} ETB\n"
            f"📊 ሁኔታ፦ {status_icon} {'አለ' if is_active else 'አልቋል'}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton(toggle_label, callback_data=f"tog_itm_{item_id}"))
        markup.add(types.InlineKeyboardButton("✏️ ዋጋ", callback_data=f"edit_prc_{item_id}"),
                   types.InlineKeyboardButton("🗑️ አጥፋ", callback_data=f"del_itm_{item_id}"))

        if item.get('photo') and item['photo'] != "no_photo":
            bot.send_photo(call.message.chat.id, item['photo'], caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")

    # ወደ ምድብ መመለሻ በተን
    back_markup = types.InlineKeyboardMarkup()
    back_markup.add(types.InlineKeyboardButton("🔙 ወደ ምድቦች ተመለስ", callback_data="vendor_my_items"))
    bot.send_message(call.message.chat.id, f"እነዚህ የ '{selected_cat}' ምድብ እቃዎች ናቸው።", reply_markup=back_markup)

# 2. የእቃውን ሁኔታ (አለ/አልቋል) መቀያየሪያ
@bot.callback_query_handler(func=lambda call: call.data.startswith("tog_itm_"))
def toggle_item_status(call):
    item_id = call.data.replace("tog_itm_", "")
    db = load_data()
    
    item_found = False
    for item in db.get('items', []):
        if str(item['id']) == str(item_id):
            item_found = True
            # ሁኔታውን መቀልበስ
            current_status = item.get('status', 'active')
            item['status'] = 'out_of_stock' if current_status == 'active' else 'active'
            save_data(db)
            
            is_active = item['status'] == 'active'
            status_icon = "🟢" if is_active else "🔴"
            status_text = "አለ" if is_active else "አልቋል"
            toggle_label = "🔴 አልቋል በል" if is_active else "🟢 አለ በል"
            
            caption = (
                f"🛍️ **እቃ፦ {item['name']}**\n"
                f"💰 ዋጋ፦ {item['price']} ETB / {item.get('unit', 'Pcs')}\n"
                f"📊 ሁኔታ፦ {status_icon} {status_text}\n"
                f"📂 ምድብ፦ {item.get('category', 'ያልታወቀ')}\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton(toggle_label, callback_data=f"tog_itm_{item_id}"))
            markup.add(
                types.InlineKeyboardButton("✏️ ዋጋ ቀይር", callback_data=f"edit_prc_{item_id}"),
                types.InlineKeyboardButton("🗑️ አጥፋ", callback_data=f"del_itm_{item_id}")
            )
            
            # ካርዱን አፕዴት ማድረግ (Edit)
            try:
                if item.get('photo') and item['photo'] != "no_photo":
                    bot.edit_message_caption(caption, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
                else:
                    bot.edit_message_text(caption, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception as e:
                print(f"Update Error: {e}")
            
            bot.answer_callback_query(call.id, f"✅ ወደ '{status_text}' ተቀይሯል")
            break
            
    if not item_found:
        bot.answer_callback_query(call.id, "⚠️ እቃው አልተገኘም!", show_alert=True)




@bot.callback_query_handler(func=lambda call: call.data.startswith("del_itm_"))
def delete_item_handler(call):
    item_id = call.data.replace("del_itm_", "")
    db = load_data()
    
    # እቃውን ከዝርዝር ውስጥ ማውጣት
    original_count = len(db.get('items', []))
    db['items'] = [i for i in db.get('items', []) if str(i.get('id')) != str(item_id)]
    
    if len(db['items']) < original_count:
        save_data(db)
        bot.answer_callback_query(call.id, "🗑️ እቃው ተሰርዟል!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "⚠️ እቃው አልተገኘም!")


@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_prc_"))
def edit_item_price_start(call):
    item_id = call.data.replace("edit_prc_", "")
    msg = bot.send_message(call.message.chat.id, "💰 እባክዎ አዲሱን ዋጋ በቁጥር ብቻ ያስገቡ፦")
    # ተጠቃሚው የሚጽፈውን ዋጋ ተቀብሎ ሴቭ የሚያደርግ ፋንክሽን መጥራት
    bot.register_next_step_handler(msg, save_new_price, item_id, call.message.chat.id, call.message.message_id)

def save_new_price(message, item_id, chat_id, old_msg_id):
    if not message.text.isdigit():
        msg = bot.send_message(chat_id, "⚠️ ስህተት፦ እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ!")
        return bot.register_next_step_handler(msg, save_new_price, item_id, chat_id, old_msg_id)
    
    db = load_data()
    for item in db.get('items', []):
        if str(item['id']) == str(item_id):
            item['price'] = message.text
            save_data(db)
            bot.send_message(chat_id, f"✅ የ{item['name']} ዋጋ ወደ {message.text} ETB ተቀይሯል።")
            # አሮጌውን ካርድ ማጥፋት (አዲስ ዋጋ ስላለው)
            try: bot.delete_message(chat_id, old_msg_id)
            except: pass
            break







@bot.callback_query_handler(func=lambda call: call.data == "vendor_view_orders")
def vendor_view_orders(call):
    db = load_data()
    v_id = str(call.from_user.id)
    
    # ለዚህ ቬንደር የመጡ እና ገና ያልተመለሰላቸው (Pending) ትዕዛዞች
    v_orders = [o for o in db.get('orders', []) if str(o.get('vendor_id')) == v_id and o.get('status') == 'pending']
    
    if not v_orders:
        return bot.answer_callback_query(call.id, "🔔 በአሁኑ ሰዓት ምንም አዲስ ትዕዛዝ የለም።", show_alert=True)
    
    bot.answer_callback_query(call.id, "ትዕዛዞች እየተጫኑ ነው...")

    for o in v_orders:
        order_id = o['order_id']
        items_detail = ""
        # እቃዎቹን በዝርዝር መጻፍ
        for item in o.get('items', []):
            items_detail += f"🔹 {item['name']} (x{item.get('qty', 1)})\n"

        text = (
            f"🆔 **ትዕዛዝ ቁጥር፦ #{order_id}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 **የታዘዙ እቃዎች፦**\n{items_detail}\n"
            f"💰 **ጠቅላላ ዋጋ፦ {o['total_price']} ETB**\n"
            f"📊 **ሁኔታ፦ 🟡 አዲስ ትዕዛዝ**\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ ተቀበል", callback_data=f"v_acc_{order_id}"),
            types.InlineKeyboardButton("❌ ሰርዝ", callback_data=f"v_rej_{order_id}")
        )
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")





@bot.callback_query_handler(func=lambda call: call.data.startswith('v_acc_'))
def vendor_accept_handler(call):
    order_id = call.data.replace('v_acc_', '')
    db = load_data()
    
    for order in db.get('orders', []):
        if str(order['order_id']) == str(order_id):
            if order['status'] != 'pending':
                return bot.answer_callback_query(call.id, "ይህ ትዕዛዝ ቀድሞ ተስተናግዷል።")
            
            # ሁኔታውን ወደ Accepted መቀየር
            order['status'] = 'accepted'
            save_data(db)
            
            bot.edit_message_text(
                f"✅ **ትዕዛዝ #{order_id} ተቀብለዋል።**\nአሁን ሾፌር እየተፈለገ ነው... እቃውን ማዘጋጀት ይጀምሩ።",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown"
            )
            
            # ለደንበኛው ማሳወቅ
            bot.send_message(order['customer_id'], f"🎉 ትዕዛዝዎ #{order_id} በድርጅቱ ተቀባይነት አግኝቷል። ሾፌር እንደተገኘ እናሳውቅዎታለን!")
            
            # TODO: እዚህ ጋር ለሾፌሮች ማሳወቂያ (Notification) መላክ አለበት
            break
    bot.answer_callback_query(call.id)





@bot.callback_query_handler(func=lambda call: call.data.startswith('v_rej_'))
def vendor_reject_handler(call):
    order_id = call.data.replace('v_rej_', '')
    db = load_data()
    
    for order in db.get('orders', []):
        if str(order['order_id']) == str(order_id):
            order['status'] = 'cancelled'
            save_data(db)
            
            bot.edit_message_text(f"🔴 ትዕዛዝ #{order_id} ተሰርዟል።", call.message.chat.id, call.message.message_id)
            bot.send_message(order['customer_id'], f"⚠️ ይቅርታ፣ ትዕዛዝ #{order_id} በድርጅቱ ምክንያት ተሰርዟል።")
            break
    bot.answer_callback_query(call.id)




def process_order_pickup(order_id):
    db = load_data()
    for order in db.get('orders', []):
        if str(order['order_id']) == str(order_id):
            v_id = str(order['vendor_id'])
            total = float(order['total_price'])
            
            # የቬንደሩን ባላንስ መቀነስ
            current_bal = float(db['vendors_list'].get(v_id, {}).get('deposit_balance', 0))
            db['vendors_list'][v_id]['deposit_balance'] = current_bal - total
            
            order['status'] = 'picked_up'
            save_data(db)
            
            bot.send_message(v_id, f"📦 ትዕዛዝ #{order_id} በሾፌር ተረክቧል።\n📉 አዲስ ባላንስ፦ {db['vendors_list'][v_id]['deposit_balance']} ETB")
            break



def notify_vendor_new_order(order_id):
    db = load_data()
    order = next(o for o in db['orders'] if o['order_id'] == order_id)
    vendor_id = order['vendor_id']
    
    items_text = ""
    for item in order['items']:
        items_text += f"🔹 {item['name']} (x{item['qty']})\n"

    text = (
        f"🔔 **አዲስ ትዕዛዝ መጥቷል!**\n"
        f"🆔 ትዕዛዝ ቁጥር፦ #{order_id}\n\n"
        f"📦 ዝርዝር፦\n{items_text}\n"
        f"💰 ጠቅላላ ዋጋ፦ {order['total_price']} ETB\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"እቃው አሁን ይገኛል? (ካለህ 'ተቀበል' በል፣ ሾፌር ይታዘዝልሃል)"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ተቀበል (Accept)", callback_data=f"v_acc_{order_id}"),
        types.InlineKeyboardButton("❌ የለም (Reject)", callback_data=f"v_rej_{order_id}")
    )
    
    bot.send_message(vendor_id, text, reply_markup=markup, parse_mode="Markdown")



def finalize_vendor_accounting(order_id):
    db = load_data()
    order = next((o for o in db['orders'] if o['order_id'] == order_id), None)
    
    if order and order['status'] == 'completed':
        vendor_id = str(order['vendor_id'])
        total_price = float(order['total_price'])
        
        # የቬንደሩን መረጃ ማግኘት
        v_info = db['vendors_list'].get(vendor_id)
        if v_info:
            current_bal = float(v_info.get('deposit_balance', 0))
            
            # አሁን ሂሳቡ ተቀነሰ (ወደ Negative ይሄዳል)
            new_bal = current_bal - total_price
            db['vendors_list'][vendor_id]['deposit_balance'] = new_bal
            
            save_data(db)
            
            # ለቬንደሩ ማሳወቂያ መላክ
            bot.send_message(vendor_id, 
                f"✅ **ሽያጭ ተጠናቋል!**\n"
                f"🆔 ትዕዛዝ ቁጥር፦ #{order_id}\n"
                f"💰 የተቀነሰ ሂሳብ፦ {total_price} ETB\n"
                f"📉 የአሁኑ ባላንስዎ፦ {new_bal:,.2f} ETB", 
                parse_mode="Markdown")









# --- 1. ባዶ ዳታ ማዘጋጃ ---
def get_empty_item_data():
    return {
        'name': None, 
        'price': None, 
        'unit': None, 
        'photo': "no_photo",
        'category': None
    }

# --- 2. ቬንደሩ 'እቃ ጨምር' ሲል የሚቀሰቀስ (Trigger) ---
@bot.callback_query_handler(func=lambda call: call.data == "vendor_add_item")
def trigger_add_item(call):
    user_id = str(call.from_user.id)
    item_creation_temp[user_id] = get_empty_item_data()
    text, markup = render_item_card(user_id)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")

# --- 3. የካርዱ መልክ (Render Card) ---
def render_item_card(user_id):
    u_id = str(user_id)
    if u_id not in item_creation_temp:
        item_creation_temp[u_id] = get_empty_item_data()

    data = item_creation_temp[u_id]
    text = (
        "📦 **አዲስ እቃ ምዝገባ**\n"
        "━━━━━━━━━━━━━━━\n"
        f"📝 ስም፦ {data['name'] if data['name'] else '❌ አልተሞላም'}\n"
        f"💰 ዋጋ፦ {data['price'] if data['price'] else '❌ አልተሞላም'}\n"
        f"📏 መመዘኛ፦ {data['unit'] if data['unit'] else '❌ አልተሞላም'}\n"
        f"📁 ምድብ፦ {data['category'] if data['category'] else '❌ አልተመረጠም'}\n"
        "━━━━━━━━━━━━━━━\n"
        "💡 *እባክዎ መረጃዎቹን ይሙሉ*"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 ስም ሙላ", callback_data="set_name"),
        types.InlineKeyboardButton("💰 ዋጋ ሙላ", callback_data="set_price")
    )
    markup.add(
        types.InlineKeyboardButton("📏 ዩኒት ምረጥ", callback_data="set_unit"),
        types.InlineKeyboardButton("📁 ምድብ ምረጥ", callback_data="set_category")
    )
    markup.add(types.InlineKeyboardButton("📸 ፎቶ ጨምር", callback_data="set_photo"))

    if data['name'] and data['price'] and data['unit'] and data['category']:
        markup.add(types.InlineKeyboardButton("✅ አሁኑኑ መዝግብ", callback_data="final_save_item"))

    markup.add(types.InlineKeyboardButton("🗑️ ሰርዝ", callback_data="cancel_item"))
    return text, markup

# --- 4. የንዑስ ምድብ ምርጫ (Set Category) ---
@bot.callback_query_handler(func=lambda call: call.data == "set_category")
def handle_category_selection(call):
    user_id = str(call.from_user.id)
    db = load_data()

    # 1. ዳታውን ከዳታቤዝ እናገኛለን
    vendor_raw_cat = db.get('vendors_list', {}).get(user_id, {}).get('category')

    # 2. FORCE CLEANUP: ቅንፍን፣ ኮቴን እና ትርፍ ባዶ ቦታን (Space) እናጠፋለን
    import re
    # ማንኛውንም ጽሁፍ ያልሆነ ምልክት (ከኢሞጂ ውጭ) እናጸዳለን
    clean_name = re.sub(r"[\[\]']", "", str(vendor_raw_cat)).strip()
    
    # 3. በ SUB_CATEGORIES ውስጥ ያለውን ቁልፍ (Key) ፈልጎ ከ clean_name ጋር ማመሳሰል
    # ይህ በspace ምክንያት የሚመጣን ስህተት ይከላከላል
    matched_key = None
    for key in SUB_CATEGORIES.keys():
        # ባዶ ቦታን አጥፍተን እናነጻጽራለን (ለምሳሌ "🍴ምግብቤት" == "🍴ምግብቤት")
        if key.replace(" ", "") == clean_name.replace(" ", ""):
            matched_key = key
            break

    if not matched_key:
        return bot.answer_callback_query(call.id, f"⚠️ ለ '{clean_name}' ንዑስ ምድብ አልተዘጋጀም።", show_alert=True)

    # 4. ንዑስ ምድቦችን ማውጣት
    subs = SUB_CATEGORIES.get(matched_key)
    
    c_markup = types.InlineKeyboardMarkup(row_width=2)
    for sub in subs:
        # callback_data ውስን ስለሆነ ስሙን አሳጥረን መላክ ይቻላል
        c_markup.add(types.InlineKeyboardButton(sub, callback_data=f"save_sub:{sub[:15]}"))

    c_markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="refresh_card_only"))
    
    try:
        bot.edit_message_text(f"📁 የ [{matched_key}] ንዑስ ምድብ ይምረጡ፦", 
                              call.message.chat.id, call.message.message_id, reply_markup=c_markup)
    except:
        bot.send_message(call.message.chat.id, f"📁 የ [{matched_key}] ንዑስ ምድብ ይምረጡ፦", reply_markup=c_markup)


# --- 5. የመረጥነውን ንዑስ ምድብ ሴቭ ማድረጊያ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("save_sub:"))
def save_sub_category(call):
    user_id = str(call.from_user.id)
    
    # 1. መጀመሪያ ዳታውን እንቀበላለን
    raw_data = call.data
    
    # 2. ✅ FORCE CLEANUP: 'save_sub:' የሚለውን አጥፍቶ ንጹህ ጽሁፉን ብቻ መውሰድ
    # split ብቻውን ሊስት ስለሚፈጥር እኛ በቀጥታ ጽሁፉን እንነጥላለን
    if ":" in raw_data:
        sub_cat = raw_data.split(":")
    else:
        sub_cat = raw_data

    # 3. ለበለጠ ጥንቃቄ፡ ማንኛውንም አይነት ቅንፍ ወይም ኮቴ በሃይል እናጠፋለን
    import re
    sub_cat = re.sub(r"[\[\]']", "", str(sub_cat)).strip()

    # 4. በጊዜያዊ ማህደረ ትውስታ ውስጥ ማስቀመጥ
    if user_id not in item_creation_temp:
        item_creation_temp[user_id] = get_empty_item_data()

    # አሁን 'sub_cat' ንጹህ ጽሁፍ (ለምሳሌ፦ "ቁርስ") ብቻ ነው
    item_creation_temp[user_id]['category'] = sub_cat

    # 5. ውጤቱን ለቬንደሩ በትንሽ መልዕክት ማሳየት
    bot.answer_callback_query(call.id, f"✅ ምድብ፦ {sub_cat} ተመርጧል")

    # 6. ካርዱን ማደስ
    refresh_card(call.message.chat.id, call.message.message_id, user_id)


# --- 6. የካርድ በተኖች Handler ---
@bot.callback_query_handler(func=lambda call: call.data in ["set_name", "set_price", "set_unit", "set_photo", "final_save_item", "cancel_item", "refresh_card_only"])
def handle_item_creation(call):
    user_id = str(call.from_user.id)
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if call.data == "refresh_card_only":
        refresh_card(chat_id, msg_id, user_id)
    elif call.data == "set_name":
        msg = bot.send_message(chat_id, "🔤 የእቃውን ስም ይጻፉ፦")
        bot.register_next_step_handler(msg, save_temp_name, msg_id)
    elif call.data == "set_price":
        msg = bot.send_message(chat_id, "💰 ዋጋውን በቁጥር ብቻ ያስገቡ፦")
        bot.register_next_step_handler(msg, save_temp_price, msg_id)
    elif call.data == "set_unit":
        u_markup = types.InlineKeyboardMarkup(row_width=2)
        u_markup.add(
            types.InlineKeyboardButton("1 Pcs", callback_data="u_Pcs"),
            types.InlineKeyboardButton("1 Kg", callback_data="u_Kg"),
            types.InlineKeyboardButton("1 Ltr", callback_data="u_Ltr"),
            types.InlineKeyboardButton("1 Pack", callback_data="u_Pack")
        )
        bot.edit_message_text("📏 መመዘኛውን ይምረጡ፦", chat_id, msg_id, reply_markup=u_markup)
    elif call.data == "set_photo":
        msg = bot.send_message(chat_id, "📸 የእቃውን ፎቶ ይላኩ፦")
        bot.register_next_step_handler(msg, save_temp_photo, msg_id)
    elif call.data == "final_save_item":
        db = load_data()
        data = item_creation_temp.get(user_id)
        if not data: return
        item_id = f"itm_{int(time.time())}"
        data.update({'vendor_id': user_id, 'id': item_id, 'status': 'available'})
        if user_id not in db['vendors_list']:
             return bot.answer_callback_query(call.id, "❌ መረጃዎ አልተገኘም!", show_alert=True)
        if 'items' not in db['vendors_list'][user_id]:
            db['vendors_list'][user_id]['items'] = {}
        db['vendors_list'][user_id]['items'][item_id] = data
        save_data(db)
        bot.answer_callback_query(call.id, f"✅ {data['name']} ተመዝግቧል!", show_alert=True)
        bot.delete_message(chat_id, msg_id)
        item_creation_temp.pop(user_id, None)
    elif call.data == "cancel_item":
        bot.clear_step_handler_by_chat_id(chat_id)
        item_creation_temp.pop(user_id, None)
        bot.delete_message(chat_id, msg_id)

# --- 7. ረዳት ፋንክሽኖች ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("u_"))
def save_temp_unit(call):
    user_id = str(call.from_user.id)
    item_creation_temp[user_id]['unit'] = call.data.replace("u_", "")
    refresh_card(call.message.chat.id, call.message.message_id, user_id)

def save_temp_name(message, card_msg_id):
    user_id = str(message.from_user.id)
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    item_creation_temp[user_id]['name'] = message.text
    refresh_card(message.chat.id, card_msg_id, user_id)

def save_temp_price(message, card_msg_id):
    user_id = str(message.from_user.id)
    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "⚠️ ዋጋ በቁጥር ብቻ ይሁን፦")
        return bot.register_next_step_handler(msg, save_temp_price, card_msg_id)
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    item_creation_temp[user_id]['price'] = message.text
    refresh_card(message.chat.id, card_msg_id, user_id)

def save_temp_photo(message, card_msg_id):
    user_id = str(message.from_user.id)
    if message.content_type != 'photo':
        msg = bot.send_message(message.chat.id, "⚠️ እባክዎ ፎቶ ይላኩ፦")
        return bot.register_next_step_handler(msg, save_temp_photo, card_msg_id)
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    item_creation_temp[user_id]['photo'] = message.photo[-1].file_id
    bot.delete_message(message.chat.id, card_msg_id)
    text, markup = render_item_card(user_id)
    bot.send_photo(message.chat.id, item_creation_temp[user_id]['photo'], caption=text, reply_markup=markup, parse_mode="Markdown")

def refresh_card(chat_id, message_id, user_id):
    text, markup = render_item_card(user_id)
    data = item_creation_temp.get(str(user_id), {})
    try:
        if data.get('photo') == "no_photo":
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.edit_message_caption(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        pass









# 1. የራይደር ምዝገባ መጀመሪያ
@command_breaker
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_rider")
def start_add_rider(call):
    msg = bot.send_message(call.message.chat.id, "🆔 የራይደሩን (Driver) Telegram User ID ያስገቡ፦\n\n(ለመሰረዝ /start ይበሉ)")
    bot.register_next_step_handler(msg, process_rider_id)

def process_rider_id(message):
    r_id = message.text.strip()
    if r_id == "/start": return bot.send_message(message.chat.id, "⚠️ ተቋርጧል።")
    
    if not r_id.isdigit():
        msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ ID ቁጥር መሆን አለበት። ድጋሚ ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_rider_id)
    
    msg = bot.send_message(message.chat.id, "👤 የራይደሩን ሙሉ ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, process_rider_name, r_id)

# አዲስ የተጨመረ - ስም መቀበያ
def process_rider_name(message, r_id):
    name = message.text.strip()
    if name == "/start": return bot.send_message(message.chat.id, "⚠️ ተቋርጧል።")
    
    msg = bot.send_message(message.chat.id, f"📞 የራይደር {name} ስልክ ቁጥር ያስገቡ፦")
    bot.register_next_step_handler(msg, save_new_rider, r_id, name)

def save_new_rider(message, r_id, name):
    phone = message.text.strip()
    if phone == "/start": return bot.send_message(message.chat.id, "⚠️ ተቋርጧል።")
    
    db = load_data()
    if 'riders_list' not in db: db['riders_list'] = {}
    
    # --- አውቶማቲክ የታርጋ/መለያ ቁጥር አሰጣጥ (Driver 1, 2...) ---
    rider_count = len(db['riders_list']) + 1
    auto_plate = f"Driver {rider_count}"
    
    db['riders_list'][str(r_id)] = {
        "name": name,
        "phone": phone,
        "plate_no": auto_plate, # ቦቱ የሰጠው መለያ
        "wallet": 0,
        "status": "offline",
        "is_active": True,
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_data(db)
    
    bot.send_message(message.chat.id, 
                     f"✅ **ራይደር በትክክል ተመዝግቧል!**\n\n"
                     f"👤 ስም፦ {name}\n"
                     f"📞 ስልክ፦ {phone}\n"
                     f"🔢 መለያ፦ {auto_plate}\n"
                     f"🆔 User ID፦ {r_id}")






# ለገንዘብ ዝውውር ጊዜያዊ መረጃ መያዣ
Temp_topup_data = {}

# 1. ባላንስ መሙያ በተን ሲነካ
@command_breaker
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_funds")
def start_topup(call):
    msg = bot.send_message(call.message.chat.id, "🆔 ባላንስ ሊሞላለት ወይም ሊቀነስለት የሚገባውን ሰው (Rider/Vendor) Telegram ID ያስገቡ፦\n\n(ለመሰረዝ /start ይበሉ)")
    bot.register_next_step_handler(msg, find_user_for_topup)

# 2. ተጠቃሚውን መፈለግ
def find_user_for_topup(message):
    uid = message.text.strip()
    
    # የ /start ቼክ
    if uid == "/start":
        return bot.send_message(message.chat.id, "⚠️ የባላንስ ማስተካከያ ሂደት ተቋርጧል።")
        
    db = load_data()
    user_data = None
    role = ""
    
    # በሁለቱም ዝርዝር ውስጥ መፈለግ
    if uid in db.get('vendors_list', {}):
        user_data = db['vendors_list'][uid]
        role = "vendor"
    elif uid in db.get('riders_list', {}):
        user_data = db['riders_list'][uid]
        role = "rider"
        
    if not user_data:
        msg = bot.send_message(message.chat.id, "❌ በዚህ ID የተመዘገበ ራይደር ወይም ድርጅት አልተገኘም። እባክዎ ID በትክክል ያስገቡ፦")
        return bot.register_next_step_handler(msg, find_user_for_topup)

    temp_topup_data[message.chat.id] = {'target_id': uid, 'role': role}
    
    # የአሁኑን ባላንስ ማውጣት (ባዶ ከሆነ 0 እንዲል)
    curr_bal = 0
    if role == "vendor":
        curr_bal = user_data.get('deposit_balance', 0)
        label = "💰 የአሁኑ ዲፖዚት"
    else:
        curr_bal = user_data.get('wallet', 0)
        label = "💳 የአሁኑ ዋሌት"

    text = (
        f"👤 ተጠቃሚ፦ **{user_data.get('name', 'ያልታወቀ')}**\n"
        f"🎭 ሚና፦ {role.capitalize()}\n"
        f"{label}፦ {curr_bal} ብር\n"
        "━━━━━━━━━━━━━━━\n"
        "📝 ብር ለመጨመር (ለምሳሌ፦ 500)\n"
        "📝 ለመቀነስ የይለይ ምልክት (ለምሳሌ፦ -200) ያስገቡ፦"
    )

    msg = bot.send_message(message.chat.id, text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_balance_update)

# 3. የሂሳብ ማስተካከያውን መተግበር
@command_breaker
def process_balance_update(message):
    admin_id = message.chat.id
    val_text = message.text.strip()

    if val_text == "/start":
        if admin_id in temp_topup_data: del temp_topup_data[admin_id]
        return bot.send_message(admin_id, "⚠️ ሂደት ተቋርጧል።")

    try:
        amount = float(val_text)
        t_data = temp_topup_data.get(admin_id)
        if not t_data: return

        db = load_data()
        target_id = t_data['target_id']
        role = t_data['role']
        
        if role == "vendor":
            # ድርጅት ውስጥ ቁልፉ (Key) መኖሩን ቼክ ማድረግ
            if 'deposit_balance' not in db['vendors_list'][target_id]:
                db['vendors_list'][target_id]['deposit_balance'] = 0
            
            db['vendors_list'][target_id]['deposit_balance'] += amount
            new_bal = db['vendors_list'][target_id]['deposit_balance']
        else:
            # ራይደር ውስጥ ቁልፉ መኖሩን ቼክ ማድረግ
            if 'wallet' not in db['riders_list'][target_id]:
                db['riders_list'][target_id]['wallet'] = 0
                
            db['riders_list'][target_id]['wallet'] += amount
            new_bal = db['riders_list'][target_id]['wallet']

        save_data(db)
        
        action = "ተጨምሯል" if amount > 0 else "ተቀንሷል"
        msg_text = f"✅ ለ{role} {abs(amount)} ብር {action}።\n💰 አዲስ ባላንስ፦ {new_bal} ብር"
        bot.send_message(admin_id, msg_text)
        
        # ለተጠቃሚው ማሳወቂያ መላክ
        try:
            bot.send_message(target_id, f"🔔 የሂሳብ ማስተካከያ ተደርጓል!\n💰 የአሁኑ ባላንስዎ፦ {new_bal} ብር")
        except: pass 
            
        if admin_id in temp_topup_data: del temp_topup_data[admin_id]
        
    except ValueError:
        msg = bot.send_message(admin_id, "⚠️ ስህተት፡ እባክዎ በትክክል ቁጥር ብቻ ያስገቡ (ለምሳሌ፦ 500)፦")
        bot.register_next_step_handler(msg, process_balance_update)
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(admin_id, "❌ ስህተት ተፈጥሯል።")





# --- የዴሊቨሪ መቆጣጠሪያ ገጽ ማሳያ ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_delivery_mgmt")
def admin_delivery_mgmt_page(call):
    try:
        db = load_data()
        s = db.get('settings', {})
        
        # ዳታው ከሌለ default ዋጋ እንዲወስድ (ስህተት እንዳይፈጥር)
        base = s.get('base_delivery', 50)
        rain_v = s.get('rain_val', 25)
        night_v = s.get('night_val', 15)
        
        # የ On/Off ሁኔታ (ከሌለ False እንዲሆን)
        r_status = "🟢 በርቷል" if s.get('rain_mode', False) else "🔴 ጠፍቷል"
        n_status = "🟢 በርቷል" if s.get('night_mode', False) else "🔴 ጠፍቷል"

        text = (
            "🚚 **የማጓጓዣ ዋጋ መቆጣጠሪያ**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 መነሻ ዋጋ፦ `{base} ETB`\n"
            f"🌧️ የዝናብ ሁኔታ፦ {r_status} (+{rain_v} ETB)\n"
            f"🌙 የምሽት ሁኔታ፦ {n_status} (+{night_v} ETB)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👇 ዋጋ ለመቀየር ወይም ሁኔታውን ለመቀየር ይጠቀሙ፦"
        )

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("💰 መነሻ ዋጋ ቀይር", callback_data="edit_val_base_delivery"))
        markup.add(
            types.InlineKeyboardButton("🌧️ ዝናብ On/Off", callback_data="toggle_rain"),
            types.InlineKeyboardButton("🌧️ የዝናብ ዋጋ", callback_data="edit_val_rain_val")
        )
        markup.add(
            types.InlineKeyboardButton("🌙 ምሽት On/Off", callback_data="toggle_night"),
            types.InlineKeyboardButton("🌙 የምሽት ዋጋ", callback_data="edit_val_night_val")
        )
        markup.add(types.InlineKeyboardButton("🏠 ወደ ዳሽቦርድ", callback_data="admin_main_menu"))

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"Delivery Mgmt Error: {e}")
        bot.answer_callback_query(call.id, "❌ በዳታቤዝ ስህተት ምክንያት መክፈት አልተቻለም።")





# --- 1. የዝናብ ሁኔታን On/Off ማድረጊያ ---
@command_breaker
@bot.callback_query_handler(func=lambda call: call.data == "toggle_rain")
def toggle_rain_mode(call):
    db = load_data()
    # ያለበትን ሁኔታ መገልበጥ (True ከሆነ False፣ False ከሆነ True)
    current_status = db['settings'].get('rain_mode', False)
    db['settings']['rain_mode'] = not current_status
    save_data(db)
    
    # ገጹን በራሱ አድስ (Refresh)
    bot.answer_callback_query(call.id, "🌧️ የዝናብ ሁኔታ ተቀይሯል!")
    admin_delivery_mgmt_page(call) # ገጹን ተመልሶ እንዲያሳየው መጥራት

# --- 2. የምሽት ሁኔታን On/Off ማድረጊያ ---
@bot.callback_query_handler(func=lambda call: call.data == "toggle_night")
def toggle_night_mode(call):
    db = load_data()
    # ያለበትን ሁኔታ መገልበጥ
    current_status = db['settings'].get('night_mode', False)
    db['settings']['night_mode'] = not current_status
    save_data(db)
    
    # ገጹን በራሱ አድስ (Refresh)
    bot.answer_callback_query(call.id, "🌙 የምሽት ሁኔታ ተቀይሯል!")
    admin_delivery_mgmt_page(call) # ገጹን ተመልሶ እንዲያሳየው መጥራት






# --- 1. ዋጋ መቀበያ ሎጂክ (Generic Function) ---
@command_breaker
def update_delivery_value(message, key_name, display_name):
    chat_id = message.chat.id
    new_val = message.text

    # በቁጥር መሆኑን ማረጋገጥ
    if not new_val.isdigit():
        msg = bot.send_message(chat_id, f"❌ ስህተት፦ እባክዎ የ{display_name} ዋጋን በቁጥር ብቻ ያስገቡ፦")
        return bot.register_next_step_handler(msg, update_delivery_value, key_name, display_name)

    db = load_data()
    db['settings'][key_name] = int(new_val)
    save_data(db)

    bot.send_message(chat_id, f"✅ የ{display_name} ዋጋ ወደ **{new_val} ETB** ተቀይሯል!")
    # ወደ ማጓጓዣ ገጹ እንዲመለስ ለማድረግ (አማራጭ)
    # admin_delivery_mgmt_page(message) 

# --- 2. የዋጋ መቀየሪያ ቁልፎች (Callbacks) ---
@command_breaker
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_val_"))
def handle_price_edits(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if data == "edit_val_base_delivery":
        msg = bot.send_message(chat_id, "🔢 አዲሱን የ**መነሻ ማጓጓዣ** ዋጋ ያስገቡ፦")
        bot.register_next_step_handler(msg, update_delivery_value, "base_delivery", "መነሻ")
        
    elif data == "edit_val_rain_val":
        msg = bot.send_message(chat_id, "🔢 አዲሱን የ**ዝናብ ሁኔታ** ተጨማሪ ዋጋ ያስገቡ፦")
        bot.register_next_step_handler(msg, update_delivery_value, "rain_val", "የዝናብ")
        
    elif data == "edit_val_night_val":
        msg = bot.send_message(chat_id, "🔢 አዲሱን የ**ምሽት ሁኔታ** ተጨማሪ ዋጋ ያስገቡ፦")
        bot.register_next_step_handler(msg, update_delivery_value, "night_val", "የምሽት")
    
    bot.answer_callback_query(call.id)




# 1. ድርጅት መመዝገቢያ መጀመሪያ (ምድብ ማስመረጫ)
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_vendor")
def start_add_vendor(call):
    db = load_data()
    categories = db.get('categories', [])

    if not categories:
        return bot.answer_callback_query(call.id, "⚠️ ድርጅት ከመመዝገብዎ በፊት መጀመሪያ 'አዲስ ምድብ' (Category) ይፍጠሩ!", show_alert=True)

    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"sel_cat_v:{cat}"))

    bot.edit_message_text("📂 ለድርጅቱ ምድብ (ዘርፍ) ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

# 1. ምድብ ሲመረጥ (Force Cleanup እዚህ ይጀምራል)
@bot.callback_query_handler(func=lambda call: call.data.startswith("sel_cat_v:"))
def get_id_after_cat(call):
    # 1. መጀመሪያ ዳታውን ወደ ጽሁፍ (String) እንቀይረዋለን
    data_str = str(call.data)
    
    # 2. FORCE CLEANUP: የማይፈለጉትን ቃላት በሙሉ እዚህ ጋር እናጥፋለን
    # 'sel_cat_v:' የሚለውን ያጠፋል
    clean_cat = data_str.replace("sel_cat_v:", "")
    
    # ሊስት ሆኖ ከመጣ 'sel_cat_v', የሚለውን እና ቅንፎችን ያጠፋል
    clean_cat = clean_cat.replace("sel_cat_v", "").replace("[", "").replace("]", "").replace("'", "").replace(",", "")
    
    # ትርፍ ባዶ ቦታ ካለ እናጽዳ
    actual_cat = clean_cat.strip()

    # 3. መልዕክቱን እንልካለን
    # አሁን በምንም ተአምር 'sel_cat_v' ወይም ኮማ ሊመጣ አይችልም
    msg = bot.send_message(
        call.message.chat.id, 
        f"🆔 የ {actual_cat} ባለቤት Telegram ID ያስገቡ፦"
    )
    bot.register_next_step_handler(msg, process_vendor_id, actual_cat)

# 2. ID መቀበያ
def process_vendor_id(message, actual_cat):
    v_id = message.text.strip()
    if v_id == "/start": return
    
    if not v_id.isdigit():
        msg = bot.send_message(message.chat.id, "⚠️ ID ቁጥር መሆን አለበት። ድጋሚ ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_vendor_id, actual_cat)

    msg = bot.send_message(message.chat.id, "🏢 የድርጅቱን ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, process_vendor_name, v_id, actual_cat)

# 3. ስም መቀበያ
def process_vendor_name(message, v_id, actual_cat):
    v_name = message.text.strip()
    if v_name == "/start": return
    
    msg = bot.send_message(message.chat.id, f"📞 የ '{v_name}' ስልክ ያስገቡ፦")
    bot.register_next_step_handler(msg, save_new_vendor_final, v_id, v_name, actual_cat)

# 4. የመጨረሻው ሴቭ (Force String Conversion)
def save_new_vendor_final(message, v_id, v_name, actual_cat):
    v_phone = message.text.strip()
    if v_phone == "/start": return

    db = load_data()
    if 'vendors_list' not in db: db['vendors_list'] = {}

    # የመጨረሻው የጥራት ምርመራ (String Force)
    # እዚህ ጋር actual_cat በምንም ተአምር ሊስት መሆን አይችልም
    final_cat = str(actual_cat).strip()

    db['vendors_list'][str(v_id)] = {
        "name": v_name,
        "phone": v_phone,
        "category": final_cat, # ✅ ንጹህ ጽሁፍ
        "status": "active",
        "deposit_balance": 0,
        "items": {}, 
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_data(db)
    
    bot.send_message(message.chat.id, f"✅ **ድርጅት ተመዝግቧል!**\n\n🏢 ስም፦ {v_name}\n📁 ዘርፍ፦ {final_cat}")








# --- 1. የተመዘገቡ ምድቦችን ዝርዝር ማሳያ ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_view_categories")
def admin_categories_menu(call):
    db = load_data()
    cats = db.get('categories', [])

    text = "📁 **የተመዘገቡ የምድብ አይነቶች**\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    if not cats:
        text += "ገና ምንም ምድብ አልተመዘገበም።"
    else:
        for i, c in enumerate(cats, 1):
            text += f"{i}. {c}\n"

    text += "\n⚠️ *ማሳሰቢያ፦ እዚህ የሚመዘግቡት ስም 'SUB_CATEGORIES' ውስጥ ካለው ጋር አንድ መሆን አለበት።*"

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ አዲስ ምድብ ጨምር", callback_data="admin_add_cat"),
        types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu")
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")

# --- 2. አዲስ የምድብ ስም መቀበያ ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_cat")
def ask_category_name(call):
    # ተጠቃሚው ግራ እንዳይጋባ ያለውን መልዕክት አጥፍተን አዲስ እንልካለን
    bot.delete_message(call.message.chat.id, call.message.message_id)
    msg = bot.send_message(call.message.chat.id, "✏️ ለመጨመር የሚፈልጉትን የምድብ ስም ይጻፉ፦\n\n💡 ምሳሌ፦ `🛍️ ሱፐርማርኬት` ወይም `🍴 ምግብ ቤት`")
    bot.register_next_step_handler(msg, save_category_logic)

# --- 3. ምድቡን ዳታቤዝ ላይ የማስቀመጫ ሎጂክ ---
def save_category_logic(message):
    new_cat = message.text.strip()
    
    if new_cat.startswith('/'):
        bot.send_message(message.chat.id, "⚠️ የምድብ ምዝገባ ተቋርጧል።")
        return

    db = load_data()

    if 'categories' not in db:
        db['categories'] = []

    if new_cat in db['categories']:
        bot.send_message(message.chat.id, f"⚠️ '{new_cat}' ቀደም ብሎ ተመዝግቧል።")
    else:
        db['categories'].append(new_cat)
        save_data(db)
        
        # ስኬት መልዕክት ከነ በተኑ
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዝርዝር ተመለስ", callback_data="admin_view_categories"))
        bot.send_message(message.chat.id, f"✅ ምድብ **'{new_cat}'** በተሳካ ሁኔታ ተመዝግቧል!", 
                         reply_markup=markup, parse_mode="Markdown")





@bot.callback_query_handler(func=lambda call: call.data == "admin_system_lock")
def toggle_system_lock(call):
    db = load_data()
    # አሁን ያለውን ሁኔታ መቀልበስ (True ከሆነ False, False ከሆነ True)
    current_status = db['settings'].get('system_locked', False)
    new_status = not current_status
    db['settings']['system_locked'] = new_status
    save_data(db)
    
    status_text = "🔒 ተዘግቷል (ደንበኞች ማዘዝ አይችሉም)" if new_status else "🔓 ተከፍቷል (ሲስተሙ በስራ ላይ ነው)"
    bot.answer_callback_query(call.id, f"ሲስተሙ {status_text}")
    
    # በተኑ ላይ ያለውን ጽሁፍ መቀየር
    markup = get_admin_dashboard() # ዳሽቦርዱን እንደገና መጥራት
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)




# 1. ማገጃ ሜኑ
@command_breaker
@bot.callback_query_handler(func=lambda call: call.data == "admin_block_manager")
def start_block_process(call):
    msg = bot.send_message(call.message.chat.id, "🚫 ለማገድ ወይም ለመፍቀድ የተጠቃሚውን (Rider/Vendor) ID ያስገቡ፦")
    bot.register_next_step_handler(msg, process_block_unblock)

# 2. የማገጃ ስራውን መተግበር
def process_block_unblock(message):
    uid = message.text.strip()
    db = load_data()
    user_found = False
    new_state = False

    # በቬንደር ውስጥ መፈለግ
    if uid in db['vendors_list']:
        db['vendors_list'][uid]['is_active'] = not db['vendors_list'][uid].get('is_active', True)
        new_state = db['vendors_list'][uid]['is_active']
        user_found = True
    # በራይደር ውስጥ መፈለግ
    elif uid in db['riders_list']:
        db['riders_list'][uid]['is_active'] = not db['riders_list'][uid].get('is_active', True)
        new_state = db['riders_list'][uid]['is_active']
        user_found = True

    if user_found:
        save_data(db)
        status_msg = "✅ ተፈቅዶለታል (Unblocked)" if new_state else "🚫 ታግዷል (Blocked)"
        bot.send_message(message.chat.id, f"ተጠቃሚ {uid} አሁን {status_msg} ነው።")
        
        # ለታገደው ሰው ማሳወቂያ መላክ
        try:
            notification = "🔓 አካውንትዎ በባለቤቱ ተከፍቷል።" if new_state else "🚫 አካውንትዎ ለጊዜው ታግዷል። እባክዎ አድሚኑን ያነጋግሩ።"
            bot.send_message(uid, notification)
        except: pass
    else:
        bot.send_message(message.chat.id, "❌ ተጠቃሚው በዳታቤዝ ውስጥ አልተገኘም።")




# 1. ማስታወቂያ ለመላክ መጠየቂያ
@command_breaker
@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def start_broadcast(call):
    msg = bot.send_message(call.message.chat.id, "📢 ለሁሉም ተጠቃሚዎች የሚተላለፈውን ማስታወቂያ ይጻፉ፦\n\n(ማስታወሻ፡ መልዕክቱ ለሁሉም ተመዝጋቢዎች ይደርሳል)")
    bot.register_next_step_handler(msg, send_broadcast_messages)

# 2. መልዕክቱን መላክ
def send_broadcast_messages(message):
    db = load_data()
    # በ user_list ውስጥ ያሉትን ሁሉንም UID ማግኘት
    all_users = db.get('user_list', [])
    
    if not all_users:
        return bot.send_message(message.chat.id, "⚠️ ምንም ተጠቃሚ በዳታቤዝ ውስጥ አልተገኘም።")

    success_count = 0
    fail_count = 0
    
    bot.send_message(message.chat.id, f"⏳ ማስታወቂያ መላክ ተጀምሯል... (ለ {len(all_users)} ሰዎች)")



@bot.callback_query_handler(func=lambda call: call.data == "admin_rider_status")
def view_riders_status(call):
    try:
        db = load_data()
        riders = db.get('riders_list', {})
        
        if not riders:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_main_menu"))
            return bot.edit_message_text("⚠️ እስካሁን ምንም ራይደር አልተመዘገበም።", 
                                        call.message.chat.id, 
                                        call.message.message_id, 
                                        reply_markup=markup)

        report = "🛵 **የራይደሮች ሁኔታ ዝርዝር**\n\n"
        
        online_count = 0
        for r_id, info in riders.items():
            # ሁኔታውን በኢሞጂ ለማሳየት
            status = info.get('status', 'offline')
            is_active = info.get('is_active', True)
            
            status_icon = "🟢" if status == "online" else "🔴"
            if status == "online": online_count += 1
            
            active_icon = "✅ ንቁ" if is_active else "🚫 የታገደ"
            
            report += f"{status_icon} **{info['name']}**\n"
            report += f"   🆔 ID: `{r_id}`\n"
            report += f"   💳 ዋሌት: `{info.get('wallet', 0)}` ብር\n"
            report += f"   🔒 ሁኔታ: {active_icon}\n"
            report += "------------------------\n"
        
        report += f"\n📊 ጠቅላላ ራይደሮች፦ {len(riders)}\n✅ አሁን ኦንላይን፦ {online_count}"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_rider_status"))
        markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu"))

        bot.edit_message_text(report, 
                             call.message.chat.id, 
                             call.message.message_id, 
                             reply_markup=markup, 
                             parse_mode="Markdown")
                             
    except Exception as e:
        print(f"Rider Status Error: {e}")
        bot.answer_callback_query(call.id, "❌ መረጃውን መጫን አልተቻለም።")





@bot.callback_query_handler(func=lambda call: call.data == "admin_list_vendors")
def list_all_entities(call):
    try:
        db = load_data()
        vendors = db.get('vendors_list', {})
        riders = db.get('riders_list', {})
        
        # ርዕስ
        report = "📋 **BDF የተመዘገቡ አካላት ዝርዝር**\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # 🏢 የድርጅቶች (Vendors) ዝርዝር
        report += "🏢 **የድርጅቶች ዝርዝር (Vendors)**\n"
        if not vendors:
            report += "_👉 እስካሁን ምንም ድርጅት አልተመዘገበም_\n"
        else:
            for v_id, info in vendors.items():
                # ምድቡን ማጽዳት (Tuple/List ከሆነ ወደ String ይቀይረዋል)
                cat = info.get('category', 'ምድብ የሌለው')
                if isinstance(cat, (list, tuple)):
                    cat = cat[-1] # ንጹህ ስሙን ብቻ ይወስዳል
                
                # አቀራረብ
                report += f"🔹 **{info.get('name', 'ስም የሌለው')}**\n"
                report += f"   📁 ምድብ፦ `{cat}`\n"
                report += f"   🆔 ID፦ `{v_id}`\n"
                report += f"   💰 ባላንስ፦ `{info.get('deposit_balance', 0)}` ብር\n"
                report += "------------------------\n"

        report += "\n" # ክፍተት
        
        # 🛵 የራይደሮች (Drivers) ዝርዝር
        report += "🛵 **የራይደሮች ዝርዝር (Drivers)**\n"
        if not riders:
            report += "_👉 እስካሁን ምንም ራይደር አልተመዘገበም_\n"
        else:
            for r_id, info in riders.items():
                # ሁኔታ (Online/Offline)
                status_icon = "🟢" if info.get('status') == "online" else "🔴"
                
                report += f"{status_icon} **{info.get('name', 'ስም የሌለው')}**\n"
                report += f"   🆔 ID፦ `{r_id}`\n"
                report += f"   💳 ዋሌት፦ `{info.get('wallet', 0)}` ብር\n"
                report += "------------------------\n"

        # የመመለሻ በተን
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=report,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        print(f"List Display Error: {e}")
        bot.answer_callback_query(call.id, "❌ ዝርዝሩን ማሳየት አልተቻለም።")




# 1. የኮሚሽን ማስተካከያ መጀመሪያ
@command_breaker
@bot.callback_query_handler(func=lambda call: call.data == "admin_set_commission")
def start_commission_settings(call):
    text = "⚙️ የኮሚሽን ማስተካከያ\n\nእባክዎ 3 ቁጥሮችን በኮማ ይላኩ (ለምሳሌ፦ 3, 5, 8)"
    # መልዕክቱን ለኪል ተጠቃሚው መላክ
    msg = bot.send_message(call.message.chat.id, text)
    # ቀጣዩን መልዕክት 'save_commissions' እንዲቀበለው ማድረግ
    bot.register_next_step_handler(msg, save_commissions)






@bot.callback_query_handler(func=lambda call: call.data == "admin_profit_track")
def view_profit_stats(call):
    db = load_data()
    
    # በዳታቤዝህ ውስጥ 'stats' የሚል ክፍል መኖር አለበት
    stats = db.get('stats', {
        'total_vendor_comm': 0.0,
        'total_rider_comm': 0.0,
        'total_customer_comm': 0.0,
        'total_orders': 0
    })
    
    total_net_profit = stats['total_vendor_comm'] + stats['total_rider_comm'] + stats['total_customer_comm']
    
    report = "💰 **የትርፍ እና የሽያጭ ሪፖርት**\n\n"
    report += f"📊 **አጠቃላይ ትርፍ፦ {total_net_profit:,.2f} ብር**\n"
    report += "--------------------------------\n"
    report += f"🏢 ከድርጅቶች ኮሚሽን፦ {stats['total_vendor_comm']:,.2f} ብር\n"
    report += f"🛵 ከራይደሮች አገልግሎት፦ {stats['total_rider_comm']:,.2f} ብር\n"
    report += f"👤 ከደንበኞች ሰርቪስ ፊ፦ {stats['total_customer_comm']:,.2f} ብር\n"
    report += "--------------------------------\n"
    report += f"📦 ጠቅላላ የተጠናቀቁ ትዕዛዞች፦ {stats['total_orders']} ትዕዛዝ\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 ሪፖርት አድስ", callback_data="admin_profit_track"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu"))
    
    bot.edit_message_text(report, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")




@bot.callback_query_handler(func=lambda call: call.data == "admin_monitor_balance")
def monitor_all_balances(call):
    try:
        db = load_data()
        vendors = db.get('vendors_list', {})
        riders = db.get('riders_list', {})
        
        report = "📉 **የፋይናንስ ክትትል መቆጣጠሪያ**\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # 🏢 የድርጅቶች የዲፖዚት ሁኔታ
        report += "🏢 **የድርጅቶች ባላንስ (Vendors)**\n"
        if not vendors:
            report += "_👉 እስካሁን ምንም ድርጅት አልተመዘገበም_\n"
        else:
            for v_id, info in vendors.items():
                cat = info.get('category', 'ያልተገለጸ')
                bal = info.get('deposit_balance', 0)
                # ባላንሱ 0 ከሆነ ቀይ ምልክት፣ ከፍ ያለ ከሆነ አረንጓዴ እንዲያሳይ
                status_dot = "🔴" if bal <= 0 else "🟢"
                report += f"{status_dot} **{info['name']}** ({cat})\n"
                report += f"    └─ 💰 ባላንስ፦ `{bal}` ብር\n"
        
        report += "\n" + "─" * 20 + "\n\n"
        
        # 🛵 የራይደሮች ዋሌት ሁኔታ
        report += "🛵 **የራይደሮች ባላንስ (Drivers)**\n"
        if not riders:
            report += "_👉 እስካሁን ምንም ራይደር አልተመዘገበም_\n"
        else:
            for r_id, info in riders.items():
                w_bal = info.get('wallet', 0)
                r_status = "🟢" if w_bal > 0 else "⚪"
                report += f"{r_status} **{info['name']}**\n"
                report += f"    └─ 💳 ዋሌት፦ `{w_bal}` ብር\n"

        report += "\n━━━━━━━━━━━━━━━━━━━━\n"
        report += f"📊 **አጠቃላይ በሲስተሙ ያለው ገንዘብ፦** `{sum(v.get('deposit_balance', 0) for v in vendors.values()) + sum(r.get('wallet', 0) for r in riders.values())}` ብር"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu"))
        
        bot.edit_message_text(report, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        print(f"Balance Monitor Error: {e}")
        bot.answer_callback_query(call.id, "❌ መረጃውን ማምጣት አልተቻለም።")





@bot.callback_query_handler(func=lambda call: call.data == "admin_live_orders")
def view_live_orders(call):
    db = load_data()
    # 'orders' ውስጥ ያሉትን ትዕዛዞች በሙሉ ይወስዳል
    all_orders = db.get('orders', {})
    
    # ሁኔታቸው "Completed" ወይም "Cancelled" ያልሆኑትን ብቻ ለይቶ ማውጣት
    active_orders = {k: v for k, v in all_orders.items() if v.get('status') not in ['Completed', 'Cancelled']}

    if not active_orders:
        # ምንም ትዕዛዝ ከሌለ ያለውን ሜሴጅ አጥፍቶ አዲስ ሜሴጅ ይልካል
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 እንደገና ሞክር", callback_data="admin_live_orders"))
        markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu"))
        
        try:
            return bot.edit_message_text("📭 አሁን ላይ ምንም ቀጥታ ትዕዛዝ የለም።", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except:
            return bot.answer_callback_query(call.id, "📭 ምንም ቀጥታ ትዕዛዝ የለም።")

    report = "📋 **የቀጥታ ትዕዛዞች ክትትል**\n\n"

    for order_id, info in active_orders.items():
        status = info.get('status', 'Pending')
        
        # አይኮኖችን በሁኔታው መሰረት መቀየር
        if status == "Pending": status_icon = "⏳"
        elif status == "Accepted": status_icon = "✅"
        elif status == "On Way": status_icon = "🛵"
        else: status_icon = "📦"

        # መረጃዎችን በጥንቃቄ ማውጣት
        vendor = info.get('vendor_name', 'ያልታወቀ ድርጅት')
        rider = info.get('rider_name', 'ገና አልተያዘም')
        price = info.get('item_total', 0)
        
        report += f"{status_icon} **ትዕዛዝ ID፦** `{order_id}`\n"
        report += f"🏢 **ድርጅት፦** {vendor}\n"
        report += f"🛵 **ራይደር፦** {rider}\n"
        report += f"📍 **ሁኔታ፦** {status}\n"
        report += f"💰 **ዋጋ፦** {price} ETB\n"
        report += "------------------------\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_live_orders"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu"))

    try:
        bot.edit_message_text(report, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print(f"Error updating live orders: {e}")





@bot.callback_query_handler(func=lambda call: call.data == "admin_full_stats")
def show_enhanced_analytics(call):
    db = load_data()
    vendors = db.get('vendors_list', {})
    riders = db.get('riders_list', {})
    orders = db.get('orders', {})
    s = db.get('settings', {}) # ሴቲንግን እዚህ ጋር እናወጣለን

    # የሂሳብ ስሌቶች
    total_vendor_deposit = sum(v.get('deposit_balance', 0) for v in vendors.values())
    total_rider_wallet = sum(r.get('wallet', 0) for r in riders.values())
    system_profit = db.get('total_profit', 0)

    # የዴሊቨሪ እና ኮሚሽን ሁኔታዎች
    r_mode = "🟢 በርቷል" if s.get('rain_mode') else "🔴 ጠፍቷል"
    n_mode = "🟢 በርቷል" if s.get('night_mode') else "🔴 ጠፍቷል"
    v_comm = s.get('vendor_commission_p', 5)
    srv_fee = s.get('service_fee', 8)

    report = "📊 **ጥልቅ የቢዝነስ ትንታኔ (Full Analytics)**\n"
    report += "━━━━━━━━━━━━━━━━━━━━\n\n"

    # 🚚 የማጓጓዣ እና ኮሚሽን ሁኔታ (አንተ የፈለግከው አዲስ ክፍል)
    report += "⚙️ **የሲስተም ሁኔታ (Current Settings)**\n"
    report += f"• የዝናብ ሁኔታ፦ {r_mode} (`+{s.get('rain_val', 0)} ETB`)\n"
    report += f"• የምሽት ሁኔታ፦ {n_mode} (`+{s.get('night_val', 0)} ETB`)\n"
    report += f"• የድርጅት ኮሚሽን፦ `{v_comm}%` | ሰርቪስ ፊ፦ `{srv_fee} ETB` \n"
    report += "------------------------\n\n"

    # 🏢 የድርጅቶች ሁኔታ
    report += "🏢 **የድርጅቶች ሁኔታ (Vendors)**\n"
    report += f"• ጠቅላላ ድርጅቶች፦ `{len(vendors)}` \n"
    report += f"• አጠቃላይ ዲፖዚት፦ `{total_vendor_deposit:,.2f}` ብር\n"
    report += "------------------------\n\n"

    # 🛵 የራይደሮች ሁኔታ
    report += "🛵 **የራይደሮች ሁኔታ (Drivers)**\n"
    report += f"• ጠቅላላ ራይደሮች፦ `{len(riders)}` \n"
    online_riders = sum(1 for r in riders.values() if r.get('status') == 'online')
    report += f"• አሁን በስራ ላይ (Online)፦ `{online_riders}`\n"
    report += f"• አጠቃላይ ዋሌት፦ `{total_rider_wallet:,.2f}` ብር\n"
    report += "------------------------\n\n"

    # 💰 ፋይናንስ
    report += "💰 **ፋይናንስ እና ትዕዛዞች**\n"
    report += f"• የተሳኩ ትዕዛዞች፦ `{len(orders)}` \n"
    report += f"• አጠቃላይ የሲስተም ትርፍ፦ `{system_profit:,.2f}` ብር 💵\n"
    report += "━━━━━━━━━━━━━━━━━━━━"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_full_stats"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu"))

    bot.edit_message_text(report, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")







# 1. ዳግም ማስጀመሪያ መጀመሪያ - ማስጠንቀቂያ
@command_breaker
@bot.callback_query_handler(func=lambda call: call.data == "admin_system_reset")
def confirm_reset_request(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚠️ አዎ! ሙሉ በሙሉ አጽዳ", callback_data="admin_final_reset_confirm"))
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_main_menu"))
    
    text = "❗ **ጥንቃቄ፦ ሲስተም ዳግም ማስጀመር**\n\n"
    text += "ይህንን ካደረጉ የሚከተሉት መረጃዎች በሙሉ ይጠፋሉ፦\n"
    text += "• ሁሉም ድርጅቶች እና ራይደሮች\n"
    text += "• የሂሳብ እና የትርፍ መዝገቦች\n"
    text += "• የተመዘገቡ እቃዎች\n\n"
    text += "እርግጠኛ ነዎት?"
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")




# 2. ሚስጥራዊ ኮድ መጠየቅ
@command_breaker
@bot.callback_query_handler(func=lambda call: call.data == "admin_final_reset_confirm")
def ask_secret_code(call):
    msg = bot.send_message(call.message.chat.id, "🔐 ለማጽዳት ሚስጥራዊ ቁልፉን ያስገቡ (ለምሳሌ፦ `RESET123`)፦")
    bot.register_next_step_handler(msg, perform_database_reset)

# 3. ዳታቤዙን ማጽዳት
def perform_database_reset(message):
    secret_code = "RESET123" # ይህንን ኮድ ለጥንቃቄ መቀየር ትችላለህ
    
    if message.text.strip() == secret_code:
        # ዳታቤዙን ወደ መጀመሪያው ሁኔታ መመለስ
        new_db = {
            "riders_list": {},
            "vendors_list": {},
            "orders": {},
            "carts": {},
            "categories": [],
            "total_profit": 0,
            "user_list": [message.chat.id],
            "settings": {
                "vendor_commission_p": 5,
                "rider_commission_p": 10,
                "system_locked": False 
            }
        }
        save_data(new_db)
        bot.send_message(message.chat.id, "✅ ሲስተሙ ሙሉ በሙሉ ጸድቷል!")
    else:
        bot.send_message(message.chat.id, "❌ የተሳሳተ ሚስጥራዊ ቁልፍ! ማጽዳቱ ተሰርዟል።")



@command_breaker
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_val_"))
def ask_new_value(call):
    field = call.data.replace("edit_val_", "")
    msg = bot.send_message(call.message.chat.id, f"🔢 አዲሱን የ `{field}` ዋጋ በቁጥር ብቻ ያስገቡ፦")
    bot.register_next_step_handler(msg, save_new_setting_value, field)

def save_new_setting_value(message, field):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ቁጥር ብቻ ያስገቡ!")
        return

    db = load_data()
    if 'settings' not in db: db['settings'] = {}
    
    db['settings'][field] = int(message.text)
    save_data(db)
    
    bot.send_message(message.chat.id, f"✅ `{field}` ወደ {message.text} ብር ተቀይሯል!", 
                     reply_markup=get_admin_settings_markup())





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


