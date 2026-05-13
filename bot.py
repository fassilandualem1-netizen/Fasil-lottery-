import os
import threading
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from upstash_redis import Redis

# Configuration (ከ Render Environment Variables የሚነበብ)
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
REDIS_URL = os.getenv("REDIS_URL")
REDIS_TOKEN = os.getenv("REDIS_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# Initializations
bot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond("<b>ሰላም ፋሲል!</b> ቦቱ በትክክል እየሰራ ነው።")

if __name__ == "__main__":
    # Flaskን በሌላ Thread ማስነሳት
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("ቦቱ እየሰራ ነው...")
    bot.start()
    bot.run_until_disconnected()
