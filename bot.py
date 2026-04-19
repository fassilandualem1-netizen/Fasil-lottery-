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
            "vendor_commission_p": 5,    # ከእቃ ዋጋ 5%
            "rider_commission_p": 10,   # ከራይደሩ ዋሌት የሚቀነስ 10%
            "vendor_negative_limit": -1000, # ⬅️ አዲስ፦ ቬንደሩ እስከዚህ ድረስ በዕዳ መስራት ይችላል
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
                return default_db

            # 🛠 አዳዲስ የ settings ቁልፎች በቆየው ዳታቤዝ ውስጥ ከሌሉ እንዲጨመሩ (Syncing)
            if "settings" not in loaded_db:
                loaded_db["settings"] = default_db["settings"]
            else:
                for key, value in default_db["settings"].items():
                    if key not in loaded_db["settings"]:
                        loaded_db["settings"][key] = value
            
            # ሌሎች ዋና ዋና ቁልፎች መኖራቸውን ማረጋገጥ
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



def get_final_delivery_fee(distance_meters, settings):
    distance_km = distance_meters / 1000
    base_fee = settings.get('base_delivery', 50) # መነሻ 50 ብር
    
    # ለምሳሌ ከ 2 ኪሎ ሜትር በላይ ለሆነ ለእያንዳንዱ 1 ኪሜ 15 ብር ቢታሰብ
    if distance_km > 2:
        extra_km = distance_km - 2
        extra_fee = extra_km * 15
        total_fee = base_fee + extra_fee
    else:
        total_fee = base_fee
        
    return round(total_fee, 2)






