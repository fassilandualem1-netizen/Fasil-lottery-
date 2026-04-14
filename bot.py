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

# --- 2. ዳታቤዝ ተግባራት ---
def load_data():
    try:
        # 'r' ሳይሆን 'redis' መሆን አለበት
        raw = redis.get("beu_delivery_db")
        if raw: 
            return json.loads(raw)
        
        # ዳታቤዙ ባዶ ከሆነ መጀመሪያ የሚፈጠሩ ነገሮች
        initial_data = {
            "vendors": {}, 
            "vendors_list": {}, # ይህ ለባለሱቆች መለያ ያስፈልጋል
            "orders": {}, 
            "items": {}, 
            "pending": {}, 
            "users": {}, 
            "total_profit": 0, 
            "settings": {"base_delivery": 50}
        }
        return initial_data
    except Exception as e:
        print(f"❌ Database Load Error: {e}")
        return {"vendors": {}, "vendors_list": {}, "orders": {}, "items": {}, "pending": {}, "users": {}, "total_profit": 0, "settings": {"base_delivery": 50}}

def save_data(data):
    try:
        # 'r' ሳይሆን 'redis' መሆን አለበት
        redis.set("beu_delivery_db", json.dumps(data))
    except Exception as e:
        print(f"❌ Database Save Error: {e}")


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def kb_admin_main():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🏬 አጋር ድርጅቶች", "📦 ትዕዛዞች", "📊 ሪፖርት", "👤 የኔ ፕሮፋይል", "⚙️ ሲስተም")
    return kb

def kb_vendor_main():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ እቃ ጨምር", "📦 የመጡ ትዕዛዞች", "📉 የኔ ሽያጭ", "⚙️ የሱቅ ሁኔታ")
    return kb

def kb_customer_main():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🏪 ሱቆችን ተመልከት", "🛍 የኔ ትዕዛዞች")
    kb.add("👤 ፕሮፋይል", "📞 እርዳታ")
    return kb

@bot.message_handler(func=lambda m: m.text == "🏪 ሱቆችን ተመልከት")
def show_vendors(message):
    db = load_data()
    vendors = db.get("vendors_list", {})
    
    if not vendors:
        return bot.send_message(message.chat.id, "ለጊዜው ምንም የተመዘገቡ ሱቆች የሉም።")

    markup = types.InlineKeyboardMarkup(row_width=2)
    for vid, vdata in vendors.items():
        # ሱቁ ክፍት መሆኑን ቼክ ማድረግ (አማራጭ)
        status = vdata.get("shop_status", "Open 🟢")
        if "Open" in status:
            markup.add(types.InlineKeyboardButton(f"🏬 {vdata['name']}", callback_data=f"v_show_{vid}"))
    
    bot.send_message(message.chat.id, "🛒 **የመረጡትን ሱቅ ይክፈቱ፦**", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        uid_str = str(user_id) # ለዳታቤዝ ፍለጋ እንዲመች
        db = load_data() 

        # 1. አድሚን መሆኑን መለየት (ADMIN_IDS ዝርዝር ውስጥ ካለ)
        if user_id in ADMIN_IDS:
            return bot.send_message(user_id, "👑 እንኳን ደህና መጡ ጌታዬ (አድሚን)!", 
                                    reply_markup=kb_admin_main())

        # 2. ባለሱቅ (Vendor) መሆኑን መለየት (በመዘገብከው ID መሠረት)
        # እዚህ ጋር 'vendors_list' መሆኑን እርግጠኛ ሁን (ከላይ ምዝገባው ላይ የተጠቀምነው ስም ነው)
        vendors = db.get("vendors_list", {})
        if uid_str in vendors:
            v_name = vendors[uid_str]["name"]
            return bot.send_message(user_id, f"🏬 ሰላም {v_name} (ባለሱቅ)!\nዛሬ ምን ማስተካከል ይፈልጋሉ?", 
                                    reply_markup=kb_vendor_main())

        # 3. ደንበኛ (Customer) - ከላይ ያሉት ካልሆኑ እንደ ደንበኛ ይታያል
        bot.send_message(user_id, "👋 እንኳን ወደ BDF በደህና መጡ! የሚፈልጉትን ሱቅ መርጠው ማዘዝ ይችላሉ።", 
                         reply_markup=kb_customer_main())
        
        # አዲስ ደንበኛ ከሆነ መመዝገብ
        if "users" not in db: db["users"] = {}
        if uid_str not in db["users"]:
            db["users"][uid_str] = {"name": message.from_user.first_name, "joined_at": time.time()}
            save_data(db)

    except Exception as e:
        print(f"❌ Start Error: {e}")
        bot.send_message(message.chat.id, "⚠️ በሲስተሙ ላይ ትንሽ ችግር አጋጥሟል፣ እባክዎ ጥቂት ቆይተው ይሞክሩ።")

@bot.message_handler(func=lambda m: m.text == "⚙️ ሲስተም")
def system_settings(message):
    if message.from_user.id not in ADMIN_IDS: return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🛵 የማድረሻ ዋጋ ቀይር", callback_data="set_del_fee"),
        types.InlineKeyboardButton("📈 የኮሚሽን % ቀይር", callback_data="set_comm_rate")
    )
    bot.send_message(message.chat.id, "የሲስተም ማስተካከያ፦", reply_markup=markup)


