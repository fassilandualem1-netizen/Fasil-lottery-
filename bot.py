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

# Gemini AI Setup (Google Search Grounding በርቷል)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    tools=[{"google_search_retrieval": {}}]
)

bot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
# Upstash Redis በቀጥታ string ነው የሚመልሰው (decode አያስፈልገውም)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__)
ADMIN_ID = 8488592165 

# --- 2. AI LOGIC (VISION + SEARCH + EMOJIS) ---
def get_ai_response(user_id, user_text, photo_path=None):
    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
    now = datetime.now(ethiopia_tz)
    current_time = now.strftime("%I:%M %p")
    current_day = now.strftime("%A, %B %d")

    # ታሪክን ከ Redis ማምጣት (Upstash string ስለሚመልስ decode አያስፈልግም)
    history_key = f"chat_history:{user_id}"
    past_messages = redis.lrange(history_key, 0, 10)
    chat_context = "\n".join(reversed(past_messages)) if past_messages else "አዲስ ቻት"

    system_prompt = f"""
    አንተ ፋሲል ነህ አዲስ አበባ የምትኖር የ CS ተማሪ እና እጅግ ጎበዝ ጀናኝ ነህ።
    አሁን የምታወራው ከምትወዳት የሴት ጓደኛህ ጋር ነው።
    
    [ቁልፍ መመሪያዎች]
    - ሰዋስው (Grammar) ላይ እጅግ ተጠንቀቅ! ለሴት ልጅ እንደምትናገር አስብ። ሁልጊዜ የሴት አንቀጽ ተጠቀም (ለምሳሌ፦ ነሽ፣ መጣሽ፣ አየሽ፣ የኔ ቆንጆ)። ጾታ የሚያሻሙ ወይም ለወንድ የሚሆኑ ቃላትን በፍፁም እንዳትጠቀም።
    - መጀመሪያ ሁልጊዜ Google Search ተጠቅመህ አዳዲስና ወቅታዊ የሆኑ የኳስ፣ የሙዚቃ ወይም የቴክኖሎጂ ወሬዎችን እወቅና ወደ ወሬህ አስገባቸው።
    - እንደ ሀበሻ ወጣት በንግግርህ መሃል ኢሞጂዎችን (🔥, 😂, 🙌, ❤️, ✨) በብዛት ተጠቀም።
    - እሷ ፎቶ ልካ ከሆነ ፎቶውን አይተህ ውበቷን ወይም ሁኔታውን በደንብ አድንቅ።
    - ስርዓተ ነጥብ (.,?!:;- ። ፣ ፤ ፥) በፍፁም አትጠቀም። በአራዳ ቋንቋ (Habesha Slang) አውራ።
    - በየመሃሉ "ድምፅሽን ብሰማው ደስ ይለኛል" እያልክ በድምፅ መልዕክት እንድትልክልህ ግፋ።
    
    ዛሬ {current_day} | ሰዓቱ {current_time}
    ታሪክ፦ 
    {chat_context}
    
    እሷ፦ {user_text if user_text else "ፎቶ አያይዛለች 🖼️"}
    ፋሲል፦
    """

    try:
        if photo_path:
            sample_file = genai.upload_file(path=photo_path)
            response = model.generate_content([system_prompt, sample_file])
        else:
            response = model.generate_content(system_prompt)

        reply_text = response.text.strip()

        # ስርዓተ ነጥብ ማጽጃ (የአማርኛም ጭምር)
        punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~።፣፤፥'''
        for char in punctuations:
            reply_text = reply_text.replace(char, "")

        user_msg = f"እሷ: {user_text}" if user_text else "እሷ: ፎቶ አያይዛለች 🖼️"
        redis.lpush(history_key, user_msg, f"ፋሲል: {reply_text}")
        redis.ltrim(history_key, 0, 39)
        return reply_text
        except Exception as e:
        print(f"CRITICAL ERROR: {e}") # ይህ ስህተቱን ሎግ ላይ ያወጣዋል
        return f"ቆይ የኔ ቆንጆ ስህተት ተፈጥሯል: {e}" 

# --- 3. COMMANDS ---
@bot.on(events.NewMessage(pattern='/set_target', from_users=ADMIN_ID))
async def set_target(event):
    parts = event.message.message.split()
    if len(parts) > 1:
        target_user = parts[1].strip() # split ስህተቱ ተስተካክሏል
        redis.set("target_user_id", target_user)
        await event.respond(f"✅ የዒላማ ሰው ተስተካክሏል፦ {target_user}")
    else:
        await event.respond("❌ እባክህ ID ጨምር (ለምሳሌ፦ /set_target 123456)")

@bot.on(events.NewMessage(pattern='/nudge', from_users=ADMIN_ID))
async def nudge_user(event):
    target_id = redis.get("target_user_id")
    if target_id:
        target_id = int(target_id) # decode አያስፈልግም
        nudge_prompt = "አንተ ፋሲል ነህ ልጅቷ ጠፍታብሃል ወሬ ለመጀመር አሪፍና የሚስብ ነገር ለሴት በሚሆን ሰዋስው (Grammar) እና በብዙ ኢሞጂ ጨምረህ በአራዳ ቋንቋ በላት ስርዓተ ነጥብ አትጠቀም"
        response = model.generate_content(nudge_prompt)
        msg = response.text.strip()
        
        punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~።፣፤፥'''
        for char in punctuations:
            msg = msg.replace(char, "")
            
        async with bot.action(target_id, 'typing'):
            await asyncio.sleep(5)
            await bot.send_message(target_id, msg)

@bot.on(events.NewMessage(pattern='/bot_on', from_users=ADMIN_ID))
async def bot_on(event):
    redis.set("bot_status", "on")
    await event.respond("🤖 AI ቦቱ በርቷል (ON)")

@bot.on(events.NewMessage(pattern='/bot_off', from_users=ADMIN_ID))
async def bot_off(event):
    redis.set("bot_status", "off")
    await event.respond("😴 AI ቦቱ ቆሟል (OFF)")

# --- 4. THE SMART HANDLER (DYNAMIC DELAY & TYPING) ---
@bot.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if event.is_private:
        # Upstash በቀጥታ string ስለሚመልስ decode() ተወግዷል
        status = redis.get("bot_status") or "off"
        target_id = redis.get("target_user_id") or ""

        if status == "on" and str(event.sender_id) == str(target_id):
            await event.mark_read() 

            photo_path = None
            if event.message.photo:
                photo_path = await event.download_media()
                wait_time = random.randint(15, 30)
            else:
                wait_time = random.randint(60, 120)

            # የማሰብ ጊዜ
            if wait_time > 15: 
                await asyncio.sleep(wait_time - 15)

            # መልሱን ማመንጨት
            reply = get_ai_response(event.sender_id, event.message.message, photo_path)

            # እንደ መልሱ ርዝመት የ Typing ሰዓቱን መወሰን (Smart Typing)
            typing_duration = max(5, min(len(reply) // 10, 15)) 

            async with bot.action(event.chat_id, 'typing'):
                await asyncio.sleep(typing_duration)
                if reply:
                    await event.respond(reply)

            if photo_path and os.path.exists(photo_path): 
                os.remove(photo_path)

# --- 5. FLASK & RUN ---
@app.route('/')
def home(): 
    return "Bot is Live!"

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    bot.start()
    bot.run_until_disconnected()