def process_order_settlement(order_id):
    with db_lock:
        db = load_data()
        order = db['orders'].get(str(order_id))

        if not order or order.get('status') == "Completed":
            return False

        r_id = str(order.get('rider_id'))
        v_id = str(order.get('vendor_id'))
        item_price = float(order.get('item_total', 0))
        held_amount = order.get('held_amount', 0)

        # 1. ከራይደሩ የ Hold ዝርዝር ላይ ብሩን ማጽዳት
        if r_id in db['riders_list']:
            db['riders_list'][r_id]['on_hold_balance'] -= held_amount
            # ራይደሩ አስቀድሞ ስለከፈለ (Prepaid) እዚህ ባላንስ አይቀነስም

        # 2. የቬንደር ባላንስ መቀነስ (Negative እንዲሆን ይፈቀዳል)
        if v_id in db['vendors_list']:
            # አድሚኑ ለቬንደሩ የከፈለው 'Deposit' ላይ የእቃው ዋጋ ይቀነሳል
            db['vendors_list'][v_id]['deposit_balance'] -= item_price
            
            # የቬንደር ኮሚሽን ስሌት (ከእቃው ዋጋ ላይ)
            v_comm_p = db['settings'].get('vendor_commission_p', 5)
            v_commission = item_price * (v_comm_p / 100)
            
            # ኮሚሽኑንም ከቬንደሩ እንቀንሳለን
            db['vendors_list'][v_id]['deposit_balance'] -= v_commission
            
            # የአድሚን ትርፍ መመዝገብ
            # 1. ከቬንደር የተገኘ ኮሚሽን + 2. ከራይደር የተገኘ ኮሚሽን (held_amount - item_price)
            r_commission = held_amount - item_price
            db['total_profit'] += (v_commission + r_commission)

        order['status'] = "Completed"
        order['settled_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        save_data(db)
        return True




def add_org_item(v_id, text_input):
    try:
        name, price = text_input.split(",")
        item_id = str(int(time.time())) # ልዩ መለያ
        db = load_data()
        db['vendors_list'][str(v_id)]['items'][item_id] = {
            "name": name.strip(),
            "price": float(price.strip()),
            "available": True
        }
        save_data(db)
        return True
    except:
        return False




def register_vendor_logic(v_id, name, category):
    db = load_data()
    db['vendors_list'][str(v_id)] = {
        "name": name,
        "category": category,
        "deposit_balance": 0.0,
        "items": {},          # እቃዎች በ "Add to Cart" መልክ እዚህ ይገባሉ
        "sales_history": [],  # ለወደፊት ሪፖርት
        "is_active": True,
        "shop_open": True
    }
    save_data(db)


def get_org_financials(v_id):
    db = load_data()
    vendor = db['vendors_list'].get(str(v_id))
    if vendor:
        bal = vendor['deposit_balance']
        limit = db['settings']['vendor_negative_limit']
        return f"🏢 ድርጅት፦ {vendor['name']}\n💰 ቀሪ ሂሳብ፦ {bal} ETB\n📉 የብድር ገደብ፦ {limit} ETB"
    return "❌ መረጃ አልተገኘም።"




def complete_order_finance(order_id):
    db = load_data()
    order = db['orders'].get(order_id)
    v_id = str(order['vendor_id'])
    r_id = str(order['rider_id'])
    item_price = order['item_price']
    
    # 1. የቬንደር ኮሚሽን ስሌት (ከእቃው ላይ ብቻ)
    v_comm_p = db['settings'].get('vendor_commission_p', 5)
    vendor_deduction = item_price + (item_price * v_comm_p / 100)
    
    # 2. ከቬንደር ዋሌት ላይ መቀነስ (አድሚኑ ቀድሞ ስለከፈለው)
    db['vendors_list'][v_id]['deposit_balance'] -= vendor_deduction
    
    # 3. ለቬንደሩ ትራንዛክሽን መመዝገብ
    new_txn = {
        "date": datetime.now().strftime("%m-%d %H:%M"),
        "amount": vendor_deduction,
        "desc": f"Order #{order_id[-5:]}"
    }
    if 'transactions' not in db['vendors_list'][v_id]:
        db['vendors_list'][v_id]['transactions'] = []
    db['vendors_list'][v_id]['transactions'].append(new_txn)
    
    # 4. ለአድሚን ኖቲፊኬሽን መላክ (ባላንስ ካለቀ)
    if db['vendors_list'][v_id]['deposit_balance'] < 500:
        admin_msg = (f"🚨 **የድርጅት ባላንስ አልቋል!**\n\n"
                     f"🏢 ድርጅት፦ {db['vendors_list'][v_id]['name']}\n"
                     f"💵 ቀሪ ሂሳብ፦ {db['vendors_list'][v_id]['deposit_balance']} ETB\n"
                     f"እባክዎ ለድርጅቱ ክፍያ በመፈጸም ባላንስ ይሙሉ።")
        bot.send_message(ADMIN_ID, admin_msg)
        
    save_data(db)



def accept_order(rider_id, order_id):
    db = load_data()
    order = db['orders'].get(str(order_id))
    v_id = str(order.get('vendor_id'))
    
    # የቬንደር የብድር ገደብ ፍተሻ
    v_bal = db['vendors_list'].get(v_id, {}).get('deposit_balance', 0)
    v_limit = db['settings'].get('vendor_negative_limit', -1000) # ካልተገኘ -1000 default
    
    if v_bal <= v_limit:
        bot.send_message(rider_id, "❌ ይቅርታ፣ የዚህ ድርጅት የሂሳብ ዝውውር ለጊዜው ተቋርጧል።")
        return

    item_price = order['item_total']
    bot_comm_p = db['settings'].get('rider_commission_p', 10) 
    bot_commission = item_price * (bot_comm_p / 100)
    total_to_hold = item_price + bot_commission
    
    rider_wallet = db['riders_list'][str(rider_id)].get('wallet', 0)

    if rider_wallet >= total_to_hold:
        order['rider_id'] = rider_id
        order['status'] = "Accepted"
        order['held_amount'] = total_to_hold
        
        db['riders_list'][str(rider_id)]['wallet'] -= total_to_hold
        db['riders_list'][str(rider_id)]['on_hold_balance'] += total_to_hold
        
        save_data(db)
        bot.send_message(rider_id, f"✅ ትዕዛዙን ተቀብለዋል። {total_to_hold} ETB ታግዷል።")
    else:
        bot.send_message(rider_id, f"❌ በቂ ባላንስ የለዎትም። የሚያስፈልገው፦ {total_to_hold} ETB")




def calculate_manual_order_total(item_price, db_settings):
    # 1. የማድረሻ ክፍያ (Base Delivery)
    delivery_fee = db_settings.get('base_delivery', 50)
    
    # 2. የቦቱ ኮሚሽን ከእቃው ዋጋ ላይ (ለምሳሌ 5%)
    # ማሳሰቢያ፡ ይህ ቬንደሩ የሚከፍለው ኮሚሽን ነው
    vendor_comm_p = db_settings.get('vendor_commission_p', 5)
    vendor_commission = item_price * (vendor_comm_p / 100)
    
    # 3. ለደንበኛው የሚነገረው ጠቅላላ ዋጋ
    # ደንበኛው የሚከፍለው = የእቃ ዋጋ + የማድረሻ ክፍያ
    total_to_customer = item_price + delivery_fee
    
    return total_to_customer, vendor_commission



def cancel_and_refund_order(order_id):
    with db_lock:
        db = load_data()
        order = db['orders'].get(str(order_id))
        
        if not order or order['status'] in ["Completed", "Cancelled"]:
            return False

        r_id = str(order['rider_id'])
        held_amount = order.get('held_amount', 0)

        # 1. ለራይደሩ የታገደውን ብር መመለስ
        if r_id in db['riders_list']:
            db['riders_list'][r_id]['wallet'] += held_amount # ብሩ ተመለሰ
            db['riders_list'][r_id]['on_hold_balance'] -= held_amount

        # 2. የቬንደር ባላንስ ላይ ምንም አንቀንስም (ምክንያቱም ኦርደሩ አልተሳካም)
        
        order['status'] = "Cancelled"
        save_data(db)
        return True




def can_rider_take_more(rider_id, new_order_price):
    db = load_data()
    rider = db['riders_list'].get(str(rider_id))
    
    # ሊሰራበት የሚችለው ብር (Available Balance)
    available_balance = rider.get('wallet', 0)
    
    if available_balance >= new_order_price:
        return True
    else:
        return False





def get_vendor_items_menu(v_id):
    db = load_data()
    v_id_str = str(v_id)
    # ቬንደሩ መኖሩን ማረጋገጥ
    vendor = db['vendors_list'].get(v_id_str, {})
    if not vendor:
        return "❌ ድርጅቱ አልተገኘም", None

    # 'items' የሚለው ቁልፍ ከሌለ ባዶ ዲክሽነሪ ይስጠው
    items = vendor.get('items', {})
    category = vendor.get('category', 'ዕቃዎች')

    icons = {
        "ኮስሞቲክስ": "💄", "ቡቲክ": "👗", "ሱፐርማርኬት": "🛒", 
        "ምግብ ቤት": "🍔", "ግሮሰሪ": "🛍", "ፋርማሲ": "💊"
    }
    icon = icons.get(category, "📦")

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton(f"➕ አዲስ {category} መዝግብ", callback_data="v_add_item_start"))

    msg = f"{icon} **የ{category} ማስተዳደሪያ**\n━━━━━━━━━━━━━━━━━━━━\n"

    if not items:
        msg += "እስካሁን ምንም የተመዘገበ ዕቃ የለም።"
    else:
        msg += "ለማስተካከል ወይም ዝርዝር ለማየት ዕቃውን ይጫኑ፦\n"
        for i_id, info in items.items():
            stock_status = "🟢" if info.get('available', True) else "🔴"
            has_photo = "📸" if info.get('photo') else ""
            btn_text = f"{stock_status} {info['name']} - {info['price']} ETB {has_photo}"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"v_view_item_{i_id}"))

    msg += "\n━━━━━━━━━━━━━━━━━━━━"
    markup.add(types.InlineKeyboardButton("⬅️ ወደ ዳሽቦርድ ተመለስ", callback_data="v_dashboard_back"))

    return msg, markup



