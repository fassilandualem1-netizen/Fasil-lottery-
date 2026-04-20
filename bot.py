import telebot
from telebot import types
import os, json, math, threading, time
from flask import Flask
from upstash_redis import Redis

# --- 1. ውቅረት ---
TOKEN = "8663228906:AAFsTC0fKqAVEWMi7rk59iSdfVD-1vlJA0Y"
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
        "settings": {
            "vendor_commission_p": 5,    # 5% ኮሚሽን ከእቃ ዋጋ
            "rider_commission_p": 10,   # 10% ኮሚሽን ከዴሊቨሪ ክፍያ
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

            # አዳዲስ ቁልፎች በቆየው ዳታቤዝ ውስጥ ከሌሉ እንዲጨመሩ (Merge)
            for key, value in default_db.items():
                if key not in loaded_db:
                    loaded_db[key] = value
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



def accept_order(rider_id, order_id):
    db = load_data()
    order = db['orders'].get(str(order_id))
    
    # ራይደሩ መክፈል ያለበት (የእቃ ዋጋ + የቦቱ ኮሚሽን)
    item_price = order['item_total']
    # ከ settings ትክክለኛውን key መጠቀማችንን እናረጋግጥ
    bot_comm_p = db['settings'].get('rider_commission_p', 10) 
    bot_commission = item_price * (bot_comm_p / 100)
    
    total_to_hold = item_price + bot_commission
    rider_wallet = db['riders_list'][str(rider_id)].get('wallet', 0)

    if rider_wallet >= total_to_hold:
        order['rider_id'] = rider_id
        order['status'] = "Accepted"
        order['held_amount'] = total_to_hold # በትዕዛዙ ላይ መጠኑን መመዝገብ
        
        # ብሩን 'Hold' ማድረግ
        db['riders_list'][str(rider_id)]['wallet'] -= total_to_hold
        db['riders_list'][str(rider_id)]['on_hold_balance'] += total_to_hold
        
        save_data(db)
        bot.send_message(rider_id, f"✅ ትዕዛዙን ተቀብለዋል። {total_to_hold} ETB በጊዜያዊነት ታግዷል።")
    else:
        bot.send_message(rider_id, "❌ በቂ ባላንስ የለዎትም።")



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
    # 'cat_name' ውስጥ የሚመጣውን የተዝረከረከ ጽሁፍ ያጠራል
    if isinstance(cat_name, (list, tuple)):
        clean_cat = cat_name[-1] # የመጨረሻውን ንጹህ ስም ይወስዳል
    else:
        # 'select_cat_for_vendor' የሚል ጽሁፍ ካለበት እሱን ያጠፋል
        clean_cat = str(cat_name).replace("select_cat_for_vendor", "").replace(":", "").strip()
    
    # ባዶ ከሆነ "ምድብ የሌለው" ይበል
    if not clean_cat: clean_cat = "አጠቃላይ"

    v_name = message.text.strip()
    db = load_data()
    
    db['vendors_list'][v_id] = {
        "name": v_name,
        "category": clean_cat, # አሁን ንጹህ ስሙ ብቻ ይገባል
        "deposit_balance": 0,
        "is_active": True
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ ድርጅት '{v_name}' በትክክል ተመዝግቧል!")





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



@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        db = load_data()

        # 1. ተጠቃሚውን በ user_list ውስጥ ከሌለ መመዝገብ
        if user_id not in db.get('user_list', []):
            db['user_list'].append(user_id)
            save_data(db)

        # 2. አድሚን ከሆነ (ADMIN_IDS ውስጥ ካለ)
        if user_id in ADMIN_IDS:
            markup = get_admin_dashboard(user_id)
            return bot.send_message(
                user_id, 
                "👑 **እንኳን ደህና መጡ ጌታዬ!**\n\nየ BDF አስተዳዳሪ ዳሽቦርድ ዝግጁ ነው።", 
                reply_markup=markup, 
                parse_mode="Markdown"
            )

        # 3. ራይደር (Driver) መሆኑን ማረጋገጥ
        uid_str = str(user_id)
        if uid_str in db.get('riders_list', {}):
            rider_info = db['riders_list'][uid_str]
            # ራይደሩ ታግዶ ከሆነ
            if not rider_info.get('is_active', True):
                return bot.send_message(user_id, "🚫 አካውንትዎ ለጊዜው ታግዷል። እባክዎ አድሚኑን ያነጋግሩ።")
            
            # የራይደር ሜኑ እዚህ ይገባል (አሁን በ ReplyKeyboardMarkup)
            return bot.send_message(user_id, f"🛵 ሰላም {rider_info['name']}!\nወደ ስራ ለመግባት ዝግጁ ነዎት?", reply_markup=get_main_menu())

        # 4. ቬንደር (Vendor) መሆኑን ማረጋገጥ
        if uid_str in db.get('vendors_list', {}):
            vendor_info = db['vendors_list'][uid_str]
            return bot.send_message(user_id, f"🏢 ሰላም {vendor_info['name']}!\nትዕዛዞችን ለመከታተል ዝግጁ ነዎት?", reply_markup=get_main_menu())

        # 5. ተራ ተጠቃሚ (Customer) ከሆነ
        welcome_text = (
            f"👋 ሰላም {message.from_user.first_name}!\n"
            f"እንኳን ወደ **BDF Delivery** በደህና መጡ።\n\n"
            f"የእርስዎ መለያ ቁጥር (ID): `{user_id}`"
        )
        bot.send_message(user_id, welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

    except Exception as e:
        print(f"❌ Start Command Error: {e}")
        bot.send_message(message.chat.id, "🔄 ሲስተሙን እያደስኩት ነው... እባክዎ ጥቂት ቆይተው /start ይበሉ።")











# --- 1. ምዝገባ መጀመሪያ ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_rider")
def start_add_rider(call):
    try:
        # አድሚን መሆኑን ማረጋገጥ
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!")

        msg = bot.send_message(call.message.chat.id, "🆔 የራይደሩን (Driver) Telegram User ID ያስገቡ፦\n\n(ለመሰረዝ 'cancel' ይበሉ)")
        bot.register_next_step_handler(msg, process_rider_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error in start_add_rider: {e}")
        bot.send_message(call.message.chat.id, "❌ ስህተት ተፈጥሯል፣ እባክዎ ደግመው ይሞክሩ።")

# --- 2. ID መቀበያ ---
def process_rider_id(message):
    try:
        r_id = message.text.strip()
        
        if r_id.lower() == 'cancel':
            return send_admin_dashboard(message) # ወደ ዳሽቦርድ መመለሻ

        if not r_id.isdigit():
            msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ ID ቁጥር መሆን አለበት። ድጋሚ ያስገቡ፦")
            return bot.register_next_step_handler(msg, process_rider_id)
        
        # ራይደሩ ቀድሞ ተመዝግቦ እንደሆነ መፈተሽ
        db = load_data()
        if r_id in db.get('riders_list', {}):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main_menu"))
            return bot.send_message(message.chat.id, "❌ ይህ ራይደር ቀድሞ ተመዝግቧል!", reply_markup=markup)

        msg = bot.send_message(message.chat.id, "👤 የራይደሩን ሙሉ ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, lambda m: save_new_rider(m, r_id))
    except Exception as e:
        print(f"Error in process_rider_id: {e}")

# --- 3. ዳታውን ሴቭ ማድረጊያ ---
def save_new_rider(message, r_id):
    try:
        name = message.text.strip()
        if name.lower() == 'cancel':
            return send_admin_dashboard(message)

        db = load_data()
        if 'riders_list' not in db: db['riders_list'] = {}
        
        db['riders_list'][r_id] = {
            "name": name,
            "wallet": 0.0,
            "on_hold_balance": 0.0, # የታገደ ብር (ለደህንነት)
            "status": "offline",
            "is_active": True,
            "reg_date": str(message.date) # ምዝገባ ቀን
        }
        save_data(db)
        
        # የመመለሻ በተን ማዘጋጀት
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ ተመለስ", callback_data="admin_main_menu"))
        
        bot.send_message(
            message.chat.id, 
            f"✅ ራይደር **'{name}'** በትክክል ተመዝግቧል!\nID: `{r_id}`", 
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error in save_new_rider: {e}")
        bot.send_message(message.chat.id, "❌ ዳታውን ሴቭ ማድረግ አልተቻለም።")

# ረዳት ፋንክሽን (ለካንስል ጊዜ)
def send_admin_dashboard(message):
    markup = get_admin_dashboard(message.from_user.id)
    bot.send_message(message.chat.id, "👋 ወደ አድሚን ዳሽቦርድ ተመልሰዋል፡", reply_markup=markup)









# ለገንዘብ ዝውውር ጊዜያዊ መረጃ መያዣ
temp_topup_data = {}

# 1. ባላንስ መሙያ በተን ሲነካ
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_funds")
def start_topup(call):
    try:
        # የአድሚን ጥበቃ
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!")

        msg = bot.send_message(
            call.message.chat.id, 
            "🆔 ባላንስ ሊሞላለት የሚገባውን ሰው (Rider/Vendor) **ID** ያስገቡ፦\n\n(ለመሰረዝ 'cancel' ይበሉ)",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, find_user_for_topup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Topup Error: {e}")

# 2. ተጠቃሚውን መፈለግ
def find_user_for_topup(message):
    try:
        uid = message.text.strip()
        
        # ወደ ኋላ መመለሻ
        if uid.lower() == 'cancel':
            return send_admin_dashboard(message)

        db = load_data()
        user_data = None
        role = ""
        
        if uid in db.get('vendors_list', {}):
            user_data = db['vendors_list'][uid]
            role = "vendor"
        elif uid in db.get('riders_list', {}):
            user_data = db['riders_list'][uid]
            role = "rider"
            
        if not user_data:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_main_menu"))
            return bot.send_message(message.chat.id, "❌ በዚህ ID የተመዘገበ አካውንት የለም።", reply_markup=markup)

        temp_topup_data[message.chat.id] = {'target_id': uid, 'role': role}
        
        text = f"👤 **ተጠቃሚ፦** {user_data['name']}\n"
        text += f"🎭 **ሚና፦** {role.capitalize()}\n"
        
        if role == "vendor":
            curr = user_data.get('deposit_balance', 0)
            text += f"💰 **የአሁኑ ዲፖዚት፦** `{curr}` ብር\n\n"
            text += "እባክዎ የሚጨምሩትን የብር መጠን ያስገቡ፦"
        else:
            curr = user_data.get('wallet', 0)
            text += f"💳 **የአሁኑ ዋሌት፦** `{curr}` ብር\n\n"
            text += "ለመሙላት (ምሳሌ: `500`)\nለመቀነስ (ምሳሌ: `-200`) ያስገቡ፦"

        msg = bot.send_message(message.chat.id, text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_balance_update)
    except Exception as e:
        print(f"Find User Error: {e}")

# 3. የሂሳብ ማስተካከያውን መተግበር
def process_balance_update(message):
    try:
        if message.text.lower() == 'cancel':
            return send_admin_dashboard(message)

        amount = float(message.text.strip())
        admin_id = message.chat.id
        t_data = temp_topup_data.get(admin_id)
        
        if not t_data:
            return send_admin_dashboard(message)

        db = load_data()
        target_id = t_data['target_id']
        role = t_data['role']
        
        new_bal = 0
        if role == "vendor":
            db['vendors_list'][target_id]['deposit_balance'] += amount
            new_bal = db['vendors_list'][target_id]['deposit_balance']
            msg_text = f"✅ ለድርጅቱ `{amount}` ብር ተጨምሯል። \n💰 አዲስ ዲፖዚት፦ `{new_bal}` ብር"
        else:
            db['riders_list'][target_id]['wallet'] += amount
            new_bal = db['riders_list'][target_id]['wallet']
            action = "ተሞልቷል" if amount > 0 else "ተቀንሷል"
            msg_text = f"✅ ለራይደሩ `{abs(amount)}` ብር {action}። \n💳 አዲስ ዋሌት፦ `{new_bal}` ብር"

        save_data(db)
        
        # ዳሽቦርድ መመለሻ በተን
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ ተመለስ", callback_data="admin_main_menu"))
        
        bot.send_message(admin_id, msg_text, reply_markup=markup, parse_mode="Markdown")
        
        # ለተጠቃሚው ማሳወቂያ
        try:
            bot.send_message(target_id, f"🔔 **የሂሳብ ማስተካከያ ተደርጓል!**\nየአሁኑ ባላንስዎ፦ `{new_bal}` ብር", parse_mode="Markdown")
        except: pass
            
        if admin_id in temp_topup_data:
            del temp_topup_data[admin_id]
        
    except ValueError:
        msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ እባክዎ በትክክል ቁጥር ያስገቡ (ምሳሌ፦ 500)፦")
        bot.register_next_step_handler(msg, process_balance_update)
    except Exception as e:
        print(f"Final Update Error: {e}")
        bot.send_message(message.chat.id, "❌ ስህተት ተከስቷል።")









# 1. የምድብ ምርጫ መጀመሪያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_vendor")
def start_add_vendor(call):
    try:
        # የአድሚን ጥበቃ
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!")

        db = load_data()
        categories = db.get('categories', [])
        
        if not categories:
            # ወደ ዳሽቦርድ መመለሻ በተን
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main_menu"))
            return bot.edit_message_text(
                "⚠️ ድርጅት ከመመዝገብዎ በፊት መጀመሪያ 'አዲስ ምድብ' (Category) ይፍጠሩ!", 
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=markup
            )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for cat in categories:
            markup.add(types.InlineKeyboardButton(f"📁 {cat}", callback_data=f"sel_cat_v:{cat}"))
        
        # የመመለሻ በተን
        markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_main_menu"))
        
        bot.edit_message_text("📂 ለድርጅቱ ምድብ ይምረጡ፦", call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Start Vendor Error: {e}")

# 2. ID መጠየቂያ
@bot.callback_query_handler(func=lambda call: call.data.startswith("sel_cat_v:"))
def get_id_after_cat(call):
    try:
        cat_name = call.data.split(":") # የምድቡን ስም መለየት
        msg = bot.send_message(
            call.message.chat.id, 
            f"🆔 የምድብ **[{cat_name}]** ባለቤት Telegram ID ያስገቡ፦\n\n(ለመሰረዝ 'cancel' ይበሉ)",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, lambda m: process_vendor_id(m, cat_name))
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Vendor Cat Selection Error: {e}")

# 3. ID ማረጋገጫ
def process_vendor_id(message, cat_name):
    try:
        v_id = message.text.strip()
        if v_id.lower() == 'cancel': return send_admin_dashboard(message)

        if not v_id.isdigit():
            msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ ID ቁጥር መሆን አለበት። ድጋሚ ያስገቡ፦")
            return bot.register_next_step_handler(msg, lambda m: process_vendor_id(m, cat_name))
        
        # ቀድሞ መኖሩን መፈተሽ
        db = load_data()
        if v_id in db.get('vendors_list', {}):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main_menu"))
            return bot.send_message(message.chat.id, "❌ ይህ ድርጅት ቀድሞ ተመዝግቧል!", reply_markup=markup)

        msg = bot.send_message(message.chat.id, "🏢 የድርጅቱን ስም ያስገቡ፦")
        bot.register_next_step_handler(msg, lambda m: save_new_vendor(m, v_id, cat_name))
    except Exception as e:
        print(f"Process Vendor ID Error: {e}")

# 4. ዳታውን ሴቭ ማድረጊያ
def save_new_vendor(message, v_id, cat_name):
    try:
        v_name = message.text.strip()
        if v_name.lower() == 'cancel': return send_admin_dashboard(message)

        db = load_data()
        if 'vendors_list' not in db: db['vendors_list'] = {}
        
        db['vendors_list'][v_id] = {
            "name": v_name,
            "category": cat_name,
            "deposit_balance": 0.0,
            "items": {},
            "is_active": True,
            "reg_date": str(message.date)
        }
        save_data(db)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ ተመለስ", callback_data="admin_main_menu"))
        
        bot.send_message(
            message.chat.id, 
            f"✅ ድርጅት **'{v_name}'** በትክክል ተመዝግቧል!\n📂 ምድብ፦ `{cat_name}`\n🆔 ID፦ `{v_id}`", 
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Save Vendor Error: {e}")
        bot.send_message(message.chat.id, "❌ መረጃውን ማስቀመጥ አልተቻለም።")




# 1. ምድቦችን ማሳያ ገጽ
@bot.callback_query_handler(func=lambda call: call.data == "admin_view_categories")
def admin_categories_menu(call):
    try:
        # የአድሚን ጥበቃ
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!")

        db = load_data()
        cats = db.get('categories', [])
        
        text = "📂 **እስካሁን ያሉ የምድብ አይነቶች**\n"
        text += "━━━━━━━━━━━━━━\n"
        
        if not cats:
            text += "⚠️ ገና ምንም ምድብ አልተመዘገበም።"
        else:
            for i, c in enumerate(cats, 1):
                text += f"**{i}.** {c}\n"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ አዲስ ምድብ ጨምር", callback_data="admin_add_cat"),
            types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ ተመለስ", callback_data="admin_main_menu")
        )
        
        bot.edit_message_text(
            text, 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup, 
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"View Categories Error: {e}")
        bot.answer_callback_query(call.id, "❌ መረጃውን መጫን አልተቻለም")

# 2. አዲስ ምድብ ስም መጠየቂያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_cat")
def ask_new_cat_name(call):
    try:
        msg = bot.send_message(
            call.message.chat.id, 
            "🖊 **የአዲሱን ምድብ ስም ያስገቡ፦**\n(ለምሳሌ፦ 🍔 ምግብ፣ 💊 መድሃኒት)\n\nለመሰረዝ 'cancel' ይበሉ"
        )
        bot.register_next_step_handler(msg, save_category_logic)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Ask Cat Error: {e}")

# 3. ስሙን መቀበል እና ሴቭ ማድረግ
def save_category_logic(message):
    try:
        cat_name = message.text.strip()
        
        if cat_name.lower() == 'cancel':
            return send_admin_dashboard(message)

        db = load_data()
        if 'categories' not in db:
            db['categories'] = []
        
        # ምድቡ ቀድሞ ካለ መፈተሽ
        if cat_name in db['categories']:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 ድጋሚ ሞክር", callback_data="admin_add_cat"))
            markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_view_categories"))
            return bot.send_message(message.chat.id, f"❌ '{cat_name}' የሚል ምድብ ቀድሞ አለ!", reply_markup=markup)

        # አዲስ ምድብ መመዝገብ
        db['categories'].append(cat_name)
        save_data(db)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ ሌላ ጨምር", callback_data="admin_add_cat"))
        markup.add(types.InlineKeyboardButton("🔙 ወደ ምድቦች ተመለስ", callback_data="admin_view_categories"))
        
        bot.send_message(
            message.chat.id, 
            f"✅ ምድብ **'{cat_name}'** በትክክል ተመዝግቧል!", 
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Save Category Error: {e}")
        bot.send_message(message.chat.id, "❌ ምድቡን ማስቀመጥ አልተቻለም።")





# 1. የምድብ ስም መጠየቂያ (ከ Callback የመጣ)
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_cat")
def ask_category_name(call):
    try:
        # የአድሚን ጥበቃ
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!")

        msg = bot.send_message(
            call.message.chat.id, 
            "✏️ **የምድቡን ስም ይጻፉ፦**\n(ለምሳሌ፦ ሱፐርማርኬት)\n\nለመሰረዝ 'cancel' ይበሉ"
        )
        bot.register_next_step_handler(msg, save_category)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Ask Category Error: {e}")

# 2. ስሙን ተቀብሎ ሴቭ ማድረጊያ
def save_category(message):
    try:
        cat_name = message.text.strip()
        
        # ካንሰል ካለ ወደ ዳሽቦርድ መመለስ
        if cat_name.lower() == 'cancel':
            return send_admin_dashboard(message)

        db = load_data()
        
        # የ 'categories' ሊስት መኖሩን ማረጋገጥ
        if 'categories' not in db:
            db['categories'] = []
        
        # የመመለሻ ማርካፕ (ለመልዕክቶቹ ሁሉ የሚያገለግል)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ምድቦች ተመለስ", callback_data="admin_view_categories"))
        markup.add(types.InlineKeyboardButton("🏠 ወደ ዳሽቦርድ", callback_data="admin_main_menu"))

        if cat_name not in db['categories']:
            db['categories'].append(cat_name)
            save_data(db)
            bot.send_message(
                message.chat.id, 
                f"✅ ምድብ **'{cat_name}'** በተሳካ ሁኔታ ተፈጥሯል።", 
                reply_markup=markup,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                message.chat.id, 
                f"⚠️ ምድብ **'{cat_name}'** ቀድሞውኑ አለ።", 
                reply_markup=markup,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        print(f"Save Category Error: {e}")
        bot.send_message(message.chat.id, "❌ ምድቡን መመዝገብ አልተቻለም። እባክዎ ደግመው ይሞክሩ።")






# 1. ያሉትን ምድቦች ዝርዝር ማሳያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_view_categories")
def view_all_categories(call):
    try:
        # የአድሚን ጥበቃ
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!")

        db = load_data()
        cats = db.get('categories', [])
        
        text = "📁 **የተመዘገቡ የምድብ አይነቶች**\n"
        text += "━━━━━━━━━━━━━━\n"
        
        if not cats:
            text += "⚠️ እስካሁን ምንም ምድብ አልተመዘገበም።"
        else:
            for i, cat in enumerate(cats, 1):
                text += f"**{i}.** {cat}\n"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        # ማስታወሻ፡ እዚህ ጋር callback_data ወደ 'admin_add_cat' ተቀይሯል ቀጥታ ምዝገባ እንዲጀምር
        markup.add(
            types.InlineKeyboardButton("➕ አዲስ ምድብ ጨምር", callback_data="admin_add_cat"),
            types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ ተመለስ", callback_data="admin_main_menu")
        )
        
        bot.edit_message_text(
            text, 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup, 
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"View Categories Error: {e}")
        bot.answer_callback_query(call.id, "❌ መረጃውን ማሳየት አልተቻለም")










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
        # 1. የአድሚን ጥበቃ (Security Check)
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!", show_alert=True)

        db = load_data()
        riders = db.get('riders_list', {})
        
        # የመመለሻ ማርካፕ
        markup = types.InlineKeyboardMarkup(row_width=2)
        back_btn = types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu")
        refresh_btn = types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_rider_status")

        if not riders:
            markup.add(back_btn)
            return bot.edit_message_text(
                "⚠️ እስካሁን ምንም ራይደር (Driver) አልተመዘገበም።", 
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=markup
            )

        report = "🛵 **የራይደሮች ሁኔታ ዝርዝር**\n"
        report += "━━━━━━━━━━━━━━\n\n"
        
        online_count = 0
        for r_id, info in riders.items():
            status = info.get('status', 'offline')
            is_active = info.get('is_active', True)
            
            # የሁኔታ ምልክቶች
            status_icon = "🟢" if status == "online" else "🔴"
            if status == "online": online_count += 1
            
            active_text = "✅ ንቁ" if is_active else "🚫 የታገደ"
            
            report += f"{status_icon} **{info['name']}**\n"
            report += f"   🆔 ID: `{r_id}`\n"
            report += f"   💳 ዋሌት: `{info.get('wallet', 0):,.2f}` ETB\n"
            report += f"   🔒 ሁኔታ: {active_text}\n"
            report += "------------------------\n"
        
        report += f"\n📊 **ጥቅል መረጃ፦**\n"
        report += f"🔹 ጠቅላላ ራይደሮች፦ `{len(riders)}` \n"
        report += f"🔹 አሁን በስራ ላይ፦ `{online_count}`"

        markup.add(refresh_btn, back_btn)

        bot.edit_message_text(
            report, 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup, 
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id) # የሊዲንግ ምልክቱን ለማጥፋት
                             
    except Exception as e:
        print(f"❌ Rider Status Error: {e}")
        bot.answer_callback_query(call.id, "❌ መረጃውን መጫን አልተቻለም።", show_alert=True)






@bot.callback_query_handler(func=lambda call: call.data == "admin_list_vendors")
def list_all_entities(call):
    try:
        # 1. የአድሚን ጥበቃ (Security Check)
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!", show_alert=True)

        db = load_data()
        vendors = db.get('vendors_list', {})
        riders = db.get('riders_list', {})
        
        # ርዕስ
        report = "📋 **BDF የተመዘገቡ አካላት ዝርዝር**\n"
        report += "━━━━━━━━━━━━━━\n\n"
        
        # 🏢 የድርጅቶች (Vendors) ዝርዝር
        report += "🏢 **የድርጅቶች ዝርዝር (Vendors)**\n"
        if not vendors:
            report += "_👉 እስካሁን ምንም ድርጅት አልተመዘገበም_\n"
        else:
            for v_id, info in vendors.items():
                # ምድቡን ማጽዳት
                cat = info.get('category', 'ምድብ የሌለው')
                if isinstance(cat, (list, tuple)):
                    cat = cat[-1] if cat else 'ምድብ የሌለው'
                
                report += f"🔹 **{info.get('name', 'N/A')}**\n"
                report += f"   📁 ምድብ፦ `{cat}`\n"
                report += f"   🆔 ID፦ `{v_id}`\n"
                report += f"   💰 ባላንስ፦ `{info.get('deposit_balance', 0):,.2f}` ETB\n"
                report += "------------------------\n"

        report += "\n" # ክፍተት
        
        # 🛵 የራይደሮች (Drivers) ዝርዝር
        report += "🛵 **የራይደሮች ዝርዝር (Drivers)**\n"
        if not riders:
            report += "_👉 እስካሁን ምንም ራይደር አልተመዘገበም_\n"
        else:
            for r_id, info in riders.items():
                status_icon = "🟢" if info.get('status') == "online" else "🔴"
                
                report += f"{status_icon} **{info.get('name', 'N/A')}**\n"
                report += f"   🆔 ID፦ `{r_id}`\n"
                report += f"   💳 ዋሌት፦ `{info.get('wallet', 0):,.2f}` ETB\n"
                report += "------------------------\n"

        # የመመለሻ በተን
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ ተመለስ", callback_data="admin_main_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=report,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"❌ List Display Error: {e}")
        bot.answer_callback_query(call.id, "❌ ዝርዝሩን ማሳየት አልተቻለም።", show_alert=True)





# 1. የኮሚሽን ማስተካከያ መጀመሪያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_set_commission")
def start_commission_settings(call):
    try:
        # የአድሚን ጥበቃ
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!")

        db = load_data()
        s = db.get('settings', {})
        
        # የአሁኑን ሁኔታ ማሳየት ለአድሚኑ ይረዳዋል
        text = "⚙️ **የኮሚሽን ማስተካከያ**\n"
        text += "━━━━━━━━━━━━━━\n"
        text += f"🏢 የአሁኑ የድርጅት፦ `{s.get('vendor_commission_p', 0)}%` \n"
        text += f"🛵 የአሁኑ የራይደር፦ `{s.get('rider_commission_p', 0)}%` \n"
        text += f"👤 የአሁኑ ሰርቪስ ፊ፦ `{s.get('customer_service_fee', 0)}` ETB\n\n"
        text += "አዲስ ለመቀየር ሦስቱን ቁጥሮች በኮማ በመለየት ያስገቡ፦\n"
        text += "💡 ቅርጸት፦ `ድርጅት, ራይደር, ሰርቪስ` (ለምሳሌ: `5, 10, 20`)\n\n"
        text += "ለመሰረዝ 'cancel' ይበሉ"
        
        msg = bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, save_commissions)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Start Commission Error: {e}")

# 2. የተቀበሉትን ቁጥሮች ዳታቤዝ ላይ ማስቀመጥ
def save_commissions(message):
    try:
        if message.text.lower() == 'cancel':
            return send_admin_dashboard(message)

        # 1. ጽሁፉን በኮማ መከፋፈል እና ባዶ ቦታዎችን ማጽዳት (strip)
        parts = [p.strip() for p in message.text.split(",")]
        
        if len(parts) != 3:
            raise ValueError("ሶስት ቁጥሮች ያስፈልጋሉ")
            
        v_comm = float(parts) 
        r_comm = float(parts) 
        c_comm = float(parts) 
        
        db = load_data()
        if 'settings' not in db: db['settings'] = {}
        
        db['settings']['vendor_commission_p'] = v_comm
        db['settings']['rider_commission_p'] = r_comm
        db['settings']['customer_service_fee'] = c_comm
        
        save_data(db)
        
        # የመመለሻ በተን
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ ተመለስ", callback_data="admin_main_menu"))
        
        response = (
            f"✅ **ኮሚሽን በተሳካ ሁኔታ ተቀይሯል!**\n"
            f"━━━━━━━━━━━━━━\n"
            f"🏢 ድርጅት (Vendor)፦ `{v_comm}%` \n"
            f"🛵 ራይደር (Rider)፦ `{r_comm}%` \n"
            f"👤 ደንበኛ (Service Fee)፦ `{c_comm}` ETB"
        )
        bot.send_message(message.chat.id, response, reply_markup=markup, parse_mode="Markdown")
        
    except (ValueError, IndexError):
        msg = bot.send_message(
            message.chat.id, 
            "⚠️ **ስህተት፦** እባክዎ በትክክል ያስገቡ።\n"
            "ለምሳሌ፦ `5, 10, 20` (በኮማ መለየትዎን ያረጋግጡ)"
        )
        bot.register_next_step_handler(msg, save_commissions)
    except Exception as e:
        print(f"Save Commission Error: {e}")
        bot.send_message(message.chat.id, "❌ ስህተት ተፈጥሯል።")







@bot.callback_query_handler(func=lambda call: call.data == "admin_profit_track")
def view_profit_stats(call):
    try:
        # 1. የአድሚን ጥበቃ (Security Check)
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!", show_alert=True)

        db = load_data()
        
        # የ 'stats' ዳታ መኖሩን እና ትክክለኛነቱን ማረጋገጥ
        stats = db.get('stats', {
            'total_vendor_comm': 0.0,
            'total_rider_comm': 0.0,
            'total_customer_comm': 0.0,
            'total_orders': 0
        })
        
        # አጠቃላይ ትርፍ ስሌት
        v_comm = float(stats.get('total_vendor_comm', 0))
        r_comm = float(stats.get('total_rider_comm', 0))
        c_comm = float(stats.get('total_customer_comm', 0))
        total_net_profit = v_comm + r_comm + c_comm
        
        # ሪፖርት ዝግጅት
        report = "💰 **የትርፍ እና የሽያጭ ሪፖርት**\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"
        report += f"📊 **አጠቃላይ የተጣራ ትርፍ፦**\n"
        report += f"💵 `{total_net_profit:,.2f}` **ETB**\n\n"
        
        report += "⚖️ **የገቢ ምንጮች ዝርዝር፦**\n"
        report += f"🏢 ከድርጅቶች (Com): `{v_comm:,.2f}` ብር\n"
        report += f"🛵 ከራይደሮች (Com): `{r_comm:,.2f}` ብር\n"
        report += f"👤 ከደንበኞች (Fee): `{c_comm:,.2f}` ብር\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n"
        report += f"📦 ጠቅላላ የተጠናቀቁ ትዕዛዞች፦ `{stats.get('total_orders', 0)}`"
        
        # የመመለሻ በተን
        markup = types.InlineKeyboardMarkup(row_width=2)
        refresh_btn = types.InlineKeyboardButton("🔄 ሪፖርት አድስ", callback_data="admin_profit_track")
        back_btn = types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu")
        markup.add(refresh_btn, back_btn)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=report,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id) # 'Loading' ምልክቱን ለማጥፋት

    except Exception as e:
        print(f"❌ Profit Stats Error: {e}")
        bot.answer_callback_query(call.id, "❌ ሪፖርቱን ማሳየት አልተቻለም።", show_alert=True)





@bot.callback_query_handler(func=lambda call: call.data == "admin_monitor_balance")
def monitor_all_balances(call):
    try:
        # 1. የአድሚን ጥበቃ (Security Check)
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!", show_alert=True)

        db = load_data()
        vendors = db.get('vendors_list', {})
        riders = db.get('riders_list', {})
        
        report = "📉 **የፋይናንስ ክትትል መቆጣጠሪያ**\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # 🏢 የድርጅቶች የዲፖዚት ሁኔታ
        report += "🏢 **የድርጅቶች ባላንስ (Vendors)**\n"
        total_v_bal = 0
        if not vendors:
            report += "_👉 እስካሁን ምንም ድርጅት አልተመዘገበም_\n"
        else:
            for v_id, info in vendors.items():
                cat = info.get('category', 'ያልተገለጸ')
                # በምድብ ምርጫ ጊዜ ሊስት ሆኖ ከመጣ የመጨረሻውን ስም ይወስዳል
                if isinstance(cat, list): cat = cat[-1] if cat else 'ያልተገለጸ'
                
                bal = float(info.get('deposit_balance', 0))
                total_v_bal += bal
                
                # ባላንሱ 0 ከሆነ ቀይ ምልክት፣ ካለው አረንጓዴ
                status_dot = "🔴" if bal <= 0 else "🟢"
                report += f"{status_dot} **{info.get('name', 'N/A')}** (`{cat}`)\n"
                report += f"    └─ 💰 ባላንስ፦ `{bal:,.2f}` ETB\n"
        
        report += "\n" + "─" * 20 + "\n\n"
        
        # 🛵 የራይደሮች ዋሌት ሁኔታ
        report += "🛵 **የራይደሮች ባላንስ (Drivers)**\n"
        total_r_bal = 0
        if not riders:
            report += "_👉 እስካሁን ምንም ራይደር አልተመዘገበም_\n"
        else:
            for r_id, info in riders.items():
                w_bal = float(info.get('wallet', 0))
                total_r_bal += w_bal
                
                r_status = "🟢" if w_bal > 0 else "⚪"
                report += f"{r_status} **{info.get('name', 'N/A')}**\n"
                report += f"    └─ 💳 ዋሌት፦ `{w_bal:,.2f}` ETB\n"

        report += "\n━━━━━━━━━━━━━━━━━━━━\n"
        grand_total = total_v_bal + total_r_bal
        report += f"📊 **አጠቃላይ በሲስተሙ ያለው ገንዘብ፦**\n"
        report += f"💵 `{grand_total:,.2f}` **ETB**"

        # የመመለሻ እና ማደሻ በተኖች
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_monitor_balance"),
            types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=report,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"❌ Balance Monitor Error: {e}")
        bot.answer_callback_query(call.id, "❌ መረጃውን ማምጣት አልተቻለም።", show_alert=True)






@bot.callback_query_handler(func=lambda call: call.data == "admin_live_orders")
def view_live_orders(call):
    try:
        # 1. የአድሚን ጥበቃ (Security Check)
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!", show_alert=True)

        db = load_data()
        # 'active_orders' እንደ ዲክሽነሪ ({}) መያዙ የተሻለ ነው
        orders = db.get('active_orders', {})
        
        # የመመለሻ ማርካፕ
        markup = types.InlineKeyboardMarkup(row_width=2)
        refresh_btn = types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_live_orders")
        back_btn = types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu")
        markup.add(refresh_btn, back_btn)

        if not orders:
            return bot.edit_message_text(
                "📭 **አሁን ላይ ምንም የሚታይ ቀጥታ ትዕዛዝ የለም።**", 
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=markup,
                parse_mode="Markdown"
            )

        report = "📋 **የቀጥታ ትዕዛዞች ክትትል**\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for order_id, info in orders.items():
            status = info.get('status', 'Pending')
            
            # የሁኔታ ምልክቶች (Icons)
            if status == "Pending":
                status_icon = "⏳"
            elif status == "Accepted":
                status_icon = "🤝"
            elif status == "On Way":
                status_icon = "🛵"
            elif status == "Arrived":
                status_icon = "📍"
            else:
                status_icon = "📦"
            
            report += f"{status_icon} **ትዕዛዝ ID፦** `{order_id}`\n"
            report += f"🏢 **ድርጅት፦** {info.get('vendor_name', 'N/A')}\n"
            report += f"🛵 **ራይደር፦** {info.get('rider_name', '🕒 ገና አልተያዘም')}\n"
            report += f"📍 **ሁኔታ፦** `{status}`\n"
            report += f"💰 **ዋጋ፦** `{info.get('total_price', 0):,.2f}` ETB\n"
            report += "------------------------\n"
        
        report += f"\n📊 **በሂደት ላይ ያሉ፦** `{len(orders)}`"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=report,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"❌ Live Orders Error: {e}")
        bot.answer_callback_query(call.id, "❌ መረጃውን መጫን አልተቻለም።", show_alert=True)






@bot.callback_query_handler(func=lambda call: call.data == "admin_full_stats")
def show_enhanced_analytics(call):
    try:
        # 1. የአድሚን ጥበቃ (Security Check)
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!", show_alert=True)

        db = load_data()
        vendors = db.get('vendors_list', {})
        riders = db.get('riders_list', {})
        orders = db.get('orders', {}) # የታሪክ መዝገብ ከሆነ
        
        # የሂሳብ ስሌቶች (Float ጥበቃ ተጨምሮበት)
        total_vendor_deposit = sum(float(v.get('deposit_balance', 0)) for v in vendors.values())
        total_rider_wallet = sum(float(r.get('wallet', 0)) for r in riders.values())
        
        # ትርፍን ከ stats ክፍል ወይም ከ total_profit መውሰድ
        stats = db.get('stats', {})
        system_profit = stats.get('total_vendor_comm', 0) + stats.get('total_rider_comm', 0) + stats.get('total_customer_comm', 0)

        report = "📊 **ጥልቅ የቢዝነስ ትንታኔ (Full Analytics)**\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"

        # 🏢 የድርጅቶች ሁኔታ (Vendors)
        report += "🏢 **የድርጅቶች ሁኔታ (Vendors)**\n"
        report += f"• ጠቅላላ ድርጅቶች፦ `{len(vendors)}` \n"
        report += f"• አጠቃላይ ዲፖዚት፦ `{total_vendor_deposit:,.2f}` ETB\n"
        report += "------------------------\n\n"

        # 🛵 የራይደሮች ሁኔታ (Drivers)
        report += "🛵 **የራይደሮች ሁኔታ (Drivers)**\n"
        report += f"• ጠቅላላ ራይደሮች፦ `{len(riders)}` \n"
        report += f"• አጠቃላይ ዋሌት፦ `{total_rider_wallet:,.2f}` ETB\n"
        online_riders = sum(1 for r in riders.values() if r.get('status') == 'online')
        report += f"• አሁን በስራ ላይ (Online)፦ `{online_riders}`\n"
        report += "------------------------\n\n"

        # 💰 የገንዘብ እና የትዕዛዝ ሁኔታ
        report += "💰 **ፋይናንስ እና ትዕዛዞች**\n"
        report += f"• የተሳኩ ትዕዛዞች፦ `{len(orders)}` \n"
        report += f"• አጠቃላይ የሲስተም ትርፍ፦ `{system_profit:,.2f}` ETB 💵\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"

        # 🏆 ምርጥ አፈጻጸም (Top Performers)
        # ማሳሰቢያ፦ እዚህ ጋር በሉፕ ትልቅ 'completed_orders' ያለውን መፈለግ ይቻላል
        report += "🏆 **ምርጥ አፈጻጸም**\n"
        report += "• ምርጥ ድርጅት፦ _በሂደት ላይ..._\n"
        report += "• ንቁ ራይደር፦ _በሂደት ላይ..._\n"

        # የመመለሻ እና ማደሻ በተኖች
        markup = types.InlineKeyboardMarkup(row_width=2)
        refresh_btn = types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_full_stats")
        back_btn = types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu")
        markup.add(refresh_btn, back_btn)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=report,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

    except Exception as e:
        print(f"❌ Full Stats Error: {e}")
        bot.answer_callback_query(call.id, "❌ መረጃውን ማመንጨት አልተቻለም።", show_alert=True)






# 1. ዳግም ማስጀመሪያ መጀመሪያ - ማስጠንቀቂያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_system_reset")
def confirm_reset_request(call):
    try:
        # የአድሚን ጥበቃ
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!", show_alert=True)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⚠️ አዎ! ሙሉ በሙሉ አጽዳ", callback_data="admin_final_reset_confirm"))
        markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_main_menu"))
        
        text = "❗ **ጥንቃቄ፦ ሲስተም ዳግም ማስጀመር**\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "ይህንን ካደረጉ የሚከተሉት መረጃዎች በሙሉ ይጠፋሉ፦\n"
        text += "• ሁሉም ድርጅቶች እና ራይደሮች\n"
        text += "• የሂሳብ እና የትርፍ መዝገቦች\n"
        text += "• የተመዘገቡ እቃዎች እና ምድቦች\n\n"
        text += "⚠️ **ይህ ተግባር ሊመለስ አይችልም!** እርግጠኛ ነዎት?"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Reset Request Error: {e}")

# 2. ሚስጥራዊ ኮድ መጠየቅ
@bot.callback_query_handler(func=lambda call: call.data == "admin_final_reset_confirm")
def ask_secret_code(call):
    try:
        msg = bot.send_message(
            call.message.chat.id, 
            "🔐 **ለማጽዳት ሚስጥራዊ ቁልፉን ያስገቡ፦**\n\n(ለመሰረዝ 'cancel' ይበሉ)",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, perform_database_reset)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Ask Secret Error: {e}")

# 3. ዳታቤዙን ማጽዳት
def perform_database_reset(message):
    try:
        # ሚስጥራዊ ኮዱን እዚህ ጋር መቀየር ትችላለህ
        SECRET_KEY = "RESET123" 
        
        if message.text.lower() == 'cancel':
            return send_admin_dashboard(message)

        if message.text.strip() == SECRET_KEY:
            # ዳታቤዙን ወደ መጀመሪያው (Default) ሁኔታ መመለስ
            new_db = {
                "riders_list": {},
                "vendors_list": {},
                "orders": {},
                "active_orders": {}, # አክቲቭ ትዕዛዞችንም መጨመር አለብን
                "carts": {},
                "categories": [],
                "stats": { # ለትርፍ ሪፖርት የምንጠቀመው
                    "total_vendor_comm": 0.0,
                    "total_rider_comm": 0.0,
                    "total_customer_comm": 0.0,
                    "total_orders": 0
                },
                "user_list": [message.chat.id],
                "settings": {
                    "vendor_commission_p": 5,
                    "rider_commission_p": 10,
                    "customer_service_fee": 20,
                    "system_locked": False 
                }
            }
            save_data(new_db)
            
            # የመመለሻ በተን
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 ወደ ዳሽቦርድ", callback_data="admin_main_menu"))
            
            bot.send_message(
                message.chat.id, 
                "✅ **ሲስተሙ በትክክል ዳግም ተጀምሯል!**\nሁሉም መረጃዎች ተሰርዘዋል።", 
                reply_markup=markup,
                parse_mode="Markdown"
            )
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 ድጋሚ ሞክር", callback_data="admin_final_reset_confirm"))
            markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="admin_main_menu"))
            
            bot.send_message(
                message.chat.id, 
                "❌ **የተሳሳተ ሚስጥራዊ ቁልፍ!**\nየማጽዳት ሂደቱ ተሰርዟል።", 
                reply_markup=markup,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        print(f"Perform Reset Error: {e}")
        bot.send_message(message.chat.id, "❌ የቴክኒክ ስህተት አጋጥሟል።")







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
