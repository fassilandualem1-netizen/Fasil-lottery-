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


# --- 2. ጊዜያዊ ዳታ መያዣዎች (እዚህ ጋር አስገባው) ---
item_creation_data = {} 


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




def is_user_complete(user_id):
    db = load_data()
    # 1. መጀመሪያ 'users' የሚባል ቁልፍ መኖሩን እናረጋግጣለን
    if 'users' not in db:
        return False
    
    # 2. የተጠቃሚውን ዳታ እናወጣለን
    user = db.get('users', {}).get(str(user_id), {})
    
    # 3. ስልክ፣ ላቲቲውድ እና ሎንግቲውድ መኖራቸውን ቼክ እናደርጋለን
    has_phone = user.get('phone') is not None
    has_location = user.get('lat') is not None and user.get('lon') is not None
    
    return has_phone and has_location





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





import math
from telebot import types

# 📏 1. ርቀት መለኪያ ሎጂክ (በኪሎ ሜትር)
def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        if None in [lat1, lon1, lat2, lon2]: return -1
        R = 6371 # የምድር ራዲየስ
        dlat = math.radians(float(lat2) - float(lat1))
        dlon = math.radians(float(lon2) - float(lon1))
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        # 30% ለመንገድ መጨመር (ያንተ ሎጂክ)
        return round((R * c) * 1.3, 2)
    except:
        return -1



def notify_vendor_new_order(order_id):
    db = load_data()
    order = db.get('orders', {}).get(order_id)
    v_id = order.get('vendor_id')
    
    text = (
        f"🔔 **አዲስ ትዕዛዝ ደርሶዎታል!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 **ትዕዛዝ ቁጥር፦** `{order_id}`\n"
        f"💰 **ጠቅላላ ዋጋ፦** `{order.get('total_price')} ETB`\n"
        f"📍 **ቦታ፦** {order.get('location_name', 'አልተጠቀሰም')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"ትዕዛዙን መቀበል ይፈልጋሉ?"
    )
    
    markup = types.InlineKeyboardMarkup()
    # 'Accept' እና 'Cancel' በተኖች
    markup.add(
        types.InlineKeyboardButton("✅ እሺ ተቀበል", callback_data=f"accept_order_{order_id}"),
        types.InlineKeyboardButton("❌ ሰርዝ", callback_data=f"cancel_order_{order_id}")
    )
    
    bot.send_message(v_id, text, reply_markup=markup, parse_mode="Markdown")







def calculate_special_final(message, order_id):
    try:
        # የባለቤቱን ግብዓት ማረጋገጥ
        item_price = float(message.text) 
        db = load_data()
        order = db['orders'].get(order_id)
        
        if not order:
            return bot.send_message(message.chat.id, "❌ ትዕዛዙ አልተገኘም!")

        vendor = db['vendors_list'].get(order['vendor_id'])
        user_data = db['users'].get(order['customer_id'])
        settings = db.get('settings', {})

        # 1. የርቀት፣ የዝናብ እና የምሽት ስሌት ከዝርዝር መረጃ ጋር
        # ከዚህ ቀደም የሰራነውን ፋንክሽን እዚህ እንጠራዋለን
        delivery_fee, fee_details = calculate_dynamic_delivery_fee(
            user_data['lat'], user_data['lon'], 
            vendor['lat'], vendor['lon']
        )

        # 2. የአገልግሎት ክፍያ
        service_fee = settings.get('service_fee', 8)

        # 3. ጠቅላላ ድምር
        grand_total = item_price + delivery_fee + service_fee

        # ዳታውን አፕዴት ማድረግ
        order['item_price'] = item_price
        order['delivery_fee'] = delivery_fee
        order['service_fee'] = service_fee
        order['grand_total'] = grand_total
        order['status'] = "Price Quoted"
        save_data(db)

        # 4. ለደንበኛው ዝርዝር መረጃ መላክ
        # እዚህ ጋር fee_details (ለምሳሌ፡ + 🌧️25) እንዲታይ ተደርጓል
        checkout_text = (
            f"✅ **የልዩ ትዕዛዝ ዋጋ ዝርዝር**\n\n"
            f"🛒 የእቃ ዋጋ፦ `{item_price:,.2f} ETB`\n"
            f"🛵 የዴሊቨሪ ክፍያ፦ `{delivery_fee:,.2f} ETB` {fee_details}\n"
            f"🏢 የአገልግሎት ክፍያ፦ `{service_fee:,.2f} ETB`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 **ጠቅላላ ድምር፦ `{grand_total:,.2f} ETB`**\n\n"
            f"ትዕዛዝዎን ማረጋገጥ ይፈልጋሉ?"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ ትዕዛዙን አረጋግጥ", callback_data=f"confirm_spec_{order_id}"))
        markup.add(types.InlineKeyboardButton("❌ ሰርዝ", callback_data=f"cancel_order_{order_id}"))

        bot.send_message(order['customer_id'], checkout_text, reply_markup=markup, parse_mode="Markdown")
        
        # ለድርጅቱ ባለቤት ማረጋገጫ
        bot.send_message(message.chat.id, "✅ ዋጋው ለደንበኛው ተልኳል። ምላሽ ሲሰጥ እናሳውቅዎታለን።")

    except ValueError:
        bot.send_message(message.chat.id, "❌ እባክዎ በትክክል ቁጥር ብቻ ያስገቡ (ለምሳሌ: 250)!")
    except Exception as e:
        print(f"Error in special final: {e}")
        bot.send_message(message.chat.id, "⚠️ ስህተት ተፈጥሯል፣ እባክዎ እንደገና ይሞክሩ።")








def get_location_keyboard():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    # ጽሁፉን ለሁለቱም እንዲሆን "📍 ያለሁበትን መገኛ (Location) ላክ" ማድረግ ትችላለህ
    button = types.KeyboardButton("📍 ያለሁበትን መገኛ (Location) ላክ", request_location=True)
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



def get_category_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🍴 ምግብና መጠጥ", callback_data="set_cat_Food_Drink"),
        types.InlineKeyboardButton("🛍️ ሱፐርማርኬትና ግሮሰሪ", callback_data="set_cat_Supermarket"),
        types.InlineKeyboardButton("👕 አልባሳትና ጫማ (Boutique)", callback_data="set_cat_Boutique"),
        types.InlineKeyboardButton("💄 ኮስሞቲክስና ውበት", callback_data="set_cat_Beauty"),
        types.InlineKeyboardButton("💊 መድኃኒት ቤት", callback_data="set_cat_Pharmacy"),
        types.InlineKeyboardButton("📦 ሌላ አገልግሎት", callback_data="set_cat_Other")
    )
    return markup



