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

ADMIN_ID = 8488592165 

# --- 2. AI LOGIC (SEARCH + NO PUNCTUATION + UNLIMITED IDEAS) ---
def get_ai_response(user_id, user_text):
    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
    now = datetime.now(ethiopia_tz)
    current_time = now.strftime("%I:%M %p")
    current_day = now.strftime("%A, %B %d")

    memory_key = f"permanent_memory:{user_id}"
    raw_memories = redis.get(memory_key)
    memories = raw_memories.decode('utf-8') if isinstance(raw_memories, bytes) else (raw_memories or "ትውስታ የለም")

    history_key = f"chat_history:{user_id}"
    past_messages = redis.lrange(history_key, 0, 19)
    decoded_history = [m.decode('utf-8') if isinstance(m, bytes) else m for m in past_messages]
    chat_context = "\n".join(reversed(decoded_history)) if decoded_history else "አዲስ ቻት"

    system_prompt = f"""
    አንተ ፋሲል ነህ። አዲስ አበባ የሚኖር የ 2ኛ አመት የ CS ተማሪ ነህ። ማንቸስተር ዩናይትድ ደጋፊ ነህ።
    አሁን የምታወራው ከምትወዳት ጓደኛህ ጋር ነው። 
    
    [ትዕዛዞች]
    - መረጃ ከፈለግህ (ስለ ኳስ፣ ዜና፣ አየር ጸባይ) Google Search ተጠቀም ግን መልስህ የፋሲልን ባህሪ ይኑረው።
    - ስርዓተ ነጥብ (.,?!:;-) በፍፁም እንዳትጠቀም።
    - እንደ አስፈላጊነቱ ኢሞጂዎችን በብዛት ተጠቀም።
    - ባህሪህ እንደ ንግግሩ ፍሰት Flirt፣ Funny ወይም Serious ይሁን። ሃሳብ ብትቀይር አብረሃት ተቀየር።
    - ቋንቋህ የአዲስ አበባ ወጣት (Habesha Slang) ይሁን።
    
    [መረጃ] ዛሬ {current_day} | አሁን {current_time} | ትውስታ {memories}
    [ታሪክ] {chat_context}
    እሷ፡ {user_text}
    ፋሲል፡
    """

    try:
        # temperature=1.0 ለአዳዲስ ሃሳቦች
        response = model.generate_content(
            system_prompt,
            generation_config=genai.types.GenerationConfig(temperature=1.0, top_p=0.99)
        )
        reply_text = response.text.strip()
        
        # ስርዓተ ነጥብን በኮድ ማጽዳት
        punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~'''
        for char in punctuations:
            reply_text = reply_text.replace(char, "")
            
        redis.lpush(history_key, f"እሷ፡ {user_text}", f"ፋሲል፡ {reply_text}")
        redis.ltrim(history_key, 0, 50)
        return reply_text
    except Exception as e:
        print(f"Error: {e}")
        return random.choice(["ኔትወርክ አስቸገረኝ", "ቆይ ልሞክረው", "ምነው ዝም አልሽ", "አልሰማሁሽም"])

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

# --- 4. THE SMART DYNAMIC HANDLER ---
@bot.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if event.is_private:
        raw_status = redis.get("bot_status")
        raw_target = redis.get("target_user_id")
        
        status = raw_status.decode('utf-8') if isinstance(raw_status, bytes) else (raw_status or "off")
        target_id = raw_target.decode('utf-8') if isinstance(raw_target, bytes) else (raw_target or "")

        if status == "on" and str(event.sender_id) == str(target_id):
            await event.mark_read() 
            
            # የመልዕክት ርዝመት መሰረት ያደረገ መዘግየት
            msg_len = len(event.message.message)
            if msg_len < 20:
                wait_time = random.randint(15, 60)
            else:
                wait_time = random.randint(60, 300)
            
            # አልፎ አልፎ ረጅም መዘግየት (Busy behavior)
            if random.random() < 0.1:
                wait_time = random.randint(600, 1800)

            # ታይፒንግ ከመልሱ 12 ሰከንድ በፊት ይጀምራል
            if wait_time > 12:
                await asyncio.sleep(wait_time - 12)
            
            async with bot.action(event.chat_id, 'typing'):
                await asyncio.sleep(12)
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
