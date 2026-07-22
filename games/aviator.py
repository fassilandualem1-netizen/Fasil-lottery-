import time
import random
import math
from threading import Lock
from flask import Blueprint, request, jsonify, render_template
from config import (
    redis, deduct_balance_safely, add_to_history,
    telegram_auth_required, get_user_id_from_request,
)

aviator_bp = Blueprint('aviator', __name__)

_socketio = None

# ==========================================
# 🎮 1. የጨዋታው ማህደረ ትውስታ (In-Memory Game State)
# ==========================================
game_state = {
    "status": "WAITING",
    "multiplier": 1.00,
    "crash_point": 1.00,
    "start_time": 0,
    "round_id": 0,
    "history": []
}

current_round_bets = {}
next_round_bets = {}
generated_crashes = []
bet_lock = Lock()


def _is_user_banned(user_id):
    if not user_id:
        return False
    return redis.sismember("banned_users", str(user_id))


def _normalize_user_id(user_id):
    return str(user_id).strip()


def _get_balance_key(user_id):
    return _normalize_user_id(user_id)


# ==========================================
# 🧮 2. Crash Point Generation
# ==========================================
def generate_crash_point():
    house_edge = 0.03
    if random.random() < house_edge:
        return 1.00

    r = random.random()
    if r == 1.0:
        r = 0.99999

    crash_point = 1.0 / (1.0 - r)
    max_multiplier = 1000.00
    final_crash = round(crash_point, 2)
    return min(final_crash, max_multiplier)


def generate_500_crashes():
    global generated_crashes
    generated_crashes = [generate_crash_point() for _ in range(500)]


def get_next_crash():
    global generated_crashes
    if not generated_crashes:
        generate_500_crashes()
    return generated_crashes.pop(0)


# ==========================================
# 💸 3. የካሽ አውት ተግባር
# ==========================================
def process_cashout(user_id, multiplier):
    user_id_key = _normalize_user_id(user_id)
    user_bet = current_round_bets.get(user_id_key)

    if not user_bet:
        return 0, False

    if user_bet.get("round_id") != game_state.get("round_id"):
        return 0, False

    if user_bet.get("cashed_out"):
        return user_bet.get("win_amount", 0), False

    user_bet["cashed_out"] = True
    win_amount = round(user_bet["amount"] * multiplier, 2)
    user_bet["win_amount"] = win_amount

    redis.hincrbyfloat("users:balance", _get_balance_key(user_id_key), win_amount)
    add_to_history(user_id_key, {
        "type": "Aviator Win",
        "amount": win_amount,
        "multiplier": multiplier,
    })

    return win_amount, True


def _emit_player_cashout(user_id, win_amount, multiplier):
    if not _socketio:
        return

    user_id_key = _normalize_user_id(user_id)
    new_balance = _get_user_balance(user_id_key)

    _socketio.emit('player_cashout', {
        'user_id': user_id_key,
        'win_amount': win_amount,
        'multiplier': multiplier,
        'new_balance': new_balance,
    })


