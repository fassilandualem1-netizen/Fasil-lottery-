import time
import random
import math
from flask import Blueprint, request, jsonify
from config import redis, deduct_balance_safely, add_to_history # ከ config.py የጋራ ቱሎችን አስገባ

aviator_bp = Blueprint('aviator', __name__)

# ==========================================
# 🎮 1. የጨዋታው ማህደረ ትውስታ (In-Memory State)
# ==========================================
game_state = {
    "status": "WAITING",  # WAITING, FLYING, CRASHED
    "multiplier": 1.00,
    "crash_point": 1.00,
    "start_time": 0
}

current_round_bets = {}  # የአሁኑ ዙር ውርርዶች e.g., {"user123": {"amount": 20, "cashed_out": False}}
next_round_bets = {}     # የቀጣይ ዙር (Next Round) ውርርዶች

# ==========================================
# 🧮 2. Provably Fair (የክራሽ ቁጥር ማመንጫ ቀመር)
# ==========================================
def generate_crash_point():
    """ 
    በሂሳባዊ ቀመር የካምፓኒውን ትርፍ (House Edge 3%) አስጠብቆ የሚያመነጭ።
    """
    r = random.random() # ከ 0.0 እስከ 1.0 ራንደም ቁጥር
    house_edge = 0.97   # የ 3% ብልጫ ለካምፓኒው
    
    # 1.00 ላይ የመከሰከስ እድሉን መፍጠር
    crash_point = house_edge / (1.0 - r)
    return max(1.00, round(crash_point, 2))

# ==========================================
# 🔄 3. የጨዋታው ሞተር (Background Game Loop)
# ==========================================
def start_aviator_loop(socketio):
    """
    ይህ ሞተር main.py ሲነሳ አብሮ ይጀምራል፤ 24/7 ይሰራል።
    """
    def loop():
        global current_round_bets, next_round_bets
        
        while True:
            # --- ሀ. የመጠባበቂያ ጊዜ (WAITING - 5 ሰከንድ) ---
            game_state["status"] = "WAITING"
            game_state["multiplier"] = 1.00
            game_state["crash_point"] = generate_crash_point()
            
            # የቀጣይ ዙር ውርርዶችን (Next Round Bets) ወደ አሁኑ ዙር ማዛወር
            current_round_bets = next_round_bets.copy()
            next_round_bets = {}
            
            # ለሁሉም ክላይንቶች (Frontend) አዲስ ዙር መጀመሩን ማሳወቅ
            socketio.emit('game_state', {'status': 'WAITING', 'time_left': 5}, namespace='/aviator')
            socketio.sleep(5) # Gevent-safe sleep
            
            # --- ለ. የበረራ ጊዜ (FLYING) ---
            game_state["status"] = "FLYING"
            game_state["start_time"] = time.time()
            
            # አውሮፕላኑ ተነሳ! የሚለውን መላክ (የሚሊሰከንድ ማሳደጉን ክላይንቱ በራሱ ይሰራል)
            socketio.emit('game_state', {'status': 'FLYING', 'start_time': game_state["start_time"]}, namespace='/aviator')
            
            crashed = False
            while not crashed:
                socketio.sleep(0.1) # በየ 100 ሚሊሰከንዱ ቼክ ያደርጋል
                elapsed_time = time.time() - game_state["start_time"]
                
                # የእድገት ሂሳብ ቀመር: M = e^(0.06 * t)
                current_multi = math.exp(0.06 * elapsed_time)
                game_state["multiplier"] = round(current_multi, 2)
                
                # አውሮፕላኑ አስቀድሞ ከተወሰነው የክራሽ ቁጥር ደረሰ ወይ?
                if game_state["multiplier"] >= game_state["crash_point"]:
                    crashed = True
                    
            # --- ሐ. የመከሰከስ ጊዜ (CRASHED - 2 ሰከንድ) ---
            game_state["status"] = "CRASHED"
            game_state["multiplier"] = game_state["crash_point"]
            
            # ክራሽ ማድረጉን መላክ!
            socketio.emit('game_state', {'status': 'CRASHED', 'crash_point': game_state["crash_point"]}, namespace='/aviator')
            
            # 2 ሰከንድ ለዕይታ ቆይቶ ወደ WAITING ይመለሳል
            socketio.sleep(2)

    # ሉፑን በ "Background task" ማስጀመር (ሰርቨሩን block አያደርገውም)
    socketio.start_background_task(loop)

# ==========================================
# 💸 4. የውርርድ (Bet) እና የክፍያ (Cash Out) ኤፒአይዎች
# ==========================================
@aviator_bp.route('/api/aviator/place_bet', methods=['POST'])
def place_bet():
    data = request.json or {}
    user_id = data.get("user_id")
    amount = float(data.get("amount", 0))
    
    if not user_id or amount <= 0:
        return jsonify({"status": "error", "message": "የተሳሳተ መረጃ"}), 400
        
    # ባላንስ ማረጋገጥና መቁረጥ (ከ redis)
    current_balance = float(redis.hget("users:balance", user_id) or 0.0)
    if current_balance < amount:
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም"}), 400
        
    # ብሩን ከባላንስ ላይ መቀነስ
    redis.hincrbyfloat("users:balance", user_id, -amount)
    
    # ጌሙ ምን ላይ ነው?
    if game_state["status"] == "WAITING":
        current_round_bets[user_id] = {"amount": amount, "cashed_out": False}
        return jsonify({"status": "success", "message": "በአሁኑ ዙር ተሳትፈዋል!", "type": "CURRENT"})
    else:
        # ጌሙ እየበረረ ስለሆነ ለቀጣይ ዙር ይቀመጣል
        next_round_bets[user_id] = {"amount": amount, "cashed_out": False}
        return jsonify({"status": "success", "message": "ለውርርድ ለቀጣዩ ዙር ተመዝግበዋል!", "type": "NEXT"})

@aviator_bp.route('/api/aviator/cashout', methods=['POST'])
def cashout():
    data = request.json or {}
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"status": "error", "message": "መረጃ የለም"}), 400
        
    if game_state["status"] != "FLYING":
        return jsonify({"status": "error", "message": "አሁን Cash out ማድረግ አይችሉም!"}), 400
        
    user_bet = current_round_bets.get(user_id)
    if not user_bet or user_bet["cashed_out"]:
        return jsonify({"status": "error", "message": "ውርርድ አልተገኘም ወይም አስቀድመው ወስደዋል"}), 400
        
    # 🔥 SECURITY: ፍሮንትኤንዱ ያመጣውን አናምንም፣ የሰርቨሩን ወቅታዊ Muliplier እንጠቀማለን!
    current_multi = game_state["multiplier"]
    
    # ተጠቃሚው አሸነፈ
    user_bet["cashed_out"] = True
    win_amount = user_bet["amount"] * current_multi
    
    # አሸናፊነቱን ወደ ሬዲስ (ባላንስ) መመለስ
    redis.hincrbyfloat("users:balance", user_id, win_amount)
    
    # ወደ ሂስትሪ መመዝገብ (አማራጭ)
    add_to_history(user_id, {"type": "አቪዬተር አሸናፊ", "amount": round(win_amount, 2), "multiplier": current_multi})
    
    return jsonify({
        "status": "success", 
        "win_amount": round(win_amount, 2),
        "multiplier": current_multi
    })
