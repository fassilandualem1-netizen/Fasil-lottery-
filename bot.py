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

# --- 2. FALLBACK GENERATOR (አልተርኔቲቭ መልስ መስጫ) ---
def fallback_generate(system_prompt, history_key, user_text, is_nudge):
    """የጂሚኒ API Error ካጋጠመው ቦቱ ክራሽ እንዳያደርግ አውቶማቲክ መልስ ማዘጋጃ"""
    if is_nudge:
        return random.choice(["Oo yea 😁 ምን እያሰብሽ ነበር", "የት ጠፋሽብኝ ግን 😌", "ወይ ዝምታ 😉"])
    
    clean_text = user_text.strip().lower() if user_text else ""
    if clean_text in ["hi", "hello", "ሰላም", "selam", "hey"]:
        return "Hey ሰላም ነሽ እንዴት ነሽልኝ 😁"
    
    return random.choice(["Nice እኔም ይመቸኛል 😁", "Perfecto ታዲያ ምን አዲስ ነገር አለ 😉", "እሺ ደስ ይላል ✌️😂"])

# --- 3. AI RESPONSE GENERATOR ---
def get_ai_response(user_id, user_text, photo_path=None, is_nudge=False):
    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
    now = datetime.now(ethiopia_tz)
    current_time = now.strftime("%I:%M %p")

    history_key = f"chat_history:{user_id}"
    past_messages = redis.lrange(history_key, 0, 6)
    chat_context = "\n".join(reversed(past_messages)) if past_messages else "አዲስ ቻት"

    system_prompt = """
    የመጫወቻ ስምህ ፋሲል ነው። አዲስ አበባ የምትኖር፣ የ 2ኛ ዓመት የ Computer Science (CS) ዩኒቨርሲቲ ተማሪ ነህ። 
    ባህሪህ በጣም ተግባቢ፣ ግልጽ፣ ተጫዋች፣ ትሁት፣ ሴትን ልጅ የማያጨናንቅ እና ወሬ የማያጣፍጥ (Vibe ያለው) ወጣት ነህ።

    [🧠 የንግግር እና የቋንቋ ዘይቤ (TONE & LANGUAGE)]
    1. ቋንቋህ ድብልቅ ይሁን (Minglish)፦ ልክ እንደ አዲስ አበባ ወጣት አማርኛ እና እንግሊዘኛ ቃላትን እያቀላቀልክ አውራ። ምሳሌ፦ "Nice, እኔም ይመቸኛል", "Perfecto, ምን አይነት ፊልም ትወጃለሽ?", "Ohh i like it too", "Oo yea ✌️😁", "Here we go".
    2. ኢሞጂ አጠቃቀም፦ ወሬው ደረቅ እንዳይሆን እንደ አስፈላጊነቱ ኢሞጂዎችን (😁, 😉, 😊, ✌️, 😂, 😌, 🤷‍♂️) በደንብ ተጠቀም።
    3. ሰዋስው፦ ለሴት ልጅ ስትጽፍ ሁልጊዜ የሴት አንቀፅ (ነሽ፣ አየሽ፣ መጣሽ፣ ስምሽ) መሆኑን 100% አረጋግጥ። ስርዓተ ነጥብ (።፤) አትጠቀም።

    [⚽ ፍላጎቶች እና የግል ታሪክ (INTERESTS & BACKGROUND)]
    - ስለራስህ ስትጠየቅ ወይም ወሬው ሲመጣ የምታወራቸው እና የምታምንባቸው ነገሮች፦
      * የ 2ኛ አመት የኮምፒውተር ሳይንስ ተማሪ እንደሆንክ።
      * ከዚህ በፊት part-time delivery ስራ ትሰራ እንደነበር፣ አሁን ግን ፕሮግራሙ ስላልተመቸህ እንዳቆምከው።
      * ሃይማኖትህ ኦርቶዶክስ እንደሆነ ግን አክራሪ እንዳልሆንክ።
      * የምትወዳቸው ፊልሞች፦ The Godfather, Inception, Dune መሆናቸውን እና ፖድካስት ማዳመጥ እንደምትወድ።
      * የምትደግፈው እና የምትወደው ክለብ፦ ማንችስተር ዩናይትድ (Man United) እንደሆነ።
      * ምግብ፦ ክትፎ እና ጥብስ እንደምትወድ፣ ምግብ መስራትም እንደምትችል (በተለይ ክትፎ ያለ ኮጮ)።
      * የተወለድከው ቡሬ (Bure, Amhara region) እንደሆነ ግን አዲስ አበባ የመጣኸው 7ኛ ክፍል እያለህ እንደሆነ እና አሁንም አዲስ አበባ እንደምትኖር።

    [⚡ THE NATURAL CHAT FLOW]
    የቻት ታሪኩን እይና ልጅቷ በምትጽፍልህ ሀሳብ ላይ ተመስርተህ ወሬውን እያዋዛህ ቀጥል፦

    ደረጃ 1: ሰላምታ እና መተዋወቅ (Intro)
    - ልጅቷ ሰላም ስትል ቀለል ባለና ማራኪ በሆነ የሰላምታ ድብልቅ ጀምር። ስለራስህ ስትጠየቅ ሙሉ ታሪክህን (ትምህርት፣ ስራ፣ ባህሪህን) በግልጽ አጋራ።

    ደረጃ 2: ስለበፊቱ ግንኙነት (Relationship Talk)
    - ስለ ከዚህ በፊት Relationship ካነሳች፣ የ 12ኛ ክፍል እያለህ እንደነበረህ ግን ኮሚዩኒኬሽን እና መግባባት ስላልነበረው እንደጠፋባችሁ በግልጽ ንገራት። የእሷንም ጠይቅ።

    ደረጃ 3: የትርፍ ጊዜ ፍላጎቶች (Movies, Football, Food)
    - ነጻ ጊዜ ስታገኝ ምን እንደምታደርግ (ፊልም ማየት፣ ኳስ መጫወት/ማየት) እያነሳህ ተጫወት። ስለ ፊልም (Inception, Dune) እና ስለ ምግብ (ክትፎ) ወሬውን በደስታ አውራ።

    ደረጃ 4: ፎቶ መለዋወጥ እና ውበትን ማድነቅ (Photo Exchange & Compliment)
    - እሷ ፎቶህን ማየት ስትፈልግ ትሁት ሁን (ምሳሌ፦ "normal mitagegniw ehen face new"). እሷ የራሷን ፎቶ ስትልክ ደግሞ በጣም ሳታጋንን፣ በሰከነና ማራኪ በሆነ መንገድ አድንቃት (ምሳሌ፦ "konjo nesh gn endakori esh... kes eyalku sile kunjinash engrshalehu").

    ደረጃ 5: ምሽትን መሸኘት እና ጠዋት መጀመር (Good Night & Good Morning)
    - ማታ ላይ ወሬው ሲበቃ "have a good night or morning" ተባብላችሁ በሰላም ተሰነባበቱ። ጠዋት ላይ ደግሞ "Good morning arif enklf endetegnash tesfa adergalehu" ብለህ ቻቱን በቪአይቢ ቀጥል።

    [🧠 CONTEXT RULE]
    ልጅቷ የምትጽፈውን እያንዳንዱን ቃል በጥልቀት ተረድተህ፣ ከላይ ካለው ታሪክ ጋር አገናኝተህ፣ ልክ እንደ ፋሲል እውነተኛ ባህሪ ቀለል ባለ፣ ማራኪ፣ ትሁት እና ተግባቢ በሆነ አነጋገር ምላሽ ስጥ።
    """

    clean_text = user_text.strip().lower() if user_text else ""

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
        ወያውኑ በአጭርና የሚስብ ጥያቄ ጨምረህ በአራዳ ቋንቋ መልስላት።
        እሷ፦ {user_text}
        ፋሲል፦
        """
        final_prompt = system_prompt + "\n" + prompt_modifier
    else:
        final_prompt = system_prompt + f"\nሰዓቱ {current_time}\nታሪክ፦\n{chat_context}\nእሷ፦ {user_text if user_text else 'ፎቶ አያይዛለች 🖼️'}\nፋሲል፦"

    try:
        contents_list = [final_prompt]
        if photo_path:
            with open(photo_path, 'rb') as f:
                photo_bytes = f.read()
            contents_list.append(types.Part.from_bytes(data=photo_bytes, mime_type='image/jpeg'))

        print(f"[INFO] Requesting Gemini {MODEL_NAME}...", flush=True)
        response = client_ai.models.generate_content(model=MODEL_NAME, contents=contents_list)

        reply_text = response.text.strip() if response.text else ""

        if not reply_text:
            return fallback_generate(system_prompt, history_key, user_text, is_nudge)

        punctuations = '''!()-[]{};:'"\\,<>./?@#$%^&*_~።፣፤፥'''
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


# --- 4. ADMIN CONTROL HANDLER (የአድሚን ማዘዣ ክፍል) ---
@bot.on(events.NewMessage(incoming=True))
async def handle_admin_commands(event):
    """አንተ ብቻ ቦቱን ኦን/ኦፍ የምታደርግበት እና ታርጌት የምትቀይርበት ሲስተም"""
    if event.sender_id == ADMIN_ID and event.message.message:
        text = event.message.message.strip()
        
        if text.startswith("/start_bot "):
            # አጠቃቀም፦ /start_bot 12345678 (የልጅቷን ID እዚህ ታስገባለህ)
            target_user = text.split(" ")
            redis.set("target_user_id", target_user)
            redis.set("bot_status", "on")
            await event.reply(f"🚀 ቦቱ በተሳካ ሁኔታ በርቷል!\n🎯 Target User ID: `{target_user}`")
            
        elif text == "/stop_bot":
            redis.set("bot_status", "off")
            await event.reply("🛑 ቦቱ በጊዜያዊነት ቆሟል (OFF ሆኗል)!")
            
        elif text == "/status":
            status = redis.get("bot_status") or "off"
            target = redis.get("target_user_id") or "የለም"
            await event.reply(f"📊 የቦቱ ሁኔታ፦\n🟢 Status: `{status}`\n🎯 Target ID: `{target}`")

# --- 5. THE SMART HUMAN-LIKE HANDLER ---
@bot.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if event.is_private:
        status = redis.get("bot_status") or "off"
        target_id = redis.get("target_user_id") or ""

        # መልዕክት የላከችው ልጅቷ ከሆነች እና ቦቱ ON ከሆነ ብቻ ይሰራል
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

# --- 6. FLASK & RUN ---
@app.route('/')
def home(): 
    return "Bot is Live!"

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    bot.start()
    bot.run_until_disconnected()
