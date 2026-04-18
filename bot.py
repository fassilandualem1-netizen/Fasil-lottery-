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

    markup.add(btn_live_orders)
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




@bot.message_handler(commands=['start', 'admin']) # 'admin'ንም እዚህ ይያዘው
def start_command(message):
    user_id = message.from_user.id
    
    # 🔄 መጀመሪያ ተቀርቅሮ የነበረውን Step Handler ያጠፋል
    bot.clear_step_handler_by_chat_id(chat_id=user_id)
    
    db = load_data()
    
    # የአድሚን ቼክ
    if user_id in ADMIN_IDS:
        markup = get_admin_dashboard(user_id)
        bot.send_message(user_id, "👋 ሰላም ጌታዬ! ወደ አድሚን ዳሽቦርድ ተመልሰዋል።", reply_markup=markup)
    else:
        # ለሌሎች ተጠቃሚዎች
        bot.send_message(user_id, "እንኳን ደህና መጡ! ምን ማዘዝ ይፈልጋሉ?")




@bot.callback_query_handler(func=lambda call: call.data == "admin_main_menu")
def back_to_admin(call):
    markup = get_admin_dashboard(call.from_user.id)
    bot.edit_message_text("👋 ወደ አድሚን ዳሽቦርድ ተመልሰዋል።", call.message.chat.id, call.message.message_id, reply_markup=markup)







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
    
    except Exception as e:
        # ማንኛውም ሌላ ስህተት ቢፈጠር ሲስተሙ እንዳይቆም ይረዳል
        print(f"Error in balance update: {e}")
        bot.send_message(message.chat.id, "❌ የቴክኒክ ስህተት አጋጥሟል። እባክዎ እንደገና ይሞክሩ።")








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
def view_all_vendors(call):
    db = load_data()
    vendors = db.get('vendors_list', {})
    
    if not vendors:
        return bot.answer_callback_query(call.id, "⚠️ እስካሁን ምንም ድርጅት አልተመዘገበም።")

    report = "🏢 **የተመዘገቡ ድርጅቶች ዝርዝር**\n\n"
    
    for v_id, info in vendors.items():
        status_icon = "✅" if info.get('is_active', True) else "🚫"
        
        report += f"{status_icon} **{info['name']}** ({info.get('category', 'ያልተገለጸ')})\n"
        report += f"   🆔 ID: `{v_id}`\n"
        report += f"   💰 ዲፖዚት: {info.get('deposit_balance', 0)} ብር\n"
        report += f"   📊 የአድሚን ትርፍ: {info.get('service_fee_total', 0)} ብር\n"
        report += "------------------------\n"
    
    markup = types.InlineKeyboardMarkup()
    # ድርጅቶቹን አንድ በአንድ ለማየት ወይም ለማስተካከል 
    # ወደፊት እዚህ ጋር ተጨማሪ በተኖች መጨመር ይቻላል
    markup.add(types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_list_vendors"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu"))

    bot.edit_message_text(report, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")




# 1. የኮሚሽን ማስተካከያ መጀመሪያ
@bot.callback_query_handler(func=lambda call: call.data == "admin_set_commission")
def start_commission_settings(call):
    text = "⚙️ **የኮሚሽን ማስተካከያ**\n\n"
    text += "እባክዎ ሦስቱን የኮሚሽን መጠኖች በኮማ በመለየት ያስገቡ፦\n\n"
    text += "1. የድርጅት ፐርሰንት (ለምሳሌ: 2)\n"
    text += "2. የራይደር ኮሚሽን (ለምሳሌ: 10)\n"
    text += "3. የደንበኛ ሰርቪስ ፊ (ለምሳሌ: 5)\n\n"
    text += "ቅርጸት፦ `2, 10, 5`"
    
    msg = bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, save_commissions)

# 2. የተቀበሉትን ቁጥሮች ዳታቤዝ ላይ ማስቀመጥ
def save_commissions(message):
    try:
        parts = message.text.split(",")
        if len(parts) != 3:
            raise ValueError
            
        v_comm = float(parts.strip()) # ፐርሰንት
        r_comm = float(parts.strip()) # ቋሚ ብር
        c_comm = float(parts.strip()) # ቋሚ ብር
        
        db = load_data()
        db['settings']['vendor_commission_percent'] = v_comm
        db['settings']['rider_service_fee'] = r_comm
        db['settings']['customer_service_fee'] = c_comm
        save_data(db)
        
        bot.send_message(message.chat.id, f"✅ ኮሚሽን በተሳካ ሁኔታ ተቀይሯል!\n\n🏢 ድርጅት፦ {v_comm}%\n🛵 ራይደር፦ {r_comm} ብር\n👤 ደንበኛ፦ {c_comm} ብር")
        
    except:
        msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ እባክዎ በትክክል ያስገቡ (ለምሳሌ፦ 2, 10, 5)፦")
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
        
        report = "📉 **አጠቃላይ የባላንስ ክትትል ሪፖርት**\n\n"
        
        # 🏢 የድርጅቶች ሁኔታ
        report += "🏢 **የድርጅቶች ዲፖዚት፦**\n"
        if not vendors:
            report += "_ምንም የተመዘገበ ድርጅት የለም_\n"
        for v_id, info in vendors.items():
            report += f"• {info['name']}: `{info.get('deposit_balance', 0)}` ብር\n"
        
        report += "\n"
        
        # 🛵 የራይደሮች ሁኔታ
        report += "🛵 **የራይደሮች ዋሌት፦**\n"
        if not riders:
            report += "_ምንም የተመዘገበ ራይደር የለም_\n"
        for r_id, info in riders.items():
            report += f"• {info['name']}: `{info.get('wallet', 0)}` ብር\n"

        # ወደ ኋላ መመለሻ በተን
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu"))
        
        # መልዕክቱን ማደስ (Edit)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=report,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        print(f"Monitor Balance Error: {e}")
        bot.answer_callback_query(call.id, "❌ መረጃውን ለማምጣት ስህተት አጋጥሟል።")






