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
    """
    ትዕዛዝ ሲጠናቀቅ በሁለቱም ወገን (Vendor & Rider) ዋሌት ላይ 
    የሂሳብ ማወራረጃ የሚሰራ ዋና ፈንክሽን።
    """
    with db_lock:
        db = load_data()
        order = db['orders'].get(str(order_id))

        if not order or order.get('status') == "Completed":
            return False

        v_id = str(order['vendor_id'])
        r_id = str(order['rider_id'])
        
        # የሂሳብ ስሌት
        item_price = float(order['item_total'])   # የእቃ ዋጋ
        delivery_fee = float(order['delivery_fee']) # የማድረሻ ክፍያ
        
        # የኮሚሽን ስሌት (ከ Settings የሚወሰድ)
        v_comm = item_price * (db['settings']['vendor_commission_p'] / 100)
        r_comm = delivery_fee * (db['settings']['rider_commission_p'] / 100)

        # 1. የቬንደር ዲፖዚት ቅነሳ (አድሚኑ አስቀድሞ ስለከፈለለት)
        if v_id in db['vendors_list']:
            db['vendors_list'][v_id]['deposit_balance'] -= item_price
            db['vendors_list'][v_id]['wallet'] -= v_comm  # የቦቱ ኮሚሽን

        # 2. የራይደር ዋሌት ቅነሳ (ራይደሩ ለደንበኛው አድርሶ ካሽ ስለሚሰበስብ)
        if r_id in db['riders_list']:
            # ከራይደሩ 'የእቃው ዋጋ + የቦቱ ኮሚሽን' ይቀነሳል
            db['riders_list'][r_id]['wallet'] -= (item_price + r_comm)

        # 3. የአድሚን ትርፍ መመዝገቢያ
        db['total_profit'] += (v_comm + r_comm)
        
        # ትዕዛዙን መዝጋት
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
    order = db['orders'].get(order_id)
    item_price = order['item_total']
    bot_commission = item_price * (db['settings']['rider_commission_p'] / 100)
    
    required_balance = item_price + bot_commission
    rider_balance = db['riders_list'][str(rider_id)].get('wallet', 0)

    if rider_balance >= required_balance:
        # ትዕዛዙን እንዲቀበል ፍቀድለት
        order['rider_id'] = rider_id
        order['status'] = "Accepted"
        
        # ሂሳቡን ከራይደሩ ዋሌት ላይ 'Hold' አድርገው ወይም ቀንስ
        db['riders_list'][str(rider_id)]['wallet'] -= required_balance
        save_data(db)
        
        bot.send_message(rider_id, f"✅ ትዕዛዙን ተቀብለዋል። ከዋሌትዎ {required_balance} ETB ተቀንሷል።")
    else:
        bot.send_message(rider_id, f"❌ በቂ የዋሌት ባላንስ የለዎትም። ቢያንስ {required_balance} ETB ያስፈልጋል።")



def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True






def get_admin_dashboard(user_id):
    db = load_data()
    markup = types.InlineKeyboardMarkup(row_width=2)

    # --- በተኖቹን መፍጠር ---
    
  
    btn_broadcast = types.InlineKeyboardButton("📢 ማስታወቂያ", callback_data="admin_broadcast")

    btn_fund = types.InlineKeyboardButton("💳 ብር መሙያ", callback_data="admin_add_funds")
    btn_balance = types.InlineKeyboardButton("📉 ክትትል", callback_data="admin_monitor_balance")
    btn_profit = types.InlineKeyboardButton("💰 ትርፍ", callback_data="admin_profit_track")
    btn_low_credit = types.InlineKeyboardButton("⚠️ ዝቅተኛ ሂሳብ", callback_data="admin_low_credit")

    btn_live_orders = types.InlineKeyboardButton("📋 ቀጥታ ትዕዛዝ", callback_data="admin_live_orders")
    btn_pending = types.InlineKeyboardButton("📦 በመጠባበቅ", callback_data="admin_pending_approvals")
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

    # --- ወደ Markup መጨመር (በሁለት ረድፍ) ---
    markup.add(btn_broadcast) # ይህ ለብቻው ሰፋ ብሎ እንዲታይ (ወይም ከፈለግክ ሌላ ጨምርበት)

    markup.add(btn_fund, btn_balance)
    markup.add(btn_profit, btn_low_credit)

    markup.add(btn_live_orders, btn_pending)
    markup.add(btn_view_cats, btn_add_cats) 
    markup.add(btn_stats) 

    markup.add(btn_add_vendor, btn_add_rider)
    markup.add(btn_vendors, btn_riders)
    markup.add(btn_set_commission, btn_block)
    markup.add(btn_lock) # መዝጊያው ለብቻው ሰፋ ብሎ ለጥንቃቄ

    return markup

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add( "📊 ሪፖርት" )
    return markup