# ሻጭ እቃ ሲጨምር ለAdmin የሚመጣ ማሳወቂያ
def notify_admin_new_item(item_id, item_data):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ፍቀድ", callback_data=f"approve_{item_id}"),
        types.InlineKeyboardButton("❌ አትፍቀድ", callback_data=f"reject_{item_id}")
    )
    for admin in ADMIN_IDS:
        bot.send_photo(admin, item_data['photo'], 
                       caption=f"🔔 አዲስ ዕቃ ቀርቧል\nስም፦ {item_data['name']}\nዋጋ፦ {item_data['price']}\nሱቅ፦ {item_data['v_name']}", 
                       reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📦 የመጡ ትዕዛዞች")
def vendor_active_orders(message):
    db = load_data()
    vid = str(message.from_user.id)
    
    # የዚህን ሱቅ ያልተጠናቀቁ ትዕዛዞች መፈለግ
    my_orders = [o for o in db["orders"].values() if str(o['vid']) == vid and o['status'] == "Pending"]
    
    if not my_orders:
        return bot.send_message(message.chat.id, "🙌 በአሁኑ ሰዓት አዲስ የመጣ ትዕዛዝ የለም።")
    
    for order in my_orders:
        oid = order.get('id', 'N/A')
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("👨‍🍳 Ready", callback_data=f"vready_{oid}"))
        
        bot.send_message(message.chat.id, f"📦 ትዕዛዝ #{oid}\n🛍 እቃ፦ {order['item_name']}\n💰 ዋጋ፦ {order['item_price']} ETB", reply_markup=markup)

# 1. ባለሱቁ እቃ መጨመር ሲጀምር
@bot.message_handler(func=lambda m: m.text == "➕ እቃ ጨምር")
def vendor_add_item(message):
    db = load_data()
    uid = str(message.from_user.id)
    if uid not in db.get("vendors_list", {}):
        bot.reply_to(message, "❌ ይቅርታ፣ እቃ ለመጨመር የባለሱቅ ፍቃድ ያስፈልገዎታል።")
        return
    
    msg = bot.send_message(message.chat.id, "📸 በመጀመሪያ የእቃውን ፎቶ ይላኩ፦")
    bot.register_next_step_handler(msg, process_item_photo)

def process_item_photo(message):
    if not message.photo:
        msg = bot.send_message(message.chat.id, "❌ እባክዎ የእቃውን ፎቶ ይላኩ!")
        bot.register_next_step_handler(msg, process_item_photo)
        return
    
    photo_id = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "📝 የእቃውን ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, process_item_name, photo_id)

def process_item_name(message, photo_id):
    item_name = message.text
    msg = bot.send_message(message.chat.id, f"📝 ስለ '{item_name}' አጭር መግለጫ (Description) ይጻፉ፦")
    bot.register_next_step_handler(msg, process_item_description, photo_id, item_name)

def process_item_description(message, photo_id, item_name):
    description = message.text
    msg = bot.send_message(message.chat.id, f"💰 የ '{item_name}' ዋጋ ስንት ነው? (ቁጥር ብቻ ያስገቡ)፦")
    bot.register_next_step_handler(msg, process_item_price, photo_id, item_name, description)

def process_item_price(message, photo_id, item_name, description):
    try:
        price = float(message.text)
        db = load_data()
        vendor_info = db["vendors_list"][str(message.from_user.id)]
        
        # ID መፍጠር
        item_id = str(len(db.get("items", {})) + len(db.get("pending", {})) + 1)
        
        pending_item = {
            "id": item_id,
            "vid": str(message.from_user.id),
            "v_name": vendor_info["name"],
            "name": item_name,
            "description": description,
            "price": price,
            "photo": photo_id,
            "status": "Pending"
        }
        
        if "pending" not in db: db["pending"] = {}
        db["pending"][item_id] = pending_item
        save_data(db)
        
        bot.send_message(message.chat.id, "✅ እቃው ተመዝግቧል! አድሚን ሲያጸድቀው ለደንበኞች ይታያል።")
        
        # ለአድሚን ማሳወቂያ መላክ
        notify_admin_new_item(item_id, pending_item)
        
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ!")
        bot.register_next_step_handler(msg, process_item_price, photo_id, item_name, description)
    except Exception as e:
        print(f"❌ Error in process_item_price: {e}")
        bot.send_message(message.chat.id, "⚠️ ችግር አጋጥሟል፣ እባክዎ ደግመው ይሞክሩ።")