def get_item_photo(message):
    v_id = str(message.from_user.id)
    
    # ፎቶ ከተላከ (በተኑን ካልተጫነ)
    if message.content_type == 'photo':
        item_creation_data[v_id]['photo'] = message.photo[-1].file_id
    elif v_id not in item_creation_data or 'photo' not in item_creation_data[v_id]:
        # ፎቶም ካልላከ በተኑንም ካልተጫነ
        msg = bot.send_message(message.chat.id, "❌ እባክዎ ፎቶ ይላኩ ወይም 'ዝለል' የሚለውን ይጫኑ፦")
        return bot.register_next_step_handler(msg, get_item_photo)

    msg = bot.send_message(message.chat.id, "📝 አሁን ደግሞ የ**እቃውን ስም** ይጻፉ፦", parse_mode="Markdown")
    bot.register_next_step_handler(msg, get_item_name)




# --- 1. ስም መቀበያ እና የመለኪያ ምርጫ ---
def get_item_name(message):
    v_id = str(message.from_user.id)
    if v_id not in item_creation_data: return

    item_creation_data[v_id]['name'] = message.text
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("Pcs (ፍሬ)", callback_data="set_unit_Pcs"),
        types.InlineKeyboardButton("Kg (ኪሎ)", callback_data="set_unit_Kg"),
        types.InlineKeyboardButton("Ltr (ሊትር)", callback_data="set_unit_Ltr")
    )
    
    bot.send_message(message.chat.id, "📏 **የእቃው መለኪያ (Unit) ምንድነው?**", reply_markup=markup, parse_mode="Markdown")

# --- 2. መለኪያውን መያዝ እና ዋጋ መጠየቅ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_unit_"))
def set_item_unit(call):
    v_id = str(call.from_user.id)
    unit = call.data.replace("set_unit_", "")
    
    if v_id in item_creation_data:
        item_creation_data[v_id]['unit'] = unit
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        msg = bot.send_message(call.message.chat.id, f"💰 **የአንድ {unit} ዋጋ ስንት ነው?** (በቁጥር ብቻ)፦")
        bot.register_next_step_handler(msg, get_item_price)

# --- 3. ዋጋ መቀበያ (ከነ መለኪያው ማሳያ) ---
def get_item_price(message):
    v_id = str(message.from_user.id)
    if v_id not in item_creation_data: return

    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ፦")
        return bot.register_next_step_handler(msg, get_item_price)

    item_creation_data[v_id]['price'] = message.text
    item = item_creation_data[v_id]
    unit = item.get('unit', 'Pcs')

    summary = (
        f"🔍 **እቃውን ያረጋግጡ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 **ስም፦** {item['name']}\n"
        f"📏 **መለኪያ፦** {unit}\n"
        f"💵 **ዋጋ፦** {item['price']} ETB / {unit}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ አረጋግጥና መዝግብ", callback_data="confirm_final_save"))
    markup.add(types.InlineKeyboardButton("❌ ሰርዝ", callback_data="vendor_refresh"))

    bot.send_message(message.chat.id, summary, reply_markup=markup, parse_mode="Markdown")






def get_item_price(message):
    v_id = str(message.from_user.id)
    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ እባክዎ ዋጋውን በቁጥር ብቻ ይጻፉ (ለምሳሌ፦ 200)፦")
        return bot.register_next_step_handler(msg, get_item_price)

    item_creation_data[v_id]['price'] = int(message.text)
    
    # ዳታውን ሰብስቦ ማሳየት
    data = item_creation_data[v_id]
    summary = f"🔍 **እቃውን ያረጋግጡ**\n\n📦 ስም፦ {data['name']}\n💵 ዋጋ፦ {data['price']} ETB"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ አረጋግጥና መዝግብ", callback_data="confirm_final_save"))
    
    if data.get('photo') == "no_image":
        bot.send_message(message.chat.id, summary, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_photo(message.chat.id, data['photo'], caption=summary, reply_markup=markup, parse_mode="Markdown")






def process_price_update(message):
    v_id = str(message.from_user.id)
    new_price = message.text

    # የትኛው እቃ እንደነበር ከጊዜያዊ ዳታው ማውጣት
    item_id = item_creation_data.get(v_id, {}).get("editing_item_id")

    if not item_id:
        return bot.send_message(message.chat.id, "❌ ስህተት ተፈጥሯል። እባክዎ እንደገና ይሞክሩ።")

    if not new_price.isdigit():
        msg = bot.send_message(message.chat.id, "❌ እባክዎ ዋጋውን በቁጥር ብቻ ይጻፉ (ለምሳሌ፦ 300)፦")
        return bot.register_next_step_handler(msg, process_price_update)

    # ዳታቤዝ ላይ ማሻሻል
    db = load_data()
    if item_id in db.get('vendors_list', {}).get(v_id, {}).get('items', {}):
        db['vendors_list'][v_id]['items'][item_id]['price'] = int(new_price)
        save_data(db)
        
        bot.send_message(message.chat.id, f"✅ ዋጋው በተሳካ ሁኔታ ወደ **{new_price} ETB** ተቀይሯል!")
        
        # ወደ እቃው መቆጣጠሪያ ማውጫ ተመለስ
        text, markup, photo = get_item_management_markup(v_id, item_id)
        if photo and photo != "no_image":
            bot.send_photo(message.chat.id, photo, caption=text, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")
    
    # ጊዜያዊ ዳታውን አጽዳ
    if v_id in item_creation_data:
        del item_creation_data[v_id]





def get_items_pagination_markup(v_id, page=1):
    # 1. ሙሉውን ዳታቤዝ ከ Redis ጫን
    db = load_data()
    
    # 2. የዚህን ቬንደር መረጃ ከ vendors_list ውስጥ ፈልግ
    vendor_info = db.get('vendors_list', {}).get(str(v_id), {})
    items_dict = vendor_info.get('items', {})

    # 3. እቃ ከሌለ "እቃ ጨምር" የሚል በተን ብቻ አሳይ
    if not items_dict:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ የመጀመሪያ እቃህን ጨምር", callback_data="vendor_add_item"))
        markup.add(types.InlineKeyboardButton("🏠 ወደ ዳሽቦርድ", callback_data="vendor_refresh"))
        return markup

    # 4. እቃ ካለ በገጽ (Pagination) ከፋፍለህ አሳይ
    item_ids = list(items_dict.keys())
    total_items = len(item_ids)
    items_per_page = 6 # በገጽ 6 እቃ እንዲታይ
    
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    current_items = item_ids[start_index:end_index]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for i_id in current_items:
        item = items_dict[i_id]
        status_icon = "🟢" if item.get('status') == "Available" else "🔴"
        # እቃው ላይ ስትነካ ማስተካከያ ገጽ እንዲከፍት
        btn_text = f"{status_icon} {item['name']} - {item['price']} ETB"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"manage_item_{i_id}"))
    
    # 5. የገጽ መቀየሪያ በተኖች
    nav_btns = []
    if page > 1:
        nav_btns.append(types.InlineKeyboardButton("⬅️ የቀደመ", callback_data=f"v_items_page_{page-1}"))
    
    total_pages = (total_items + items_per_page - 1) // items_per_page
    if total_pages > 1:
        nav_btns.append(types.InlineKeyboardButton(f"ገጽ {page}/{total_pages}", callback_data="ignore"))
        
    if end_index < total_items:
        nav_btns.append(types.InlineKeyboardButton("ቀጣይ ➡️", callback_data=f"v_items_page_{page+1}"))
    
    if nav_btns:
        markup.row(*nav_btns)
        
    markup.add(types.InlineKeyboardButton("🏠 ወደ ዳሽቦርድ ተመለስ", callback_data="vendor_refresh"))
    
    return markup




