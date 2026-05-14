import os
import asyncio
import random
import threading
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from upstash_redis import Redis
import google.generativeai as genai
from datetime import datetime
import pytz

# --- 1. CONFIGURATION ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
REDIS_URL = os.getenv("REDIS_URL")
REDIS_TOKEN = os.getenv("REDIS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 8080))

# Gemini AI Setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Initializations
bot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__)

ADMIN_ID = 5690096145 

# --- 2. AI LOGIC ---
def get_ai_response(user_id, user_text):
    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
    now = datetime.now(ethiopia_tz)
    current_time = now.strftime("%I:%M %p")
    current_day = now.strftime("%A, %B %d")

    memory_key = f"permanent_memory:{user_id}"
    memories = redis.get(memory_key) or "እስካሁን ምንም የተለየ ትውስታ አልተመዘገበም።"

    history_key = f"chat_history:{user_id}"
    past_messages = redis.lrange(history_key, 0, 29)
    # redis results are bytes, decode them to string
    decoded_history = [m.decode('utf-8') if isinstance(m, bytes) else m for m in past_messages]
    chat_context = "\n".join(reversed(decoded_history)) if decoded_history else "ገና መተዋወቃቸው ነው።"

    system_prompt = f"""
    አንተ ፋሲል ነህ። አዲስ አበባ የሚኖር፣ የኮምፒውተር ሳይንስ ተማሪ እና ማንቸስተር ዩናይትድ ደጋፊ ነህ። 
    አሁን የምታወራው ከምትወዳት የቅርብ ጓደኛህ ጋር ነው።
    [አካባቢያዊ መረጃ] ዛሬ፡ {current_day} | ሰዓቱ፡ {current_time}
    [ትውስታ] {memories}
    [ባህሪ] እንደ እውነተኛ የአዲስ አበባ ወጣት አጭርና ማራኪ መልስ ስጥ። እንደ AI አትሁን።
    [ታሪክ] {chat_context}
    እሷ፡ "{user_text}"
    """

    try:
        response = model.generate_content(system_prompt)
        reply_text = response.text.strip()
        redis.lpush(history_key, f"እሷ፡ {user_text}", f"ፋሲል፡ {reply_text}")
        redis.ltrim(history_key, 0, 50)
        return reply_text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "ቆይ የኔ ቆንጆ፣ ትንሽ ስራ ይዤ ነው።"

# --- 3. COMMANDS ---
@bot.on(events.NewMessage(pattern='/set_target', from_users=ADMIN_ID))
async def set_target(event):
    try:
        parts = event.message.message.split()
        if len(parts) > 1:
            target_id = parts[1].strip()
            redis.set("target_user_id", target_id)
            await event.respond(f"✅ የዒላማ ሰው ID ተስተካክሏል፦ {target_id}")
        else:
            await event.respond("❌ አጠቃቀም፦ `/set_target 12345`")
    except Exception as e: await event.respond(f"❌ ስህተት፦ {e}")

@bot.on(events.NewMessage(pattern='/bot_on', from_users=ADMIN_ID))
async def bot_on(event):
    redis.set("bot_status", "on")
    await event.respond("🤖 AI ቦቱ ስራ ጀምሯል (ON)።")

@bot.on(events.NewMessage(pattern='/bot_off', from_users=ADMIN_ID))
async def bot_off(event):
    redis.set("bot_status", "off")
    await event.respond("😴 AI ቦቱ ቆሟል (OFF)።")

@bot.on(events.NewMessage(pattern='/add_memory', from_users=ADMIN_ID))
async def add_memory(event):
    text = event.message.message.replace('/add_memory', '').strip()
    target_id = redis.get("target_user_id")
    if text and target_id:
        target_id = target_id.decode('utf-8') if isinstance(target_id, bytes) else target_id
        m_key = f"permanent_memory:{target_id}"
        old = redis.get(m_key) or ""
        old = old.decode('utf-8') if isinstance(old, bytes) else old
        redis.set(m_key, f"{old}\n- {text}")
        await event.respond("✅ ትውስታ ተመዝግቧል።")

# --- 4. HANDLER ---
@bot.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if event.is_private:
        status = redis.get("bot_status")
        target_id = redis.get("target_user_id")
        
        # Decode Redis bytes
        status = status.decode('utf-8') if status else "off"
        target_id = target_id.decode('utf-8') if target_id else ""

        if status == "on" and str(event.sender_id) == target_id:
            async with bot.action(event.chat_id, 'typing'):
                wait_time = random.randint(30, 240)
                print(f"Waiting {wait_time}s for {event.sender_id}...")
                await asyncio.sleep(wait_time)
                reply = get_ai_response(event.sender_id, event.message.message)
                await event.respond(reply)

# --- 5. FLASK & RUN ---
@app.route('/')
def home(): return "Bot is Live!"

def run_flask(): app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.start()
    bot.run_until_disconnected()