def process_photo_step_1(message):
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, "❌ እባክዎ ፎቶ ይላኩ!")
        return
    file_id = message.photo[-1].file_id
    sent = bot.send_message(message.chat.id, "✅ ፎቶው ደርሷል! አሁን ስም እና ዋጋ በኮማ ይላኩ (ምሳሌ፦ `ቀሚስ, 1200`)")
    bot.register_next_step_handler(sent, process_photo_step_2, file_id)

def process_photo_step_2(message, file_id):
    v_id = str(message.chat.id)
    try:
        name, price = message.text.split(",")
        item_id = str(int(time.time()))
        db = load_data()
        if 'items' not in db['vendors_list'][v_id]: db['vendors_list'][v_id]['items'] = {}
        db['vendors_list'][v_id]['items'][item_id] = {
            "name": name.strip(), "price": float(price.strip()), "photo": file_id, "available": True
        }
        save_data(db)
        bot.send_message(v_id, "✅ በፎቶ በትክክል ተመዝግቧል!")
        msg, markup = get_vendor_items_menu(v_id)
        bot.send_message(v_id, msg, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(v_id, "❌ ስህተት! እባክዎ ስም እና ዋጋን በኮማ ይላኩ።")




def get_order_detail_view(order_id, v_id):
    db = load_data()
    order = db['orders'].get(str(order_id))
    
    text = (f"🆔 <b>ትዕዛዝ ቁጥር፦ #{order_id[-5:]}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 ደንበኛ፦ {order.get('customer_name', 'ያልታወቀ')}\n"
            f"📦 ዕቃዎች፦ {order.get('items_summary', 'በጽሁፍ')}\n"
            f"💰 ዋጋ፦ {order.get('item_total', 0)} ETB\n"
            f"📊 ሁኔታ፦ <b>{order.get('status')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━")

    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # በሁኔታው (Status) ላይ ተመስርቶ የሚመጡ በተኖች
    status = order.get('status')
    if status == "Pending":
        markup.add(types.InlineKeyboardButton("✅ ትዕዛዝ ተቀበል", callback_data=f"v_order_accept_{order_id}"))
    elif status == "Preparing":
        markup.add(types.InlineKeyboardButton("👨‍🍳 ዝግጁ ነው (ራይደር ጥራ)", callback_data=f"v_order_ready_{order_id}"))
    
    markup.add(types.InlineKeyboardButton("❌ ትዕዛዝ ሰርዝ", callback_data=f"v_order_cancel_{order_id}"))
    markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data="v_active_orders"))
    
    return text, markup





