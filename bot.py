import telebot
from telebot import types
import json, time
from upstash_redis import Redis

# --- 1. CONFIGURATION ---
TOKEN = "8721334129:AAFpNmNq1PpTQ_SWsj4dye8T3-TXNAZA7Kg"
MY_ID = 8488592165          
ASSISTANT_ID = 7072611117   
GROUP_ID = -1003749311489
ADMIN_IDS = [MY_ID, ASSISTANT_ID]

# አዲሱ REDIS መረጃ (እዚህ ጋር ይተኩ)
REDIS_URL = "https://charmed-sailfish-95943.upstash.io"
REDIS_TOKEN = "gQAAAAAAAXbHAAIncDJmOWM3ZWY3ZTc5MmQ0ZmI0OWIyNjUzY2Y4YmFlZGEyM3AyOTU5NDM"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

# --- 2. DATA MANAGEMENT ---
def load_data():
    raw = redis.get("fasil_bingo_db")
    if raw: return json.loads(raw)
    return {
        "users": {}, # {uid: {"name": str, "wallet": int}}
        "board": {"max": 25, "price": 50, "prize": "ያልተወሰነ", "slots": {}},
        "pinned_msg_id": None
    }

data = load_data()
def save_data(): redis.set("fasil_bingo_db", json.dumps(data))

# --- 3. BOARD UI ---
def update_group_board():
    b = data["board"]
    text = f"🏟️ <b>ፋሲል እና ዳመነ ዲጂታል ዕጣ</b> 🏟️\n"
    text += f"💰 ዋጋ፦ <b>{b['price']} ብር</b>\n"
    text += f"🎁 ሽልማት፦ <b>{b['prize']}</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

    for i in range(1, b["max"] + 1):
        n = str(i)
        status = f"✅ {data['board']['slots'][n]}" if n in data['board']['slots'] else "⬜️ @@@@"
        text += f"<b>{i:02}👉</b> {status}\t\t"
        if i % 2 == 0: text += "\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 ዙር፦ አዲስ | ሰዓት፦ {time.strftime('%H:%M')}"

    try:
        if data["pinned_msg_id"]:
            bot.edit_message_text(text, GROUP_ID, data["pinned_msg_id"])
        else:
            m = bot.send_message(GROUP_ID, text)
            bot.pin_chat_message(GROUP_ID, m.message_id)
            data["pinned_msg_id"] = m.message_id
            save_data()
    except:
        m = bot.send_message(GROUP_ID, text)
        data["pinned_msg_id"] = m.message_id
        save_data()

# --- 4. PHOTO LISTENER (FROM GROUP) ---
@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.id == GROUP_ID)
def handle_receipt(message):
    uid = message.from_user.id
    name = message.from_user.first_name
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ አፅድቅ", callback_data=f"approve_{uid}"),
               types.InlineKeyboardButton("❌ ውድቅ", callback_data=f"decline_{uid}"))
    caption = f"📩 <b>አዲስ ደረሰኝ</b>\n👤 ከ፦ {name}\n🆔 ID፦ <code>{uid}</code>"
    for adm in ADMIN_IDS:
        bot.send_photo(adm, message.photo[-1].file_id, caption=caption, reply_markup=markup)

