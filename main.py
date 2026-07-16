# main.py
import eventlet
eventlet.monkey_patch()

import os
import time
from flask import Flask, render_template
from flask_socketio import SocketIO
from config import bot, TOKEN, WEB_APP_URL

# ብሉፕሪንቶቹን ከየራሳቸው ፋይሎች እናስገባለን
from games.chicken import chicken_bp
from games.keno import keno_bp
from games.sports import sports_bp

server = Flask(__name__)
socketio = SocketIO(server, cors_allowed_origins="*", async_mode='eventlet')

# ብሉፕሪንቶቹን በFlask ሰርቨር ላይ መመዝገብ (Registering Blueprints)
server.register_blueprint(chicken_bp)
server.register_blueprint(keno_bp)
server.register_blueprint(sports_bp)

# HTML ገጾች መሸጋገሪያ (Routing)
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/chicken')
def chicken_page():
    return render_template('chicken.html')

@server.route('/keno')
def keno_page():
    return render_template('keno.html')

@server.route('/sports')
def sports_page():
    return render_template('sports.html')

# ዌብሁክ እና ቴሌግራም ቦት ስታርት
@server.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    import flask
    json_string = flask.request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

@bot.message_handler(commands=['start'])
def send_welcome(message):
    from telebot.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
    web_app_info = WebAppInfo(url=WEB_APP_URL)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎮 Play Games", web_app=web_app_info))
    bot.reply_to(message, "👋 እንኳን ወደ ሰፈር ቦት በደህና መጡ! ለመጫወት ከታች ያለውን ቁልፍ ይጫኑ።", reply_markup=markup)

if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(0.1)
        bot.set_webhook(url=f"{WEB_APP_URL}/webhook/{TOKEN}")
        print("✅ Webhook setup was successful!")
    except Exception as e:
        print(f"❌ Webhook Setup Failed: {e}")
        
    socketio.run(server, host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