# ==========================================
# 🔄 4. የጨዋታው ሞተር (Background Game Loop)
# ==========================================
def start_aviator_loop(socketio):
    global _socketio
    _socketio = socketio
    generate_500_crashes()

    @socketio.on('request_aviator_state')
    def handle_state_request():
        time_left = 0
        if game_state["status"] == "WAITING":
            elapsed = time.time() - game_state.get("wait_start_time", time.time())
            time_left = max(0, 10 - elapsed)

        socketio.emit('game_state', {
            'status': game_state["status"],
            'time_left': time_left,
            'start_time': game_state.get("start_time", 0),
            'multiplier': game_state["multiplier"],
            'history': game_state["history"]
        }, to=request.sid)

    def loop():
        global current_round_bets, next_round_bets

        while True:
            try:
                # --- WAITING ---
                game_state["status"] = "WAITING"
                game_state["multiplier"] = 1.00
                game_state["wait_start_time"] = time.time()
                game_state["crash_point"] = get_next_crash()

                with bet_lock:
                    current_round_bets = next_round_bets.copy()
                    next_round_bets.clear()

                socketio.emit('game_state', {
                    'status': 'WAITING',
                    'time_left': 10,
                    'multiplier': 1.00,
                    'history': game_state["history"]
                })
                socketio.sleep(10)

                # --- FLYING ---
                game_state["status"] = "FLYING"
                game_state["start_time"] = time.time()

                socketio.emit('game_state', {
                    'status': 'FLYING',
                    'start_time': game_state["start_time"],
                    'multiplier': 1.00
                })

                crashed = False
                while not crashed:
                    socketio.sleep(0.05)
                    elapsed_time = time.time() - game_state["start_time"]

                    current_multi = round(math.exp(0.06 * elapsed_time), 2)

                    if current_multi >= game_state["crash_point"]:
                        current_multi = game_state["crash_point"]
                        crashed = True

                    game_state["multiplier"] = current_multi
                    socketio.emit('multiplier_update', {'multiplier': current_multi})

                    with bet_lock:
                        for uid, bet in list(current_round_bets.items()):
                            if (
                                not bet.get("cashed_out")
                                and bet.get("auto_cashout_val")
                                and bet.get("round_id") == game_state["round_id"]
                            ):
                                if current_multi >= bet["auto_cashout_val"]:
                                    try:
                                        win_amount, was_processed = process_cashout(uid, bet["auto_cashout_val"])
                                        if was_processed and win_amount > 0:
                                            _emit_player_cashout(uid, win_amount, bet["auto_cashout_val"])
                                    except Exception as ex:
                                        print(f"⚠️ Auto-Cashout Error for UID {uid}: {ex}")

                # --- CRASHED ---
                game_state["status"] = "CRASHED"
                game_state["multiplier"] = game_state["crash_point"]

                with bet_lock:
                    for uid, bet in list(current_round_bets.items()):
                        if not bet.get("cashed_out"):
                            add_to_history(uid, {
                                "type": "Aviator Loss",
                                "amount": bet["amount"],
                                "multiplier": game_state["crash_point"],
                            })

                game_state["history"].insert(0, game_state["crash_point"])
                if len(game_state["history"]) > 20:
                    game_state["history"].pop()

                try:
                    redis.lpush("aviator:history", game_state["crash_point"])
                    redis.ltrim("aviator:history", 0, 19)
                except Exception as e:
                    print(f"Redis History Error: {e}")

                socketio.emit('game_state', {
                    'status': 'CRASHED',
                    'crash_point': game_state["crash_point"],
                    'history': game_state["history"]
                })

                socketio.sleep(3)

            except Exception as e:
                print(f"🛑 Critical Aviator Loop Error: {e}")
                socketio.sleep(2)

    socketio.start_background_task(loop)


# ==========================================
# 📡 5. የውርርድ እና የካሽ አውት ኤፒአይ (Endpoints)
# ==========================================

@aviator_bp.route('/api/aviator/bet', methods=['POST'])
@telegram_auth_required
def place_bet():
    data = request.json or {}
    user_id = get_user_id_from_request()

    try:
        amount = float(data.get("bet_amount", 0))
        auto_cashout_val = float(data.get("auto_cashout", 0))
    except ValueError:
        return jsonify({"status": "error", "message": "የተሳሳተ የገንዘብ መጠን ፎርማት"}), 400

    if not user_id or amount < 10:
        return jsonify({"status": "error", "message": "ዝቅተኛው የውርርድ መጠን 10 ብር ነው"}), 400

    if _is_user_banned(user_id):
        return jsonify({"status": "error", "message": "አካውንትዎ ታግዷል!"}), 403

    user_id_key = _normalize_user_id(user_id)

    with bet_lock:
        if game_state["status"] == "WAITING":
            target_dict = current_round_bets
            round_type = "CURRENT"
            round_id = game_state.get("round_id", 0)
        else:
            target_dict = next_round_bets
            round_type = "NEXT"
            round_id = game_state.get("round_id", 0) + 1

        msg = "በአሁኑ ዙር ተሳትፈዋል!" if round_type == "CURRENT" else "ለውርርድ ለቀጣዩ ዙር ተመዝግበዋል!"

        if user_id_key in target_dict:
            return jsonify({"status": "error", "message": "በዚህ ዙር አስቀድመው ተወራርደዋል!"}), 400

        deduct_status = deduct_balance_safely(user_id_key, amount)
        if deduct_status == "INSUFFICIENT":
            return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400
        if deduct_status == "ERROR":
            return jsonify({"status": "error", "message": "ሲስተሙ ስራ በዝቶበታል"}), 500

        bet_data = {
            "amount": amount,
            "cashed_out": False,
            "auto_cashout_val": auto_cashout_val if auto_cashout_val > 1.00 else None,
            "round_id": round_id,
        }

        target_dict[user_id_key] = bet_data
        new_balance = _get_user_balance(user_id_key)

    return jsonify({
        "status": "success",
        "message": msg,
        "type": round_type,
        "new_balance": new_balance
    })


