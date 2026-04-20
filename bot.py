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




def save_commissions(message):
    try:
        # አድሚን መሆኑን ማረጋገጥ
        if message.from_user.id not in ADMIN_IDS:
            return

        # 1. ጽሁፉን በኮማ መከፋፈል እና እያንዳንዱን ቁጥር ማጽዳት (Strip)
        # በላክኸው ኮድ ላይ የነበረው ስህተት እዚህ ጋር ነው የተስተካከለው
        raw_parts = message.text.split(",")
        
        if len(raw_parts) != 3:
            msg = bot.send_message(message.chat.id, "⚠️ ስህተት፦ እባክዎ 3 ቁጥሮችን በኮማ በመለየት ያስገቡ (ለምሳሌ፦ 5, 10, 20)")
            bot.register_next_step_handler(msg, save_commissions)
            return

        # እያንዳንዱን ቁጥር ነጥሎ ማውጣት
        v_comm = float(raw_parts.strip()) 
        r_comm = float(raw_parts.strip()) 
        c_comm = float(raw_parts.strip()) 
        
        db = load_data()
        if 'settings' not in db: db['settings'] = {}
        
        db['settings']['vendor_commission_p'] = v_comm
        db['settings']['rider_commission_p'] = r_comm
        db['settings']['customer_service_fee'] = c_comm
        
        save_data(db)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu"))
        
        response = (
            f"✅ **ኮሚሽን በትክክል ተቀምጧል!**\n\n"
            f"🏢 የድርጅት፦ `{v_comm}%` \n"
            f"🛵 የራይደር፦ `{r_comm}%` \n"
            f"👤 ሰርቪስ ፊ፦ `{c_comm} ETB`"
        )
        bot.send_message(message.chat.id, response, reply_markup=markup, parse_mode="Markdown")
        
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ቁጥር ብቻ ያስገቡ (ለምሳሌ፦ 2, 10, 5)")
        bot.register_next_step_handler(msg, save_commissions)
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "❌ ችግር አጋጥሟል።")



def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True






def get_admin_dashboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)

    # 1. ኦፕሬሽን (Daily Tasks)
    btn_live_orders = types.InlineKeyboardButton("📋 የቀጥታ ትዕዛዞች", callback_data="admin_live_orders")
    btn_broadcast = types.InlineKeyboardButton("📢 ማስታወቂያ ላክ", callback_data="admin_broadcast")

    # 2. ሪፖርት እና ፋይናንስ (የተቀናጀ)
    # ክትትል፣ ትርፍ እና ሪፖርት እዚህ ውስጥ ይጠቃለላሉ
    btn_reports = types.InlineKeyboardButton("📊 አጠቃላይ ሪፖርትና ክትትል", callback_data="admin_full_stats")
    btn_fund = types.InlineKeyboardButton("💳 ብር መሙያ (Top-up)", callback_data="admin_add_funds")

    # 3. አስተዳደር (Management)
    btn_user_mgmt = types.InlineKeyboardButton("👥 ድርጅትና ራይደር ማስተዳደሪያ", callback_data="admin_list_vendors")
    btn_cat_mgmt = types.InlineKeyboardButton("📁 የምድቦች ማዕከል", callback_data="admin_view_categories")

    # 4. ሲስተም (Settings)
    btn_set_commission = types.InlineKeyboardButton("⚙️ ኮሚሽን", callback_data="admin_set_commission")
    btn_lock = types.InlineKeyboardButton("🔒/🔓 ሲስተም ዝጋ", callback_data="admin_system_lock")
    btn_system_reset = types.InlineKeyboardButton("🗑 Reset System", callback_data="admin_system_reset")

    # በተኖቹን መጨመር
    markup.add(btn_live_orders)
    markup.add(btn_reports, btn_fund)
    markup.add(btn_user_mgmt)
    markup.add(btn_cat_mgmt)
    markup.add(btn_broadcast)
    markup.add(btn_set_commission, btn_lock)
    markup.add(btn_system_reset)

    return markup