def get_item_management_markup(v_id, item_id):
    db = load_data()
    item = db.get('vendors_list', {}).get(str(v_id), {}).get('items', {}).get(str(item_id))
    
    if not item:
        return None, None

    status = item.get('status', 'Available')
    status_text = "🟢 አለ (Available)" if status == "Available" else "🔴 አልቋል (Out of Stock)"
    toggle_text = "🔴 አልቋል በል" if status == "Available" else "🟢 አለ በል"
    
    text = (
        f"🛠 **የእቃ ማስተዳደሪያ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 **ስም፦** {item['name']}\n"
        f"💵 **ዋጋ፦** {item['price']} ETB\n"
        f"📊 **ሁኔታ፦** {status_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"ምን ማድረግ ይፈልጋሉ?"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        # የሁኔታ መቀየሪያ (Available <-> Out of Stock)
        types.InlineKeyboardButton(toggle_text, callback_data=f"toggle_status_{item_id}"),
        # ዋጋ መቀየሪያ
        types.InlineKeyboardButton("💰 ዋጋ ቀይር", callback_data=f"edit_price_{item_id}")
    )
    markup.add(types.InlineKeyboardButton("🗑️ እቃውን ሰርዝ", callback_data=f"delete_item_{item_id}"))
    markup.add(types.InlineKeyboardButton("🔙 ወደ ዝርዝር ተመለስ", callback_data="vendor_my_items"))
    
    return text, markup, item.get('photo')






from datetime import datetime, timedelta

def get_detailed_report(v_id, period="day"):
    db = load_data()
    orders = db.get('orders', {})
    now = datetime.now()
    
    total_sales = 0
    total_revenue = 0
    
    # የጊዜ ገደቡን መወሰኛ
    if period == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        title = "የዛሬ (Daily)"
    elif period == "week":
        start_date = now - timedelta(days=7)
        title = "የሳምንቱ (Weekly)"
    else: # Month
        start_date = now - timedelta(days=30)
        title = "የወሩ (Monthly)"

    for order_id, order in orders.items():
        # ትዕዛዙ የዚህ ቬንደር ከሆነ እና የተሳካ (Delivered) ከሆነ
        if str(order.get('vendor_id')) == str(v_id) and order.get('status') == 'Delivered':
            order_time = datetime.fromtimestamp(order.get('timestamp', 0))
            
            if order_time >= start_date:
                total_sales += 1
                total_revenue += order.get('total_price', 0)

    report_text = (
        f"📊 **{title} የሽያጭ ሪፖርት**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 **ጠቅላላ ትዕዛዞች፦** `{total_sales}`\n"
        f"💰 **ጠቅላላ ሽያጭ፦** `{total_revenue:,.2f} ETB`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 ሪፖርቱ የተዘጋጀው፦ {now.strftime('%H:%M')}"
    )
    
    # የሪፖርት መቀየሪያ በተኖች
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("📅 የዛሬ", callback_data="rep_day"),
        types.InlineKeyboardButton("🗓️ የሳምንት", callback_data="rep_week"),
        types.InlineKeyboardButton("📆 የወር", callback_data="rep_month")
    )
    markup.add(types.InlineKeyboardButton("🏠 ወደ ዳሽቦርድ", callback_data="vendor_refresh"))
    
    return report_text, markup





def get_vendor_settings_markup(v_id):
    raw_data = redis.hget("vendors", str(v_id))
    if not raw_data:
        return "❌ የድርጅት መረጃ አልተገኘም", None

    vendor_db = json.loads(raw_data)

    is_open = vendor_db.get('is_open', True)
    status_text = "🟢 ክፍት (Open)" if is_open else "🔴 ዝግ (Closed)"
    # በተኑንም ጭምር ቀይረነዋል
    toggle_btn = "🔴 ድርጅቱን ዝጋ" if is_open else "🟢 ድርጅቱን ክፈት"

    text = (
        f"⚙️ **የመቆጣጠሪያ ገጽ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏢 **የድርጅት ስም፦** {vendor_db.get('shop_name', 'ያልተገለጸ')}\n"
        f"📞 **ስልክ፦** {vendor_db.get('phone', 'ያልተገለጸ')}\n"
        f"📍 **አድራሻ፦** {vendor_db.get('location', 'ያልተገለጸ')}\n"
        f"📊 **ሁኔታ፦** {status_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(toggle_btn, callback_data="v_toggle_shop"),
        types.InlineKeyboardButton("📝 ስም ቀይር", callback_data="v_edit_name")
    )
    markup.add(
        types.InlineKeyboardButton("📞 ስልክ ቀይር", callback_data="v_edit_phone"),
        types.InlineKeyboardButton("📍 ቦታ ቀይር", callback_data="v_edit_loc")
    )
    markup.add(types.InlineKeyboardButton("🏠 ወደ ዳሽቦርድ ተመለስ", callback_data="vendor_refresh"))

    return text, markup






def show_settings_after_edit(message):
    v_id = message.from_user.id
    text, markup = get_vendor_settings_markup(v_id)
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")





# ስም ሴቭ ማድረጊያ
def v_save_new_name(message):
    v_id = str(message.from_user.id)
    new_name = message.text
    
    raw_data = redis.hget("vendors", v_id)
    if raw_data:
        vendor_db = json.loads(raw_data)
        vendor_db['shop_name'] = new_name # ስሙን ማዘመን
        redis.hset("vendors", v_id, json.dumps(vendor_db))
        
        bot.send_message(message.chat.id, f"✅ የሱቅ ስም ወደ **{new_name}** ተቀይሯል!")
        # ወደ settings ይመልሰዋል
        show_settings_after_edit(message)

