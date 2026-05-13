import os
import asyncio
import random
import threading
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from upstash_redis import Redis

# --- 1. ውቅረት ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
REDIS_URL = os.getenv("REDIS_URL")
REDIS_TOKEN = os.getenv("REDIS_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# --- 2. ግንኙነቶች ---
bot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__)

# --- 3. ቦቱን በሜሴጅ መቆጣጠሪያ (ለአንተ ብቻ) ---
ADMIN_ID = 8488592165

@bot.on(events.NewMessage(pattern='/set_target', from_users=ADMIN_ID))
async def set_target(event):
    try:
        # መልዕክቱን በባዶ ቦታ ከፍሎ ሁለተኛውን ቃል (ID-ውን) ብቻ ይወስዳል
        parts = event.message.message.split()
        if len(parts) > 1:
            target_id = parts
            redis.set("target_user_id", target_id)
            await event.respond(f"✅ የዒላማ ሰው ID ወደ <code>{target_id}</code> ተቀይሯል።", parse_mode='html')
        else:
            await event.respond("❌ እባክህ ID ጨምር። ለምሳሌ፦ `/set_target 5122026260`")
    except Exception as e:
        await event.respond(f"❌ ስህተት፦ {e}")

@bot.on(events.NewMessage(pattern='/bot_on', from_users=ADMIN_ID))
async def bot_on(event):
    redis.set("bot_status", "on")
    await event.respond("🤖 ቦቱ አሁን ስራ ጀምሯል (ON)።")

@bot.on(events.NewMessage(pattern='/bot_off', from_users=ADMIN_ID))
async def bot_off(event):
    redis.set("bot_status", "off")
    await event.respond("😴 ቦቱ አሁን ቆሟል (OFF)።")

# --- 4. የ Smart Reply ሲስተም ---
@bot.on(events.NewMessage(incoming=True))
async def smart_reply(event):
    # ቦቱ ON መሆኑን ቼክ ያደርጋል
    status = redis.get("bot_status") or "off"
    target_id = redis.get("target_user_id")
    
    if status == "off" or str(event.sender_id) != str(target_id):
        return

    # መልዕክቱን አንብቦ "Typing..." እንዲያሳይ
    async with bot.action(event.chat_id, 'typing'):
        # ከ 30 ሰከንድ እስከ 4 ደቂቃ (240 ሰከንድ) በዘፈቀደ እንዲቆይ
        wait_time = random.randint(30, 240)
        print(f"ለ {wait_time} ሰከንድ እየቆየሁ ነው...")
        await asyncio.sleep(wait_time)
        
        # ምላሾች (እዚህ ጋ በ AI ወይም በዝርዝር መቀየር ይቻላል)
        responses = [
            "እንዴት ነሽ የኔ ቆንጆ? አሁን አየሁት።",
            "ሰላም ነው? ትንሽ ስራ ላይ ሆኜ ነው የቆየሁት።",
            "አንቺስ እንዴት ነሽ? ሁሉ ነገር ደህና?",
            "እሺ የኔ ውድ፣ ቆይቼ እደውላለሁ።"
        ]
        
        reply = random.choice(responses)
        await event.respond(reply)

# --- 5. Flask & Execution ---
@app.route('/')
def home(): return "Smart Bot is Live!"

def run_flask(): app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("ቦቱ በ Smart Mode ተነስቷል...")
    bot.start()
    bot.run_until_disconnected()
