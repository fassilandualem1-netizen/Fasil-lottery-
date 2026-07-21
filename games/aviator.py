import time
import random
import math
from threading import Lock
from flask import Blueprint, request, jsonify, render_template

from config import (
    redis,
    deduct_balance_safely,
    add_to_history,
    telegram_auth_required,
    get_user_id_from_request,
)

aviator_bp = Blueprint("aviator", __name__)

_socketio = None

game_state = {
    "status": "WAITING",
    "multiplier": 1.00,
    "crash_point": 1.00,
    "start_time": 0,
    "round_id": 0,
    "time_left": 10,
    "history": []
}

current_round_bets = {}
next_round_bets = {}
generated_crashes = []
bet_lock = Lock()


def _normalize_user_id(user_id):
    return str(user_id).strip() if user_id else None


def _is_user_banned(user_id):
    if not user_id:
        return False
    return redis.sismember("banned_users", str(user_id))


def _get_user_balance(user_id):
    user_id = _normalize_user_id(user_id)
    if not user_id:
        return 0.0
    try:
        raw = redis.hget("users:balance", user_id)
        if raw is None:
            return 1000.0
        return float(raw)
    except Exception:
        return 1000.0


def _set_user_balance(user_id, balance):
    user_id = _normalize_user_id(user_id)
    if not user_id:
        return
    try:
        redis.hset("users:balance", user_id, float(balance))
    except Exception:
        pass


def generate_crash_point():
    house_edge = 0.03
    if random.random() < house_edge:
        return 1.00

    r = random.random()
    if r >= 1.0:
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

    current_balance = _get_user_balance(user_id_key)
    new_balance = current_balance + win_amount
    _set_user_balance(user_id_key, new_balance)

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
    _socketio.emit("player_cashout", {
        "user_id": user_id_key,
        "win_amount": win_amount,
        "multiplier": multiplier,
        "new_balance": new_balance,
    })


def start_aviator_loop(socketio):
    global _socketio
    _socketio = socketio
    generate_500_crashes()

    @socketio.on("connect")
    def handle_connect():
        socketio.emit("game_state", {
            "status": game_state["status"],
            "multiplier": game_state["multiplier"],
            "round_id": game_state["round_id"],
            "time_left": game_state["time_left"],
            "history": game_state["history"]
        })

    def loop():
        global current_round_bets, next_round_bets

        while True:
            try:
                game_state["status"] = "WAITING"
                game_state["multiplier"] = 1.00
                game_state["round_id"] += 1
                game_state["time_left"] = 10
                game_state["crash_point"] = get_next_crash()

                socketio.emit("game_state", {
                    "status": "WAITING",
                    "multiplier": 1.00,
                    "round_id": game_state["round_id"],
                    "time_left": 10,
                    "history": game_state["history"]
                })

                for step in range(10, 0, -1):
                    game_state["time_left"] = step
                    socketio.emit("game_state", {
                        "status": "WAITING",
                        "multiplier": 1.00,
                        "round_id": game_state["round_id"],
                        "time_left": step,
                        "history": game_state["history"]
                    })
                    socketio.sleep(1)

                with bet_lock:
                    current_round_bets = next_round_bets.copy()
                    next_round_bets = {}

                game_state["status"] = "FLYING"
                game_state["start_time"] = time.time()
                game_state["time_left"] = 0

                socketio.emit("game_state", {
                    "status": "FLYING",
                    "multiplier": 1.00,
                    "round_id": game_state["round_id"],
                    "time_left": 0,
                    "history": game_state["history"]
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
                    socketio.emit("multiplier_update", {"multiplier": current_multi})

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
                                        print(f"Auto Cashout Error {uid}: {ex}")

                game_state["status"] = "CRASHED"
                game_state["multiplier"] = game_state["crash_point"]
                game_state["history"].insert(0, game_state["crash_point"])
                if len(game_state["history"]) > 20:
                    game_state["history"].pop()

                with bet_lock:
                    for uid, bet in list(current_round_bets.items()):
                        if not bet.get("cashed_out"):
                            add_to_history(uid, {
                                "type": "Aviator Loss",
                                "amount": bet["amount"],
                                "multiplier": game_state["crash_point"],
                            })

                socketio.emit("game_state", {
                    "status": "CRASHED",
                    "crash_point": game_state["crash_point"],
                    "multiplier": game_state["crash_point"],
                    "round_id": game_state["round_id"],
                    "time_left": 0,
                    "history": game_state["history"]
                })

                socketio.sleep(3)

            except Exception as e:
                print(f"Aviator loop error: {e}")
                socketio.sleep(2)

    socketio.start_background_task(loop)


@aviator_bp.route("/api/aviator/state", methods=["GET"])
def aviator_state():
    return jsonify({
        "status": game_state["status"],
        "multiplier": game_state["multiplier"],
        "round_id": game_state["round_id"],
        "time_left": game_state["time_left"],
        "history": game_state["history"]
    }), 200


@aviator_bp.route("/api/wallet/balance", methods=["GET"])
@telegram_auth_required
def wallet_balance():
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"status": "error", "balance": 0.0}), 400
    return jsonify({"status": "success", "balance": round(_get_user_balance(user_id), 2)}), 200


