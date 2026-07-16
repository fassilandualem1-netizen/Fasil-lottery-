# games/real_sports.py
from flask import Blueprint, request, jsonify, render_template
import time
import json
from config import (
    redis, telegram_auth_required, deduct_balance_safely, add_to_history, ADMIN_ID, bot
)

real_sports_bp = Blueprint('real_sports', __name__)

@real_sports_bp.route('/real_sports')
def real_sports_page():
    return render_template('real_sports.html')

@real_sports_bp.route('/api/sports/bet', methods=['POST'])
@telegram_auth_required
def place_real_sports_bet():
    data = request.json or {}
    user_id = data.get("user_id")
    match_detail = data.get("match")      # ለምሳሌ "Chelsea vs Arsenal"
    bet_on = data.get("bet_on")          # "Chelsea Win"
    odds = float(data.get("odds", 1.85))
    bet_amount = float(data.get("bet_amount", 0))
    game_mode = data.get("game_mode", "real")

    if not user_id or bet_amount <= 0 or not match_detail or not bet_on:
        return jsonify({"status": "error", "message": "የውርርድ መረጃው አልተሟላም"}), 400

    if game_mode == "demo":
        return jsonify({"status": "error", "message": "በዴሞ አካውንት እውነተኛ ስፖርቶችን መወራረድ አይቻልም!"}), 400

    deduct_status = deduct_balance_safely(user_id, bet_amount, "real")
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400

    bet_ticket_id = f"ticket:{int(time.time())}:{user_id[:4]}"
    
    # ለወደፊቱ አድሚኑ ማጽደቅ ወይም መሰረዝ እንዲችል መረጃውን ሪዲስ ላይ ማስቀመጥ
    ticket_data = {
        "ticket_id": bet_ticket_id,
        "user_id": user_id,
        "match": match_detail,
        "bet_on": bet_on,
        "odds": odds,
        "amount": bet_amount,
        "status": "pending"
    }
    redis.set(f"sport_ticket:{bet_ticket_id}", json.dumps(ticket_data))

    add_to_history(user_id, {
        "tx_id": bet_ticket_id,
        "type": f"Sport Ticket: {bet_on}",
        "amount": bet_amount,
        "status": "pending",
        "date": time.strftime("%Y-%m-%d %H:%M")
    })

    # ለአድሚን ኖቲፊኬሽን መላክ (ለእጅ ክትትል እንዲያመች)
    admin_msg = f"⚽ <b>አዲስ ስፖርት ውርርድ ቲኬት</b>\n\n👤 ተጠቃሚ: {user_id}\n🎫 ID: <code>{bet_ticket_id}</code>\n🏟️ ጨዋታ: <b>{match_detail}</b>\n🎯 ምርጫ: <b>{bet_on} (Odds: {odds})</b>\n💵 መጠን: <b>{bet_amount} ብር</b>"
    try:
        bot.send_message(ADMIN_ID, admin_msg)
    except Exception as e:
        print(f"Failed sending ticket notify to admin: {e}")

    return jsonify({
        "status": "success",
        "ticket_id": bet_ticket_id,
        "message": "ቲኬትዎ ተመዝግቧል! እንደ ጨዋታው ማጠናቀቂያ በአድሚን ይረጋገጣል።"
    })
