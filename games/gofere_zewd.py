# games/gofere_zewd.py
from flask import Blueprint, request, jsonify, render_template
import random
import time
from config import (
    redis, deduct_balance_safely, add_to_history, add_balance_safely
)

gofere_zewd_bp = Blueprint('gofere_zewd', __name__)

@gofere_zewd_bp.route('/coin_flip_game')
def coin_flip_page():
    return render_template('gofere_zewd.html')

@gofere_zewd_bp.route('/api/coin_flip', methods=['POST'])
def coin_flip_game():
    data = request.json or {}
    user_id = data.get("user_id")
    choice = data.get("choice")
    bet_amount = float(data.get("bet_amount", 0))
    game_mode = data.get("game_mode", "real")

    if not user_id or bet_amount <= 0 or not choice:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    deduct_status = deduct_balance_safely(user_id, bet_amount, game_mode)
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
    elif deduct_status == "ERROR":
        return jsonify({"status": "error", "message": "የሲስተም ስህተት ተከስቷል"}), 500

    sides = ["ዘውድ", "ጎፈር"]
    winning_side = random.choice(sides)
    did_win = (choice == winning_side)
    
    balance_key = "users:demo_balance" if game_mode == "demo" else "users:balance"
    
    if did_win:
        redis.hincrbyfloat(balance_key, user_id, bet_amount * 2)
        status_str = "completed"
        game_status = "win"
        msg = f"🎉 እንኳን ደስ አለዎት! {winning_side} ነው ወጥቷል! +{(bet_amount * 2)} ብር ተሰጥቶዎታል!"
    else:
        status_str = "failed"
        game_status = "lose"
        msg = f"😢 ይቅርታ! {winning_side} ነው ወጥቷል! -{bet_amount} ብር ተቀናጅ!"

    new_balance = float(redis.hget(balance_key, user_id) or 0.0)

    add_to_history(user_id, {
        "type": f"ዘውድና ጎፈር ({choice}) [{game_mode.upper()}]", 
        "amount": bet_amount, 
        "status": status_str,
        "date": time.strftime("%Y-%m-%d %H:%M")
    })

    return jsonify({
        "status": "success", 
        "game_status": game_status, 
        "result": winning_side, 
        "new_balance": new_balance,
        "message": msg
    })

@gofere_zewd_bp.route('/api/claim_daily_bonus', methods=['POST'])
def claim_daily_bonus():
    data = request.json or {}
    user_id = data.get("user_id")
    amount = float(data.get("amount", 0))

    if not user_id or amount <= 0:
        return jsonify({"status": "error", "message": "የጎደለ መረጃ አለ"}), 400

    # Add bonus balance
    add_balance_safely(user_id, amount, "የዕለቱ ቦነስ", "real")

    add_to_history(user_id, {
        "type": "የዕለቱ ቦነስ", 
        "amount": amount, 
        "status": "completed",
        "date": time.strftime("%Y-%m-%d %H:%M")
    })

    return jsonify({
        "status": "success", 
        "message": f"+{amount} ብር ተሰጥቶዎታል!"
    })
