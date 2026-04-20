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
    """ከ Redis ዳታውን ይጭናል፣ ከሌለ መሠረታዊ መዋቅር ይፈጥራል"""
    default_db = {
        "riders_list": {},     
        "vendors_list": {}, 
        "orders": {},          
        "carts": {},           
        "categories": [],      
        "total_profit": 0,     
        "user_list": [],       
        "stats": {  # ለሪፖርት እና ለትርፍ ክትትል አዲስ የታከለ
            "total_vendor_comm": 0.0,
            "total_rider_comm": 0.0,
            "total_customer_comm": 0.0,
            "total_orders": 0
        },
        "settings": {
            "vendor_commission_p": 5,    
            "rider_commission_fixed": 5, # ለራይደር የሚታሰብ ቋሚ ትርፍ
            "service_fee": 8,            # ከደንበኛው የሚወሰድ ሰርቪስ ፊ
            "rider_fixed_fee": 30,       
            "base_delivery": 50,
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





def process_order_settlement(order_id):
    with db_lock:
        db = load_data()
        order = db['orders'].get(str(order_id))

        if not order or order.get('status') == "Completed":
            return False

        r_id = str(order['rider_id'])
        held_amount = order.get('held_amount', 0)

        # 1. ከራይደሩ የ Hold ዝርዝር ላይ ብሩን ማጽዳት
        if r_id in db['riders_list']:
            db['riders_list'][r_id]['on_hold_balance'] -= held_amount
            # ብሩ አስቀድሞ ከ wallet ላይ ተቀንሷል፣ ስለዚህ እዚህ ሌላ ቅነሳ አያስፈልግም!

        # 2. የቬንደር እና የአድሚን ትርፍ ስሌት (ካለህበት ኮድ ላይ ማስቀጠል)
        # ... (የቬንደር ዲፖዚት ቅነሳ እና የአድሚን ትርፍ መመዝገብ)
        
        order['status'] = "Completed"
        save_data(db)
        return True





def backup_db_to_channel():
    """የሪዲዝ ዳታቤዝን ፋይል አድርጎ ወደ ቴሌግራም ቻናል ይልካል"""
    try:
        db = load_data()
        file_path = 'database_backup.json'
        with open(file_path, 'w') as f:
            json.dump(db, f, indent=4)
            
        with open(file_path, 'rb') as f:
            bot.send_document(
                CHANNEL_ID, 
                f, 
                caption=f"🔄 የዳታቤዝ ባካፕ\n📅 ቀን፦ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
    except Exception as e:
        print(f"❌ Backup Error: {e}")



import math

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    መሬት ላይ ያለውን ርቀት በግምት ለማስላት 30% ጭማሪ (Multiplier) ይጠቀማል።
    """
    try:
        if None in [lat1, lon1, lat2, lon2]:
            return -1
        
        R = 6371000 # የምድር ራዲየስ በሜትር
        
        phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
        dphi = math.radians(float(lat2) - float(lat1))
        dlambda = math.radians(float(lon2) - float(lon1))

        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        air_distance = R * c
        
        # 📌 የመሬት ላይ መንገድ ማስተካከያ (Routing Multiplier)
        # አብዛኛውን ጊዜ የመንገድ ርቀት ከቀጥታ መስመር በ 1.3 እጥፍ ይበልጣል
        routing_multiplier = 1.3 
        road_distance = air_distance * routing_multiplier
        
        return round(road_distance, 2) 

    except (ValueError, TypeError, ZeroDivisionError) as e:
        print(f"❌ የርቀት ስሌት ስህተት፦ {e}")
        return -1



def get_location_keyboard():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    button = types.KeyboardButton("📍 የድርጅትዎን መገኛ (Location) እዚህ ተጭነው ይላኩ", request_location=True)
    markup.add(button)
    return markup


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







def accept_order(rider_id, order_id):
    db = load_data()
    order = db['orders'].get(str(order_id))
    
    if not order:
        bot.send_message(rider_id, "❌ ትዕዛዙ አልተገኘም።")
        return

    # 1. ራይደሩ መያዝ ያለበት (የእቃ ዋጋ + የድርጅቱ ለቦቱ የሚከፍለው ኮሚሽን)
    item_price = order['item_total']
    
    # እዚህ ጋር 'vendor_commission_p' መጠቀማችንን እርግጠኛ እንሁን
    bot_comm_p = db['settings'].get('vendor_commission_p', 5) 
    bot_commission = item_price * (bot_comm_p / 100)
    
    total_to_hold = item_price + bot_commission
    rider_wallet = db['riders_list'][str(rider_id)].get('wallet', 0)

    if rider_wallet >= total_to_hold:
        # 2. በትዕዛዙ ላይ መረጃ መመዝገብ
        order['rider_id'] = rider_id
        order['status'] = "Accepted"
        order['held_amount'] = total_to_hold 
        
        # 3. ብሩን ከራይደሩ ዋሌት ቀንሶ 'Hold' ላይ ማድረግ
        db['riders_list'][str(rider_id)]['wallet'] -= total_to_hold
        
        # 'on_hold_balance' ቁልፍ መኖሩን ማረጋገጥ
        if 'on_hold_balance' not in db['riders_list'][str(rider_id)]:
            db['riders_list'][str(rider_id)]['on_hold_balance'] = 0
            
        db['riders_list'][str(rider_id)]['on_hold_balance'] += total_to_hold
        
        save_data(db)
        bot.send_message(rider_id, f"✅ ትዕዛዙን ተቀብለዋል።\n💰 የታገደ ብር፦ {total_to_hold} ETB\n\nእባክዎ እቃውን ከድርጅቱ ተረክበው ለደንበኛው ያድርሱ።")
    else:
        bot.send_message(rider_id, f"❌ በቂ ባላንስ የለዎትም።\nየሚያስፈልገው፦ {total_to_hold} ETB\nየእርስዎ፦ {rider_wallet} ETB")



def cancel_order(order_id):
    db = load_data()
    order = db['orders'].get(str(order_id))
    r_id = str(order.get('rider_id'))
    held_amount = order.get('held_amount', 0)

    if r_id in db['riders_list'] and held_amount > 0:
        db['riders_list'][r_id]['wallet'] += held_amount # ብሩን መመለስ
        db['riders_list'][r_id]['on_hold_balance'] -= held_amount
        order['status'] = "Cancelled"
        save_data(db)
        bot.send_message(r_id, f"⚠️ ትዕዛዝ ተሰርዟል። የታገደው {held_amount} ብር ወደ ዋሌትዎ ተመልሷል።")
 






def save_new_vendor(message, v_id, cat_name):
    # cat_name ከ callback_query የመጣ ከሆነ 'select_cat_for_vendor:ምግብ' ሊሆን ይችላል
    if isinstance(cat_name, str) and ":" in cat_name:
        clean_cat = cat_name.split(":")[-1]
    elif isinstance(cat_name, (list, tuple)):
        clean_cat = cat_name[-1]
    else:
        clean_cat = str(cat_name)

    v_name = message.text.strip()
    db = load_data()
    
    if 'vendors_list' not in db: db['vendors_list'] = {}

    db['vendors_list'][str(v_id)] = {
        "vendor_name": v_name,
        "name": v_name,
        "category": clean_cat, 
        "deposit_balance": 0,
        "items": {},
        "is_active": True
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ ድርጅት '{v_name}' በምድብ '{clean_cat}' ተመዝግቧል!")





def process_final_settlement(order_id):
    db = load_data()
    order = db.get('orders', {}).get(str(order_id))
    
    if not order or order.get('status') == "Completed":
        return "⚠️ ትዕዛዙ አልተገኘም ወይም ቀድሞ ተጠናቅቋል።"

    v_id = str(order['vendor_id'])
    item_price = order['item_total']
    
    # የኮሚሽን መጠኖችን ማግኘት
    v_comm_p = db.get('settings', {}).get('vendor_commission_p', 3)
    r_fixed = db.get('settings', {}).get('rider_commission_fixed', 5)
    s_fee = db.get('settings', {}).get('service_fee', 8)

    # ትርፍ ስሌት
    vendor_profit = item_price * (v_comm_p / 100)
    total_order_profit = vendor_profit + r_fixed + s_fee
    
    # --- ዳታቤዝ ማዘመን ---
    # 1. ቬንደር ባላንስ
    if v_id in db['vendors_list']:
        db['vendors_list'][v_id]['deposit_balance'] -= (item_price + vendor_profit)

    # 2. ትርፍ መመዝገቢያ (Stats)
    if 'stats' not in db: # ለጥንቃቄ
        db['stats'] = {"total_vendor_comm": 0, "total_rider_comm": 0, "total_customer_comm": 0, "total_orders": 0}
    
    db['stats']['total_vendor_comm'] += vendor_profit
    db['stats']['total_rider_comm'] += r_fixed
    db['stats']['total_customer_comm'] += s_fee
    db['stats']['total_orders'] += 1
    
    # 3. ጠቅላላ ትርፍ
    db['total_profit'] = db.get('total_profit', 0) + total_order_profit
    
    order['status'] = "Completed"
    save_data(db)
    
    return f"✅ ሂሳብ ተወራርዷል!\n💰 ትርፍ፦ {total_order_profit:.2f} ETB"





def accept_order_with_hold(rider_id, order_id):
    db = load_data()
    order = db['orders'].get(str(order_id))
    
    # ራይደሩ መያዝ ያለበት = (የእቃው ዋጋ + የዴሊቨሪ ክፍያ)
    # ማሳሰቢያ፡ ራይደሩ ከደንበኛው ሙሉውን ስለሚቀበል ነው ይሄ የሚያዘው
    item_price = order['item_total']
    delivery_fee = order['delivery_fee']
    total_to_hold = item_price + delivery_fee
    
    rider_wallet = db['riders_list'][str(rider_id)].get('wallet', 0)

    if rider_wallet >= total_to_hold:
        # ብሩን ከዋሌት ቀንሶ 'Hold' ላይ ማድረግ
        db['riders_list'][str(rider_id)]['wallet'] -= total_to_hold
        db['riders_list'][str(rider_id)]['on_hold_balance'] += total_to_hold
        
        order['rider_id'] = rider_id
        order['status'] = "Accepted"
        order['held_amount'] = total_to_hold
        
        save_data(db)
        return True, f"✅ ተቀብለዋል። {total_to_hold} ብር ታግዷል።"
    else:
        return False, "❌ በቂ ባላንስ የለዎትም።"






def finalize_escrow_settlement(order_id):
    with db_lock:
        db = load_data()
        order = db['orders'].get(str(order_id))
        
        if not order or order.get('status') == "Completed":
            return False

        v_id = str(order['vendor_id'])
        r_id = str(order['rider_id'])
        held_amount = order.get('held_amount', 0)
        item_price = order['item_total']
        
        # --- ሀ. የድርጅቱ ሂሳብ (Negative Balance Logic) ---
        # ከድርጅቱ ላይ (የእቃ ዋጋ + የቦቱ ኮሚሽን) መቀነስ
        bot_comm_p = db['settings'].get('vendor_commission_p', 5)
        bot_commission = item_price * (bot_comm_p / 100)
        total_vendor_deduction = item_price + bot_commission
        
        # ባላንሱ Negative ቢሆንም ይቀንሳል
        db['vendors_list'][v_id]['deposit_balance'] -= total_vendor_deduction
        
        # --- ለ. የራይደሩ ሂሳብ ---
        # የታገደውን ብር ማጽዳት (አስቀድሞ ከዋሌቱ ስለተቀነሰ እዚህ ማጥፋት ብቻ ነው)
        db['riders_list'][r_id]['on_hold_balance'] -= held_amount
        # ለራይደሩ ትርፉን (Delivery Fee) ወደ ዋሌቱ መመለስ
        db['riders_list'][r_id]['wallet'] += order['delivery_fee']
        
        # --- ሐ. የአድሚን ትርፍ ---
        db['total_profit'] += bot_commission
        
        # ሁኔታውን መቀየር
        order['status'] = "Completed"
        save_data(db)
        return True




def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True






def get_admin_dashboard(user_id):
    try:
        db = load_data()
        markup = types.InlineKeyboardMarkup(row_width=2)

        # --- በተኖቹን መፍጠር ---
        btn_broadcast = types.InlineKeyboardButton("📢 ማስታወቂያ", callback_data="admin_broadcast")
        btn_fund = types.InlineKeyboardButton("💳 ብር መሙያ", callback_data="admin_add_funds")
        btn_balance = types.InlineKeyboardButton("📉 ክትትል", callback_data="admin_monitor_balance")
        btn_profit = types.InlineKeyboardButton("💰 ትርፍ", callback_data="admin_profit_track")
        
        # ስሙን እዚህ አስተካክለነዋል (ከታች ከምንጨምረው ጋር አንድ እንዲሆን)
        btn_system_reset = types.InlineKeyboardButton("🗑 Reset System", callback_data="admin_system_reset")

        btn_live_orders = types.InlineKeyboardButton("📋 ቀጥታ ትዕዛዝ", callback_data="admin_live_orders")
        btn_add_vendor = types.InlineKeyboardButton("➕ አዲስ ድርጅት", callback_data="admin_add_vendor")
        btn_add_rider = types.InlineKeyboardButton("➕ አዲስ driver", callback_data="admin_add_rider")
        btn_vendors = types.InlineKeyboardButton("🏢 ድርጅቶች", callback_data="admin_list_vendors")
        btn_view_cats = types.InlineKeyboardButton("📁 ምድቦች ማሳያ", callback_data="admin_view_categories")
        btn_add_cats = types.InlineKeyboardButton("➕ አዲስ ምድብ", callback_data="admin_manage_cats")
        btn_riders = types.InlineKeyboardButton("🛵 driver", callback_data="admin_rider_status")
        btn_set_commission = types.InlineKeyboardButton("⚙️ ኮሚሽን", callback_data="admin_set_commission")
        btn_block = types.InlineKeyboardButton("🚫 አግድ/ፍቀድ", callback_data="admin_block_manager")
        btn_lock = types.InlineKeyboardButton("🔒 ሲስተም ዝጋ", callback_data="admin_system_lock")
        btn_stats = types.InlineKeyboardButton("📈 ሪፖርት", callback_data="admin_full_stats")

        # --- ወደ Markup መጨመር ---
        markup.add(btn_broadcast)
        markup.add(btn_fund, btn_balance)
        markup.add(btn_profit, btn_system_reset) # እዚህ ጋር ስሙ ተስተካክሏል
        markup.add(btn_live_orders)
        markup.add(btn_view_cats, btn_add_cats) 
        markup.add(btn_stats) 
        markup.add(btn_add_vendor, btn_add_rider)
        markup.add(btn_vendors, btn_riders)
        markup.add(btn_set_commission, btn_block)
        markup.add(btn_lock)

        return markup
    except Exception as e:
        print(f"Error building dashboard: {e}")
        return None



def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add( "📊 ሪፖርት" )
    return markup





def get_vendor_dashboard_elements(v_id):
    db = load_data()
    v_info = db.get('vendors_list', {}).get(str(v_id))
    
    if not v_info:
        return "❌ የድርጅት መረጃ አልተገኘም!", None

    v_name = v_info.get('name', 'የእኔ ድርጅት')
    balance = v_info.get('deposit_balance', 0)
    items_count = len(v_info.get('items', {}))
    
    # ንቁ ትዕዛዞችን መቁጠር
    active_orders = 0 
    for order in db.get('orders', {}).values():
        if str(order.get('vendor_id')) == str(v_id) and order.get('status') not in ['Completed', 'Cancelled']:
            active_orders += 1

    summary_text = (
        f"🏠 **የድርጅት ዳሽቦርድ፦ {v_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 **ቀሪ ባላንስ፦** `{balance:,.2f} ETB`\n"
        f"📦 **ንቁ ትዕዛዞች፦** `{active_orders}`\n"
        f"🛍 **ጠቅላላ እቃዎች፦** `{items_count}`\n"
        f"🟢 **ሁኔታ፦** ክፍት (ለደንበኞች ይታያሉ)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 ስራ ለመጀመር ከታች ያሉትን በተኖች ይጠቀሙ፦"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ እቃ ጨምር", callback_data="vendor_add_item"),
        types.InlineKeyboardButton("📦 የእኔ እቃዎች", callback_data="vendor_my_items"),
        types.InlineKeyboardButton("📈 የሽያጭ ታሪክ", callback_data="vendor_sales_report"),
        types.InlineKeyboardButton("⚙️ መቆጣጠሪያ", callback_data="vendor_settings"),
        types.InlineKeyboardButton("🔄 አድስ", callback_data="vendor_refresh")
    )
    return summary_text, markup




@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_id_str = str(user_id) # ለዳታቤዝ ንፅፅር እንዲመች
    db = load_data()

    # 1. ተጠቃሚውን ለብሮድካስት መመዝገብ
    if 'user_list' not in db: db['user_list'] = []
    if user_id not in db['user_list']:
        db['user_list'].append(user_id)
        save_data(db)

    # 2. አድሚን ከሆነ
    if user_id in ADMIN_IDS:
        markup = get_admin_dashboard(user_id)
        return bot.send_message(
            message.chat.id, 
            "👋 ሰላም ጌታዬ! እንኳን ወደ **BDF Delivery** መቆጣጠሪያ መጡ።\nከታች ያሉትን አማራጮች ተጠቅመው ሲስተሙን ያስተዳድሩ።",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    # 3. ቬንደር (ድርጅት) ከሆነ
    vendors_list = db.get('vendors_list', {})
    if user_id_str in vendors_list:
        v_info = vendors_list[user_id_str]
        
        # ሎኬሽን ገና ካልላከ ሎኬሽን ይጠይቃል
        if 'lat' not in v_info or 'lon' not in v_info:
            text = (
                f"ሰላም {v_info.get('name', 'ባለቤት')}! 👋\n\n"
                "ወደ BDF Delivery እንኳን በደህና መጡ። ስራ ከመጀመርዎ በፊት የድርጅቱን ትክክለኛ መገኛ (Location) መላክ አለብዎት።\n"
                "ይህ ለደንበኞች የዴሊቨሪ ክፍያ ስሌት ጥቅም ላይ ይውላል።\n\n"
                "👇 እባክዎ ከታች ያለውን በተን ተጭነው ሎኬሽን ይላኩ።"
            )
            return bot.send_message(message.chat.id, text, reply_markup=get_location_keyboard())
        
        # ሎኬሽን ካለው ቀጥታ ወደ ቬንደር ዳሽቦርድ
        text, markup = get_vendor_dashboard_elements(user_id)
        return bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

    # 4. ተራ ደንበኛ ከሆነ
    welcome_text = (
        "እንኳን ወደ **BDF Delivery** በደህና መጡ! 👋\n\n"
        "በቀላሉ የሚፈልጉትን እቃ ይዘዙ፣ ያሉበት እናደርሳለን።\n"
        "ለመጀመር ከታች ያሉትን በተኖች ይጠቀሙ።"
    )
    # የደንበኛ ማርካፕ እዚህ ጋር መጨመር ትችላለህ
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")



# አድሚኑ ወደ ዳሽቦርድ መመለስ ሲፈልግ (ለተደጋጋሚ አጠቃቀም)
@bot.callback_query_handler(func=lambda call: call.data == "admin_main_menu")
def back_to_dashboard(call):
    if call.from_user.id in ADMIN_IDS:
        markup = get_admin_dashboard(call.from_user.id)
        bot.edit_message_text(
            "👋 የአድሚን ዳሽቦርድ", 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup
        )
    bot.answer_callback_query(call.id)



@bot.callback_query_handler(func=lambda call: call.data == "admin_main_menu")
def back_to_admin(call):
    try:
        user_id = call.from_user.id
        # የአድሚን ዳሽቦርድ ማርካፕን እንጠራለን
        markup = get_admin_dashboard(user_id)
        
        # የነበረውን መልዕክት ወደ ዋናው ዳሽቦርድ ይቀይረዋል
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="👋 ሰላም ጌታዬ! ወደ አድሚን ዳሽቦርድ ተመልሰዋል።\nከታች ካሉት አማራጮች አንዱን ይምረጡ፦",
            reply_markup=markup
        )
        # በተኑ ሲነካ የሚመጣውን 'Loading' ምልክት ያጠፋል
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"Back to Admin Error: {e}")
        bot.answer_callback_query(call.id, "❌ ወደ ዋናው ገጽ መመለስ አልተቻለም።")




@bot.message_handler(content_types=['location'])
def save_vendor_location(message):
    user_id = str(message.from_user.id)
    db = load_data()
    
    if user_id in db.get('vendors_list', {}):
        db['vendors_list'][user_id]['lat'] = message.location.latitude
        db['vendors_list'][user_id]['lon'] = message.location.longitude
        save_data(db)
        
        # ሎኬሽን በተኑን አጥፍተን ምድብ እንዲመርጥ እንጠይቃለን
        bot.send_message(
            message.chat.id, 
            "✅ ሎኬሽንዎ ተመዝግቧል!\nአሁን ደግሞ የድርጅትዎን አይነት (Category) ይምረጡ፦", 
            reply_markup=get_category_markup()
        )





# 1. የራይደር ምዝገባ መጀመሪያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_rider")
def start_add_rider(call):
    msg = bot.send_message(call.message.chat.id, "🆔 የራይደሩን (Driver) Telegram User ID ያስገቡ፦")
    bot.register_next_step_handler(msg, process_rider_id)

def process_rider_id(message):
    r_id = message.text.strip()
    if not r_id.isdigit():
        msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ ID ቁጥር መሆን አለበት። ድጋሚ ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_rider_id)
    
    msg = bot.send_message(message.chat.id, "👤 የራይደሩን ሙሉ ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, lambda m: save_new_rider(m, r_id))

def save_new_rider(message, r_id):
    name = message.text.strip()
    db = load_data()
    
    if 'riders_list' not in db: db['riders_list'] = {}
    
    db['riders_list'][r_id] = {
        "name": name,
        "wallet": 0,
        "status": "offline",
        "is_active": True
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ ራይደር '{name}' በትክክል ተመዝግቧል!")






# ለገንዘብ ዝውውር ጊዜያዊ መረጃ መያዣ
temp_topup_data = {}

# 1. ባላንስ መሙያ በተን ሲነካ
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_funds")
def start_topup(call):
    msg = bot.send_message(call.message.chat.id, "🆔 ባላንስ ሊሞላለት ወይም ሊቀነስለት የሚገባውን ሰው (Rider/Vendor) Telegram ID ያስገቡ፦")
    bot.register_next_step_handler(msg, find_user_for_topup)

# 2. ተጠቃሚውን መፈለግ
def find_user_for_topup(message):
    uid = message.text.strip()
    db = load_data()
    
    user_data = None
    role = ""
    
    if uid in db['vendors_list']:
        user_data = db['vendors_list'][uid]
        role = "vendor"
    elif uid in db['riders_list']:
        user_data = db['riders_list'][uid]
        role = "rider"
        
    if not user_data:
        bot.send_message(message.chat.id, "❌ በዚህ ID የተመዘገበ ራይደር ወይም ድርጅት አልተገኘም።")
        return

    temp_topup_data[message.chat.id] = {'target_id': uid, 'role': role}
    
    text = f"👤 ተጠቃሚ፦ {user_data['name']}\n"
    text += f"🎭 ሚና፦ {role.capitalize()}\n"
    if role == "vendor":
        text += f"💰 የአሁኑ ዲፖዚት፦ {user_data['deposit_balance']} ብር\n\n"
        text += "እባክዎ የሚጨምሩትን የብር መጠን ያስገቡ፦"
    else:
        text += f"💳 የአሁኑ ዋሌት፦ {user_data['wallet']} ብር\n\n"
        text += "ብር ለመሙላት (ለምሳሌ: 500) \nለመቀነስ ደግሞ የይለይ ምልክት ይጠቀሙ (ለምሳሌ: -200) ያስገቡ፦"

    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, process_balance_update)

# 3. የሂሳብ ማስተካከያውን መተግበር
def process_balance_update(message):
    try:
        amount = float(message.text.strip())
        admin_id = message.chat.id
        t_data = temp_topup_data.get(admin_id)
        
        if not t_data: return

        db = load_data()
        target_id = t_data['target_id']
        role = t_data['role']
        
        if role == "vendor":
            # ለድርጅት ሁሌም መደመር ነው (Pre-payment)
            db['vendors_list'][target_id]['deposit_balance'] += amount
            new_bal = db['vendors_list'][target_id]['deposit_balance']
            msg_text = f"✅ ለድርጅቱ {amount} ብር ተጨምሯል። አዲስ ዲፖዚት፦ {new_bal} ብር"
            
        else:
            # ለራይደር መደመርም መቀነስም ይቻላል
            db['riders_list'][target_id]['wallet'] += amount
            new_bal = db['riders_list'][target_id]['wallet']
            if amount > 0:
                msg_text = f"✅ ለራይደሩ {amount} ብር ተሞልቷል። አዲስ ዋሌት፦ {new_bal} ብር"
            else:
                msg_text = f"✅ ከራይደሩ ዋሌት {abs(amount)} ብር ተቀንሷል። ቀሪ ዋሌት፦ {new_bal} ብር"

        save_data(db)
        bot.send_message(admin_id, msg_text)
        
        # ለተጠቃሚው ማሳወቂያ መላክ (Notification)
        try:
            bot.send_message(target_id, f"🔔 የሂሳብ ማስተካከያ ተደርጓል!\nየአሁኑ ባላንስዎ፦ {new_bal} ብር")
        except:
            pass # ተጠቃሚው ቦቱን ካቆመው ስህተት እንዳይሰጥ
            
        
        del temp_topup_data[admin_id]
        
    except ValueError:
        msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ እባክዎ በትክክል ቁጥር ያስገቡ (ለምሳሌ፦ 500 ወይም -200)፦")
        bot.register_next_step_handler(msg, process_balance_update)
    
    except Exception as e:
        # ማንኛውም ሌላ ስህተት ቢፈጠር ሲስተሙ እንዳይቆም ይረዳል
        print(f"Error in balance update: {e}")
        bot.send_message(message.chat.id, "❌ የቴክኒክ ስህተት አጋጥሟል። እባክዎ እንደገና ይሞክሩ።")








# መጀመሪያ ID ለመቀበል
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_vendor")
def start_add_vendor(call):
    db = load_data()
    categories = db.get('categories', [])
    
    if not categories:
        return bot.answer_callback_query(call.id, "⚠️ ድርጅት ከመመዝገብዎ በፊት መጀመሪያ 'አዲስ ምድብ' (Category) ይፍጠሩ!", show_alert=True)
    
    # የምድብ ምርጫ በተኖች
    markup = types.InlineKeyboardMarkup()
    for cat in categories:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"select_cat_for_vendor:{cat}"))
    
    bot.edit_message_text("📂 ለድርጅቱ ምድብ ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)





@bot.callback_query_handler(func=lambda call: call.data.startswith('set_cat_'))
def set_vendor_category(call):
    user_id = str(call.from_user.id)
    category = call.data.replace('set_cat_', '')
    db = load_data()
    
    if user_id in db.get('vendors_list', {}):
        db['vendors_list'][user_id]['category'] = category
        save_data(db)
        
        bot.answer_callback_query(call.id, f"ምድብ፦ {category} ተመርጧል")
        bot.delete_message(call.message.chat.id, call.message.message_id) # ምርጫውን ማጥፋት
        
        # አሁን ዳሽቦርዱን አሳየው
        text, markup = get_vendor_dashboard_elements(user_id)
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")




# ምድብ ከተመረጠ በኋላ ID መጠየቂያ
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_cat_for_vendor:"))
def get_id_after_cat(call):
    # .split(":") ካደረግን በኋላ ሁለተኛውን (index 1) ብቻ ነው የምንፈልገው
    parts = call.data.split(":")
    cat_name = parts # እውነተኛውን የምድብ ስም ብቻ ለመውሰድ
    
    msg = bot.send_message(call.message.chat.id, f"🆔 የ[{cat_name}] ባለቤት Telegram ID ያስገቡ፦")
    bot.register_next_step_handler(msg, lambda m: process_vendor_id(m, cat_name))

def process_vendor_id(message, cat_name):
    v_id = message.text.strip()
    if not v_id.isdigit():
        msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ ID ቁጥር መሆን አለበት። ድጋሚ ያስገቡ፦")
        return bot.register_next_step_handler(msg, lambda m: process_vendor_id(m, cat_name))

    msg = bot.send_message(message.chat.id, "🏢 የድርጅቱን ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, lambda m: save_new_vendor(m, v_id, cat_name))

def save_new_vendor(message, v_id, cat_name_list):
    v_name = message.text.strip()
    db = load_data()

    if 'vendors_list' not in db: db['vendors_list'] = {}

    # 1. የምድቡን ስም ብቻ ነጥሎ ማውጣት (ያንን ረጅም ዝርዝር ለማጥፋት)
    # cat_name_list ['select_cat_for_vendor', '🍔 ምግብ ቤት'] ከሆነ 
    # እኛ የምንፈልገው index 1 ላይ ያለውን ብቻ ነው
    actual_cat = cat_name_list if isinstance(cat_name_list, list) else cat_name_list

    # 2. ዳታውን በሁለቱም Key (ስም) ማስቀመጥ (ለጥንቃቄ)
    db['vendors_list'][v_id] = {
        "vendor_name": v_name, # ሪፖርቱ የሚፈልገው ይሄን ሊሆን ይችላል
        "name": v_name,        # ለሌላ ቦታ ካስፈለገህ
        "category": actual_cat,
        "deposit_balance": 0,
        "items": {},
        "is_active": True
    }
    
    save_data(db)
    
    # እዚህ ጋር መልዕክቱ ሲላክም ትክክለኛውን የምድብ ስም ብቻ እንዲያሳይ
    bot.send_message(message.chat.id, f"✅ ድርጅት '{v_name}' በምድብ '{actual_cat}' ተመዝግቧል!")




# 1. 'ምድብ' መጨመር ሲመረጥ
@bot.callback_query_handler(func=lambda call: call.data == "admin_view_categories")
def admin_categories_menu(call):
    db = load_data()
    cats = db.get('categories', [])
    
    text = "📁 **እስካሁን ያሉ የምድብ አይነቶች**\n\n"
    if not cats:
        text += "ገና ምንም ምድብ አልተመዘገበም።"
    else:
        for i, c in enumerate(cats, 1):
            text += f"{i}. {c}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ አዲስ ምድብ ጨምር", callback_data="admin_add_cat"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# 2. የምድብ ስም መቀበያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_cat")
def ask_category_name(call):
    msg = bot.send_message(call.message.chat.id, "✏️ የምድቡን ስም ይጻፉ (ለምሳሌ፦ ሱፐርማርኬት)፦")
    bot.register_next_step_handler(msg, save_category)

def save_category(message):
    cat_name = message.text.strip()
    db = load_data()
    
    if cat_name not in db['categories']:
        db['categories'].append(cat_name)
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ምድብ '{cat_name}' በተሳካ ሁኔታ ተፈጥሯል።")
    else:
        bot.send_message(message.chat.id, "⚠️ ይህ ምድብ ቀድሞውኑ አለ።")




# 1. 'ምድቦች ማሳያ' - ያሉትን ምድቦች ዝርዝር ያሳያል
@bot.callback_query_handler(func=lambda call: call.data == "admin_view_categories")
def view_all_categories(call):
    db = load_data()
    cats = db.get('categories', [])
    
    text = "📁 **የተመዘገቡ የምድብ አይነቶች**\n\n"
    if not cats:
        text += "ገና ምንም ምድብ አልተመዘገበም። እባክዎ አዲስ ምድብ ይጨምሩ።"
    else:
        for i, cat in enumerate(cats, 1):
            text += f"{i}. {cat}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ አዲስ ምድብ ጨምር", callback_data="admin_manage_cats"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# 2. 'አዲስ ምድብ' - ስም መቀበያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_cats")
def ask_new_cat_name(call):
    msg = bot.send_message(call.message.chat.id, "✏️ ለመጨመር የሚፈልጉትን የምድብ ስም ይጻፉ፦\n(ለምሳሌ፦ 🍔 ምግብ ቤት ወይም 💊 መድኃኒት ቤት)")
    bot.register_next_step_handler(msg, save_category_logic)

# 3. ምድቡን ዳታቤዝ ላይ ማስቀመጥ
def save_category_logic(message):
    new_cat = message.text.strip()
    db = load_data()
    
    if 'categories' not in db:
        db['categories'] = []
        
    if new_cat in db['categories']:
        bot.send_message(message.chat.id, f"⚠️ '{new_cat}' ቀደም ብሎ ተመዝግቧል።")
    else:
        db['categories'].append(new_cat)
        save_data(db)
        bot.send_message(message.chat.id, f"✅ ምድብ '{new_cat}' በተሳካ ሁኔታ ተመዝግቧል።")
    
    # ተመልሶ ወደ ምድብ ማሳያ እንዲሄድ ማድረግ ይቻላል






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
    
    # የሂሳብ ስሌቶች
    total_vendor_deposit = sum(v.get('deposit_balance', 0) for v in vendors.values())
    total_rider_wallet = sum(r.get('wallet', 0) for r in riders.values())
    system_profit = db.get('total_profit', 0)

    report = "📊 **ጥልቅ የቢዝነስ ትንታኔ (Full Analytics)**\n"
    report += "━━━━━━━━━━━━━━━━━━━━\n\n"

    # 🏢 የድርጅቶች ሁኔታ (Vendors)
    report += "🏢 **የድርጅቶች ሁኔታ (Vendors)**\n"
    report += f"• ጠቅላላ ድርጅቶች፦ `{len(vendors)}` \n"
    report += f"• አጠቃላይ ዲፖዚት፦ `{total_vendor_deposit}` ብር\n"
    report += "------------------------\n\n"

    # 🛵 የራይደሮች ሁኔታ (Drivers)
    report += "🛵 **የራይደሮች ሁኔታ (Drivers)**\n"
    report += f"• ጠቅላላ ራይደሮች፦ `{len(riders)}` \n"
    report += f"• አጠቃላይ ዋሌት፦ `{total_rider_wallet}` ብር\n"
    online_riders = sum(1 for r in riders.values() if r.get('status') == 'online')
    report += f"• አሁን በስራ ላይ (Online)፦ `{online_riders}`\n"
    report += "------------------------\n\n"

    # 💰 የገንዘብ እና የትዕዛዝ ሁኔታ
    report += "💰 **ፋይናንስ እና ትዕዛዞች**\n"
    report += f"• የተሳኩ ትዕዛዞች፦ `{len(orders)}` \n"
    report += f"• አጠቃላይ የሲስተም ትርፍ፦ `{system_profit}` ብር 💵\n"
    report += "━━━━━━━━━━━━━━━━━━━━\n\n"

    # 🏆 ምርጥ አፈጻጸም (Top Performers)
    report += "🏆 **ምርጥ አፈጻጸም**\n"
    # እዚህ ጋር ብዙ ትዕዛዝ ያላቸውን በቀጣይ በLogic መጨመር ይቻላል
    report += "• ምርጥ ድርጅት፦ _ገና አልተለየም_\n"
    report += "• ንቁ ራይደር፦ _ገና አልተለየም_\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_full_stats"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu"))

    bot.edit_message_text(report, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")





# 1. ዳግም ማስጀመሪያ መጀመሪያ - ማስጠንቀቂያ
# 1. ዳግም ማስጀመሪያ መጀመሪያ - ማስጠንቀቂያ
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
