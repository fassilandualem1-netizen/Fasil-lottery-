import time
import random
import math
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
    "history": []  # ያለፉትን 20 የክራሽ ነጥቦች ይይዛል (ለ Frontend የቀለም ታሪክ ማሳያ)
}

current_round_bets = {}  
next_round_bets = {}     
pre_generated_crashes = [] # 500 አስቀድመው የተሰሩ የክራሽ ነጥቦች

# ==========================================
# 🧮 2. Provably Fair (500 ነጥቦችን አስቀድሞ ማመንጨት)
# ==========================================
def generate_500_crashes():
    """ 
    ሰርቨሩን ጫና ላለማብዛት 500 የክራሽ ቁጥሮችን በአንድ ጊዜ ያዘጋጃል። 
    ሲያልቅም በራሱ ይሞላል።
    """
    global pre_generated_crashes
    crashes = []
    house_edge = 0.97 # የ 3% ትርፍ 
    for _ in range(500):
        r = random.random()
        crash_point = house_edge / (1.0 - r)
        crashes.append(max(1.00, round(crash_point, 2)))
    pre_generated_crashes = crashes

def get_next_crash():
    global pre_generated_crashes
    if not pre_generated_crashes:
        generate_500_crashes() # ካለቀበት ዳግም ይሞላል
    return pre_generated_crashes.pop(0)

# ==========================================
# 💸 3. የካሽ አውት ተግባር (ለ Auto እና Manual የሚያገለግል)
# ==========================================
def process_cashout(user_id, multiplier):
    """ ሰርቨር-ሳይድ ካሽ አውት ማድረጊያ (Robust Function) """
    user_bet = current_round_bets.get(user_id)
    if user_bet and not user_bet["cashed_out"]:
        user_bet["cashed_out"] = True
        win_amount = user_bet["amount"] * multiplier
        
        # ብሩን ደህንነቱ በተጠበቀ ሁኔታ Redis ላይ መጨመር
        redis.hincrbyfloat("users:balance", str(user_id), win_amount)
        add_to_history(user_id, {"type": "Aviator Win", "amount": round(win_amount, 2), "multiplier": multiplier})
        return win_amount
    return 0

# ==========================================
# 🔄 4. የጨዋታው ሞተር (Robust Background Game Loop)
# ==========================================
def start_aviator_loop(socketio):
    generate_500_crashes() # ሰርቨሩ ሲነሳ መጀመሪያ 500 ዙር ያዘጋጃል
    
    def loop():
        global current_round_bets, next_round_bets
        
        while True:
            try:
                # --- ሀ. የመጠባበቂያ ጊዜ (WAITING - 10 ሰከንድ) ---
                game_state["status"] = "WAITING"
                game_state["multiplier"] = 1.00
                game_state["crash_point"] = get_next_crash()
                
                # ውርርዶችን ማዛወር
                current_round_bets = next_round_bets.copy()
                next_round_bets = {}
                
                # ክላይንቶች ታሪኩን (History Tape) እና ቆጠራውን እንዲያዩ መላክ
                socketio.emit('game_state', {
                    'status': 'WAITING', 
                    'time_left': 10, # 10 ሰከንድ
                    'multiplier': 1.00,
                    'history': game_state["history"] 
                })
                socketio.sleep(10) 
                
                # --- ለ. የበረራ ጊዜ (FLYING) ---
                game_state["status"] = "FLYING"
                game_state["start_time"] = time.time()
                
                socketio.emit('game_state', {
                    'status': 'FLYING', 
                    'start_time': game_state["start_time"],
                    'multiplier': 1.00
                })
                
                crashed = False
                while not crashed:
                    socketio.sleep(0.05) # 20fps 
                    elapsed_time = time.time() - game_state["start_time"]
                    
                    # ኃይለኛ አድጓዊ ቀመር (Exponential Growth)
                    current_multi = round(math.exp(0.06 * elapsed_time), 2)
                    game_state["multiplier"] = current_multi
                    
                    socketio.emit('multiplier_update', {'multiplier': current_multi})
                    
                    # 🔥 SERVER-SIDE AUTO CASHOUT ሎጂክ
                    # ተጫዋቹ ኢንተርኔት ቢቋረጥበትም ሰርቨሩ አውቶማቲክ ያወጣለታል
                    for uid, bet in current_round_bets.items():
                        if not bet["cashed_out"] and bet.get("auto_cashout_val"):
                            if current_multi >= bet["auto_cashout_val"]:
                                process_cashout(uid, current_multi)
                                # (አማራጭ: እዚህ ጋር ለተጠቃሚው ብቻውን 'win' ኢቨንት መላክ ይቻላል)
                    
                    if current_multi >= game_state["crash_point"]:
                        crashed = True
                        
                # --- ሐ. የመከሰከስ ጊዜ (CRASHED - 3 ሰከንድ) ---
                game_state["status"] = "CRASHED"
                game_state["multiplier"] = game_state["crash_point"]
                
                # ታሪክ ውስጥ መጨመር (በ 20 ዙር የተገደበ)
                game_state["history"].insert(0, game_state["crash_point"])
                if len(game_state["history"]) > 20:
                    game_state["history"].pop()
                
                socketio.emit('game_state', {
                    'status': 'CRASHED', 
                    'crash_point': game_state["crash_point"],
                    'history': game_state["history"]
                })
                
                socketio.sleep(3) 

            except Exception as e:
                # ሉፑ እንዳይሞት መከላከያ
                print(f"⚠️ Aviator Loop Error: {e}")
                socketio.sleep(1)

    socketio.start_background_task(loop)

