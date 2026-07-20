import time
import random
import math
import logging
from threading import Lock
from flask import Blueprint, request, jsonify, render_template
from config import redis, deduct_balance_safely, add_to_history 

aviator_bp = Blueprint('aviator', __name__)

# ==========================================
# 🎮 1. የጨዋታው ማህደረ ትውስታ (In-Memory Game State)
# ==========================================
game_state = {
    "status": "WAITING",  
    "multiplier": 1.00,
    "crash_point": 1.00,
    "start_time": 0,
    "history": []  
}

current_round_bets = {}  
next_round_bets = {}     
generated_crashes = []   
bet_lock = Lock()        

# ==========================================
# 🧮 2. Provably Fair (የክራሽ ነጥቦችን አስቀድሞ ማመንጨት)
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
    user_bet = current_round_bets.get(user_id)

    if user_bet:
        if not user_bet.get("cashed_out"):
            user_bet["cashed_out"] = True
            win_amount = round(user_bet["amount"] * multiplier, 2)
            user_bet["win_amount"] = win_amount 

            redis.hincrbyfloat("users:balance", str(user_id), win_amount)
            add_to_history(user_id, {"type": "Aviator Win", "amount": win_amount, "multiplier": multiplier})

            return win_amount
        else:
            return user_bet.get("win_amount", 0)

    return 0

# ==========================================
# 🔄 4. የጨዋታው ሞተር (Background Game Loop)
# ==========================================
def start_aviator_loop(socketio):
    generate_500_crashes() 

    def loop():
        global current_round_bets, next_round_bets

        while True:
            try:
                game_state["status"] = "WAITING"
                game_state["multiplier"] = 1.00
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
                            if not bet.get("cashed_out") and bet.get("auto_cashout_val"):
                                if current_multi >= bet["auto_cashout_val"]:
                                    try:
                                        process_cashout(uid, bet["auto_cashout_val"])
                                    except Exception as ex:
                                        print(f"⚠️ Auto-Cashout Error for UID {uid}: {ex}")

                game_state["status"] = "CRASHED"
                game_state["multiplier"] = game_state["crash_point"]

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

@aviator_bp.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.json or {}
    user_id = str(data.get("user_id"))

    if not user_id:
        return jsonify({"status": "error", "message": "User ID required"}), 400

    try:
        balance_raw = redis.hget("users:balance", user_id)
        current_balance = float(balance_raw) if balance_raw else 0.0
        return jsonify({"status": "success", "balance": current_balance})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@aviator_bp.route('/api/aviator/bet', methods=['POST'])
def place_bet():
    data = request.json or {}
    user_id = str(data.get("user_id"))

    try:
        amount = float(data.get("bet_amount", 0))
        auto_cashout_val = float(data.get("auto_cashout", 0))
    except ValueError:
        return jsonify({"status": "error", "message": "የተሳሳተ የገንዘብ መጠን ፎርማት"}), 400

    if not user_id or amount < 10: 
        return jsonify({"status": "error", "message": "ዝቅተኛው የውርርድ መጠን 10 ብር ነው"}), 400

    with bet_lock:
        target_dict = current_round_bets if game_state["status"] == "WAITING" else next_round_bets
        round_type = "CURRENT" if game_state["status"] == "WAITING" else "NEXT"
        msg = "በአሁኑ ዙር ተሳትፈዋል!" if round_type == "CURRENT" else "ለውርርድ ለቀጣዩ ዙር ተመዝግበዋል!"

        if user_id in target_dict:
            return jsonify({"status": "error", "message": "በዚህ ዙር አስቀድመው ተወራርደዋል!"}), 400

        if not deduct_balance_safely(user_id, amount):
            return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም ወይም ሲስተሙ ስራ በዝቶበታል"}), 400

        bet_data = {
            "amount": amount, 
            "cashed_out": False, 
            "auto_cashout_val": auto_cashout_val if auto_cashout_val > 1.00 else None
        }

        new_balance = round(float(redis.hget("users:balance", user_id) or 0.0), 2)
        target_dict[user_id] = bet_data

    return jsonify({
        "status": "success", 
        "message": msg, 
        "type": round_type,
        "new_balance": new_balance
    })

@aviator_bp.route('/api/aviator/cancel_bet', methods=['POST'])
def cancel_bet():
    data = request.json or {}
    user_id = str(data.get("user_id"))
    
    with bet_lock:
        # ውርርዱ ከነበረበት ሰርሰነው ብሩን እንመልሳለን
        target_dict = next_round_bets if user_id in next_round_bets else current_round_bets
        if user_id in target_dict:
            bet_info = target_dict.pop(user_id)
            refund_amount = bet_info["amount"]
            redis.hincrbyfloat("users:balance", user_id, refund_amount)
            new_balance = round(float(redis.hget("users:balance", user_id) or 0.0), 2)
            return jsonify({"status": "success", "new_balance": new_balance})
            
    return jsonify({"status": "error", "message": "ውርርድ አልተገኘም"})

@aviator_bp.route('/api/aviator/cashout', methods=['POST'])
def manual_cashout():
    data = request.json or {}
    user_id = str(data.get("user_id"))

    if not user_id:
        return jsonify({"status": "error", "message": "መረጃ የለም"}), 400

    with bet_lock:
        if game_state["status"] != "FLYING":
            return jsonify({"status": "error", "message": "አሁን Cash out ማድረግ አይችሉም!"}), 400

        current_multi = game_state["multiplier"]
        win_amount = process_cashout(user_id, current_multi)

        if win_amount > 0:
            new_balance = round(float(redis.hget("users:balance", user_id) or 0.0), 2)
            return jsonify({
                "status": "success", 
                "win_amount": win_amount, 
                "multiplier": current_multi,
                "new_balance": new_balance 
            })
        else:
            return jsonify({"status": "error", "message": "ውርርድ አልተገኘም ወይም አስቀድመው ወስደዋል"}), 400

@aviator_bp.route('/aviator')
def aviator_page():
    return render_template('aviator.html')
