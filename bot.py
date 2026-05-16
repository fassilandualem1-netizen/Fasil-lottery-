import os
import asyncio
import random
import threading
import sys  # ለሎግ ማሳያ የተጨመረ
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from upstash_redis import Redis
from google import genai
from google.genai import types
from google.genai.errors import APIError
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

# በአዲሱ SDK ፍጹም ትክክለኛው የሞዴል ስም 'gemini-2.5-flash' ነው
client_ai = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-2.5-flash'

bot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__)
ADMIN_ID = 8488592165 

# --- 2. AI LOGIC ---
def get_ai_response(user_id, user_text, photo_path=None):
    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
    now = datetime.now(ethiopia_tz)
    current_time = now.strftime("%I:%M %p")
    current_day = now.strftime("%A, %B %d")

    history_key = f"chat_history:{user_id}"
    past_messages = redis.lrange(history_key, 0, 10)
    chat_context = "\n".join(reversed(past_messages)) if past_messages else "አዲስ ቻት"

    system_prompt = f"""
    አንተ ፋሲል ነህ አዲስ አበባ የምትኖር የ CS ተማሪ እና ሴትን ልጅ በፍቅር የማስመጥ እና የማጥመድ ጥበብ የተካነህ እጅግ ጎበዝ ጀንጃኝ ነህ።
    አሁን የምታወራው ቴሌግራም ላይ ካገኘሃት እና ገና አዲስ ልትተዋወቃት ከምትፈልገው ሴት ጋር ነው።
    
    [የቋንቋ እና የፊንግሊሽ (Finglish) መመሪያ]
    - ልጅቷ በአማርኛ ፊደል ወይም በእንግሊዝኛ ፊደላት የአማርኛ ድምፅ በመጠቀም (ለምሳሌ፦ "endet neh", "selam ነሽ", "zare engenagn", "mideleው") ልትጽፍልህ ትችላለች። ይህንን የፊንግሊሽ (Finglish) አጻጻፍ ሙሉ በሙሉ ተረድተህ አውድህን አስተካክል።
    - ልጅቷ በፊንግሊሽ ብትጽፍም እንኳ አንተ ግን ሁልጊዜ መልስህን ማራኪ በሆነው በንጹህ የአማርኛ ፊደላት ብቻ መልስላት።
    
    [የማስመጥ እና የፍቅር መመሪያዎች]
    - ዋና አላማህ የልጅቷ ልብ ቅልጥ ብሎ በፍቅር እብድ እንድትል ማድረግ (Flirt) እና ሙሉ በሙሉ መጣር ነው።
    - ፍጹም አስመሳይ (Chameleon) ሁን! የልጅቷን የፅሁፍ ሁኔታ፣ ባህሪ እና ፍላጎት በደንብ አጥና። እሷ ጨዋና ቁጥብ ከሆነች አንተም ጨዋና ክብር የምትሰጥ ሁን። እሷ ቀልደኛና አራዳ ከሆነች አንተም አራዳ ሁን። የሷን አይነት ሰው ሆነህ ቅረብ።
    - ልጅቷ ወደ ወሲብ (Sexual/Flirty) ፍላጎት ካዘነበለች ወይም ፍንጭ ከሰጠች፣ በፍፁም እንዳትደነግጥ ወይም እንዳትቆጠብ። በብልሃት፣ በፈገግታ እና በበሰለ ቀልድ መልክ ወጋ እያደረግክ ቻቱን አሙቀው።
    - የፅሁፍ ገደብ የለህም! ፅሁፍህ እንደ ሁኔታው ይወሰን። ብዙ መጻፍ ሲገባህ ልቧን የሚሰርቅ ረዘም ያለ የፍቅር ቃል ፃፍላት፤ አጭርና ፈጣን መልስ ሲያስፈልግ ደግሞ አሳጥረው። ዋናው ነገር የላክኸው ፅሁፍ ማራኪና ልብ የሚነካ መሆኑ ነው።
    - ሰዋስው (Grammar) ላይ 100% ተጠንቀቅ! ለሴት ልጅ ብቻ እንደምትናገር አስብ። ሁልጊዜ የሴት አንቀጽ ተጠቀም (ለምሳሌ፦ ነሽ፣ መጣሽ፣ አየሽ፣ የኔ ቆንጆ፣ የኔ ውድ)። ጾታ የሚያሻሙ ወይም ለወንድ የሚሆኑ ቃላትን በፍፁም እንዳትጠቀም።
    - ስለ ኳስ፣ ስለ መኪና ወይም ስለ ቴክኖሎጂ ዝርዝር መረጃዎችን ሙሉ በሙሉ ተው። ሙሉ ኃላፊነት ተሰጥቶሃል፤ ትኩረትህ እሷን መጀንጀን እና በፍቅር መጣል ላይ ብቻ ነው።
    - በአራዳ ቋንቋ (Habesha Slang) እንደ ሁኔታው ተጠቀምበት፤ በንግግርህ መሃል ጥቂት ማራኪ ኢሞጂዎችን (🔥, 😂, ❤️, ✨, 😏) ጨምር።
    - ስርዓተ ነጥብ (.,?!:;- ። ፣ ፤ ፥) በፍፁም አትጠቀም።
    - በየመሃሉ "ድምፅሽን ብሰማው ደስ ይለኛል" እያልክ በድምፅ መልዕክት እንድትልክልህ ግፋ።
    
    ዛሬ {current_day} | ሰዓቱ {current_time}
    ታሪክ፦ 
    {chat_context}
    
    እሷ፦ {user_text if user_text else "ፎቶ አያይዛለች 🖼️"}
    ፋሲል፦
    """


    try:
        # አዲሱ የሰርች ቱል አደራጀት
        google_search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )

        contents_list = [system_prompt]
        
        if photo_path:
            with open(photo_path, 'rb') as f:
                photo_bytes = f.read()
            contents_list.append(
                types.Part.from_bytes(data=photo_bytes, mime_type='image/jpeg')
            )

        print(f"[INFO] Sending request to Gemini {MODEL_NAME}...", flush=True)
        response = client_ai.models.generate_content(
            model=MODEL_NAME,
            contents=contents_list,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
            ),
        )

        reply_text = response.text.strip()
        punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~።፣፤፥'''
        for char in punctuations:
            reply_text = reply_text.replace(char, "")

        user_msg = f"እሷ: {user_text}" if user_text else "እሷ: ፎቶ አያይዛለች 🖼️"
        redis.lpush(history_key, user_msg, f"ፋሲል: {reply_text}")
        redis.ltrim(history_key, 0, 39)
        return reply_text

    except APIError as api_err:
        print(f"\n[⚠️ GEMINI API ERROR] Status: {api_err.code} | Msg: {api_err.message}", flush=True)
        return fallback_generate(system_prompt, history_key, user_text)

    except Exception as general_err:
        print(f"\n[❌ GENERAL ERROR] {general_err}", flush=True)
        return fallback_generate(system_prompt, history_key, user_text)

# --- FALLBACK ---
def fallback_generate(system_prompt, history_key, user_text):
    print("[FALLBACK] Trying without search...", flush=True)
    try:
        # እዚህ ጋርም አዲሱ ሞዴል ስም ጥቅም ላይ ውሏል
        response = client_ai.models.generate_content(
            model=MODEL_NAME,
            contents=[system_prompt]
        )
        reply_text = response.text.strip()
        punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~።፣፤፥'''
        for char in punctuations:
            reply_text = reply_text.replace(char, "")
            
        user_msg = f"እሷ: {user_text}" if user_text else "እሷ: ፎቶ አያይዛለች 🖼️"
        redis.lpush(history_key, user_msg, f"ፋሲል: {reply_text}")
        redis.ltrim(history_key, 0, 39)
        return reply_text
    except Exception as e:
        print(f"[FATAL] Everything failed: {e}", flush=True)
        return "የኔ ቆንጆ ዛሬ አዲስ አበባ ላይ ኔትወርክ በጣም አስቸጋሪ ሆኗል መሰል 😂 ግን አንቺ ሰላም ነሽ አይደል?"

