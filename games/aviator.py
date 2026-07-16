# games/aviator.py
from flask import Blueprint, render_template, request, jsonify
import random
import time
from config import (
    redis, telegram_auth_required, deduct_balance_safely, add_to_history
)

aviator_bp = Blueprint('aviator', __name__)

# አቪዬተር የሚነሳበትና የሚከሽፍበት (Crash) ሰዓት መቆጣጠሪያ ሎጂክ
def generate_multiplier():
    # 90% ጊዜ ከ 1.01 በላይ ይሄዳል፣ 10% ጊዜ ግን 1.00 ላይ ወዲያው ይከሽፋል (Instant Crash)
    if random.random() < 0.10:
        return 1.00
    return round(random.uniform(1.01, 10.0), 2)

@aviator_bp.route('/aviator_game')
def aviator_page():
    return render_template('aviator.html')

@aviator_bp.route('/api/aviator/bet', methods=['POST'])
@telegram_auth_required
def place_aviator_bet():
    data = request.json or {}
    user_id = data.get("user_id")
    bet_amount = float(data.get("bet_amount", 0))
    game_mode = data.get("game_mode", "real")

    if not user_id or bet_amount <= 0:
        return jsonify({"status": "error", "message": "ትክክለኛ ውርርድ አላስገቡም"}), 400

    deduct_status = deduct_balance_safely(user_id, bet_amount, game_mode)
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
    
    # የውርርድ መታወቂያ ፈጥረን በሪዲስ እናስቀምጣለን
    round_id = f"av_round:{user_id}:{int(time.time())}"
    redis.setex(f"bet:{user_id}", 300, f"{bet_amount}|{game_mode}|{round_id}")

    return jsonify({"status": "success", "round_id": round_id, "message": "ውርርድዎ ተመዝግቧል፤ በረራውን ይጀምሩ!"})

@aviator_bp.route('/api/aviator/cashout', methods=['POST'])
@telegram_auth_required
def aviator_cashout():
    data = request.json or {}
    user_id = data.get("user_id")
    cashout_multiplier = float(data.get("multiplier", 1.0))

    bet_data = redis.get(f"bet:{user_id}")
    if not bet_data:
        return jsonify({"status": "error", "message": "ገቢር የሆነ ውርርድ አልተገኘም!"}), 400

    bet_amount, game_mode, round_id = bet_data.decode('utf-8').split('|')
    bet_amount = float(bet_amount)

    # አዲሱን የዕድል መጠን እንወስናለን
    final_crash = generate_multiplier()
    redis.delete(f"bet:{user_id}")  # ውርርዱን እናጠፋለን

    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"

    if cashout_multiplier <= final_crash:
        # አሸንፏል!
        win_amount = round(bet_amount * cashout_multiplier, 2)
        redis.hincrbyfloat(balance_key, user_id, win_amount)
        new_balance = float(redis.hget(balance_key, user_id) or 0.0)

        add_to_history(user_id, {
            "type": f"Aviator Cashout @ {cashout_multiplier}x [{game_mode.upper()}]",
            "amount": bet_amount,
            "status": "completed",
            "date": time.strftime("%Y-%m-%d %H:%M")
        })

        return jsonify({
            "status": "win",
            "crash_multiplier": final_crash,
            "win_amount": win_amount,
            "new_balance": new_balance,
            "message": f"እንኳን ደስ አለዎት! በ {cashout_multiplier}x ወጥተዋል!"
        })
    else:
        # ተሸንፏል (ፕሌኑ ከርሱ ቀድሞ ክራሽ አድርጓል)
        new_balance = float(redis.hget(balance_key, user_id) or 0.0)

        add_to_history(user_id, {
            "type": f"Aviator Crashed @ {final_crash}x [{game_mode.upper()}]",
            "amount": bet_amount,
            "status": "failed",
            "date": time.strftime("%Y-%m-%d %H:%M")
        })

        return jsonify({
            "status": "lose",
            "crash_multiplier": final_crash,
            "new_balance": new_balance,
            "message": f"አውሮፕላኑ በ {final_crash}x ላይ ተከስክሷል!"
        })
