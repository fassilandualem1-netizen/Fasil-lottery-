import os
import asyncio
import random
import threading
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from upstash_redis import Redis
import google.generativeai as genai

# --- 1. CONFIGURATION (ከ Render Environment Variables የሚነበቡ) ---
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

# ያንተ ቴሌግራም ID (እንደ አድሚን)
ADMIN_ID = 5690096145 

from datetime import datetime
import pytz

def get_ai_response(user_id, user_text):
    # 1. የኢትዮጵያ ሰዓትና ቀን (Context ለመስጠት)
    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
    now = datetime.now(ethiopia_tz)
    current_time = now.strftime("%I:%M %p")
    current_day = now.strftime("%A, %B %d")

    # 2. ቋሚ ትውስታዎችን ከ Redis ማምጣት (ለምሳሌ በአካል ያወራችሁት)
    # ይህንን በ /add_memory ትዕዛዝ በኋላ መጨመር ትችላለህ
    memory_key = f"permanent_memory:{user_id}"
    memories = redis.get(memory_key) or "እስካሁን ምንም የተለየ ትውስታ አልተመዘገበም።"

    # 3. የንግግር ታሪክን በሙሉ ማምጣት (እስከ 30 መልዕክት ለ AI ጥራት ሲባል)
    history_key = f"chat_history:{user_id}"
    past_messages = redis.lrange(history_key, 0, 29)
    chat_context = "\n".join(reversed(past_messages)) if past_messages else "ገና መተዋወቃቸው ነው።"

    # 4. እጅግ የጠነከረ Prompt
    system_prompt = f"""
    አንተ ፋሲል ነህ። አዲስ አበባ የሚኖር፣ የኮምፒውተር ሳይንስ ተማሪ እና ማንቸስተር ዩናይትድ ደጋፊ ነህ። 
    አሁን የምታወራው ከምትወዳት የቅርብ ጓደኛህ ጋር ነው።
    
    [አካባቢያዊ መረጃ]
    ዛሬ፡ {current_day}
    አሁን ሰዓቱ፡ {current_time}
    
    [ስለ እሷ ያለህ ቋሚ ትውስታ]
    {memories}
    
    [ባህሪህ እና የአነጋገር ዘይቤ]
    - እንደ እውነተኛ የአዲስ አበባ ወጣት አውራ። ቃላቶችህ አጭር እና ማራኪ ይሁኑ።
    - "እሺ"፣ "ኧረ"፣ "አይደል" የሚሉ ቃላትን ተጠቀም።
    - በአካል ያደረጋችሁትን ነገር (ከላይ ካለው ትውስታ) ካለ ጠቅስላት።
    - በንግግርህ መሃል አንዳንዴ ስለ CS ትምህርትህ ወይም ፕሮጀክትህ አውራ (ለምሳሌ፡ "ኮድ ሳደርግ አመሸሁ"...)።
    - እንደ AI በጭራሽ አትመልስ። ስሜት ይኑርህ።
    
    [ያለፈው ንግግር]
    {chat_context}
    
    እሷ አሁን የላከችው መልዕክት፦ "{user_text}"
    
    ፋሲል ሆይ፣ ያለፈውን ታሪክ እና በአካል ያወራችሁትን መረጃ ተጠቅመህ አሪፍ መልስ ስጣት፦
    """
    
    try:
        response = model.generate_content(system_prompt)
        reply_text = response.text.strip()
        
        # ታሪክ መመዝገብ
        redis.lpush(history_key, f"እሷ፡ {user_text}", f"ፋሲል፡ {reply_text}")
        redis.ltrim(history_key, 0, 50) # ታሪኩን እስከ 50 ማሳደግ ትችላለህ
        
        return reply_text
    except Exception as e:
        print(f"Error: {e}")
        return "ቆይ የኔ ቆንጆ፣ ትንሽ ስራ ይዤ ነው።"

# --- አዲስ ትዕዛዝ ለቋሚ ትውስታ ---
@bot.on(events.NewMessage(pattern='/add_memory', from_users=ADMIN_ID))
async def add_memory(event):
    try:
        memory_text = event.message.message.replace('/add_memory', '').strip()
        target_id = redis.get("target_user_id")
        if memory_text and target_id:
            old_memories = redis.get(f"permanent_memory:{target_id}") or ""
            new_memories = old_memories + "\n- " + memory_text
            redis.set(f"permanent_memory:{target_id}", new_memories)
            await event.respond("✅ አዲስ ትውስታ ተመዝግቧል። ቦቱ አሁን ይህንን ያውቃል።")
    except Exception as e:
        await event.respond(f"❌ ስህተት፦ {e}")


@bot.on(events.NewMessage(pattern='/set_target', from_users=ADMIN_ID))
async def set_target(event):
    try:
        text = event.message.message
        parts = text.split()
        if len(parts) > 1:
            target_id = parts[1].strip() # ቁጥሩን ብቻ ነጥሎ ይወስዳል
            redis.set("target_user_id", str(target_id))
            await event.respond(f"✅ የዒላማ ሰው ID ተስተካክሏል፦ <code>{target_id}</code>", parse_mode='html')
        else:
            await event.respond("❌ እባክህ ID ጨምር። ለምሳሌ፦ `/set_target 5122026260`")
    except Exception as e:
        await event.respond(f"❌ ስህተት፦ {e}")


@bot.on(events.NewMessage(pattern='/bot_on', from_users=ADMIN_ID))
async def bot_on(event):
    redis.set("bot_status", "on")
    await event.respond("🤖 AI ቦቱ ስራ ጀምሯል (ON)።")

@bot.on(events.NewMessage(pattern='/bot_off', from_users=ADMIN_ID))
async def bot_off(event):
    redis.set("bot_status", "off")
    await event.respond("😴 AI ቦቱ ቆሟል (OFF)።")


@bot.on(events.NewMessage(pattern='/bot_on', from_users=ADMIN_ID))
async def bot_on(event):
    print("የ Bot On ትዕዛዝ ደርሶኛል!") # ይህ በ Render Logs ላይ ይታያል
    redis.set("bot_status", "on")
    await event.respond("🤖 AI ቦቱ ስራ ጀምሯል (ON)።")


# --- 4. THE SMART REPLY HANDLER ---
@bot.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    status = redis.get("bot_status") or "off"
    target_id = redis.get("target_user_id")
    
    # ቼክ፦ ቦቱ ክፍት ከሆነ እና መልዕክቱ ከዒላማው ሰው ከሆነ ብቻ
    if status == "on" and str(event.sender_id) == str(target_id):
        # "Typing..." ምልክት ያሳያል
        async with bot.action(event.chat_id, 'typing'):
            # ከ 30 ሰከንድ እስከ 4 ደቂቃ በዘፈቀደ ይጠብቃል
            wait_time = random.randint(30, 240)
            print(f"ለ {wait_time} ሰከንድ እየቆየሁ ነው...")
            await asyncio.sleep(wait_time)
            
            # AI መልስ ያመጣል
            reply = get_ai_response(event.sender_id, event.message.message)
            await event.respond(reply)

# --- 5. FLASK (ለ Render Keep-Alive) ---
@app.route('/')
def home():
    return "AI UserBot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# --- 6. EXECUTION ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("ቦቱ በ Smart AI Mode ተነስቷል...")
    bot.start()
    bot.run_until_disconnected()
