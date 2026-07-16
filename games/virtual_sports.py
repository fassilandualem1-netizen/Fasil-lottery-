# games/virtual_sports.py
from flask import Blueprint, request, jsonify, render_template
import random
import time
from config import (
    redis, telegram_auth_required, deduct_balance_safely, add_to_history
)

virtual_sports_bp = Blueprint('virtual_sports', __name__)

@virtual_sports_bp.route('/virtual_sports')
def virtual_sports_page():
    return render_template('virtual_sports.html')

@virtual_sports_bp.route('/api/virtual/matches', methods=['GET'])
def get_virtual_matches():
    # በዘፈቀደ የሚፈጠሩ የቨርቹዋል እግር ኳስ ጨዋታዎች
    teams = ["Arsenal", "Chelsea", "Man Utd", "Man City", "Liverpool", "Real Madrid", "Barcelona", "Bayern"]
    matches = []
    selected_teams = random.sample(teams, 4)
    
    matches.append({
        "match_id": "v_match_1",
        "home": selected_teams[0],
        "away": selected_teams[1],
        "odds": {"home_win": 1.9, "draw": 3.10, "away_win": 2.8}
    })
    matches.append({
        "match_id": "v_match_2",
        "home": selected_teams[2],
        "away": selected_teams[3],
        "odds": {"home_win": 1.5, "draw": 3.8, "away_win": 4.5}
    })
    return jsonify({"status": "success", "matches": matches})

@virtual_sports_bp.route('/api/virtual/bet', methods=['POST'])
@telegram_auth_required
def place_virtual_bet():
    data = request.json or {}
    user_id = data.get("user_id")
    match_id = data.get("match_id")
    bet_on = data.get("bet_on")  # 'home_win', 'draw', 'away_win'
    bet_amount = float(data.get("bet_amount", 0))
    game_mode = data.get("game_mode", "real")

    if not user_id or bet_amount <= 0 or not match_id or not bet_on:
        return jsonify({"status": "error", "message": "የውርርድ መረጃው አልተሟላም"}), 400

    deduct_status = deduct_balance_safely(user_id, bet_amount, game_mode)
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400

    # አስመስለን ውጤቱን በፍጥነት እንወስናለን (ቀጥታ ሲሙሌሽን)
    results_choices = ["home_win", "draw", "away_win"]
    # በዕድል 50% ሆም ዊን፣ 30% ድሮው፣ 20% አዌይ ዊን
    actual_result = random.choices(results_choices, weights=[0.5, 0.3, 0.2], k=1)[0]
    
    # ቀላል የኦድስ ሰንጠረዥ
    odds_map = {"home_win": 2.0, "draw": 3.2, "away_win": 2.7}
    odd = odds_map.get(bet_on, 1.5)

    did_win = (bet_on == actual_result)
    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"

    if did_win:
        win_amount = round(bet_amount * odd, 2)
        redis.hincrbyfloat(balance_key, user_id, win_amount)
        status_str = "completed"
    else:
        win_amount = 0
        status_str = "failed"

    new_balance = float(redis.hget(balance_key, user_id) or 0.0)

    add_to_history(user_id, {
        "type": f"Virtual Bet ({bet_on.upper()}) [{game_mode.upper()}]",
        "amount": bet_amount,
        "status": status_str,
        "date": time.strftime("%Y-%m-%d %H:%M")
    })

    return jsonify({
        "status": "win" if did_win else "lose",
        "actual_result": actual_result,
        "win_amount": win_amount,
        "new_balance": new_balance
    })