def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add( "📊 ሪፖርት" )
    return markup


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # ዳታቤዝ ውስጥ ተጠቃሚውን መመዝገብ (ለብሮድካስት እንዲረዳን)
    db = load_data()
    if 'user_list' not in db: db['user_list'] = []
    if user_id not in db['user_list']:
        db['user_list'].append(user_id)
        save_data(db)

    if user_id in ADMIN_IDS:
        markup = get_admin_dashboard(user_id)
        bot.send_message(
            message.chat.id, 
            "👋 ሰላም ጌታዬ! እንኳን ወደ **BDF Delivery** መቆጣጠሪያ መጡ።\nከታች ያሉትን አማራጮች ተጠቅመው ሲስተሙን ያስተዳድሩ።",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        # ለደንበኞች የሚታይ ገጽ (ለጊዜው)
        customer_markup = types.InlineKeyboardMarkup()
        customer_markup.add(types.InlineKeyboardButton("🛍 እቃዎችን ማየት", callback_data="customer_view_items"))
        bot.send_message(
            message.chat.id, 
            "እንኳን ወደ **BDF Delivery** በደህና መጡ! 🛵\nእቃ ለማዘዝ ከታች ያለውን በተን ይጫኑ።",
            reply_markup=customer_markup,
            parse_mode="Markdown"
        )

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







@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_accounts")
def account_hub(call):
    try:
        # 1. የአድሚን ጥበቃ (Security Check)
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!", show_alert=True)

        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # --- ድርጅት አስተዳደር ---
        btn_v_list = types.InlineKeyboardButton("🏢 የድርጅቶች ዝርዝር", callback_data="admin_list_vendors")
        btn_v_add = types.InlineKeyboardButton("➕ አዲስ ድርጅት", callback_data="admin_add_vendor")
        
        # --- ራይደር አስተዳደር ---
        btn_r_list = types.InlineKeyboardButton("🛵 የራይደሮች ዝርዝር", callback_data="admin_rider_status")
        btn_r_add = types.InlineKeyboardButton("➕ አዲስ ራይደር", callback_data="admin_add_rider")
        
        # --- መመለሻ ---
        btn_back = types.InlineKeyboardButton("🔙 ወደ ዋናው ሜኑ", callback_data="admin_main_menu")
        
        # በተኖቹን በሥርዓት መደርደር
        markup.add(btn_v_list, btn_v_add)
        markup.add(btn_r_list, btn_r_add)
        markup.add(btn_back)
        
        text = "👥 **የአካውንቶች ማስተዳደሪያ ማዕከል**\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "እዚህ ገጽ ላይ የሲስተሙን ተዋናዮች (ድርጅቶች እና ራይደሮች) ማስተዳደር ይችላሉ።\n\n"
        text += "ምን ማድረግ ይፈልጋሉ?"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"❌ Account Hub Error: {e}")
        bot.answer_callback_query(call.id, "❌ ገጹን መክፈት አልተቻለም።", show_alert=True)




@bot.callback_query_handler(func=lambda call: call.data == "admin_full_stats")
def show_combined_metrics(call):
    try:
        # 1. የአድሚን ጥበቃ
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "🚫 ፍቃድ የለዎትም!", show_alert=True)

        db = load_data()
        vendors = db.get('vendors_list', {})
        riders = db.get('riders_list', {})
        
        # ስታትስቲክስ ከሌለ ባዶ ዳታ እንዳይሰጠን
        stats = db.get('stats', {
            'total_vendor_comm': 0.0, 
            'total_rider_comm': 0.0, 
            'total_customer_comm': 0.0, 
            'total_orders': 0
        })
        
        # የሂሳብ ስሌቶች (Data Type Casting ተጨምሮበታል)
        total_v_bal = sum(float(v.get('deposit_balance', 0)) for v in vendors.values())
        total_r_bal = sum(float(r.get('wallet', 0)) for r in riders.values())
        
        v_profit = float(stats.get('total_vendor_comm', 0))
        r_profit = float(stats.get('total_rider_comm', 0))
        c_profit = float(stats.get('total_customer_comm', 0))
        net_profit = v_profit + r_profit + c_profit
        
        online_riders = sum(1 for r in riders.values() if r.get('status') == 'online')

        # ሪፖርት ዝግጅት
        report = "📊 **አጠቃላይ የሲስተም ክትትልና ሪፖርት**\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        report += "💰 **የፋይናንስ ሁኔታ፦**\n"
        report += f"💵 **የተጣራ ትርፍ፦** `{net_profit:,.2f} ETB`\n"
        report += f"🏢 ድርጅቶች ዲፖዚት፦ `{total_v_bal:,.2f} ETB`\n"
        report += f"🛵 ራይደሮች ዋሌት፦ `{total_r_bal:,.2f} ETB`\n\n"

        report += "📈 **የስራ እንቅስቃሴ፦**\n"
        report += f"📦 የተጠናቀቁ ትዕዛዞች፦ `{int(stats.get('total_orders', 0))}`\n"
        report += f"🟢 አሁን ኦንላይን ያሉ ራይደሮች፦ `{online_riders}`\n"
        report += "━━━━━━━━━━━━━━━━━━━━"

        # በተኖች
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_v_list = types.InlineKeyboardButton("🏢 የድርጅቶች ዝርዝር", callback_data="admin_list_vendors")
        btn_r_list = types.InlineKeyboardButton("🛵 የራይደሮች ሁኔታ", callback_data="admin_rider_status")
        btn_back = types.InlineKeyboardButton("🔙 ወደ ዳሽቦርድ", callback_data="admin_main_menu")
        
        markup.add(btn_v_list, btn_r_list)
        markup.add(btn_back)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=report,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

    except Exception as e:
        print(f"❌ Metrics Error: {e}")
        bot.answer_callback_query(call.id, "❌ ሪፖርቱን ማመንጨት አልተቻለም።", show_alert=True)







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