@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        uid_str = str(user_id)
        bot.clear_step_handler_by_chat_id(chat_id=user_id) 

        db = load_data()





# 1. የራይደር ምዝገባ መጀመሪያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_rider")
def start_rider_reg(call):
    msg = bot.send_message(call.message.chat.id, "🆔 የራይደሩን Telegram User ID ያስገቡ፦")
    bot.register_next_step_handler(msg, process_rider_id)

# 2. ID ተቀብሎ ስም መጠየቅ
def process_rider_id(message):
    r_id = message.text.strip()
    if not r_id.isdigit():
        msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ ID ቁጥር መሆን አለበት። እባክዎ እንደገና ያስገቡ፦")
        return bot.register_next_step_handler(msg, process_rider_id)
    
    temp_vendor_data[message.chat.id] = {'u_id': r_id} # ለጊዜው እዚህ እናስቀምጠው
    msg = bot.send_message(message.chat.id, "🛵 የራይደሩን ሙሉ ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, save_rider_final)

# 3. ስም ተቀብሎ መመዝገብ
def save_rider_final(message):
    r_name = message.text.strip()
    admin_id = message.chat.id
    r_data = temp_vendor_data.get(admin_id)
    
    db = load_data()
    db['riders_list'][r_data['u_id']] = {
        "name": r_name,
        "wallet": 0.0,      # መጀመሪያ ባዶ ነው
        "role": "rider",
        "status": "offline",
        "is_active": True
    }
    save_data(db)
    bot.send_message(admin_id, f"✅ ራይደር '{r_name}' ተመዝግቧል። አሁን በ 'ባላንስ መሙያ' በኩል ዋሌቱን መሙላት ይችላሉ።")
    if admin_id in temp_vendor_data: del temp_vendor_data[admin_id]





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







# 1. መጀመሪያ ID መጠየቅ
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_vendor")
def start_vendor_reg(call):
    msg = bot.send_message(call.message.chat.id, "🆔 የድርጅቱን ባለቤት Telegram User ID ያስገቡ፦")
    bot.register_next_step_handler(msg, process_id_step)

# 2. ስም መጠየቅ
def process_id_step(message):
    user_id = message.text.strip()
    temp_vendor_data[message.chat.id] = {'u_id': user_id}
    msg = bot.send_message(message.chat.id, "🏢 የድርጅቱን (የንግድ ቤቱን) ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, process_name_step)

# 3. ምድብ መጠየቅ እና መጨረስ
def process_name_step(message):
    temp_vendor_data[message.chat.id]['name'] = message.text.strip()
    db = load_data()
    markup = types.InlineKeyboardMarkup()
    
    for cat in db['categories']:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"sel_cat:{cat}"))
    
    bot.send_message(message.chat.id, "📁 የምድብ አይነት ይምረጡ፦", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("sel_cat:"))
def final_vendor_reg(call):
    category = call.data.split(":")
    admin_id = call.message.chat.id
    v_data = temp_vendor_data.get(admin_id)
    
    db = load_data()
    db['vendors_list'][v_data['u_id']] = {
        "name": v_data['name'],
        "category": category,
        "deposit_balance": 0.0, # መጀመሪያ ባዶ ነው
        "service_fee_total": 0.0, # ድርጅቱ ለቦቱ የከፈለው ጠቅላላ ክፍያ
        "role": "vendor",
        "is_active": True
    }
    save_data(db)
    bot.send_message(admin_id, f"✅ ድርጅት '{v_data['name']}' ተመዝግቧል። አሁን በ 'ባላንስ መሙያ' በኩል ቅድመ ክፍያ መሙላት ይችላሉ።")









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




