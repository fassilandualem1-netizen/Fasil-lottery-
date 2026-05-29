import os
import asyncio
import random
import threading
import sys
from flask import Flask
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession 
from upstash_redis import Redis
from google import genai
from google.genai import types
from datetime import datetime
import pytz

# --- 1. CONFIGURATION ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING") # የቴሌቶን String Session መሆን አለበት!
REDIS_URL = os.getenv("REDIS_URL")
REDIS_TOKEN = os.getenv("REDIS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 8080))

client_ai = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-2.5-flash'

# StringSessionን በመጠቀም አካውንቱን ማንሳት
bot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) 
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__)
ADMIN_ID = 8488592165 


# --- 2. FALLBACK GENERATOR ---
def fallback_generate(system_prompt, history_key, user_text, is_nudge):
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
    1. ቋንቋህ ድብልቅ ይሁን (Minglish)፦ ልክ እንደ አዲስ አበባ ወጣት አማርኛ እና እንግሊዘኛ ቃላትን እያቀላቀልክ አውራ።
    2. ኢሞጂ አጠቃቀም፦ እንደ አስፈላጊነቱ ኢሞጂዎችን (😁, 😉, 😊, ✌️, 😂, 😌, 🤷‍♂️) በደንብ ተጠቀም።
    3. ሰዋስው፦ ለሴት ልጅ ስትጽፍ ሁልጊዜ የሴት አንቀፅ (ነሽ፣ አየሽ) መሆኑን 100% አረጋግጥ።

    [⚽ ፍላጎቶች እና የግል ታሪክ]
    - የ 2ኛ አመት የኮምፒውተር ሳይንስ ተማሪ እንደሆንክ።
    - ከዚህ በፊት part-time delivery ስራ ትሰራ እንደነበር፣ አሁን ግን ፕሮግራሙ ስላልተመቸህ እንዳቆምከው።
    - ሃይማኖትህ ኦርቶዶክስ እንደሆነ፣ የምትወዳቸው ፊልሞች The Godfather, Inception, Dune መሆናቸውን።
    - ማንችስተር ዩናይትድ (Man United) እንደምትደግፍ፣ ክትፎ እና ጥብስ እንደምትወድ።
    - የተወለድከው ቡሬ እንደሆነ ግን አዲስ አበባ የመጣኸው 7ኛ ክፍል እያለህ እንደሆነ።

    [🧠 CONTEXT RULE]
    ልጅቷ የምትጽፈውን እያንዳንዱን ቃል በጥልቀት ተረድተህ፣ ከላይ ካለው ታሪክ ጋር አገናኝተህ፣ ልክ እንደ ፋሲል እውነተኛ ባህሪ ምላሽ ስጥ።
    """

    clean_text = user_text.strip().lower() if user_text else ""

    if is_nudge:
        prompt_modifier = f"\n[ልዩ ትዕዛዝ - Double Text] ልጅቷ መልስ ሳትሰጥህ ቆይታለች፤ ወሬው እንዲቀጥል የሚያደርግ ማራኪ አጭር ነገር በአራዳ ቋንቋ ፃፍላት።\nታሪክ፦ {chat_context}\nፋሲል፦"
        final_prompt = system_prompt + "\n" + prompt_modifier
    elif clean_text in ["hi", "hello", "ሰላም", "selam", "hey"]:
        prompt_modifier = f"\n[ልዩ ትዕዛዝ - Icebreaker] ልጅቷ ገና ሰላም ማለቷ ነው። ወዲያውኑ በአጭርና የሚስብ ጥያቄ ጨምረህ መልስላት።\nእሷ፦ {user_text}\nፋሲል፦"
        final_prompt = system_prompt + "\n" + prompt_modifier
    else:
        final_prompt = system_prompt + f"\nሰዓቱ {current_time}\nታሪክ፦\n{chat_context}\nእሷ፦ {user_text if user_text else 'ፎቶ አያይዛለች 🖼️'}\nፋሲል፦"

    try:
        contents_list = [final_prompt]
        if photo_path:
            with open(photo_path, 'rb') as f:
                photo_bytes = f.read()
            contents_list.append(types.Part.from_bytes(data=photo_bytes, mime_type='image/jpeg'))

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
        redis.lpush(history_key, f"ፋሲል: {reply_text.replace('[SEND_MY_PHOTO]', '')}")
        redis.ltrim(history_key, 0, 39)
        return reply_text
    except Exception:
        return fallback_generate(system_prompt, history_key, user_text, is_nudge)


# --- 4. ADMIN CONTROL HANDLER (Saved Messages) ---

async def get_admin_buttons():
    status = redis.get("bot_status") or "off"
    status_emoji = "🟢 ON" if status == "on" else "🔴 OFF"
    targets = redis.lrange("target_user_ids_list", 0, -1) or []
    
    buttons = [
        [
            Button.inline(f"የቦቱ ሁኔታ፦ {status_emoji}", data="toggle_status"),
            Button.inline("🔄 አድስ", data="refresh_panel")
        ]
    ]
    
    if targets:
        buttons.append([Button.inline("📋 የታርጌቶች ዝርዝር (ለመሰረዝ ❌ ይጫኑ)፦", data="none")])
        for t_id in targets:
            t_id_str = t_id.decode('utf-8') if isinstance(t_id, bytes) else str(t_id)
            buttons.append([
                Button.inline(f"👤 ID: {t_id_str}", data=f"view_{t_id_str}"),
                Button.inline("❌ Remove", data=f"remove_{t_id_str}")
            ])
    else:
        buttons.append([Button.inline("🤷‍♂️ በአሁኑ ሰዓት ምንም ታርጌት የለም", data="none")])
        
    return buttons

@bot.on(events.NewMessage(incoming=False)) 
async def handle_admin_commands(event):
    """አንተ በ Saved Messages ላይ /panel ስትል ብቻ ፓነሉን ያመጣል"""
    if event.sender_id == ADMIN_ID and event.is_private and event.chat_id == ADMIN_ID:
        text = event.message.message.strip()

        if text in ["/panel", "/start"]:
            await event.reply("🎛️ **የአድሚን መቆጣጠሪያ ፓነል (ሚስጥራዊ)**\n\nአዲስ ሰው ታርጌት ለማድረግ፦ `/set_target የሰውየው_ID` ብለህ እዚህ ላክ።", buttons=await get_admin_buttons())

        elif text.startswith("/set_target "):
            parts = text.split(" ")
            if len(parts) > 1:
                # [ባግ ፊክስ] አሁን ከሊስቱ ውስጥ ኢንዴክስ 1ን በትክክል መርጦ .strip() ያደርገዋል
                new_target = parts.strip()
                existing_targets = [t.decode('utf-8') if isinstance(t, bytes) else str(t) for t in redis.lrange("target_user_ids_list", 0, -1)]
                
                if new_target not in existing_targets:
                    redis.lpush("target_user_ids_list", new_target)
                    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
                    redis.set(f"last_chat_time:{new_target}", datetime.now(ethiopia_tz).isoformat())
                    await event.reply(f"✅ ID: `{new_target}` ወደ ታርጌት ዝርዝር ተጨምሯል!", buttons=await get_admin_buttons())
                else:
                    await event.reply(f"⚠️ ይህ ID (`{new_target}`) አስቀድሞ አለ!", buttons=await get_admin_buttons())

@bot.on(events.CallbackQuery)
async def handle_callback_queries(event):
    if event.sender_id != ADMIN_ID:
        return

    data = event.data.decode('utf-8')

    if data == "toggle_status":
        current_status = redis.get("bot_status") or "off"
        new_status = "off" if current_status == "on" else "on"
        redis.set("bot_status", new_status)
        await event.answer(f"ቦቱ {new_status.upper()} ሆኗል!")
        await event.edit("🎛️ **የአድሚን መቆጣጠሪያ ፓነል (ሚስጥራዊ)**", buttons=await get_admin_buttons())

    elif data == "refresh_panel":
        await event.answer("ታድሷል! 🔄")
        await event.edit("🎛️ **የአድሚን መቆጣጠሪያ ፓነል (ሚስጥራዊ)**", buttons=await get_admin_buttons())

    elif data.startswith("remove_"):
        target_to_remove = data.replace("remove_", "")
        redis.lrem("target_user_ids_list", 0, target_to_remove)
        await event.answer(f"❌ ID: {target_to_remove} ተሰርዟል!", alert=True)
        await event.edit("🎛️ **የአድሚን መቆጣጠሪያ ፓነል (ሚስጥራዊ)**", buttons=await get_admin_buttons())
        
    elif data.startswith("view_"):
        target_id = data.replace("view_", "")
        try:
            user_entity = await bot.get_entity(int(target_id))
            first_name = user_entity.first_name or "ስም የለም"
            username = f"@{user_entity.username}" if user_entity.username else "የለም"
            await event.answer(f"👤 {first_name} ({username})", alert=True)
        except:
            await event.answer(f"ID: {target_id} (የአካውንት መረጃው አልተገኘም)", alert=True)


# --- 5. THE SMART AUTOMATIC NUDGE SCHEDULER ---
async def nudge_scheduler_loop():
    while True:
        await asyncio.sleep(1800)
        status = redis.get("bot_status") or "off"
        
        if status == "on":
            raw_targets = redis.lrange("target_user_ids_list", 0, -1) or []
            target_ids = [t.decode('utf-8') if isinstance(t, bytes) else str(t) for t in raw_targets]

            for target_id in target_ids:
                last_time_str = redis.get(f"last_chat_time:{target_id}")
                if last_time_str:
                    last_time = datetime.fromisoformat(last_time_str)
                    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
                    now = datetime.now(ethiopia_tz)

                    if (now - last_time).total_seconds() > 21600:
                        reply = get_ai_response(target_id, user_text="", is_nudge=True)
                        if reply:
                            async with bot.action(int(target_id), 'typing'):
                                await asyncio.sleep(random.randint(5, 10))
                                await bot.send_message(int(target_id), reply)
                            redis.set(f"last_chat_time:{target_id}", now.isoformat())


# --- 6. THE SMART HUMAN-LIKE HANDLER ---
@bot.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if event.is_private:
        status = redis.get("bot_status") or "off"
        raw_targets = redis.lrange("target_user_ids_list", 0, -1) or []
        target_ids = [t.decode('utf-8') if isinstance(t, bytes) else str(t) for t in raw_targets]

        if status == "on" and str(event.sender_id) in target_ids:
            target_id = str(event.sender_id)
            ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
            redis.set(f"last_chat_time:{target_id}", datetime.now(ethiopia_tz).isoformat())

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
                should_send_photo = "[SEND_MY_PHOTO]" in reply
                clean_reply = reply.replace("[SEND_MY_PHOTO]", "").strip()

                if clean_reply:
                    typing_duration = max(5, min(len(clean_reply) // 10, 12)) + random.randint(2, 5)
                    async with bot.action(event.chat_id, 'typing'):
                        await asyncio.sleep(typing_duration)
                        await event.respond(clean_reply)

                if should_send_photo:
                    await asyncio.sleep(random.randint(3, 6))
                    async with bot.action(event.chat_id, 'document'):
                        if os.path.exists("my_profile.jpg"):
                            await bot.send_file(event.chat_id, "my_profile.jpg", caption="የድሮ ፎቶ ነው ግን 😁")
                        else:
                            await event.respond("normal face ነው ማታ እልክልሻለሁ አሁን ፎቶ የለኝም 🤷‍♂️")

            redis.set(f"last_chat_time:{target_id}", datetime.now(ethiopia_tz).isoformat())

            if photo_path and os.path.exists(photo_path): 
                try:
                    os.remove(photo_path)
                except Exception:
                    pass


# --- 7. FLASK & RUN ---
@app.route('/')
def home(): 
    return "Bot is Live!"

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()
    
    bot.start() 
    bot.run_until_disconnected()
