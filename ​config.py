import os
import telebot
from upstash_redis import Redis

# ==========================================
# ⚙️ Configuration (ማዋቀሪያዎች)
# ==========================================
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_TOKEN = os.environ.get("REDIS_TOKEN")
WEB_APP_URL = "https://sefer-bot.onrender.com"
ADMIN_ID = 8488592165  # የአድሚን ቴሌግራም ID

# 🤖 የቴሌግራም ቦት ማስነሻ
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)

# 💾 የUpstash Redis ዳታቤዝ ግንኙነት
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