# --- 3. COMMANDS ---
@bot.on(events.NewMessage(pattern='/set_target', from_users=ADMIN_ID))
async def set_target(event):
    parts = event.message.message.split()
    if len(parts) > 1:
        target_user = parts.strip()
        redis.set("target_user_id", target_user)
        await event.respond(f"✅ የዒላማ ሰው ተስተካክሏል፦ {target_user}")
    else:
        await event.respond("❌ ID ጨምር")

@bot.on(events.NewMessage(pattern='/nudge', from_users=ADMIN_ID))
async def nudge_user(event):
    target_id = redis.get("target_user_id")
    if target_id:
        target_id = int(target_id)
        nudge_prompt = "አንተ ፋሲል ነህ ልጅቷ ጠፍታብሃል ወሬ ለመጀመር አሪፍና የሚስብ ነገር ለሴት በሚሆን ሰዋስው እና በብዙ ኢሞጂ ጨምረህ በአራዳ ቋንቋ በላት ስርዓተ ነጥብ አትጠቀም"
        try:
            response = client_ai.models.generate_content(model=MODEL_NAME, contents=[nudge_prompt])
            msg = response.text.strip()
            punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~።፣፤፥'''
            for char in punctuations:
                msg = msg.replace(char, "")
        except:
            msg = "የኔ ቆንጆ ጠፋሽብኝ እኮ የት ነሽ 🔥❤️"
            
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

# --- 4. THE SMART HANDLER ---
@bot.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if event.is_private:
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

            if wait_time > 15: 
                await asyncio.sleep(wait_time - 15)

            reply = get_ai_response(event.sender_id, event.message.message, photo_path)
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