@bot.callback_query_handler(func=lambda call: call.data == "admin_live_orders")
def view_live_orders(call):
    db = load_data()
    # በዳታቤዝህ ውስጥ 'active_orders' የሚል ሊስት መኖር አለበት
    orders = db.get('active_orders', {})
    
    if not orders:
        return bot.answer_callback_query(call.id, "📭 አሁን ላይ ምንም ቀጥታ ትዕዛዝ የለም።")

    report = "📋 **የቀጥታ ትዕዛዞች ክትትል**\n\n"
    
    for order_id, info in orders.items():
        status = info.get('status', 'Pending')
        status_icon = "⏳" if status == "Pending" else "🛵" if status == "On Way" else "📦"
        
        report += f"{status_icon} **ትዕዛዝ ID፦** `{order_id}`\n"
        report += f"🏢 **ድርጅት፦** {info['vendor_name']}\n"
        report += f"🛵 **ራይደር፦** {info.get('rider_name', 'ገና አልተያዘም')}\n"
        report += f"📍 **ሁኔታ፦** {status}\n"
        report += f"💰 **ጠቅላላ ዋጋ፦** {info['total_price']} ብር\n"
        report += "------------------------\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 አድስ", callback_data="admin_live_orders"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu"))
    
    bot.edit_message_text(report, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")




@bot.callback_query_handler(func=lambda call: call.data == "admin_full_stats")
def view_business_analytics(call):
    db = load_data()
    vendors = db.get('vendors_list', {})
    riders = db.get('riders_list', {})
    stats = db.get('stats', {})
    
    # ለሪፖርቱ የሚሆኑ መረጃዎችን ማሰባሰብ
    total_users = len(db.get('user_list', []))
    active_vendors = sum(1 for v in vendors.values() if v.get('is_active'))
    online_riders = sum(1 for r in riders.values() if r.get('status') == 'online')
    
    report = "📈 **ጥልቅ የቢዝነስ ሪፖርት (Full Analytics)**\n\n"
    
    report += "👥 **የተጠቃሚዎች ሁኔታ**\n"
    report += f"• ጠቅላላ የቦቱ ተጠቃሚዎች፦ {total_users}\n"
    report += f"• ንቁ ድርጅቶች፦ {active_vendors}\n"
    report += f"• አሁን ኦንላይን ያሉ ራይደሮች፦ {online_riders}\n\n"
    
    report += "📦 **የትዕዛዝ ስታቲስቲክስ**\n"
    report += f"• የተሳኩ ትዕዛዞች፦ {stats.get('total_orders', 0)}\n"
    # ወደፊት እዚህ ጋር 'የተሰረዙ' የሚል መጨመር ይቻላል
    
    report += "\n🏆 **ምርጥ አፈጻጸም**\n"
    # እዚህ ጋር ዳታቤዝህ ውስጥ ካስቀመጥከው 'Top Vendor' ማምጣት ይቻላል
    report += "• ብዙ ትዕዛዝ ያስተናገዱ ድርጅቶችና ራይደሮችን እዚህ ጋር ማየት ይቻላል።\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 ሪፖርት አድስ", callback_data="admin_full_stats"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="admin_main_menu"))
    
    bot.edit_message_text(report, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")






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

# 2. ሚስጥራዊ ኮድ መጠየቅ (ለበለጠ ጥንቃቄ)
@bot.callback_query_handler(func=lambda call: call.data == "admin_final_reset_confirm")
def ask_secret_code(call):
    msg = bot.send_message(call.message.chat.id, "🔐 ለማጽዳት ሚስጥራዊ ቁልፉን ያስገቡ (ለምሳሌ፦ `RESET123`)፦")
    bot.register_next_step_handler(msg, perform_database_reset)

# 3. ዳታቤዙን ማጽዳት
def perform_database_reset(message):
    secret_code = "RESET123" # ይህንን ኮድ መቀየር ትችላለህ
    
    if message.text.strip() == secret_code:
        # ዳታቤዙን ወደ መጀመሪያው ሁኔታ መመለስ
        new_db = {
            "vendors_list": {},
            "riders_list": {},
            "categories": [],
            "user_list": [message.chat.id], # የአድሚኑን ID ብቻ እናስቀር
            "stats": {
                "total_vendor_comm": 0.0,
                "total_rider_comm": 0.0,
                "total_customer_comm": 0.0,
                "total_orders": 0
            },
            "settings": {
                "system_locked": False,
                "vendor_commission_percent": 2.0,
                "rider_service_fee": 10.0,
                "customer_service_fee": 5.0
            }
        }
        save_data(new_db)
        bot.send_message(message.chat.id, "✅ ሲስተሙ ሙሉ በሙሉ ጸድቷል! አሁን እንደ አዲስ መጀመር ይችላሉ።")
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
