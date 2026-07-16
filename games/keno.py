# games/keno.py
from flask import Blueprint, request, jsonify, render_template
import random
import time
from config import (
    redis, telegram_auth_required, deduct_balance_safely, add_to_history
)

keno_bp = Blueprint('keno', __name__)

@keno_bp.route('/keno_game')
def keno_page():
    return render_template('keno.html')

@keno_bp.route('/api/keno/play', methods=['POST'])
@telegram_auth_required
def play_keno():
    data = request.json or {}
    user_id = data.get("user_id")
    selected_numbers = data.get("numbers", [])  # ተጫዋቹ የመረጣቸው ከ 1 እስከ 10 የሚደርሱ ቁጥሮች
    bet_amount = float(data.get("bet_amount", 0))
    game_mode = data.get("game_mode", "real")

    if not user_id or bet_amount <= 0 or not (1 <= len(selected_numbers) <= 10):
        return jsonify({"status": "error", "message": "እባክዎ ከ 1 እስከ 10 ቁጥሮችን ይምረጡ"}), 400

    deduct_status = deduct_balance_safely(user_id, bet_amount, game_mode)
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400

    # ሲስተሙ 20 እድለኛ ቁጥሮችን ከ 1 እስከ 80 በዘፈቀደ ይመርጣል
    house_draw = random.sample(range(1, 81), 20)
    
    # ተጋጣሚ ቁጥሮች (Matches)
    matches = list(set(selected_numbers).intersection(house_draw))
    match_count = len(matches)

    # ቀላል የኬኖ ክፍያ ሎጂክ (Payout table)
    # ማባዣው በተገጣጠመው ቁጥር ብዛት ይወሰናል
    payout_table = {
        1: {1: 3.0},
        2: {1: 1.0, 2: 5.0},
        3: {1: 1.0, 2: 2.5, 3: 15.0},
        4: {2: 2.0, 3: 5.0, 4: 50.0},
        5: {2: 1.0, 3: 3.0, 4: 15.0, 5: 250.0},
        6: {3: 2.5, 4: 10.0, 5: 50.0, 6: 1000.0},
        7: {3: 1.0, 4: 5.0, 5: 15.0, 6: 150.0, 7: 5000.0},
        8: {4: 2.0, 5: 10.0, 6: 50.0, 7: 1000.0, 8: 10000.0},
        9: {4: 1.0, 5: 5.0, 6: 25.0, 7: 200.0, 8: 4000.0, 9: 25000.0},
        10: {5: 2.0, 6: 10.0, 7: 100.0, 8: 500.0, 9: 10000.0, 10: 50000.0}
    }

    selected_count = len(selected_numbers)
    multiplier = payout_table.get(selected_count, {}).get(match_count, 0.0)

    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    win_amount = round(bet_amount * multiplier, 2)

    if win_amount > 0:
        redis.hincrbyfloat(balance_key, user_id, win_amount)
        status_str = "completed"
    else:
        status_str = "failed"

    new_balance = float(redis.hget(balance_key, user_id) or 0.0)

    add_to_history(user_id, {
        "type": f"Keno ({match_count}/{selected_count} Matches) [{game_mode.upper()}]",
        "amount": bet_amount,
        "status": status_str,
        "date": time.strftime("%Y-%m-%d %H:%M")
    })

    return jsonify({
        "status": "success" if win_amount > 0 else "lose",
        "draw": house_draw,
        "matches": matches,
        "match_count": match_count,
        "multiplier": multiplier,
        "win_amount": win_amount,
        "new_balance": new_balance
    })