# --- 5. CALLBACK HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    is_admin = call.from_user.id in ADMIN_IDS
    d = call.data

    if d.startswith("approve_") and is_admin:
        target_id = d.split("_")
        m = bot.send_message(call.message.chat.id, "💰 <b>የተከፈለውን ብር ይጻፉ፦</b>")
        bot.register_next_step_handler(m, process_wallet_add, target_id)

    elif d.startswith("pick_"):
        num = d.split("_")
        uid = str(call.from_user.id)
        u_data = data["users"].get(uid, {"name": call.from_user.first_name, "wallet": 0})
        price = data["board"]["price"]

        if u_data["wallet"] < price:
            bot.answer_callback_query(call.id, "⚠️ በቂ ሂሳብ የለዎትም!", show_alert=True)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            return

        if num in data["board"]["slots"]:
            bot.answer_callback_query(call.id, "❌ ተይዟል!")
            return

        u_data["wallet"] -= price
        data["board"]["slots"][num] = u_data["name"][:10]
        data["users"][uid] = u_data
        save_data()
        update_group_board()

        if u_data["wallet"] < price:
            bot.edit_message_text(f"✅ ምርጫዎ ተጠናቋል።", call.message.chat.id, call.message.message_id)
        else:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=gen_pick_buttons(uid))

    elif d == "stop_picking":
        bot.edit_message_text("🏁 ምርጫዎን አቁመዋል።", call.message.chat.id, call.message.message_id)

    elif d == "admin_reset" and is_admin:
        m = bot.send_message(call.from_user.id, "📝 <b>መረጃውን በዚሁ መልኩ ይጻፉ፦</b>\nሰው-ዋጋ-ሽልማት\n(ምሳሌ: 25-50-1ኛ 500, 2ኛ 200, 3ኛ 100)")
        bot.register_next_step_handler(m, execute_reset)

# --- 6. ADMIN & LOGIC FUNCTIONS ---
def process_wallet_add(message, target_id):
    try:
        # መልዕክቱን ወደ ቁጥር መቀየር
        amount = int(message.text.strip()) 
        target_id = str(target_id)
        
        if target_id not in data["users"]:
            data["users"][target_id] = {"name": "ተጫዋች", "wallet": 0}
            
        data["users"][target_id]["wallet"] += amount
        save_data()
        
        bot.send_message(message.chat.id, f"✅ ለተጫዋች {amount} ብር ተሞልቷል!")
        bot.send_message(target_id, f"✅ ሂሳብዎ ጸድቋል! {amount} ብር ተሞልቶልዎታል።\nአሁን ቁጥር ይምረጡ፦", 
                         reply_markup=gen_pick_buttons(target_id))
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ ስህተት! እባክዎ ቁጥር ብቻ ይጻፉ (ምሳሌ: 200)።")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ ያልታወቀ ስህተት፦ {e}")

def gen_pick_buttons(uid):
    markup = types.InlineKeyboardMarkup(row_width=5)
    u_wallet = data["users"][str(uid)]["wallet"]
    btns = [types.InlineKeyboardButton(str(i), callback_data=f"pick_{i}") 
            for i in range(1, data["board"]["max"] + 1) if str(i) not in data["board"]["slots"]]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton(f"🏁 በቃኝ (ቀሪ: {u_wallet})", callback_data="stop_picking"))
    return markup

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id in ADMIN_IDS:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🧹 ሰሌዳ አጽዳ (አዲስ ዙር)", callback_data="admin_reset"))
        bot.send_message(message.chat.id, "🛠 <b>አድሚን ፓናል</b>", reply_markup=markup)

def execute_reset(message):
    try:
        # ባዶ ቦታዎችን አጽድቶ በሰረዝ መከፋፈል
        text = message.text.replace(' ', '') # ሁሉንም ባዶ ቦታ ያጠፋል
        parts = text.split('-')
        
        if len(parts) < 3:
            # ምናልባት ተጫዋቹ ሌላ አይነት ሰረዝ ተጠቅሞ ከሆነ
            parts = text.split('–') 

        data["board"]["max"] = int(parts)
        data["board"]["price"] = int(parts)
        data["board"]["prize"] = parts
        data["board"]["slots"] = {} # ቁጥሮችን ማጽዳት
        save_data()
        update_group_board()
        bot.send_message(message.chat.id, "✅ ሰሌዳው በትክክል ጸድቶ አዲስ ዙር ተጀምሯል!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ስህተት! እባክዎ እንዲህ ይጻፉ፦\n`25-30-ሽልማት` (መሃል ላይ ሰረዝ ብቻ ይጠቀሙ)")

import telebot
TOKEN = "8721334129:AAFF0Irx3Pa7add9rnMcm855Xsg2G3zMzFM"
bot = telebot.TeleBot(TOKEN)
bot.remove_webhook() # የቆየውን ያጸዳል
print("Webhook removed and sessions cleared!")
