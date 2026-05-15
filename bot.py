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

# Gemini AI Setup (Google Search ተጨምሮበት)
genai.configure(api_key=GEMINI_API_KEY)

# ሞዴሉን በምናዝዝበት ጊዜ ሰርች እንዲጠቀም tools እንጨምራለን
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    tools=[{'google_search_retrieval': {}}]
)

# Initializations
bot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__)

ADMIN_ID = 8488592165 

def get_ai_response(user_id, user_text):
    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
    now = datetime.now(ethiopia_tz)
    current_time = now.strftime("%I:%M %p")
    current_day = now.strftime("%A, %B %d")

    # 1. ትውስታና የድሮ ንግግሮችን ማምጣት
    memory_key = f"permanent_memory:{user_id}"
    raw_memories = redis.get(memory_key)
    memories = raw_memories.decode('utf-8') if isinstance(raw_memories, bytes) else (raw_memories or "ትውስታ የለም")

    history_key = f"chat_history:{user_id}"
    past_messages = redis.lrange(history_key, 0, 15)
    decoded_history = [m.decode('utf-8') if isinstance(m, bytes) else m for m in past_messages]
    chat_context = "\n".join(reversed(decoded_history)) if decoded_history else "አዲስ ቻት"

    # 2. የጌሚኒን አእምሮ ከፋሲል ማንነት ጋር ማሰር
    system_prompt = f"""
    አንተ ፋሲል ነህ አዲስ አበባ የምትኖር የ CS ተማሪ እና የማንቸስተር ዩናይትድ ደጋፊ ነህ
    አሁን የምታወራው ከምትወዳት ጓደኛህ ጋር ነው
    
    [ባህሪ]
    - Google Search ተጠቅመህ አዳዲስ ወሬዎችን አምጣ ግን መልስህ አጭር ይሁን
    - ስርዓተ ነጥብ አትጠቀም እና በአራዳ ቋንቋ አውራ
    - በፎቶ ላይ የታዩትን ሰበቦች (ኔትወርክ፣ ስራ ይዤ ነው) በፍፁም እንዳትጠቀም
    
    ዛሬ {current_day} ሰዓቱ {current_time} ነው
    ታሪክ፦ {chat_context}
    እሷ፦ {user_text}
    ፋሲል፦
    """

    try:
        # temperature=1.0 ለፈጠራ ችሎታ፣ tools ለ Google Search
        response = model.generate_content(
            system_prompt,
            generation_config=genai.types.GenerationConfig(temperature=1.0, top_p=0.99)
        )
        reply_text = response.text.strip()
        
        # ስርዓተ ነጥብን በኮድ ማጽዳት (ለበለጠ Realነት)
        punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~'''
        for char in punctuations:
            reply_text = reply_text.replace(char, "")
            
        # ወሬውን ለቀጣይ እንዲያስታውስ ማስቀመጥ
        redis.lpush(history_key, f"እሷ፡ {user_text}", f"ፋሲል፡ {reply_text}")
        redis.ltrim(history_key, 0, 40)
        return reply_text
    except Exception as e:
        print(f"Error: {e}")
        # ሰርች ቢቋረጥ እንኳ ተፈጥሯዊ መልስ
        return "ወዬ የኔ ቆንጆ ሰላም ነው እንዴት ነሽልኝ"


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

            # መዘግየቱን በ 1 እና 2 ደቂቃ (60 - 120 ሰከንድ) መካከል አድርጌዋለሁ
            # ይህ ቦቱ ሰርች አድርጎ እስኪጨርስ በቂ ጊዜ ይሰጠዋል
            wait_time = random.randint(60, 120)

            # ታይፒንግ (Typing) ከመልሱ 15 ሰከንድ በፊት ይጀምራል
            if wait_time > 15:
                await asyncio.sleep(wait_time - 15)

            async with bot.action(event.chat_id, 'typing'):
                # ጌሚኒ ሰርች አድርጎ እንዲጨርስ 15 ሰከንድ ታይፒንግ ያሳያል
                await asyncio.sleep(15)
                reply = get_ai_response(event.sender_id, event.message.message)
                
                # መልሱ ባዶ ካልሆነ ብቻ ይላክ
                if reply:
                    await event.respond(reply)



# --- 5. FLASK & RUN ---
@app.route('/')
def home(): return "Bot is Live!"

def run_flask(): app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.start()
    bot.run_until_disconnected()