@aviator_bp.route('/api/aviator/cashout', methods=['POST'])
@telegram_auth_required
def manual_cashout():
    user_id = get_user_id_from_request()

    if not user_id:
        return jsonify({"status": "error", "message": "መረጃ የለም"}), 400

    if _is_user_banned(user_id):
        return jsonify({"status": "error", "message": "አካውንትዎ ታግዷል!"}), 403

    user_id_key = _normalize_user_id(user_id)

    with bet_lock:
        if game_state["status"] != "FLYING":
            return jsonify({"status": "error", "message": "አሁን Cash out ማድረግ አይችሉም!"}), 400

        current_multi = game_state["multiplier"]
        win_amount, was_processed = process_cashout(user_id_key, current_multi)

        if was_processed and win_amount > 0:
            new_balance = _get_user_balance(user_id_key)
            return jsonify({
                "status": "success",
                "win_amount": win_amount,
                "multiplier": current_multi,
                "new_balance": new_balance
            })
        elif not was_processed and win_amount > 0:
            return jsonify({"status": "error", "message": "ውርርድዎ አስቀድመው ተሰርቷል!"}), 400
        else:
            return jsonify({"status": "error", "message": "ውርርድ አልተገኘም ወይም አስቀድመው ወስደዋል"}), 400


@aviator_bp.route('/api/aviator/cancel_bet', methods=['POST'])
@telegram_auth_required
def cancel_bet():
    user_id = get_user_id_from_request()

    if not user_id:
        return jsonify({"status": "error", "message": "መረጃ የለም"}), 400

    if _is_user_banned(user_id):
        return jsonify({"status": "error", "message": "አካውንትዎ ታግዷል!"}), 403

    user_id_key = _normalize_user_id(user_id)

    with bet_lock:
        if user_id_key in next_round_bets:
            bet_amount = next_round_bets[user_id_key]["amount"]
            del next_round_bets[user_id_key]
            redis.hincrbyfloat("users:balance", _get_balance_key(user_id_key), bet_amount)
            new_balance = _get_user_balance(user_id_key)
            return jsonify({
                "status": "success",
                "message": "የቀጣይ ዙር ውርርድዎ ተሰርዟል!",
                "new_balance": new_balance,
            })

        if user_id_key in current_round_bets and game_state["status"] == "WAITING":
            bet_amount = current_round_bets[user_id_key]["amount"]
            del current_round_bets[user_id_key]
            redis.hincrbyfloat("users:balance", _get_balance_key(user_id_key), bet_amount)
            new_balance = _get_user_balance(user_id_key)
            return jsonify({
                "status": "success",
                "message": "ውርርድዎ በተሳካ ሁኔታ ተሰርዟል!",
                "new_balance": new_balance,
            })

    return jsonify({"status": "error", "message": "አሁን ውርርድ መሰረዝ አይችሉም (ጨዋታው እየበረረ ነው)!"}), 400


@aviator_bp.route('/aviator')
def aviator_page():
    return render_template('aviator.html')