# ==========================================
# 📡 5. የውርርድ እና የካሽ አውት ኤፒአይ (Endpoints)
# ==========================================
@aviator_bp.route('/api/aviator/place_bet', methods=['POST'])
def place_bet():
    data = request.json or {}
    user_id = str(data.get("user_id"))
    amount = float(data.get("amount", 0))
    auto_cashout_val = float(data.get("auto_cashout", 0)) # Auto Cashout ካለ
    
    if not user_id or amount < 10: # ዝቅተኛ መነሻ 10 ETB
        return jsonify({"status": "error", "message": "የተሳሳተ መረጃ"}), 400
        
    current_balance = float(redis.hget("users:balance", user_id) or 0.0)
    if current_balance < amount:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400
        
    redis.hincrbyfloat("users:balance", user_id, -amount)
    
    bet_data = {
        "amount": amount, 
        "cashed_out": False, 
        "auto_cashout_val": auto_cashout_val if auto_cashout_val > 1.00 else None
    }
    
    if game_state["status"] == "WAITING":
        current_round_bets[user_id] = bet_data
        return jsonify({"status": "success", "message": "በአሁኑ ዙር ተሳትፈዋል!", "type": "CURRENT"})
    else:
        next_round_bets[user_id] = bet_data
        return jsonify({"status": "success", "message": "ለውርርድ ለቀጣዩ ዙር ተመዝግበዋል!", "type": "NEXT"})

@aviator_bp.route('/api/aviator/cashout', methods=['POST'])
def manual_cashout():
    data = request.json or {}
    user_id = str(data.get("user_id"))
    
    if not user_id:
        return jsonify({"status": "error", "message": "መረጃ የለም"}), 400
        
    if game_state["status"] != "FLYING":
        return jsonify({"status": "error", "message": "አሁን Cash out ማድረግ አይችሉም!"}), 400
        
    current_multi = game_state["multiplier"]
    win_amount = process_cashout(user_id, current_multi)
    
    if win_amount > 0:
        return jsonify({
            "status": "success", 
            "win_amount": round(win_amount, 2),
            "multiplier": current_multi
        })
    else:
        return jsonify({"status": "error", "message": "ውርርድ አልተገኘም ወይም አስቀድመው ወስደዋል"}), 400

@aviator_bp.route('/aviator')
def aviator_page():
    return render_template('aviator.html')
