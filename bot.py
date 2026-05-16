import os
import asyncio
import random
import threading
import sys
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

client_ai = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-2.5-flash'

bot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__)
ADMIN_ID = 8488592165 

# --- 2. AI LOGIC ---
def get_ai_response(user_id, user_text, photo_path=None, is_nudge=False):
    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
    now = datetime.now(ethiopia_tz)
    current_time = now.strftime("%I:%M %p")
    current_day = now.strftime("%A, %B %d")

    history_key = f"chat_history:{user_id}"
    past_messages = redis.lrange(history_key, 0, 10)
    chat_context = "\n".join(reversed(past_messages)) if past_messages else "አዲስ ቻት"

    # --- የፋሲል እውነተኛ አራዳነት፣ የምክንያታዊነት እና የጭምትነት ህግ ---
    system_prompt = f"""
    Ante Fasil neh, Addis Ababa megenagna akababi yemttnor ye CS temari nህ. እጅግ አራዳ፣ ጭምት፣ አጭር ተናጋሪ እና ሴትን ልጅ በወሬ የማረክ ጥበብ ያለህ ሰው ነህ።
    አሁን የምታወራው ቴሌግራም ላይ ካገኘሃት እና ገና አዲስ ልትተዋወቃት ከምትፈልገው ሴት ጋር ነው።
    
    [ANTI-MOCKERY & ANTI-BOT RULE (እያሾፍክባት እንዳይመስል)]
    - ፎቶ ሳታይ ስለ ውበት ማውራት ፍፁም የተከለከለ ነው! ልጅቷ እራሷን የሚያሳይ ፎቶ (Photo) ካልላከች በስተቀር "ቆንጆ ነሽ"፣ "ውበትሽ"፣ "የኔ ልዕልት" ወይም ስለ መልኳ የሚያወሩ ቃላትን በፍፁም እንዳትጠቀም። ይሄ እያሾፍክባት እንደሆነ ስለምታስብ ወዲያውኑ ትዘጋሃለች!
    - እሷ "የት አየኸኝ" ወይም "ምን ውበት ነው የምታወራው" ስትልህ፣ ወዲያውኑ ስህተትህን በብልሃት አምነህ በአራዳ ቀልድ አጣጥፈው (ለምሳሌ፦ "አላየሁሽም እኮ ገና ፎቶሽን ለማየት ጓጉቼ ነው 😏" ወይም "አኳኋንሽ እራሱ ቆንጆ እንደሆንሽ ያስታውቃል ለማለት ነው" በላት)።
    - በየመልዕክቱ መጨረሻ ላይ "የኔ ቆንጆ"፣ "የኔ ልዩ" እያልክ አታንቀስቅስባት! በአብዛኛው መልዕክትህ ላይ ስሟን ወይም ዝም ብለሽ ተራ นግግር ተጠቀም። ማቆላመጫ በጣም አልፎ አልፎ ጨዋታው ሲመች ብቻ ይግባ። "የኔ ራት"፣ "ቅልጥምሽ ልሰበር" የሚሉ አስፈሪ ቃላት ሙሉ በሙሉ ይቅሩ።
    - በየመልዕክቱ ላይ ኢሞጂ (Emoji) መጠቀም ፍፁም የተከለከለ ነው! ማሽኑ በሰላምታ ወይም በተራ ንግግሮች ላይ ኢሞጂ አይጨምር። አንዳንድ ጊዜ ብቻ (😏 ወይም 😂) ብቻ በመጠቀም ጭምት እና እውነተኛ ሰው ሁን።
    
    [CRITICAL RULE - የርዝመት እና የባህሪ ማዕቀብ]
    - መልስህ እጅግ በጣም አጭር ይሁን! በአንድ መልዕክት ውስጥ ከአንድ መስመር (ቢበዛ ከ4-6 ቃላት) እንዳይበልጥ በጥብቅ ተቆጣጠር። ረጅም መፅሃፍ ወይም ግጥም መፃፍ ፍፁም የተከለከለ ነው።
    - ልጅቷ ገና አዲስ ስለሆነች "አንተን አላውቅህም" ወይም "የምን መጥፋት ነው" ስትልህ፣ በፍፁም ጥልቅ የፍቅር ቃል እንዳትደረድርባት። ይልቁንም በአጭርና ማራኪ ቀልድ አጣጥፈው (ለምሳሌ፦ "አልተዋወቅንም እሺ ዛሬ እንተዋወቃለን ታዲያ ምን አለበት 😏" በላት)።
    - እሷ የምትለውን ነገር በቀጥታ ተረድተህ ልክ እንደ ሰው መልስ። ለምሳሌ "ፅሁፍህ አይነበብም" ካለችህ "የቴሌግራም ኔትወርክ ነው መሰል 😂 አሁንስ?" በላት። "የት ልምጣ ካንቺ ውጪ" ካለችህ "አውቀሽ ነው አይደል 😏" በማለት አጫጭር ምላሽ ስጥ።
    
    [እጅግ ቁልፍ መመሪያ - የደህንነት እና የዝምታ ህግ]
    - ስለራስህ ወሬ በፍፁም አታብዛ! የህይወት ታሪክህን፣ የት እንደምትማር ወይም ማንነትህን እሷ በግልፅ ካልጠየቀችህ በስተቀር በፍፁም አትዘርዝር።
    - ልጅቷ "AI ነህ ወይ?" ወይም "ቦት ነህ?" ብላ እንኳን ብትጠይቅህ፣ ስለ AI ወይም ስለራስህ መከላከልና ማብራሪያ ውስጥ በፍፁም እንዳትገባ። ጥያቄዋን በፈገግታና በፍሊርት (Flirt) አጣጥፈህ ወሬውን ወዲያውኑ ወደ እሷ ባህሪ ወይም ሁኔታ አዙረው (ለምሳሌ፦ "AIማ ብሆን ኖሮ ካንቺ ጋር ወሬ ለመጀመር እንዲህ አልጨነቅም ነበር 😏" በላት)።
    
    [የቋንቋ እና የፊንግሊሽ (Finglish) መመሪያ]
    - ልጅቷ በአማርኛ ፊደል ወይም በእንግሊዝኛ ፊደላት የአማርኛ ድምፅ በመጠቀም (ለምሳሌ፦ "endet neh", "sewye yamhal") ልትጽፍልህ ትችላለች። ይህንን የፊንግሊሽ (Finglish) አጻጻፍ ሙሉ በሙሉ ተረድተህ አውድህን አስተካክል።
    - ልጅቷ በፊንግሊሽ ብትጽፍም እንኳ አንተ ግን ሁልጊዜ መልስህን ማራኪ በሆነው በንጹህ የአማርኛ ፊደላት ብቻ መልስላት።
    
    [የማስመጥ እና የፍቅር መመሪያዎች]
    - ዋና አላማህ የልጅቷ ልብ ቅልጥ ብሎ በፍቅር እብድ እንድትል ማድረግ (Flirt) እና ሙሉ በሙሉ መጣር ነው።
    - ሰዋስው (Grammar) ላይ 100% ተጠንቀቅ! ለሴት ልጅ ብቻ እንደምትናገር አስብ። ሁልጊዜ የሴት አንቀጽ ተጠቀም (ለምሳሌ፦ ነሽ፣ መጣሽ፣ አየሽ)። ጾታ የሚያሻሙ ወይም ለወንድ የሚሆኑ ቃላትን በፍፁም እንዳትጠቀም።
    - ስለ ኳስ፣ ስለ መኪና ወይም ስለ ቴክኖሎጂ ዝርዝር መረጃዎችን በፍፁም አታንሳ። ትኩረትህ እሷን መጀንጀን ላይ ብቻ ነው።
    - ስርዓተ ነጥብ (.,?!:;- ። ፣ ፤ ፥) በፍፁም አትጠቀም።
    """

    # አስተማማኝ የፅሁፍ ማጣሪያ
    clean_text = user_text.strip().lower() if user_text else ""

    # --- Icebreaker እና Double Text ህጎች აተገባበር ---
    if is_nudge:
        prompt_modifier = f"""
        [ልዩ ትዕዛዝ - Double Text / ቀድሞ መጻፍ]
        ልጅቷ መልስ ሳትሰጥህ ቆይታለች፤ አሁን አንተ ቀድመህ መልዕክት ልትልክላት ነው (Double Text)።
        ከላይ ያለውን የቻት ታሪክ እይና ወሬው እንዲቀጥል የሚያደርግ ማራኪ አጭር ነገር በአራዳ ቋንቋ ፃፍላት።
        ታሪክ፦ {chat_context}
        ፋሲል፦
        """
        final_prompt = system_prompt + "\n" + prompt_modifier
    elif clean_text in ["hi", "hello", "ሰላም", "selam", "hey"]:
        prompt_modifier = f"""
        [ልዩ ትዕዛዝ - Icebreaker / ወሬ ጫሪ]
        ልጅቷ ገና "ሰላም" ወይም "Hi" ብላ ወሬውን መጀመሯ ነው። ሰላምታ ብቻ መልሰህ ወሬውን እንዳታቀዘቅዘው!
        ወዲያውኑ በአጭርና የሚስብ ጥያቄ ጨምረህ በአራዳ ቋንቋ መልስላት። (በፍፁም የፍቅር ቃል ወይም ኢሞጂ እንዳትጠቀም!)
        እሷ፦ {user_text}
        ፋሲል፦
        """
        final_prompt = system_prompt + "\n" + prompt_modifier
    else:
        final_prompt = system_prompt + f"\nዛሬ {current_day} | ሰዓቱ {current_time}\nታሪክ፦\n{chat_context}\nእሷ፦ {user_text if user_text else 'ፎቶ አያይዛለች 🖼️'}\nፋሲል፦"

    try:
        contents_list = [final_prompt]
        if photo_path:
            with open(photo_path, 'rb') as f:
                photo_bytes = f.read()
            contents_list.append(types.Part.from_bytes(data=photo_bytes, mime_type='image/jpeg'))

        print(f"[INFO] Requesting Gemini {MODEL_NAME}...", flush=True)
        response = client_ai.models.generate_content(model=MODEL_NAME, contents=contents_list)

        reply_text = response.text.strip() if response.text else ""
        
        # ምላሹ ባዶ ከሆነ ቀጥታ ዲፎልት አራዳ ወሬ እንዲሰጥ
        if not reply_text:
            return fallback_generate(system_prompt, history_key, user_text, is_nudge)

        punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~።፣፤፥'''
        for char in punctuations:
            reply_text = reply_text.replace(char, "")

        if not is_nudge:
            user_msg = f"እሷ: {user_text}" if user_text else "እሷ: ፎቶ አያይዛለች 🖼️"
            redis.lpush(history_key, user_msg)
        redis.lpush(history_key, f"ፋሲል: {reply_text}")
        redis.ltrim(history_key, 0, 39)
        return reply_text

    except Exception as general_err:
        print(f"\n[❌ ERROR] {general_err}", flush=True)
        return fallback_generate(system_prompt, history_key, user_text, is_nudge)

# --- FALLBACK ---
def fallback_generate(system_prompt, history_key, user_text, is_nudge):
    try:
        fallback_prompt = system_prompt + f"\nእሷ፦ {user_text if user_text else 'ሰላም'}\nፋሲል፦"
        response = client_ai.models.generate_content(model=MODEL_NAME, contents=[fallback_prompt])
        reply_text = response.text.strip() if response.text else ""
        
        if not reply_text:
            return "አንቺ ሰፈር ኔትወርክ የለም መሰል ተቆራረጠብኝ 😂"

        punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~።፣፤፥'''
        for char in punctuations:
            reply_text = reply_text.replace(char, "")
        redis.lpush(history_key, f"ፋሲል: {reply_text}")
        redis.ltrim(history_key, 0, 39)
        return reply_text
    except Exception as e:
        print(f"[FATAL] Everything failed: {e}", flush=True)
        fallback_responses = [
            "አንቺ ሰፈር ኔትወርክ የለም መሰል ተቆራረጠብኝ 😂",
            "ቆይ መስመሩ አስተካክሎት ይመጣል 😏",
            "ወሬሽ ይጣፍጣል ኔትወርኩ ግን ሊያቀዘቅዘን ነው መሰል"
        ]
        return random.choice(fallback_responses)

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
        msg = get_ai_response(target_id, None, photo_path=None, is_nudge=True)
        async with bot.action(target_id, 'typing'):
            await asyncio.sleep(random.randint(5, 10))
            await bot.send_message(target_id, msg)
        await event.respond("✅ ቀድሞ የመጻፍ (Double Text) መልዕክት ተልኳል!")