def process_price_update(message, item_id):
    v_id = str(message.chat.id)
    try:
        new_price = float(message.text.strip())
        db = load_data()
        db['vendors_list'][v_id]['items'][item_id]['price'] = new_price
        save_data(db)
        bot.send_message(v_id, "✅ ዋጋው ተቀይሯል!")
        msg, markup = get_item_detail_menu(v_id, item_id)
        bot.send_message(v_id, msg, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(v_id, "❌ ስህተት! እባክዎ በትክክል ቁጥር ብቻ ያስገቡ።")

def process_photo_update(message, item_id):
    v_id = str(message.chat.id)
    if message.content_type != 'photo':
        bot.send_message(v_id, "❌ ስህተት! እባክዎ ፎቶ ብቻ ይላኩ።")
        return

    file_id = message.photo[-1].file_id # ትልቁን ፎቶ ይወስዳል
    db = load_data()
    db['vendors_list'][v_id]['items'][item_id]['photo'] = file_id
    save_data(db)
    
    bot.send_message(v_id, "✅ ፎቶው ተመዝግቧል!")
    msg, markup = get_item_detail_menu(v_id, item_id)
    bot.send_photo(v_id, file_id, caption=msg, reply_markup=markup, parse_mode="Markdown")





def save_new_item(message):
    v_id = str(message.chat.id)
    text = message.text

    if "," not in text:
        msg = bot.send_message(v_id, "⚠️ ስህተት! እባክዎ በኮማ ይለዩ።\nምሳሌ፦ `በርገር, 250`")
        bot.register_next_step_handler(msg, save_new_item)
        return

    try:
        name, price = text.split(",")
        item_id = str(int(time.time()))
        db = load_data()

        # ቬንደሩ መኖሩን ቼክ ማድረግ
        if v_id not in db['vendors_list']:
            bot.send_message(v_id, "❌ ድርጅትዎ በሲስተሙ አልተገኘም።")
            return

        # 'items' የሚለውን ዲክሽነሪ መፍጠር (ከሌለ)
        if 'items' not in db['vendors_list'][v_id]:
            db['vendors_list'][v_id]['items'] = {}

        db['vendors_list'][v_id]['items'][item_id] = {
            "name": name.strip(),
            "price": float(price.strip()),
            "available": True,
            "photo": None
        }

        save_data(db)
        bot.send_message(v_id, f"✅ ዕቃው '{name.strip()}' በትክክል ተመዝግቧል!")
        
        # ወደ እቃዎች ዝርዝር መመለስ
        msg, markup = get_vendor_items_menu(v_id)
        bot.send_message(v_id, msg, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(v_id, "❌ ስህተት! እባክዎ ዋጋውን ቁጥር ብቻ ያድርጉ።")





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







def get_vendor_main_menu(vendor_id):
    db = load_data()
    vendor = db['vendors_list'].get(str(vendor_id))
    
    if not vendor:
        return "❌ ይቅርታ፣ ይህ ድርጅት በሲስተሙ ውስጥ አልተመዘገበም።", None

    # 📍 ደረጃ 1፡ ሎኬሽን መኖሩን ማረጋገጥ (ለዴሊቨሪ ክፍያ ስሌት ወሳኝ ነው)
    if not vendor.get('location'):
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        btn_loc = types.KeyboardButton("📍 የድርጅቱን መገኛ ቦታ ላክ", request_location=True)
        markup.add(btn_loc)
        return "እንኳን ደህና መጡ! ድርጅትዎን ለመጨረስ መጀመሪያ ያሉበትን ቦታ (Location) መላክ አለብዎት።", markup

    # 🟢 ደረጃ 2፡ ሎኬሽን ካለው ሙሉ ዳሽቦርድ ማሳየት
    is_open = vendor.get('shop_open', True)
    status_text = "🟢 ድርጅቱ ክፍት ነው" if is_open else "🔴 ድርጅቱ ዝግ ነው"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # ዋና ዋና በተኖች
    btn_orders = types.InlineKeyboardButton("📋 ወቅታዊ ትዕዛዞች", callback_data="v_active_orders")
    btn_items = types.InlineKeyboardButton("📦 የእኔ እቃዎች", callback_data="v_manage_items")
    btn_wallet = types.InlineKeyboardButton("💰 የሂሳብ ሁኔታ", callback_data="v_wallet")
    btn_history = types.InlineKeyboardButton("📊 የሽያጭ ታሪክ", callback_data="v_history")
    btn_status = types.InlineKeyboardButton(status_text, callback_data="v_toggle_shop")
    btn_exit = types.InlineKeyboardButton("⬅️ ውጣ", callback_data="main_menu")
    
    # አቀማመጥ
    markup.add(btn_orders)
    markup.add(btn_items, btn_wallet)
    markup.add(btn_history, btn_status)
    markup.add(btn_exit)
    
    msg = (f"🏢 **የድርጅት ዳሽቦርድ፦ {vendor['name']}**\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"💰 ባላንስ፦ {vendor['deposit_balance']} ETB\n"
           f"📍 ቦታ፦ ተመዝግቧል ✅\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"ምን ማድረግ ይፈልጋሉ?")
    
    return msg, markup





def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add( "📊 ሪፖርት" )
    return markup





@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        uid_str = str(user_id)
        
        # ማንኛውንም የቆየ ስራ ማጽዳት
        bot.clear_step_handler_by_chat_id(chat_id=user_id) 

        db = load_data() 

        # ተጠቃሚውን ወደ ሊስት መጨመሪያ
        if "user_list" not in db: db["user_list"] = []
        if user_id not in db["user_list"]:
            db["user_list"].append(user_id)
            save_data(db)

        # 1. አድሚን ከሆነ
        if user_id in ADMIN_IDS:
            markup = get_admin_dashboard(user_id)
            return bot.send_message(user_id, "👑 **እንኳን ደህና መጡ የBDF አድሚን!**", 
                                   reply_markup=markup, parse_mode="Markdown")

        # 2. ቬንደር ከሆነ
        if uid_str in db.get('vendors_list', {}):
            result = get_vendor_main_menu(uid_str)
            # get_vendor_main_menu አንዳንድ ጊዜ (msg, markup) አንዳንድ ጊዜ ደግሞ (markup) ብቻ ሊመልስ ይችላል
            if isinstance(result, tuple):
                msg, markup = result
                return bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")
            else:
                return bot.send_message(user_id, "እንኳን ደህና መጡ!", reply_markup=result)

        # 3. ለሌላ ተጠቃሚ (ደንበኛ ወይም አዲስ ሰው)
        welcome_text = (f"ሰላም {message.from_user.first_name} 👋\n"
                        f"ወደ BDF ዴሊቨሪ ቦት እንኳን ደህና መጡ።\n\n"
                        f"የመለያ ቁጥርዎ፦ `{user_id}`")
        bot.send_message(user_id, welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

    except Exception as e:
        print(f"❌ Error in start_command: {e}")
        bot.send_message(message.chat.id, "⚠️ ቦቱን ማስጀመር ላይ ስህተት ተፈጥሯል። እባክዎ ደግመው ይሞክሩ።")


@bot.message_handler(commands=['admin'])
def show_admin_panel(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        markup = get_admin_dashboard(user_id) # 👈 user_id ተጨምሯል
        bot.send_message(
            message.chat.id, 
            "👑 **BDF አድሚን ዳሽቦርድ**",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id, "❌ ፈቃድ የለዎትም።")







@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def interrupt_handler(message):
    # ማንኛውም ኮማንድ ሲመጣ የቆየውን Next Step ይሰርዛል
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    
    # ከዚያ ወደ ትክክለኛው ኮማንድ ይልከዋል
    if message.text == '/start':
        start_command(message)
    elif message.text == '/admin':
        show_admin_panel(message)



@bot.callback_query_handler(func=lambda call: call.data == "v_history")
def vendor_history_main(call):
    v_id = str(call.message.chat.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # የሪፖርት ዓይነቶች
    btn_today = types.InlineKeyboardButton("📅 የዛሬ ሽያጭ", callback_data="v_hist_today")
    btn_week = types.InlineKeyboardButton("📅 የሳምንቱ ሽያጭ", callback_data="v_hist_week")
    btn_back = types.InlineKeyboardButton("⬅️ ተመለስ", callback_data="v_dashboard")
    
    markup.add(btn_today, btn_week, btn_back)
    
    text = "📊 **የሽያጭ ታሪክ ማህደር**\n\nማየት የሚፈልጉትን የጊዜ ገደብ ይምረጡ፦"
    bot.edit_message_text(text, v_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")




@bot.callback_query_handler(func=lambda call: call.data.startswith('v_order_'))
def vendor_order_logic(call):
    v_id = str(call.message.chat.id)
    db = load_data()
    
    # 1.1 ትዕዛዝ መቀበል (Accept)
    if call.data.startswith("v_order_accept_"):
        order_id = call.data.replace("v_order_accept_", "")
        if order_id in db['orders']:
            db['orders'][order_id]['status'] = "Preparing"
            save_data(db)
            bot.answer_callback_query(call.id, "✅ ትዕዛዙ ተቀባይነት አግኝቷል!")
            
            # ለደንበኛው ኖቲፊኬሽን መላክ
            customer_id = db['orders'][order_id]['customer_id']
            bot.send_message(customer_id, f"✅ ትዕዛዝዎ #{order_id[-5:]} በዝግጅት ላይ ነው።")
            
            # ገጹን ወደ 'በዝግጅት ላይ' እንዲቀየር ማዘመን
            msg, markup = get_order_detail_view(order_id, v_id)
            bot.edit_message_text(msg, v_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # 1.2 ዝግጅት አልቆ ለራይደር ጥሪ ማስተላለፍ (Ready)
    elif call.data.startswith("v_order_ready_"):
        order_id = call.data.replace("v_order_ready_", "")
        db['orders'][order_id]['status'] = "Waiting for Rider"
        save_data(db)
        
        bot.answer_callback_query(call.id, "🚀 ለራይደሮች ጥሪ ተላልፏል!")
        # እዚህ ጋር ለራይደሮች ጥሪ የሚልከውን ተግባር ጥራ
        # announce_to_riders(order_id)
        
        msg, markup = get_order_detail_view(order_id, v_id)
        bot.edit_message_text(msg, v_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # 1.3 ትዕዛዝ መሰረዝ (Cancel)
    elif call.data.startswith("v_order_cancel_"):
        order_id = call.data.replace("v_order_cancel_", "")
        db['orders'][order_id]['status'] = "Cancelled"
        save_data(db)
        bot.answer_callback_query(call.id, "❌ ትዕዛዙ ተሰርዟል")
        bot.edit_message_text("❌ ይህ ትዕዛዝ ተሰርዟል።", v_id, call.message.message_id)





from datetime import datetime, timedelta

@bot.callback_query_handler(func=lambda call: call.data.startswith('v_hist_'))
def show_vendor_report(call):
    v_id = str(call.message.chat.id)
    report_type = call.data.replace('v_hist_', '')
    db = load_data()
    
    now = datetime.now()
    orders_to_show = []
    total_sales = 0
    
    # 1. ዳታውን ማጣራት (Filtering)
    for oid, order in db['orders'].items():
        if str(order.get('vendor_id')) != v_id or order.get('status') != 'Completed':
            continue
            
        order_time = datetime.strptime(order['timestamp'], "%Y-%m-%d %H:%M:%S")
        
        if report_type == "today" and order_time.date() == now.date():
            orders_to_show.append(order)
            total_sales += order['item_price']
        elif report_type == "week" and order_time > (now - timedelta(days=7)):
            orders_to_show.append(order)
            total_sales += order['item_price']

    # 2. ጽሁፉን ማዘጋጀት
    title = "📅 የዛሬ ሽያጭ" if report_type == "today" else "📅 የሳምንቱ ሽያጭ"
    report_msg = f"📊 **{title}**\n━━━━━━━━━━━━━━━\n"
    
    if not orders_to_show:
        report_msg += "_ምንም ዓይነት የተጠናቀቀ ሽያጭ የለም።_"
    else:
        for o in orders_to_show[-10:]: # የመጨረሻ 10ሩን ብቻ ለማሳየት
            rider_name = o.get('rider_name', 'ያልታወቀ')
            item_price = o['item_price']
            report_msg += f"• **#{o['order_id'][-5:]}** | `{item_price} ETB`\n   🛵 ራይደር፦ {rider_name}\n"
        
        v_comm_p = db['settings'].get('vendor_commission_p', 5)
        total_comm = total_sales * (v_comm_p / 100)
        
        report_msg += f"━━━━━━━━━━━━━━━\n"
        report_msg += f"💰 **ጠቅላላ ሽያጭ፦** `{total_sales}` ETB\n"
        report_msg += f"📉 **የቦት ኮሚሽን ({v_comm_p}%)፦** `{total_comm}` ETB\n"
        report_msg += f"🏦 **የተጣራ ገቢ፦** `{total_sales - total_comm}` ETB"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data="v_history"))
    
    bot.edit_message_text(report_msg, v_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "v_wallet")
def vendor_wallet_callback(call):
    v_id = str(call.message.chat.id)
    db = load_data()
    vendor = db['vendors_list'].get(v_id)
    
    # ባላንስ (አድሚኑ የሞላለት ቀሪ ብር)
    balance = vendor.get('deposit_balance', 0)
    
    # ታሪክ (የመጨረሻ 5 ሽያጮች)
    history = vendor.get('transactions', [])[-5:]
    history.reverse()

    text = (f"💰 **የድርጅት ቅድመ-ክፍያ ዋሌት (Pre-paid)**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 ቀሪ የሽያጭ ፈቃድ፦ `{balance}` ETB\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 **የመጨረሻ ሽያጮች፦**\n")
    
    if not history:
        text += "_እስካሁን ምንም ሽያጭ አልተመዘገበም_"
    else:
        for txn in history:
            text += f"• {txn['date']} | `-{txn['amount']}` | {txn['desc']}\n"

    # ባላንስ ካነሰ ማስጠንቀቂያ
    if balance < 500:
        text += f"\n⚠️ **ማሳሰቢያ፦** ቀሪ ሂሳብዎ ዝቅተኛ ነው። እባክዎ ለአድሚኑ ያሳውቁ።"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 አድስ", callback_data="v_wallet"))
    markup.add(types.InlineKeyboardButton("⬅️ ተመለስ", callback_data="v_dashboard"))
    
    bot.edit_message_text(text, v_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")



@bot.message_handler(content_types=['location'])
def handle_vendor_location(message):
    v_id = str(message.chat.id)
    db = load_data()
    
    if v_id in db['vendors_list']:
        db['vendors_list'][v_id]['location'] = {
            "lat": message.location.latitude,
            "lon": message.location.longitude
        }
        save_data(db)
        
        msg, markup = get_vendor_main_menu(v_id)
        bot.send_message(v_id, "✅ የድርጅቱ ቦታ በትክክል ተመዝግቧል!", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(v_id, msg, reply_markup=markup)






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

# ምድብ ከተመረጠ በኋላ ID መጠየቂያ
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_cat_for_vendor:"))
def get_id_after_cat(call):
    cat_name = call.data.split(":")
    msg = bot.send_message(call.message.chat.id, f"🆔 የ[{cat_name}] ባለቤት Telegram ID ያስገቡ፦")
    bot.register_next_step_handler(msg, lambda m: process_vendor_id(m, cat_name))

def process_vendor_id(message, cat_name):
    v_id = message.text.strip()
    if not v_id.isdigit():
        msg = bot.send_message(message.chat.id, "⚠️ ስህተት፡ ID ቁጥር መሆን አለበት። ድጋሚ ያስገቡ፦")
        return bot.register_next_step_handler(msg, lambda m: process_vendor_id(m, cat_name))
    
    msg = bot.send_message(message.chat.id, "🏢 የድርጅቱን ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, lambda m: save_new_vendor(m, v_id, cat_name))

def save_new_vendor(message, v_id, cat_name):
    v_name = message.text.strip()
    db = load_data()
    
    if 'vendors_list' not in db: db['vendors_list'] = {}
    
    db['vendors_list'][v_id] = {
        "name": v_name,
        "category": cat_name, # አሁን ምድቡ እዚህ ይገባል
        "deposit_balance": 0,
        "items": {},
        "is_active": True
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ ድርጅት '{v_name}' በምድብ '{cat_name}' ተመዝግቧል!")




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
        # 1. ጽሁፉን በኮማ መከፋፈል
        parts = message.text.split(",")
        
        # 2. በትክክል 3 ቁጥሮች መኖራቸውን ማረጋገጥ
        if len(parts) != 3:
            raise ValueError("ሶስት ቁጥሮች ያስፈልጋሉ")
            
        # 3. እያንዳንዱን ክፍል ነጥሎ ማውጣትና ወደ ቁጥር መቀየር (strip እዚህ ጋር ነው የሚሰራው)
        v_comm = float(parts.strip()) 
        r_comm = float(parts.strip()) 
        c_comm = float(parts.strip()) 
        
        db = load_data()
        
        # 4. የ Key ስሞችን አንድ አይነት ማድረግ (ከ process_order_settlement ጋር እንዲሄድ)
        db['settings']['vendor_commission_p'] = v_comm
        db['settings']['rider_commission_p'] = r_comm
        db['settings']['customer_service_fee'] = c_comm
        
        save_data(db)
        
        response = (
            f"✅ **ኮሚሽን በተሳካ ሁኔታ ተቀይሯል!**\n\n"
            f"🏢 ድርጅት (Vendor)፦ `{v_comm}%` ከእቃ ዋጋ\n"
            f"🛵 ራይደር (Rider)፦ `{r_comm}%` ከማድረሻ ክፍያ\n"
            f"👤 ደንበኛ (Service Fee)፦ `{c_comm}` ብር"
        )
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
        
    except (ValueError, IndexError):
        msg = bot.send_message(
            message.chat.id, 
            "⚠️ **ስህተት፦** እባክዎ በትክክል ያስገቡ።\n"
            "ለምሳሌ፦ `5, 10, 20` (ኮማ መጠቀሙን አይርሱ)"
        )
        # ስህተት ከሰሩ ደግመው እንዲሞክሩ እድል ይሰጣል
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