# ስልክ ሴቭ ማድረጊያ
def v_save_new_phone(message):
    v_id = str(message.from_user.id)
    new_phone = message.text
    
    if len(new_phone) < 10:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፡ እባክዎ ትክክለኛ ስልክ ቁጥር ያስገቡ፦")
        return bot.register_next_step_handler(msg, v_save_new_phone)

    raw_data = redis.hget("vendors", v_id)
    if raw_data:
        vendor_db = json.loads(raw_data)
        vendor_db['phone'] = new_phone
        redis.hset("vendors", v_id, json.dumps(vendor_db))
        
        bot.send_message(message.chat.id, "✅ ስልክ ቁጥርዎ ተቀይሯል!")
        show_settings_after_edit(message)

# አድራሻ ሴቭ ማድረጊያ
def v_save_new_loc(message):
    v_id = str(message.from_user.id)
    new_loc = message.text
    
    raw_data = redis.hget("vendors", v_id)
    if raw_data:
        vendor_db = json.loads(raw_data)
        vendor_db['location'] = new_loc
        redis.hset("vendors", v_id, json.dumps(vendor_db))
        
        bot.send_message(message.chat.id, "✅ የሱቅ አድራሻ ተቀይሯል!")
        show_settings_after_edit(message)






def get_vendor_dashboard_elements(v_id):
    # ከዳታቤዝ የቬንደሩን ስም ለማውጣት (ከተመዘገበ)
    raw_data = redis.hget("vendors", str(v_id))
    shop_name = "የእርስዎ ሱቅ"
    if raw_data:
        vendor_db = json.loads(raw_data)
        shop_name = vendor_db.get('shop_name', "የእርስዎ ሱቅ")

    text = (
        f"🏪 **እንኳን ወደ {shop_name} መቆጣጠሪያ መጡ!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"ምን ማድረግ ይፈልጋሉ? ከታች ካሉት አማራጮች አንዱን ይምረጡ።"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ እቃ ጨምር", callback_data="vendor_add_item"),
        types.InlineKeyboardButton("📦 የእኔ እቃዎች", callback_data="vendor_my_items")
    )
    markup.add(
        types.InlineKeyboardButton("📈 የሽያጭ ታሪክ", callback_data="vendor_sales_report"),
        types.InlineKeyboardButton("⚙️ መቆጣጠሪያ", callback_data="vendor_settings")
    )
    markup.add(types.InlineKeyboardButton("🔄 አድስ", callback_data="vendor_refresh"))

    return text, markup




def process_wallet_deduction(v_id, order_id):
    db = load_data()
    order = db.get('orders', {}).get(order_id)
    
    # 🛡️ Safety Check 1: ትዕዛዙ መኖሩን ማረጋገጥ
    if not order:
        return False

    # 🛡️ Safety Check 2: ቀደም ብሎ ሂሳቡ ተቀንሶ ከሆነ (Double Deduction Prevention)
    if order.get('settled') == True:
        print(f"⚠️ Warning: Order {order_id} was already settled.")
        return False

    v_id = str(v_id)
    item_price = order.get('total_price', 0)
    commission = item_price * 0.10  # 10% ኮሚሽን
    total_deduct = item_price + commission

    if v_id in db['vendors_list']:
        vendor = db['vendors_list'][v_id]
        current_balance = vendor.get('deposit_balance', 0)
        
        # 🛡️ Safety Check 3: በቂ ባላንስ መኖሩን ማረጋገጥ (አማራጭ - ካስፈለገህ)
        # ባላንሱ ከሚቀንሰው ብር ካነሰ ለቬንደሩ ወይም ለአድሚን ማስጠንቀቂያ መላክ ይቻላል።
        
        # ሂሳቡን መቀነስ
        new_balance = current_balance - total_deduct
        db['vendors_list'][v_id]['deposit_balance'] = new_balance
        
        # ትዕዛዙ ተወራርዷል (Settled) ብሎ መመዝገብ
        order['settled'] = True
        order['settled_at'] = time.time() # መቼ እንደተቀነሰ ለማወቅ
        order['deducted_amount'] = total_deduct
        
        save_data(db)
        
        # ለቬንደሩ መልዕክት መላክ
        status_icon = "💳" if new_balance >= 0 else "⚠️"
        report_msg = (
            f"💸 **የሂሳብ ቅነሳ ማሳወቂያ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 ለትዕዛዝ ቁጥር፦ `{order_id}`\n"
            f"💰 የእቃ ዋጋ፦ `{item_price} ETB`\n"
            f"📈 ኮሚሽን (10%)፦ `{commission} ETB`\n"
            f"➖ **ጠቅላላ ቅነሳ፦** `{total_deduct} ETB`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{status_icon} **ቀሪ ባላንስዎ፦** `{new_balance:,.2f} ETB`"
        )
        
        # ባላንሱ ካለቀ ተጨማሪ ማስጠንቀቂያ
        if new_balance <= 0:
            report_msg += "\n\n❗ **ማሳሰቢያ፦** ቀሪ ባላንስዎ አልቋል። እባክዎ ባላንስዎን ይሙሉ!"

        bot.send_message(v_id, report_msg, parse_mode="Markdown")
        return True
        
    return False




def get_rating_markup(order_id):
    markup = types.InlineKeyboardMarkup(row_width=5)
    # አምስቱን ከዋክብት እንደ በተን ማቅረብ
    btns = [
        types.InlineKeyboardButton("⭐ 1", callback_data=f"rate_{order_id}_1"),
        types.InlineKeyboardButton("⭐ 2", callback_data=f"rate_{order_id}_2"),
        types.InlineKeyboardButton("⭐ 3", callback_data=f"rate_{order_id}_3"),
        types.InlineKeyboardButton("⭐ 4", callback_data=f"rate_{order_id}_4"),
        types.InlineKeyboardButton("⭐ 5", callback_data=f"rate_{order_id}_5")
    ]
    markup.add(*btns)
    return markup







def calculate_dynamic_delivery_fee(u_lat, u_lon, v_lat, v_lon):
    db = load_data()
    s = db.get('settings', {})

    # 1. ርቀቱን በKM እናሰላለን
    dist_m = calculate_distance(u_lat, u_lon, v_lat, v_lon)
    dist_km = dist_m / 1000

    # 2. የዋጋ መለኪያዎች
    base = float(s.get('base_delivery', 25)) # መነሻ 25 ብር
    extra_per_km = 7 # ከ 1 ኪሜ በላይ ለሚጨምር
    
    # 3. የርቀት ዋጋ ስሌት
    distance_fee = base
    if dist_km > 1.0:
        extra_dist = dist_km - 1.0
        distance_fee += (extra_dist * extra_per_km)

    # 4. ዝናብ እና ምሽት
    rain_extra = float(s.get('rain_val', 25)) if s.get('rain_mode') else 0
    night_extra = float(s.get('night_val', 15)) if s.get('night_mode') else 0

    total = distance_fee + rain_extra + night_extra

    # 5. ለደንበኛው የሚታይ ዝርዝር (በጣም ግልጽ በሆነ መንገድ)
    details = f"({distance_fee:.1f} ብር ርቀት"
    if rain_extra > 0: details += f" + 🌧️{rain_extra:.0f}"
    if night_extra > 0: details += f" + 🌙{night_extra:.0f}"
    details += ")"

    return round(total, 2), details