# ሻጭ እቃ ሲጨምር ለAdmin የሚመጣ ማሳወቂያ
def notify_admin_new_item(item_id, item_data):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ፍቀድ", callback_data=f"approve_{item_id}"),
        types.InlineKeyboardButton("❌ አትፍቀድ", callback_data=f"reject_{item_id}")
    )
    for admin in ADMIN_IDS:
        try:
            bot.send_photo(admin, item_data['photo'], 
                           caption=f"🔔 **አዲስ ዕቃ ቀርቧል**\n\n"
                                   f"📦 ስም፦ {item_data['name']}\n"
                                   f"💰 ዋጋ፦ {item_data['price']} ETB\n"
                                   f"📝 መግለጫ፦ {item_data.get('description', 'የለም')}\n"
                                   f"🏬 ሱቅ፦ {item_data['v_name']}", 
                           reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            print(f"❌ ለአድሚን {admin} መላክ አልተቻለም: {e}")


@bot.message_handler(func=lambda m: m.text == "⚙️ የሱቅ ሁኔታ")
def vendor_status_toggle(message):
    db = load_data()
    vid = str(message.from_user.id)
    
    # የሱቁን አሁናዊ ሁኔታ ማግኘት (ካለ ካልሆነ Open ነው)
    current_status = db["vendors_list"][vid].get("shop_status", "Open 🟢")
    
    markup = types.InlineKeyboardMarkup()
    new_status = "Closed 🔴" if current_status == "Open 🟢" else "Open 🟢"
    markup.add(types.InlineKeyboardButton(f"ወደ {new_status} ቀይር", callback_data=f"toggle_v_{vid}"))
    
    bot.send_message(message.chat.id, f"🏬 ሱቅዎ በአሁኑ ሰዓት፦ **{current_status}** ነው", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🛍 የኔ ትዕዛዞች")
def customer_orders(message):
    db = load_data()
    uid = message.from_user.id
    
    # የዚን ደንበኛ ትዕዛዞች መፈለግ
    my_orders = [o for o in db["orders"].values() if o['customer_id'] == uid]
    
    if not my_orders:
        return bot.send_message(message.chat.id, "እስካሁን ያዘዙት እቃ የለም።")

    text = "📦 **የእርስዎ ትዕዛዞች፦**\n\n"
    for o in my_orders[-5:]: # የመጨረሻዎቹን 5 ብቻ
        status_icon = "⏳" if o['status'] == "Pending" else "🛵" if "way" in o['status'] else "✅"
        text += f"{status_icon} #{o['id']} - {o['item_name']} ({o['status']})\n"
    
    bot.send_message(message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data.startswith("conf_order_"))
def confirm_order_final(call):
    oid = call.data.split("_")
    db = load_data()
    order = db["orders"].get(oid)
    
    if not order:
        return bot.answer_callback_query(call.id, "❌ ስህተት፦ ትዕዛዙ አልተገኘም!")

    # የትዕዛዙን ሁኔታ መቀየር
    db["orders"][oid]["status"] = "Pending"
    save_data(db)

    # 1. ለደንበኛው ማሳወቅ
    bot.edit_message_text("✅ ትዕዛዝዎ ተቀባይነት አግኝቷል! ባለሱቁ እቃውን ሲያዘጋጅ እና ሾፌር ሲረከበው እናሳውቅዎታለን።", 
                          call.message.chat.id, call.message.message_id)

    # 2. ለባለሱቁ (Vendor) ማሳወቅ (እቃ እንዲያዘጋጅ)
    notify_vendor_new_order(oid, order)

    # 3. ለአድሚኖች (Admins) ማሳወቅ (ዝግጁ እንዲሆኑ)
    # ማሳሰቢያ፦ ባለሱቁ "Ready" ሲል ነው ሾፌሩ እንዲሄድ የምናደርገው፣ ግን አሁኑኑ እንዲያውቁት ማድረግ ጥሩ ነው።
    for admin_id in ADMIN_IDS:
        bot.send_message(admin_id, f"🔔 **አዲስ ትዕዛዝ ተመዝግቧል!**\n🆔 ID: #{oid}\n🛍 እቃ: {order['item_name']}\n🏬 ሱቅ: {order.get('v_name', 'የተመዘገበ ሱቅ')}\n\nባለሱቁ 'Ready' እስኪል ይጠብቁ።")


@bot.callback_query_handler(func=lambda call: call.data == "v_manage_items")
def manage_items(call):
    db = load_data()
    vid = str(call.from_user.id)
    # የዚህ ባለሱቅ እቃዎችን መፈለግ
    my_items = [i for i in db["items"].values() if str(i['vid']) == vid]
    
    if not my_items:
        return bot.answer_callback_query(call.id, "እስካሁን የጨመሩት እቃ የለም።")
    
    markup = types.InlineKeyboardMarkup()
    for item in my_items:
        status = "✅" if item.get('available', True) else "❌"
        markup.add(types.InlineKeyboardButton(f"{status} {item['name']} - {item['price']} ETB", callback_data=f"toggle_item_{item['id']}"))
    
    bot.send_message(call.message.chat.id, "የእቃዎ ዝርዝር (ለመቀየር ይጫኑ)፦", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_v_"))
def process_status_toggle(call):
    vid = call.data.split("_")
    db = load_data()
    
    current = db["vendors_list"][vid].get("shop_status", "Open 🟢")
    db["vendors_list"][vid]["shop_status"] = "Closed 🔴" if current == "Open 🟢" else "Open 🟢"
    save_data(db)
    
    bot.edit_message_text(f"✅ የሱቅዎ ሁኔታ ወደ {db['vendors_list'][vid]['shop_status']} ተቀይሯል።", call.message.chat.id, call.message.message_id)





@bot.message_handler(func=lambda m: m.text == "📉 የኔ ሽያጭ")
def vendor_sales_report(message):
    db = load_data()
    vid = str(message.from_user.id)
    
    # ተጠቃሚው በባለሱቅ ዝርዝር ውስጥ መኖሩን ማረጋገጥ
    if vid not in db.get("vendors_list", {}):
        return bot.send_message(message.chat.id, "❌ ይህ መረጃ ለእርስዎ አልተፈቀደም።")
    
    # የዚህን ሱቅ የተጠናቀቁ ትዕዛዞች ብቻ መለየት
    delivered_orders = [o for o in db["orders"].values() if str(o.get('vid')) == vid and o['status'] == "Delivered"]
    
    total_sales = sum([o['item_price'] for o in delivered_orders])
    total_commission = sum([o.get('commission', 0) for o in delivered_orders])
    net_earnings = total_sales - total_commission
    
    report_text = (
        f"📉 **የሽያጭ ሪፖርት፦ {db['vendors_list'][vid]['name']}**\n"
        f"--------------------------\n"
        f"✅ የተጠናቀቁ ትዕዛዞች፦ {len(delivered_orders)}\n"
        f"💰 ጠቅላላ ሽያጭ፦ {total_sales} ETB\n"
        f"📈 የተከፈለ ኮሚሽን፦ {total_commission} ETB\n"
        f"--------------------------\n"
        f"💵 **የእርስዎ የተጣራ ገቢ፦ {net_earnings} ETB**\n\n"
        f"💡 *ማሳሰቢያ፦ ይህ ሂሳብ በአድሚኑ በኩል ሂሳብ እስኪወራረድ ድረስ ቦቱ ውስጥ የሚቆይ ነው።*"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📜 ያለፉ ትዕዛዞች ዝርዝር", callback_data=f"v_history_{vid}"))
    
    bot.send_message(message.chat.id, report_text, reply_markup=markup, parse_mode="Markdown")


# --- አዲሱ የሱቅ መመዝገቢያ (መስመር 522 አካባቢ መተካት ያለበት) ---

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_v")
def start_add_v(call):
    msg = bot.send_message(call.message.chat.id, "📝 ለመመዝገብ የፈለጉትን የሱቅ ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, process_vendor_name_new)

def process_vendor_name_new(message):
    v_name = message.text
    msg = bot.send_message(message.chat.id, f"🔢 የ '{v_name}' ባለቤት የቴሌግራም ID ቁጥር ያስገቡ፦\n(IDውን ለማግኘት @userinfobot መጠቀም ይቻላል)")
    bot.register_next_step_handler(msg, process_vendor_id_new, v_name)

def process_vendor_id_new(message, v_name):
    v_id = message.text.strip()
    if not v_id.isdigit():
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ ID ቁጥር ብቻ መሆን አለበት። እባክዎ እንደገና ያስገቡ፦")
        bot.register_next_step_handler(msg, process_vendor_id_new, v_name)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📍 የሱቁን ሎኬሽን ላክ", request_location=True))
    msg = bot.send_message(message.chat.id, f"📍 ለ '{v_name}' ሎኬሽን ይላኩ (ወይም ዝለል/skip ይበሉ)፦", reply_markup=markup)
    bot.register_next_step_handler(msg, finalize_vendor_reg_new, v_name, v_id)

def finalize_vendor_reg_new(message, v_name, v_id):
    db = load_data()
    lat, lon = 0, 0
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude

    if "vendors_list" not in db: db["vendors_list"] = {}
    
    db["vendors_list"][str(v_id)] = {
        "name": v_name,
        "lat": lat,
        "lon": lon,
        "shop_status": "Open 🟢",
        "balance": 0
    }
    save_data(db)
    bot.send_message(message.chat.id, f"✅ ሱቅ '{v_name}' በ ID {v_id} ተመዝግቧል!", reply_markup=kb_admin_main())


def notify_vendor_new_order(order_id, order_data):
    db = load_data()
    # የባለሱቁን የቴሌግራም ID መፈለግ
    vendor_id = None
    for vid, vdata in db.get("vendors_list", {}).items():
        if str(order_data['vid']) == str(vid): # vid በምዝገባ ወቅት የተሰጠው ነው
            vendor_id = vid
            break
            
    if vendor_id:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("👨‍🍳 እቃው ተዘጋጅቷል (Ready)", callback_data=f"vready_{order_id}"))
        
        text = (
            f"🔔 **አዲስ ትዕዛዝ መጥቷል!**\n"
            f"--------------------------\n"
            f"🆔 ትዕዛዝ ቁጥር፦ #{order_id}\n"
            f"🛍 እቃ፦ {order_data['item_name']}\n"
            f"🔢 ብዛት፦ {order_data.get('quantity', 1)}\n"
            f"💰 ዋጋ፦ {order_data['item_price']} ETB\n"
            f"--------------------------\n"
            f"እባክዎ እቃውን አዘጋጅተው ሲጨርሱ 'Ready' የሚለውን ይጫኑ።"
        )
        bot.send_message(vendor_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_history_"))
def vendor_order_history(call):
    vid = call.data.split("_")
    db = load_data()
    
    my_history = [o for o in db["orders"].values() if str(o.get('vid')) == vid and o['status'] == "Delivered"]
    
    if not my_history:
        return bot.answer_callback_query(call.id, "እስካሁን የተጠናቀቀ ትዕዛዝ የለም።", show_alert=True)
    
    history_text = "📜 **የመጨረሻዎቹ ሽያጮች፦**\n\n"
    # የመጨረሻዎቹን 10 ሽያጮች ብቻ ማሳየት
    for o in my_history[-10:]:
        history_text += f"🔹 {o['item_name']} - {o['item_price']} ETB (ID: #{o.get('id', '?')})\n"
        
    bot.send_message(call.message.chat.id, history_text)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_show_"))
def show_vendor_categories(call):
    vid = call.data.split("_")
    db = load_data()
    v_name = db["vendors_list"][vid]["name"]
    
    # በዚ ሱቅ ውስጥ ያሉ እቃዎችን ምድብ መለየት
    items = [i for i in db.get("items", {}).values() if str(i['vid']) == vid]
    categories = list(set([i.get('category', 'ሌሎች') for i in items]))

    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        markup.add(types.InlineKeyboardButton(f"📁 {cat}", callback_data=f"cat_{vid}_{cat}"))
    
    markup.add(types.InlineKeyboardButton("⬅️ ወደ ሱቆች ተመለስ", callback_data="back_to_vendors"))
    
    bot.edit_message_text(f"🏬 **የ {v_name} ማውጫ**\nእባክዎ የምድብ ምርጫዎን ያስገቡ፦", 
                          call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def start_order_process(call):
    item_id = call.data.split("_")
    
    # ሎኬሽን ለመጠየቅ ቁልፍ ማዘጋጀት
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📍 ያለሁበትን ቦታ ላክ (Share Location)", request_location=True))
    
    msg = bot.send_message(call.message.chat.id, 
                           "ትዕዛዝዎን ለማድረስ እንዲረዳን እባክዎ ያለሁበትን ቦታ ላክ የሚለውን ቁልፍ ይጫኑ፦", 
                           reply_markup=markup)
    # የሚቀጥለው እርምጃ ሎኬሽን መቀበል ነው
    bot.register_next_step_handler(msg, process_location, item_id)

def process_location(message, item_id):
    if not message.location:
        msg = bot.send_message(message.chat.id, "❌ እባክዎ የሎኬሽን ቁልፉን ተጠቅመው ሎኬሽን ይላኩ!")
        bot.register_next_step_handler(msg, process_location, item_id)
        return

    user_loc = {"lat": message.location.latitude, "lon": message.location.longitude}
    
    # የኮንዶሚኒየም ስም መጠየቅ
    msg = bot.send_message(message.chat.id, "🏢 የኮንዶሚኒየሙን ስም ያስገቡ (ለምሳሌ፦ ጎተራ ኮንዶ)፦", 
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_condo_name, item_id, user_loc)

def process_condo_name(message, item_id, user_loc):
    condo_name = message.text
    msg = bot.send_message(message.chat.id, f"🧱 የ {condo_name} ብሎክ (Block) ቁጥር ስንት ነው?")
    bot.register_next_step_handler(msg, process_block_no, item_id, user_loc, condo_name)

def process_block_no(message, item_id, user_loc, condo_name):
    block_no = message.text
    msg = bot.send_message(message.chat.id, "🚪 የቤት ቁጥር (House No) ስንት ነው?")
    bot.register_next_step_handler(msg, process_house_no, item_id, user_loc, condo_name, block_no)



@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def show_category_items(call):
    _, vid, cat = call.data.split("_")
    db = load_data()
    
    # የዚን ምድብ እቃዎች ብቻ መለየት
    cat_items = [i for i in db["items"].values() if str(i['vid']) == vid and i.get('category') == cat]

    for item in cat_items:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"🛒 {item['price']} ETB - እዘዝ", callback_data=f"buy_{item['id']}"))
        
        caption = (
            f"🛍 **{item['name']}**\n\n"
            f"📝 {item.get('description', 'መግለጫ አልተሰጠም')}\n"
            f"💰 ዋጋ፦ {item['price']} ETB"
        )
        bot.send_photo(call.message.chat.id, item['photo'], caption=caption, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
def approve_item(call):
    iid = call.data.split("_")
    db = load_data()
    if iid in db["pending"]:
        item = db["pending"].pop(iid)
        db["items"][iid] = item
        save_data(db)
        bot.edit_message_caption("✅ ዕቃው ጸድቆ ለሽያጭ ቀርቧል!", call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("vready_"))
def vendor_order_ready(call):
    oid = call.data.split("_")
    db = load_data()
    order = db["orders"].get(oid)
    
    if not order: return

    # የትዕዛዙን ሁኔታ መቀየር
    db["orders"][oid]["status"] = "Ready for Pickup 📦"
    save_data(db)
    
    # ለባለሱቁ ማረጋገጫ
    bot.edit_message_text(f"✅ ለሾፌሩ መልዕክት ተልኳል! በቅርቡ መጥቶ ይረከብዎታል።", call.message.chat.id, call.message.message_id)
    
    # ለሁሉም አድሚኖች (ሾፌሮች) እቃው ዝግጁ መሆኑን ማሳወቅ
    for admin_id in ADMIN_IDS:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🛵 እቃውን ለመውሰድ ሂድ (Claim)", callback_data=f"claim_{oid}"))
        
        alert_text = (
            f"📦 **እቃ ተዘጋጅቷል! (Ready for Pickup)**\n"
            f"--------------------------\n"
            f"🏬 ሱቅ፦ {order.get('v_name', 'የተመዘገበ ሱቅ')}\n"
            f"🆔 ትዕዛዝ፦ #{oid}\n"
            f"🛍 እቃ፦ {order['item_name']}\n"
            f"📍 ሾፌር ተፈላጊ ነው!"
        )
        bot.send_message(admin_id, alert_text, reply_markup=markup, parse_mode="Markdown")




@bot.callback_query_handler(func=lambda call: call.data == "set_del_fee")
def change_delivery_fee(call):
    msg = bot.send_message(call.message.chat.id, "አዲሱን የማድረሻ መነሻ ዋጋ ያስገቡ (ለምሳሌ፦ 60)፦")
    bot.register_next_step_handler(msg, save_delivery_fee)

def save_delivery_fee(message):
    try:
        new_fee = int(message.text)
        db = load_data()
        db["settings"]["base_delivery"] = new_fee
        save_data(db)
        bot.send_message(message.chat.id, f"✅ የማድረሻ ዋጋ ወደ {new_fee} ተቀይሯል።")
    except:
        bot.send_message(message.chat.id, "❌ እባክዎ ቁጥር ብቻ ያስገቡ!")
@bot.message_handler(func=lambda m: m.text == "📊 ሪፖርት")
def general_report(message):
    if message.from_user.id not in ADMIN_IDS: return
    db = load_data()
    
    total_sales = sum([o['total'] for o in db['orders'].values() if o['status'] == 'Delivered'])
    total_profit = db.get("total_profit", 0)
    total_v = len(db['vendors'])
    
    text = (
        f"📊 **አጠቃላይ የንግድ ሪፖርት**\n\n"
        f"🏬 አጋር ሱቆች፦ {total_v}\n"
        f"📦 ጠቅላላ ሽያጭ፦ {total_sales} ETB\n"
        f"💰 የሲስተሙ ትርፍ፦ {total_profit} ETB\n"
        f"👥 ጠቅላላ ተጠቃሚዎች፦ {len(db['users'])}\n"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")





@bot.callback_query_handler(func=lambda call: call.data.startswith("ban_"))
def ban_user(call):
    uid = call.data.split("_")
    db = load_data()
    
    if "banned_users" not in db:
        db["banned_users"] = []
    
    if uid not in db["banned_users"]:
        db["banned_users"].append(uid)
        save_data(db)
        bot.send_message(call.message.chat.id, f"🚫 ደንበኛ (ID: {uid}) ታግዷል!")
        bot.send_message(uid, "❌ ከዚህ ቦት ታግደዋል። እባክዎ አድሚን ያነጋግሩ።")
    else:
        bot.answer_callback_query(call.id, "ይህ ተጠቃሚ ቀድሞውኑ ታግዷል።")

# ይህን ቼክ በ start_command ላይ መጨመር አለብን
# if str(message.from_user.id) in db.get("banned_users", []): return

@bot.message_handler(func=lambda m: m.text == "📢 ማስታወቂያ")
def broadcast_start(message):
    if message.from_user.id not in ADMIN_IDS: return
    msg = bot.send_message(message.chat.id, "ለተከታዮች የሚተላለፈውን መልዕክት ይጻፉ (ፎቶም መጨመር ይቻላል)፦")
    bot.register_next_step_handler(msg, send_broadcast_to_all)

def send_broadcast_to_all(message):
    db = load_data()
    users = db.get("users", {}).keys() # ሁሉንም ተጠቃሚዎች ለማግኘት
    count = 0
    
    for user_id in users:
        try:
            bot.copy_message(user_id, message.chat.id, message.message_id)
            count += 1
        except:
            continue # ቦቱን Block ላደረጉ ሰዎች እንዳይቋረጥ
            
    bot.send_message(message.chat.id, f"✅ ማስታወቂያው ለ {count} ደንበኞች ደርሷል።")

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_items_"))
def list_v_items_to_edit(call):
    vid = call.data.split("_")
    db = load_data()
    markup = types.InlineKeyboardMarkup()
    
    for iid, item in db["items"].items():
        if item["vid"] == vid:
            markup.add(types.InlineKeyboardButton(f"❌ ሰርዝ፦ {item['name']}", callback_data=f"del_item_{iid}"))
            
    bot.edit_message_text(f"የ {db['vendors'][vid]['name']} ዕቃዎች፦", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_item_"))
def delete_item(call):
    iid = call.data.split("_")
    db = load_data()
    if iid in db["items"]:
        del db["items"][iid]
        save_data(db)
        bot.answer_callback_query(call.id, "ዕቃው ተሰርዟል!")
        bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "📜 የታሪክ መዝገብ")
def view_order_history(message):
    if message.from_user.id not in ADMIN_IDS: return
    db = load_data()
    delivered_orders = [o for o in db["orders"].values() if o["status"] == "Delivered"]
    
    if not delivered_orders:
        return bot.send_message(message.chat.id, "እስካሁን የተጠናቀቁ ትዕዛዞች የሉም።")
    
    text = "📜 **የመጨረሻዎቹ 5 ትዕዛዞች፦**\n\n"
    for o in delivered_orders[-5:]: # የመጨረሻዎቹን አምስት ብቻ
        text += f"🔹 #{o.get('id', 'N/A')} - {o['item_name']} - {o['total']} ETB\n"
        
    bot.send_message(message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data.startswith("force_cancel_"))
def force_cancel(call):
    oid = call.data.split("_")
    db = load_data()
    if oid in db["orders"]:
        db["orders"][oid]["status"] = "Cancelled by Admin ⚠️"
        save_data(db)
        bot.send_message(db["orders"][oid]["customer_id"], "⚠️ ይቅርታ! ትዕዛዝዎ በአድሚን ተሰርዟል።")
        bot.edit_message_text(f"❌ ትዕዛዝ #{oid} ተሰርዟል።", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("claim_"))
def claim_order_logic(call):
    oid = call.data.split("_")
    db = load_data()
    order = db["orders"].get(oid)
    
    if not order: return
    
    # ቼክ፦ ሌላ ሰው ቀድሞ ወስዶት ከሆነ
    if "driver_id" in order:
        bot.answer_callback_query(call.id, "❌ ይቅርታ፣ ይህ ትዕዛዝ በሌላ አድሚን ተይዟል።", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return

    # ትዕዛዙን በስምህ መመዝገብ
    db["orders"][oid]["driver_id"] = call.from_user.id
    db["orders"][oid]["status"] = "On the way 🛵"
    save_data(db)
    
    bot.answer_callback_query(call.id, "✅ ትዕዛዙን ተረክበዋል!")
    
    # ለደንበኛው ሾፌር እንደመጣ ማሳወቅ
    bot.send_message(order["customer_id"], f"🛵 ሾፌር {call.from_user.first_name} ትዕዛዝዎን ተረክቧል፤ በቅርቡ ይደርሳል!")

@bot.message_handler(func=lambda m: m.text == "📓 የቀን ማጠቃለያ")
def daily_summary(message):
    if message.from_user.id not in ADMIN_IDS: return
    db = load_data()
    
    # የዛሬ የተጠናቀቁ ትዕዛዞችን ብቻ መለየት
    today_orders = [o for o in db["orders"].values() if o.get("driver_id") == message.from_user.id and o["status"] == "Delivered"]
    
    total_cash = sum([o["total"] for o in today_orders])
    total_commission = sum([o["commission"] for o in today_orders])
    
    report = (
        f"📅 **የዛሬ ስራ ማጠቃለያ**\n"
        f"--------------------------\n"
        f"✅ የደረሱ ትዕዛዞች፦ {len(today_orders)}\n"
        f"💵 ጠቅላላ የተሰበሰበ ገንዘብ፦ {total_cash} ETB\n"
        f"📈 ለሲስተም የሚገባ ኮሚሽን፦ {total_commission} ETB\n"
        f"🛵 የእርስዎ ትርፍ (Delivery)፦ {total_cash - sum([o['item_price'] for o in today_orders])} ETB\n"
    )
    bot.send_message(message.chat.id, report, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "👤 የኔ ፕሮፋይል")
def admin_personal_profile(message):
    if message.from_user.id not in ADMIN_IDS: return
    db = load_data()
    my_orders = [o for o in db["orders"].values() if o.get("driver_id") == message.from_user.id]
    completed = [o for o in my_orders if o["status"] == "Delivered"]
    
    total_cash = sum([o.get("total", 0) for o in completed])
    delivery_earnings = sum([o.get("delivery_fee", 0) for o in completed])
    
    text = (
        f"💳 **የአድሚን ፕሮፋይል**\n"
        f"👤 ስም፦ {message.from_user.first_name}\n"
        f"✅ ያደረሷቸው፦ {len(completed)}\n"
        f"💵 በእጅ ያለ ገንዘብ፦ {total_cash} ETB\n"
        f"🎁 የዴሊቨሪ ትርፍ፦ {delivery_earnings} ETB"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏬 አጋር ድርጅቶች")
def admin_vendor_menu(message):
    if message.from_user.id not in ADMIN_IDS: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ አዲስ ሱቅ መዝግብ", callback_data="admin_add_v"))
    markup.add(types.InlineKeyboardButton("📜 የሱቆች ዝርዝር/ሂሳብ", callback_data="admin_list_v"))
    bot.send_message(message.chat.id, "የአጋር ድርጅቶች መቆጣጠሪያ፦", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "settle_my_cash")
def settle_cash(call):
    # ይህ አድሚኑ በእጁ ያለውን ገንዘብ አስረክቦ ሂሳቡን ዜሮ የሚያደርግበት ነው
    db = load_data()
    admin_id = str(call.from_user.id)
    
    # ሪኮርድ እንዲቀመጥ (Log)
    bot.send_message(call.message.chat.id, "✅ በእጅዎ የነበረው ገንዘብ ለዋናው ካዝና ገቢ ተደርጓል። ሂሳብዎ ተወራርዷል።")
    # እዚህ ጋር እንደ ፍላጎትህ የተወራረደበትን ሎጂክ መጻፍ ይቻላል

@bot.message_handler(func=lambda m: m.text == "📝 ማስታወሻ")
def admin_note(message):
    if message.from_user.id not in ADMIN_IDS: return
    db = load_data()
    current_note = db.get("admin_note", "ምንም ማስታወሻ የለም።")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖊 አዲስ ጻፍ", callback_data="edit_note"))
    bot.send_message(message.chat.id, f"📌 **የአድሚኖች ማስታወሻ፦**\n\n{current_note}", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "edit_note")
def start_edit_note(call):
    msg = bot.send_message(call.message.chat.id, "የሚለጠፈውን አጭር ማስታወሻ ይጻፉ፦")
    bot.register_next_step_handler(msg, save_note)

def save_note(message):
    db = load_data()
    db["admin_note"] = message.text
    save_data(db)
    bot.send_message(message.chat.id, "✅ ማስታወሻው ተለጥፏል፤ ለሁሉም አድሚኖች ይታያል።")


@bot.callback_query_handler(func=lambda call: call.data == "admin_add_v")
def start_add_v(call):
    msg = bot.send_message(call.message.chat.id, "📝 የሱቁን ስም ያስገቡ፦")
    bot.register_next_step_handler(msg, save_v_name)

def save_v_name(message):
    v_name = message.text
    msg = bot.send_message(message.chat.id, f"📍 ለ '{v_name}' ሎኬሽን ይላኩ፦")
    bot.register_next_step_handler(msg, save_v_loc, v_name)

def save_v_loc(message, v_name):
    if not message.location: return
    db = load_data()
    v_id = str(len(db["vendors"]) + 1)
    db["vendors"][v_id] = {"name": v_name, "lat": message.location.latitude, "lon": message.location.longitude, "wallet": 0, "commission": 10}
    save_data(db)
    bot.send_message(message.chat.id, f"✅ {v_name} ተመዝግቧል!")


@bot.callback_query_handler(func=lambda call: call.data.startswith("claim_"))
def claim_order(call):
    oid = call.data.split("_")
    db = load_data()
    order = db["orders"][oid]
    
    if "driver_id" in order:
        return bot.answer_callback_query(call.id, "❌ ትዕዛዙ ተይዟል!")
    
    db["orders"][oid]["driver_id"] = call.from_user.id
    db["orders"][oid]["status"] = "On the way 🛵"
    save_data(db)
    
    addr = order["address_details"]
    details = f"📍 ኮንዶ፦ {addr['condo']}\n🧱 ብሎክ፦ {addr['block']} | 🚪 ቤት ቁጥር፦ {addr['house_no']}"
    
    bot.send_message(call.message.chat.id, f"✅ ትዕዛዝ #{oid} ተረክበዋል።\n{details}")
    bot.send_location(call.message.chat.id, order["location"]["lat"], order["location"]["lon"])

@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def finalize_order(call):
    oid = call.data.split("_")
    db = load_data()
    order = db["orders"][oid]
    
    if order["status"] == "Delivered": return

    # የኮሚሽን ስሌት
    db["total_profit"] += order["commission"]
    db["vendors"][order["vid"]]["wallet"] += (order["item_price"] - order["commission"])
    db["orders"][oid]["status"] = "Delivered"
    
    save_data(db)
    bot.edit_message_text(f"✅ ትዕዛዝ #{oid} ተጠናቋል። ሂሳብ ተሰልቷል።", call.message.chat.id, call.message.message_id)
    bot.send_message(order["customer_id"], "🎉 ትዕዛዝዎ ደርሷል! እናመሰግናለን።")

def notify_admins_new_order(order_id, order_data):
    # ለሁሉም አድሚኖች መላክ
    for admin_id in ADMIN_IDS:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🛵 ትዕዛዙን ተረከብ (Claim)", callback_data=f"claim_{order_id}"))
        
        alert_text = (
            f"🚨 **አዲስ ትዕዛዝ መጥቷል!**\n"
            f"--------------------------\n"
            f"🆔 ቁጥር፦ #{order_id}\n"
            f"🛍 እቃ፦ {order_data['item_name']}\n"
            f"💰 ዋጋ፦ {order_data['total']} ETB\n"
            f"📍 አድራሻ፦ {order_data['address_details']['condo']}"
        )
        bot.send_message(admin_id, alert_text, reply_markup=markup, parse_mode="Markdown")


def send_to_admin_for_approval(item_id, item):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ፍቀድ (Approve)", callback_data=f"appr_{item_id}"),
        types.InlineKeyboardButton("❌ አትፍቀድ (Reject)", callback_data=f"rejt_{item_id}")
    )
    
    caption = (
        f"🆕 **አዲስ እቃ ከባለሱቅ ቀርቧል**\n\n"
        f"🏬 ሱቅ፦ {item['v_name']}\n"
        f"🛍 እቃ፦ {item['name']}\n"
        f"📝 መግለጫ፦ {item['description']}\n"
        f"💰 ዋጋ፦ {item['price']} ETB"
    )
    
    for admin_id in ADMIN_IDS:
        bot.send_photo(admin_id, item['photo'], caption=caption, reply_markup=markup, parse_mode="Markdown")



# 1. መግለጫ (Description) ተቀባይ ፈንክሽን መጨመር
def process_item_name(message, photo_id):
    item_name = message.text
    msg = bot.send_message(message.chat.id, f"📝 ስለ '{item_name}' አጭር መግለጫ (Description) ይጻፉ፦")
    bot.register_next_step_handler(msg, process_item_description, photo_id, item_name)

def process_item_description(message, photo_id, item_name):
    description = message.text
    msg = bot.send_message(message.chat.id, f"💰 የ '{item_name}' ዋጋ ስንት ነው? (በቁጥር ብቻ)፦")
    bot.register_next_step_handler(msg, process_item_price, photo_id, item_name, description)

# 2. ዋጋውን ተቀብሎ ሴቭ ማድረጊያ (የተስተካከለ)
def process_item_price(message, photo_id, item_name, description):
    try:
        price = float(message.text)
        db = load_data()
        
        item_id = str(len(db.get("items", {})) + len(db.get("pending", {})) + 1)
        
        pending_item = {
            "id": item_id,
            "vid": str(message.from_user.id),
            "v_name": db["vendors_list"][str(message.from_user.id)]["name"],
            "name": item_name,
            "description": description,
            "price": price,
            "photo": photo_id,
            "status": "Pending"
        }
        
        if "pending" not in db: db["pending"] = {}
        db["pending"][item_id] = pending_item
        save_data(db)
        
        bot.send_message(message.chat.id, "✅ እቃው ተመዝግቧል! አድሚን ሲያጸድቀው ለደንበኞች ይታያል።")
        
        # ለአድሚን ማሳወቂያ መላክ
        send_to_admin_for_approval(item_id, pending_item)
        
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ ስህተት፦ እባክዎ ዋጋውን በቁጥር ብቻ ያስገቡ!")
        bot.register_next_step_handler(msg, process_item_price, photo_id, item_name, description)

def process_house_no(message, item_id, user_loc, condo_name, block_no):
    house_no = message.text
    
    # ስልክ ቁጥር መጠየቅ
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📲 ስልክ ቁጥሬን ላክ (Share Contact)", request_contact=True))
    
    msg = bot.send_message(message.chat.id, "በመጨረሻም ሾፌሩ እንዲደውልልዎ ስልክ ቁጥርዎን ያጋሩ፦", reply_markup=markup)
    bot.register_next_step_handler(msg, finalize_customer_order, item_id, user_loc, condo_name, block_no, house_no)

def finalize_customer_order(message, item_id, user_loc, condo_name, block_no, house_no):
    if not message.contact:
        msg = bot.send_message(message.chat.id, "❌ እባክዎ ስልክ ቁጥርዎን ያጋሩ!")
        bot.register_next_step_handler(msg, finalize_customer_order, item_id, user_loc, condo_name, block_no, house_no)
        return

    phone = message.contact.phone_number
    db = load_data()
    item = db["items"][item_id]
    vendor = db["vendors_list"][str(item['vid'])]
    
    # ርቀት እና ዋጋ ስሌት (ቀደም ሲል የሰራነው Logic)
    dist = calculate_distance(user_loc["lat"], user_loc["lon"], vendor.get('lat', 0), vendor.get('lon', 0))
    base_fee = db["settings"].get("base_delivery", 50)
    delivery_fee = base_fee if dist <= 1000 else base_fee + 20 # ቀለል ያለ ስሌት
    total_price = item['price'] + delivery_fee

    order_id = str(len(db["orders"]) + 1)
    
    summary = (
        f"📝 **የትዕዛዝ ማጠቃለያ**\n\n"
        f"🛍 እቃ፦ {item['name']}\n"
        f"🏢 አድራሻ፦ {condo_name}, Blk {block_no}, H.No {house_no}\n"
        f"📲 ስልክ፦ {phone}\n"
        f"--------------------------\n"
        f"💰 የእቃ ዋጋ፦ {item['price']} ETB\n"
        f"🛵 ማድረሻ፦ {delivery_fee} ETB\n"
        f"💵 **ጠቅላላ ክፍያ፦ {total_price} ETB**\n\n"
        f"ትዕዛዙን ማረጋገጥ ይፈልጋሉ?"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ ትዕዛዙን አረጋግጥ", callback_data=f"conf_order_{order_id}"))
    markup.add(types.InlineKeyboardButton("❌ ሰርዝ", callback_data="cancel_order"))
    
    bot.send_message(message.chat.id, summary, reply_markup=markup, parse_mode="Markdown")

    # ትዕዛዙን በ 'Pending' ሁኔታ ለጊዜው መመዝገብ
    db["orders"][order_id] = {
        "id": order_id,
        "customer_id": message.from_user.id,
        "item_name": item['name'],
        "item_price": item['price'],
        "delivery_fee": delivery_fee,
        "total": total_price,
        "address_details": {"condo": condo_name, "block": block_no, "house_no": house_no},
        "location": user_loc,
        "phone": phone,
        "vid": item['vid'],
        "status": "Awaiting Confirmation"
    }
    save_data(db)



def check_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🚫 ይቅርታ፣ ይህን ተግባር ለመጠቀም ፍቃድ የለዎትም።")
        return False
    return True



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