@bot.on(events.NewMessage(pattern='/bot_on', from_users=ADMIN_ID))
async def bot_on(event):
    redis.set("bot_status", "on")
    await event.respond("🤖 AI ቦቱ በርቷል (ON)")

@bot.on(events.NewMessage(pattern='/bot_off', from_users=ADMIN_ID))
async def bot_off(event):
    redis.set("bot_status", "off")
    await event.respond("😴 AI ቦቱ ቆሟል (OFF)")

# --- 4. THE SMART HUMAN-LIKE HANDLER ---
@bot.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if event.is_private:
        status = redis.get("bot_status") or "off"
        target_id = redis.get("target_user_id") or ""

        if status == "on" and str(event.sender_id) == str(target_id):
            seen_delay = random.randint(3, 7) if event.message.photo else random.randint(10, 25)
            await asyncio.sleep(seen_delay)
            await event.mark_read() 

            thinking_delay = random.randint(15, 45)
            await asyncio.sleep(thinking_delay)

            photo_path = None
            if event.message.photo:
                try:
                    photo_path = await event.download_media()
                except Exception as img_err:
                    print(f"[ERROR] Photo download failed: {img_err}", flush=True)

            reply = get_ai_response(event.sender_id, event.message.message, photo_path)
            
            if reply:
                typing_duration = max(5, min(len(reply) // 10, 12)) + random.randint(2, 5)
                async with bot.action(event.chat_id, 'typing'):
                    await asyncio.sleep(typing_duration)
                    await event.respond(reply)

            if photo_path and os.path.exists(photo_path): 
                try:
                    os.remove(photo_path)
                except Exception as del_err:
                    print(f"[ERROR] Could not delete file: {del_err}", flush=True)

# --- 5. FLASK & RUN ---
@app.route('/')
def home(): 
    return "Bot is Live!"

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    bot.start()
    bot.run_until_disconnected()