def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True






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

# --- መመለሻ Handler ---
@bot.callback_query_handler(func=lambda call: call.data == "go_to_main_start")
def back_to_main_handler(call):
    # ማንኛውንም የቆየ የጥያቄ ሂደት ያጸዳል (ለምሳሌ ስም ወይም ቁጥር እየጠበቀ ከሆነ)
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    
    # ዋናውን ሜኑ መልሰህ ላክ (ይህ ፋንክሽን መኖሩን አረጋግጥ)
    bot.edit_message_text(
        "👋 ወደ ዋናው ሜኑ ተመልሰዋል።\nሚናዎን ይምረጡ፦", 
        call.message.chat.id, 
        call.message.message_id, 
        reply_markup=main_menu_markup() # ዋናው ሜኑህን የሚመልስ ፋንክሽን
    )




def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add( "📊 ሪፖርት" )
    return markup





def get_vendor_dashboard_elements(v_id):
    db = load_data()
    v_id_str = str(v_id)
    v_info = db.get('vendors_list', {}).get(v_id_str, {})

    # 🛡️ መረጃው ከሌለ ቀድሞ መመለስ
    if not v_info:
        return "❌ የድርጅት መረጃ አልተገኘም!", None

    v_name = v_info.get('name', 'የእኔ ድርጅት')
    balance = v_info.get('deposit_balance', 0)
    items_dict = v_info.get('items', {})
    items_count = len(items_dict)
    
    # ⭐ የሬቲንግ መረጃ (Star Rating)
    avg_rating = v_info.get('rating_avg', 0.0)
    # ውጤቱን ወደ ኮከብ ምልክት መቀየር (ለምሳሌ 4 ኮከብ ከሆነ 4 "⭐" እንዲያሳይ)
    stars_icons = "⭐" * int(avg_rating) if avg_rating > 0 else "ገና አልተሰጠም"

    # ንቁ ትዕዛዞችን መቁጠር
    active_orders = 0 
    for order in db.get('orders', {}).values():
        if str(order.get('vendor_id')) == v_id_str and order.get('status') not in ['Completed', 'Cancelled', 'Delivered']:
            active_orders += 1

    summary_text = (
        f"🏠 **የድርጅት ዳሽቦርድ፦ {v_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌟 **ደረጃ፦** `{stars_icons}` ({avg_rating:.1f})\n" # ሬቲንጉ እዚህ ጋር ተጨምሯል
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
        types.InlineKeyboardButton("📦 የእኔ እቃዎች", callback_data="vendor_my_items")
    )
    markup.add(
        types.InlineKeyboardButton("📈 የሽያጭ ታሪክ", callback_data="vendor_sales_history"),
        types.InlineKeyboardButton("⚙️ መቆጣጠሪያ", callback_data="vendor_settings")
    )

    btn_refresh = types.InlineKeyboardButton("🔄 አድስ", callback_data="vendor_refresh")
    btn_back_to_main = types.InlineKeyboardButton("🏠 ወደ ዋናው ሜኑ", callback_data="go_to_main_start")

    markup.add(btn_refresh, btn_back_to_main)

    return summary_text, markup





def get_customer_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # በተኖቹን አንድ በአንድ ፍጠር
    b1 = types.KeyboardButton("🛍️ እቃዎችን ግዛ")
    b2 = types.KeyboardButton("✍️ ልዩ ትዕዛዝ")
    b3 = types.KeyboardButton("📋 ትዕዛዞቼ")
    b4 = types.KeyboardButton("📍 አድራሻዬን ቀይር")
    b5 = types.KeyboardButton("📞 ስልክ ቀይር")
    b6 = types.KeyboardButton("❓ እርዳታ")

    # በትክክል ጨምራቸው
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(b5, b6)

    return markup


def get_customer_registration_markup():
    # resize_keyboard በተኖቹ ትንሽ እንዲሆኑ ያደርጋል
    # one_time_keyboard አንዴ ከተጫኑ በኋላ እንዲጠፉ ያደርጋል
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    
    # 1. ስልክ ቁጥር መጠየቂያ በተን
    phone_btn = types.KeyboardButton("📲 ስልክ ቁጥር ላክ", request_contact=True)
    
    # 2. ሎኬሽን መጠየቂያ በተን
    location_btn = types.KeyboardButton("📍 ሎኬሽን ላክ", request_location=True)
    
    # በተኖቹን መጨመር
    markup.add(phone_btn)
    markup.add(location_btn)
    
    return markup




# --- ይህ ከፋንክሽኑ ውጭ መሆን አለበት ---
@bot.callback_query_handler(func=lambda call: call.data == "go_to_main_start")
def back_to_main_handler(call):
    # ማንኛውንም የቆየ ፕሮሰስ ያጸዳል
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    
    # ወደ ዋናው ሜኑ መመለስ (የ main_menu_markup ፋንክሽንህን እዚህ ይጠራዋል)
    bot.edit_message_text(
        "👋 ወደ ዋናው ሜኑ ተመልሰዋል።\nሚናዎን ይምረጡ፦", 
        call.message.chat.id, 
        call.message.message_id, 
        reply_markup=main_menu_markup() # ዋናው ሜኑ መመለሻ ፋንክሽንህ
    )
    bot.answer_callback_query(call.id)







