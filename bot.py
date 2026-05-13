import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from flask import Flask
from upstash_redis import Redis
import threading

# --- 1. ውቅረት (Configuration) ---
# እነዚህን በ Render Environment Variables ላይ ትሞላቸዋለህ
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
REDIS_URL = os.getenv("REDIS_URL")
REDIS_TOKEN = os.getenv("REDIS_TOKEN")

ADMIN_IDS = (5690096145, 7072611117, 8488592165) # ያንተ አድሚን አይዲዎች
PORT = int(os.getenv("PORT", 8080))

# --- 2. ግንኙነቶች (Initializations) ---
bot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__)

# --- 3. የቦት ተግባራት (Bot Logic) ---
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    # መረጃ ከ Redis ለማንበብ ለምሳሌ
    user_id = str(event.sender_id)
    redis.set(f"user:{user_id}:last_seen", "now")
    await event.respond("<b>ሰላም ፋሲል!</b> ቦቱ ከ Upstash Redis ጋር ተገናኝቷል።")

# --- 4. Flask ለ Render 'Keep-Alive' ---
@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# --- 5. ማስነሳት (Execution) ---
if __name__ == "__main__":
    # Flaskን በሌላ Thread ማስነሳት (Render እንዳያጠፋው)
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("ቦቱ እየሰራ ነው...")
    bot.start()
    bot.run_until_disconnected()
