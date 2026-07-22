# games/chicken.py
from flask import Blueprint, request, jsonify, render_template
import random
import time
import json
from config import (
    redis, telegram_auth_required, deduct_balance_safely, add_to_history
)

chicken_bp = Blueprint('chicken', __name__)

@chicken_bp.route('/chicken_game')
def chicken_page():
    return render_template('chicken.html')

@chicken_bp.route('/api/chicken/start', methods=['POST'])
@telegram_auth_required
def start_chicken_game():
    data = request.json or {}
    user_id = data.get("user_id")
    bet_amount = float(data.get("bet_amount", 0))
    mines_count = int(data.get("mines", 5)) # ከ 1 እስከ 24 የሚደርሱ ቦምቦች
    game_mode = data.get("game_mode", "real")

    if not user_id or bet_amount <= 0 or not (1 <= mines_count <= 24):
        return jsonify({"status": "error", "message": "ያልተሟላ የጨዋታ ውቅር"}), 400

    deduct_status = deduct_balance_safely(user_id, bet_amount, game_mode)
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400

    # 25 ድስቶች (ከ 0 እስከ 24 ኢንዴክስ)
    # የትኛው ድስት ውስጥ ቦምብ/አጥንት (bone) እንደሚቀመጥ በዘፈቀደ መምረጥ
    all_tiles = list(range(25))
    bones = random.sample(all_tiles, mines_count)
    chickens = [t for t in all_tiles if t not in bones]

    game_session = {
        "user_id": user_id,
        "bet_amount": bet_amount,
        "mines_count": mines_count,
        "bones": bones,
        "chickens": chickens,
        "revealed": [],
        "game_mode": game_mode
    }
    
    # ሴሽኑን በሪዲስ ለ 15 ደቂቃ ማስቀመጥ
    redis.setex(f"chicken:{user_id}", 900, json.dumps(game_session))

    return jsonify({"status": "success", "message": "ጨዋታው ተጀምሯል! ድስቶቹን መክፈት ይችላሉ።"})

@chicken_bp.route('/api/chicken/reveal', methods=['POST'])
@telegram_auth_required
def reveal_tile():
    data = request.json or {}
    user_id = data.get("user_id")
    tile_index = int(data.get("tile", -1))

    if not user_id or not (0 <= tile_index <= 24):
        return jsonify({"status": "error", "message": "ትክክል ያልሆነ ድስት ቁጥር"}), 400

    session_data = redis.get(f"chicken:{user_id}")
    if not session_data:
        return jsonify({"status": "error", "message": "የተጀመረ ጨዋታ የለም"}), 400

    session = json.loads(session_data)
    
    if tile_index in session["revealed"]:
        return jsonify({"status": "error", "message": "ይህ ድስት ቀድሞ ተከፍቷል"}), 400

    # አጥንት (ቦምብ) ካገኘ
    if tile_index in session["bones"]:
        redis.delete(f"chicken:{user_id}")
        
        add_to_history(user_id, {
            "type": f"Chicken ({session['mines_count']} Mines) [{session['game_mode'].upper()}]",
            "amount": session["bet_amount"],
            "status": "failed",
            "date": time.strftime("%Y-%m-%d %H:%M")
        })

        return jsonify({
            "status": "gameover",
            "message": "💥 አጥንት አገኙ! ተሸንፈዋል!",
            "bones": session["bones"]
        })

    # ዶሮ ካገኘ
    session["revealed"].append(tile_index)
    
    # ቀጣይ የሚሆነው የሽልማት ማባዣ (Multiplier) ስሌት
    safe_clicked = len(session["revealed"])
    mines = session["mines_count"]
    # ፎርሙላ፡ (25-safe_clicked+1) / (25-safe_clicked-mines+1)
    # ይህ ፎርሙላ ለእያንዳንዱ ደህንነቱ ለተጠበቀ እርምጃ ፍትሃዊ ማባዣ ይሰጣል
    multiplier = 1.0
    for i in range(1, safe_clicked + 1):
        multiplier *= (26 - i) / (26 - i - mines)
    multiplier = round(multiplier, 2)

    redis.setex(f"chicken:{user_id}", 900, json.dumps(session))

    return jsonify({
        "status": "safe",
        "message": "🍗 ዶሮ አግኝተዋል!",
        "current_multiplier": multiplier,
        "next_multiplier": round(multiplier * (25 - safe_clicked) / (25 - safe_clicked - mines), 2)
    })

@chicken_bp.route('/api/chicken/cashout', methods=['POST'])
@telegram_auth_required
def chicken_cashout():
    data = request.json or {}
    user_id = data.get("user_id")

    session_data = redis.get(f"chicken:{user_id}")
    if not session_data:
        return jsonify({"status": "error", "message": "የተጀመረ ጨዋታ የለም"}), 400

    session = json.loads(session_data)
    safe_clicked = len(session["revealed"])

    if safe_clicked == 0:
        return jsonify({"status": "error", "message": "ቢያንስ አንድ ዶሮ ሳይከፍቱ መውጣት አይችሉም"}), 400

    mines = session["mines_count"]
    multiplier = 1.0
    for i in range(1, safe_clicked + 1):
        multiplier *= (26 - i) / (26 - i - mines)
    multiplier = round(multiplier, 2)

    win_amount = round(session["bet_amount"] * multiplier, 2)
    
    balance_key = "users:demo_balance" if session["game_mode"] == "demo" else "users:balance"
    redis.hincrbyfloat(balance_key, user_id, win_amount)
    new_balance = float(redis.hget(balance_key, user_id) or 0.0)

    redis.delete(f"chicken:{user_id}")

    add_to_history(user_id, {
        "type": f"Chicken ({mines} Mines) Cashout [{session['game_mode'].upper()}]",
        "amount": session["bet_amount"],
        "status": "completed",
        "date": time.strftime("%Y-%m-%d %H:%M")
    })

    return jsonify({
        "status": "success",
        "win_amount": win_amount,
        "new_balance": new_balance,
        "bones": session["bones"],
        "message": f"በአጠቃላይ {win_amount} ብር አሸንፈዋል!"
    })