@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_id_str = str(user_id)
    db = load_data()

    bot.clear_step_handler_by_chat_id(chat_id=chat_id)
    
    if user_id_str in item_creation_data:
        del item_creation_data[user_id_str]

    # 1. ብሮድካስት ምዝገባ
    if 'user_list' not in db: db['user_list'] = []
    if user_id not in db['user_list']:
        db['user_list'].append(user_id)
        save_data(db)

    # 2. አድሚን ከሆነ
    if user_id in ADMIN_IDS:
        markup = get_admin_dashboard(user_id)
        return bot.send_message(
            chat_id, 
            "👋 ሰላም ጌታዬ! እንኳን ወደ **BDF Delivery** መቆጣጠሪያ መጡ።",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    # 3. ቬንደር (ድርጅት) ከሆነ
    vendors_list = db.get('vendors_list', {})
    if user_id_str in vendors_list:
        v_info = vendors_list[user_id_str]
        if 'lat' not in v_info or 'lon' not in v_info:
            text = f"ሰላም {v_info.get('name', 'ባለቤት')}! 👋\n\nእባክዎ የድርጅቱን መገኛ (Location) ይላኩ።"
            return bot.send_message(chat_id, text, reply_markup=get_location_keyboard())
        
        text, markup = get_vendor_dashboard_elements(user_id)
        return bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    # 4. ተራ ደንበኛ ከሆነ (ከላይ ያሉት ካልሆኑ ብቻ ወደዚህ 'else' ይገባል)
    # ማሳሰቢያ፦ ይህ 'else' ከላይ ካለው 'if user_id_str in vendors_list' ጋር እኩል መስመር መሆን አለበት
    else:
        # ዳታቤዝ ውስጥ 'users' መኖሩን ቼክ እናደርጋለን
        if 'users' not in db: db['users'] = {}
        if user_id_str not in db['users']:
            db['users'][user_id_str] = {}
            save_data(db)

        if is_user_complete(user_id_str):
            welcome_text = f"እንኳን ደህና መጡ {message.from_user.first_name}! 👋\n\nምን ማዘዝ ይፈልጋሉ?"
            bot.send_message(chat_id, welcome_text, reply_markup=get_customer_main_markup(), parse_mode="Markdown")
        else:
            welcome_text = "እንኳን ወደ **BDF Delivery** በደህና መጡ! 👋\n\nእባክዎ መጀመሪያ ስልክና ሎኬሽን ያጋሩ።"
            bot.send_message(chat_id, welcome_text, reply_markup=get_customer_registration_markup(), parse_mode="Markdown")




# --- የተዋሃደ የአድሚን መመለሻ (ለ admin_main_menu እና go_to_main_start) ---
@bot.callback_query_handler(func=lambda call: call.data in ["admin_main_menu", "go_to_main_start"])
def back_to_main_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # የቆየ ፕሮሰስ ካለ ያጸዳል
    bot.clear_step_handler_by_chat_id(chat_id=chat_id)
    
    # አድሚን ከሆነ ወደ አድሚን ዳሽቦርድ
    if user_id in ADMIN_IDS:
        markup = get_admin_dashboard(user_id)
        bot.edit_message_text(
            "👋 ወደ አድሚን ዳሽቦርድ ተመልሰዋል።",
            chat_id, call.message.message_id, reply_markup=markup
        )
    # ቬንደር ከሆነ ወደ ቬንደር ዳሽቦርድ
    elif str(user_id) in load_data().get('vendors_list', {}):
        text, markup = get_vendor_dashboard_elements(user_id)
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    # ካልሆነ ወደ ደንበኛ ሜኑ
    else:
        bot.edit_message_text("ወደ ዋናው ሜኑ ተመልሰዋል", chat_id, call.message.message_id, reply_markup=customer_main_menu())
    
    bot.answer_callback_query(call.id)















@bot.callback_query_handler(func=lambda call: call.data.startswith('v_view_'))
def view_vendor_categories(call):
    try:
        vendor_id = call.data.replace('v_view_', '')
        db = load_data()
        vendor = db.get('vendors_list', {}).get(vendor_id)
        
        if not vendor:
            return bot.answer_callback_query(call.id, "❌ ድርጅቱ አልተገኘም!")

        v_name = vendor.get('name', 'ድርጅት')
        items = vendor.get('items', {})

        # 🛠️ ማስተካከያ፡ በ items ውስጥ ምድብ ከሌለ የቬንደሩን ዋና ምድብ ይጠቀማል
        categories = list(set([item.get('category') for item in items.values() if item.get('category')]))
        
        # እቃ ገና ካልተጨመረ የቬንደሩን ዋና ምድብ በዝርዝሩ ውስጥ ይጨምረዋል
        if not categories:
            main_cat = vendor.get('category', 'ሌሎች')
            categories = [main_cat]

        markup = types.InlineKeyboardMarkup(row_width=2)
        
        for cat in categories:
            markup.add(types.InlineKeyboardButton(f"📂 {cat}", callback_data=f"v_cat_{vendor_id}_{cat}"))

        markup.add(types.InlineKeyboardButton("⬅️ ወደ ሱቆች ዝርዝር ተመለስ", callback_data="back_to_shops"))

        text = (
            f"🏢 **ድርጅት፦ {v_name}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"እባክዎ መግዛት የሚፈልጉትን የምድብ አይነት ይምረጡ፦"
        )

        bot.edit_message_text(
            text, 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup, 
            parse_mode="Markdown"
        )

    except Exception as e:
        print(f"❌ View Category Error: {e}")
        bot.answer_callback_query(call.id, "⚠️ ስህተት ተፈጥሯል!")









@bot.callback_query_handler(func=lambda call: call.data == "vendor_refresh")
def handle_vendor_refresh(call):
    v_id = call.from_user.id
    text, markup = get_vendor_dashboard_elements(v_id)
    
    try:
        # የነበረውን መልዕክት ወደ ዳሽቦርድ መቀየር
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        # ለተጠቃሚው ትንሽዬ "Flash" መልዕክት ለማሳየት
        bot.answer_callback_query(call.id, "🔄 ዳሽቦርዱ ታድሷል!")
    except Exception as e:
        # መልዕክቱ መቀየር ካልቻለ (ለምሳሌ ዳታው ተመሳሳይ ከሆነ) አዲስ መላክ
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")






# --- ስም ለመቀየር ---
@bot.callback_query_handler(func=lambda call: call.data == "v_edit_name")
def v_edit_name_start(call):
    msg = bot.send_message(call.message.chat.id, "📝 አዲሱን የ**ሱቅ ስም** ያስገቡ፦", parse_mode="Markdown")
    bot.register_next_step_handler(msg, v_save_new_name)

# --- ስልክ ለመቀየር ---
@bot.callback_query_handler(func=lambda call: call.data == "v_edit_phone")
def v_edit_phone_start(call):
    msg = bot.send_message(call.message.chat.id, "📞 አዲሱን የ**ስልክ ቁጥር** ያስገቡ፦", parse_mode="Markdown")
    bot.register_next_step_handler(msg, v_save_new_phone)

# --- አድራሻ ለመቀየር ---
@bot.callback_query_handler(func=lambda call: call.data == "v_edit_loc")
def v_edit_loc_start(call):
    msg = bot.send_message(call.message.chat.id, "📍 አዲሱን የ**ሱቅ አድራሻ** (ሰፈር) ያስገቡ፦", parse_mode="Markdown")
    bot.register_next_step_handler(msg, v_save_new_loc)





@bot.callback_query_handler(func=lambda call: call.data == "vendor_settings")
def show_settings(call):
    v_id = call.from_user.id
    text, markup = get_vendor_settings_markup(v_id)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "v_toggle_shop")