@aviator_bp.route("/api/aviator/bet", methods=["POST"])
@telegram_auth_required
def place_bet():
    data = request.json or {}
    user_id = get_user_id_from_request()

    try:
        amount = float(data.get("bet_amount", 0))
        auto_cashout_val = float(data.get("auto_cashout", 0))
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid amount"}), 400

    if not user_id or amount < 10:
        return jsonify({"status": "error", "message": "Minimum bet is 10 ETB"}), 400

    if _is_user_banned(user_id):
        return jsonify({"status": "error", "message": "Account is banned"}), 403

    user_id_key = _normalize_user_id(user_id)

    with bet_lock:
        if game_state["status"] == "WAITING":
            target_dict = next_round_bets
            round_id = game_state.get("round_id", 0)
            round_type = "NEXT"
        else:
            target_dict = next_round_bets
            round_id = game_state.get("round_id", 0) + 1
            round_type = "NEXT"

        if user_id_key in target_dict:
            return jsonify({"status": "error", "message": "You already placed a bet for this round"}), 400

        balance = _get_user_balance(user_id_key)
        if balance < amount:
            return jsonify({"status": "error", "message": "Insufficient balance"}), 400

        _set_user_balance(user_id_key, balance - amount)

        target_dict[user_id_key] = {
            "amount": amount,
            "cashed_out": False,
            "auto_cashout_val": auto_cashout_val if auto_cashout_val > 1.00 else None,
            "round_id": round_id,
        }

        new_balance = _get_user_balance(user_id_key)

    return jsonify({
        "status": "success",
        "message": f"Bet placed for {round_type} round",
        "new_balance": new_balance
    }), 200


@aviator_bp.route("/api/aviator/cashout", methods=["POST"])
@telegram_auth_required
def manual_cashout():
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"status": "error", "message": "No user data"}), 400

    if _is_user_banned(user_id):
        return jsonify({"status": "error", "message": "Account is banned"}), 403

    user_id_key = _normalize_user_id(user_id)
    with bet_lock:
        if game_state["status"] != "FLYING":
            return jsonify({"status": "error", "message": "Cash out is not available right now"}), 400

        current_multi = game_state["multiplier"]
        win_amount, was_processed = process_cashout(user_id_key, current_multi)

        if was_processed and win_amount > 0:
            new_balance = _get_user_balance(user_id_key)
            return jsonify({
                "status": "success",
                "win_amount": win_amount,
                "multiplier": current_multi,
                "new_balance": new_balance
            }), 200

        return jsonify({"status": "error", "message": "No active bet to cash out"}), 400


@aviator_bp.route("/api/aviator/cancel_bet", methods=["POST"])
@telegram_auth_required
def cancel_bet():
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"status": "error", "message": "No user data"}), 400

    if _is_user_banned(user_id):
        return jsonify({"status": "error", "message": "Account is banned"}), 403

    user_id_key = _normalize_user_id(user_id)

    with bet_lock:
        if user_id_key in next_round_bets:
            bet_amount = next_round_bets[user_id_key]["amount"]
            del next_round_bets[user_id_key]
            balance = _get_user_balance(user_id_key) + bet_amount
            _set_user_balance(user_id_key, balance)
            return jsonify({
                "status": "success",
                "message": "Bet cancelled",
                "new_balance": round(balance, 2)
            }), 200

    return jsonify({"status": "error", "message": "No pending bet to cancel"}), 400


@aviator_bp.route("/aviator")
def aviator_page():
    return render_template("aviator.html")