def toggle_shop_status(call):
    v_id = str(call.from_user.id)
    raw_data = redis.hget("vendors", v_id)
    
    if raw_data:
        vendor_db = json.loads(raw_data)
        # ሁኔታውን መቀልበስ (True ከሆነ False፣ False ከሆነ True)
        vendor_db['is_open'] = not vendor_db.get('is_open', True)
        
        redis.hset("vendors", v_id, json.dumps(vendor_db))
        
        status = "ተከፍቷል" if vendor_db['is_open'] else "ተዘግቷል"
        bot.answer_callback_query(call.id, f"✅ ሱቁ በተሳካ ሁኔታ {status}!")
        
        # ገጹን ሪፍሬሽ ማድረግ
        text, markup = get_vendor_settings_markup(v_id)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")





@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def handle_customer_rating(call):
    # ዳታውን መበለጥ (ለምሳሌ: rate_ORDER123_5)
    _, order_id, stars = call.data.split("_")
    stars = int(stars)
    
    db = load_data()
    # የዚህን ትዕዛዝ ቬንደር መፈለግ
    order = db.get('orders', {}).get(order_id)
    if not order: return
    
    v_id = str(order.get('vendor_id'))
    v_info = db['vendors_list'].get(v_id)
    
    if v_info:
        # አዲስ አማካኝ ማስላት (አሮጌው ድምር + አዲሱ / ጠቅላላ ብዛት)
        old_total_stars = v_info.get('total_stars_sum', 0)
        old_count = v_info.get('reviews_count', 0)
        
        new_count = old_count + 1
        new_sum = old_total_stars + stars
        
        db['vendors_list'][v_id]['reviews_count'] = new_count
        db['vendors_list'][v_id]['total_stars_sum'] = new_sum
        db['vendors_list'][v_id]['rating_avg'] = round(new_sum / new_count, 1)
        
        save_data(db)
        
    bot.edit_message_text("አመሰግናለን! ሬቲንግዎ ተመዝግቧል። 🙏", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)





@bot.callback_query_handler(func=lambda call: call.data.startswith("rep_") or call.data == "vendor_sales_report")
def handle_report_switching(call):
    v_id = call.from_user.id
    
    # የትኛው ጊዜ እንደተመረጠ መለየት
    period = "day" # Default
    if "_" in call.data:
        period = call.data.split("_")
        
    text, markup = get_detailed_report(v_id, period)
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")






@bot.callback_query_handler(func=lambda call: call.data.startswith("manage_item_"))
def handle_manage_item(call):
    v_id = call.from_user.id
    item_id = call.data.replace("manage_item_", "")
    
    text, markup, photo = get_item_management_markup(v_id, item_id)
    
    if not text:
        return bot.answer_callback_query(call.id, "❌ እቃው አልተገኘም!")

    # ፎቶ ካለው ከነፎቶው ያሳያል
    if photo and photo != "no_image":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_photo(call.message.chat.id, photo, caption=text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")






@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_price_"))
def start_edit_price(call):
    item_id = call.data.replace("edit_price_", "")
    v_id = str(call.from_user.id)
    
    # የትኛው እቃ ላይ ዋጋ እየቀየርን እንደሆነ ለጊዜው መመዝገብ
    item_creation_data[v_id] = {"editing_item_id": item_id}
    
    msg = bot.send_message(
        call.message.chat.id, 
        "💰 እባክዎ አዲሱን የእቃውን **ዋጋ በቁጥር** ብቻ ይጻፉ፦\n(ስራውን ለማቆም /start ይበሉ)"
    )
    bot.register_next_step_handler(msg, process_price_update)






@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_status_"))
def handle_toggle_status(call):
    v_id = str(call.from_user.id)
    item_id = call.data.replace("toggle_status_", "")
    
    db = load_data()
    vendor_items = db.get('vendors_list', {}).get(v_id, {}).get('items', {})
    
    if item_id in vendor_items:
        current_status = vendor_items[item_id].get('status', 'Available')
        new_status = 'Out of Stock' if current_status == 'Available' else 'Available'
        
        db['vendors_list'][v_id]['items'][item_id]['status'] = new_status
        save_data(db)
        
        bot.answer_callback_query(call.id, f"ሁኔታው ወደ {new_status} ተቀይሯል")
        
        # ገጹን ሪፍሬሽ ማድረግ
        text, markup, photo = get_item_management_markup(v_id, item_id)
        if photo and photo != "no_image":
            bot.edit_message_caption(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")




@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_item_"))
def handle_delete_item(call):
    v_id = str(call.from_user.id)
    item_id = call.data.replace("delete_item_", "")
    
    db = load_data()
    if item_id in db.get('vendors_list', {}).get(v_id, {}).get('items', {}):
        del db['vendors_list'][v_id]['items'][item_id]
        save_data(db)
        
        bot.answer_callback_query(call.id, "✅ እቃው ተሰርዟል")
        # ወደ ዝርዝሩ ይመልሰዋል
        show_my_items(call) 



@bot.callback_query_handler(func=lambda call: call.data.startswith("vendor_my_items") or call.data.startswith("v_items_page_"))
def show_my_items(call):
    v_id = call.from_user.id
    
    # የገጽ ቁጥሩን ከ callback_data ላይ ማውጣት
    if "_" in call.data and "page" in call.data:
        page = int(call.data.split("_")[-1])
    else:
        page = 1
        
    markup = get_items_pagination_markup(v_id, page)
    
    text = (
        "📦 **የእርስዎ እቃዎች ዝርዝር**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "ለማስተካከል ወይም 'አልቋል' ለማለት የእቃውን ስም ይንኩ።\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    
    # ገጹን ሪፍሬሽ ለማድረግ (Edit message)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")




import time
import json

# ጊዜያዊ ዳታ መያዣ
item_creation_data = {}

# --- 1. እቃ ጨምር የሚለው በተን ሲጫን ---
@bot.callback_query_handler(func=lambda call: call.data == "vendor_add_item")
def start_adding_item(call):
    v_id = str(call.from_user.id)
    chat_id = call.message.chat.id
    
    # 🛡️ 1. ማንኛውንም የቆየ ፕሮሰስ አጽዳ
    bot.clear_step_handler_by_chat_id(chat_id=chat_id)
    
    item_creation_data[v_id] = {'photo': 'no_image', 'name': '', 'price': ''}
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⏩ ያለ ፎቶ እለፍ", callback_data="skip_photo_upload"))
    
    msg = bot.send_message(
        chat_id, 
        "<b>ደረጃ 1/3: 📸 የእቃውን ፎቶ ይላኩ</b>\n\n"
        "ፎቶ ከሌለዎት 'ያለ ፎቶ እለፍ' የሚለውን ይጫኑ።",
        reply_markup=markup,
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, get_item_photo)

# --- 2. ፎቶ መቀበያ ---
def get_item_photo(message):
    v_id = str(message.from_user.id)
    if v_id not in item_creation_data: return

    # 🛡️ 2. እዚህም አጽዳ
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

    if message.content_type == 'photo':
        item_creation_data[v_id]['photo'] = message.photo[-1].file_id
    
    msg = bot.send_message(message.chat.id, "<b>ደረጃ 2/3: 📝 የእቃውን ስም ይጻፉ</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, get_item_name)

# --- 3. ፎቶ መዝለያ (በተኑ ሲነካ) ---
@bot.callback_query_handler(func=lambda call: call.data == "skip_photo_upload")
def skip_photo_handler(call):
    v_id = str(call.from_user.id)
    chat_id = call.message.chat.id
    
    # 🛡️ 3. ፎቶ እንዲላክ ይጠብቅ የነበረውን ፕሮሰስ በግዴታ አጽዳ (ዋናው መፍትሄ!)
    bot.clear_step_handler_by_chat_id(chat_id=chat_id)
    
    if v_id not in item_creation_data:
        item_creation_data[v_id] = {'photo': 'no_image', 'name': '', 'price': ''}
        
    item_creation_data[v_id]['photo'] = "no_image"
    bot.delete_message(chat_id, call.message.message_id)
    
    msg = bot.send_message(chat_id, "<b>ደረጃ 2/3: 📝 የእቃውን ስም ይጻፉ</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, get_item_name)

# --- 4. ስም መቀበያ ---
def get_item_name(message):
    v_id = str(message.from_user.id)
    if v_id not in item_creation_data: return

    # 🛡️ 4. አጽዳ
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

    item_creation_data[v_id]['name'] = message.text
    msg = bot.send_message(message.chat.id, "<b>ደረጃ 3/3: 💰 የእቃውን ዋጋ ያስገቡ (በቁጥር ብቻ)</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, get_item_price)

# --- 5. ዋጋ መቀበያ ---
def get_item_price(message):
    v_id = str(message.from_user.id)
    if v_id not in item_creation_data: return

    # 🛡️ 5. አጽዳ
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ (ለምሳሌ 150)፦")
        return bot.register_next_step_handler(msg, get_item_price)

    item_creation_data[v_id]['price'] = message.text
    item = item_creation_data[v_id]

    summary = (
        f"🔍 **እቃውን ያረጋግጡ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 **ስም፦** {item['name']}\n"
        f"💵 **ዋጋ፦** {item['price']} ETB\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ አረጋግጥና መዝግብ", callback_data="confirm_final_save"))
    markup.add(types.InlineKeyboardButton("❌ ሰርዝ", callback_data="vendor_refresh"))

    if item['photo'] != "no_image":
        bot.send_photo(message.chat.id, item['photo'], caption=summary, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, summary, reply_markup=markup, parse_mode="Markdown")






# --- 5. መጨረሻ ላይ ዳታቤዝ ውስጥ ሴቭ ማድረጊያ ---
@bot.callback_query_handler(func=lambda call: call.data == "confirm_final_save")
def save_item_logic(call):
    v_id = str(call.from_user.id)
    if v_id in item_creation_data:
        item = item_creation_data[v_id]
        item_id = str(int(time.time()))

        db = load_data()
        
        # የቬንደሩን መዋቅር ማረጋገጥ
        if 'vendors_list' not in db: db['vendors_list'] = {}
        if v_id not in db['vendors_list']:
            db['vendors_list'][v_id] = {"name": "ያልተሰየመ ሱቅ", "items": {}, "deposit_balance": 0}
        if 'items' not in db['vendors_list'][v_id]: db['vendors_list'][v_id]['items'] = {}

        # ዳታውን ማስገባት
        db['vendors_list'][v_id]['items'][item_id] = {
            "name": item['name'],
            "price": item['price'],
            "photo": item['photo'],
            "status": "Available",
            "timestamp": time.time()
        }

        save_data(db)
        del item_creation_data[v_id]

        bot.answer_callback_query(call.id, "✅ እቃው ተመዝግቧል!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        # ወደ ዳሽቦርድ መመለስ
        text, markup = get_vendor_dashboard_elements(v_id)
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")





@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_order_"))
def confirm_cancel_request(call):
    order_id = call.data.replace("cancel_order_", "")
    
    # የማረጋገጫ በተኖች
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("⚠️ አዎ፣ በእርግጥ ሰርዝ", callback_data=f"final_cancel_{order_id}"),
        types.InlineKeyboardButton("🔙 አይ፣ ተመለስ", callback_data=f"accept_order_{order_id}") # ተመልሶ እንዲቀበል
    )
    
    confirm_text = (
        f"❗ **ትዕዛዝ ቁጥር #{order_id}ን ለመሰረዝ እየሞከሩ ነው።**\n\n"
        f"ይህንን ትዕዛዝ ከሰረዙት ደንበኛው ይናደዳል! በእርግጥ መሰረዝ ይፈልጋሉ?"
    )
    
    bot.edit_message_text(confirm_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")




@bot.callback_query_handler(func=lambda call: call.data.startswith("final_cancel_"))
def execute_final_cancel(call):
    order_id = call.data.replace("final_cancel_", "")
    db = load_data()
    order = db.get('orders', {}).get(order_id)
    
    if order:
        order['status'] = 'Cancelled'
        save_data(db)
        
        bot.edit_message_text(f"❌ ትዕዛዝ #{order_id} ተሰርዟል።", call.message.chat.id, call.message.message_id)
        
        # ለደንበኛውም "ትዕዛዝዎ በቬንደሩ ምክንያት ተሰርዟል" የሚል ኖቲፊኬሽን እዚህ ጋር መላክ ይቻላል
        # customer_id = order.get('customer_id')
        # bot.send_message(customer_id, f"ይቅርታ፣ ትዕዛዝ #{order_id} በሱቁ ባለቤት ተሰርዟል።")





@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_item_"))
def ask_quantity(call):
    _, _, v_id, i_id = call.data.split("_")
    db = load_data()
    item = db['vendors_list'][v_id]['items'][i_id]
    unit = item.get('unit', 'Pcs')

    markup = types.InlineKeyboardMarkup(row_width=3)
    
    # መለኪያው ኪሎ ከሆነ አማራጮችን መቀየር
    if unit == "Kg" or unit == "Ltr":
        options = ["0.5", "1", "1.5", "2", "5"]
    else:
        options = ["1", "2", "3", "5", "10"]
        
    btns = [types.InlineKeyboardButton(f"{opt} {unit}", callback_data=f"add_to_cart_{v_id}_{i_id}_{opt}") for opt in options]
    
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data=f"view_store_{v_id}"))

    bot.edit_message_text(
        f"🛍 **እቃ፦ {item['name']}**\n"
        f"💰 **ዋጋ፦ {item['price']} ETB / {unit}**\n\n"
        f"🔢 ስንት {unit} ይፈልጋሉ? ከታች ይምረጡ፦",
        call.message.chat.id, call.message.message_id,
        reply_markup=markup, parse_mode="Markdown"
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
