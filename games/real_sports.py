from flask import Blueprint, request, jsonify
import os
import requests
import json
import uuid
from config import redis, deduct_balance_safely, add_to_history, telegram_auth_required

real_sports_bp = Blueprint('real_sports', __name__)

# ከ Render Environment ላይ ቁልፉን እናነባለን
API_KEY = os.environ.get("API_FOOTBALL_KEY")
API_HOST = "v3.football.api-sports.io"

# 1. ጨዋታዎችን ማምጫ (Fetch Matches & Odds)
@real_sports_bp.route('/api/sports/matches', methods=['GET'])
def get_matches():
    # ማስታወሻ፡ API-Sports በቀን የተወሰነ Request ስላለው፣ Live ሲገባ ዳታውን Redis ላይ Cache እናደርገዋለን።
    # ለጊዜው ግን በቀጥታ እንጠራዋለን።
    
    url = "https://v3.football.api-sports.io/odds/live" # በቀጥታ ያሉትን ወይም የዛሬዎችን ለማምጣት
    headers = {
        "x-apisports-key": API_KEY,
        "x-apisports-host": API_HOST
    }
    
    try:
        # ለሙከራ (Test) ቆጠባ እንዲሆን የ API ጥሪውን ኮመንት አድርጌ የውሸት (Mock) ዳታ አስገብቻለሁ
        # ትክክለኛውን ለመጠቀም ከስር ያለውን mock_data አጥፍተው response = requests.get... የሚለውን ይክፈቱ
        
        """
        response = requests.get(url, headers=headers)
        data = response.json()
        matches = data.get('response', [])
        """
        
        # የሙከራ ዳታ (Frontend እሰራበት ዘንድ)
        mock_data = [
            {
                "fixture": {"id": 101, "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}}},
                "odds": {"home": 1.80, "draw": 3.20, "away": 4.10}
            },
            {
                "fixture": {"id": 102, "teams": {"home": {"name": "Man Utd"}, "away": {"name": "Liverpool"}}},
                "odds": {"home": 2.50, "draw": 3.00, "away": 2.20}
            }
        ]
        
        return jsonify({"status": "success", "matches": mock_data})
    except Exception as e:
        return jsonify({"status": "error", "message": "ጨዋታዎችን ማምጣት አልተቻለም"}), 500

# 2. ውርርድ መቀበያ (Place Bet)
@real_sports_bp.route('/api/sports/place_bet', methods=['POST'])
@telegram_auth_required
def place_bet():
    data = request.json or {}
    user_id = str(data.get("user_id"))
    bet_amount = float(data.get("bet_amount", 0))
    selections = data.get("selections", []) # Array of objects: [{match_id, pick, odd}]
    
    if bet_amount <= 0 or not selections:
        return jsonify({"status": "error", "message": "እባክዎ ጨዋታዎችን ይምረጡ እና የብር መጠን ያስገቡ!"}), 400
        
    # 1. አጠቃላይ ማባዣውን (Total Odds) እናሰላለን
    total_odds = 1.0
    for sel in selections:
        total_odds *= float(sel.get("odd", 1.0))
        
    possible_win = bet_amount * total_odds

    # 2. ባላንስ ቼክ እናደርጋለን እና እንቀንሳለን
    deduct_status = deduct_balance_safely(user_id, bet_amount, "real")
    if deduct_status == "INSUFFICIENT":
        return jsonify({"status": "error", "message": "በቂ ባላንስ የለዎትም!"}), 400

    # 3. ትኬት ቆርጠን Redis ላይ እናስቀምጣለን
    ticket_id = "TKT-" + str(uuid.uuid4())[:6].upper()
    
    bet_ticket = {
        "user_id": user_id,
        "ticket_id": ticket_id,
        "amount": bet_amount,
        "total_odds": round(total_odds, 2),
        "possible_win": round(possible_win, 2),
        "selections": selections,
        "status": "PENDING" # ጨዋታው እስኪያልቅ ይጠብቃል
    }
    
    # ትኬቱን በዳታቤዝ እናስቀምጣለን
    redis.set(f"bet:ticket:{ticket_id}", json.dumps(bet_ticket))
    # የተጠቃሚውን ትኬቶች ዝርዝር ውስጥ እንጨምረዋለን
    redis.sadd(f"user_bets:{user_id}", ticket_id)
    
    # 4. ሂስቶሪ ውስጥ እንመዘግባለን
    add_to_history(user_id, {
        "tx_id": ticket_id, 
        "type": "⚽️ ውርርድ (Bet)", 
        "amount": -bet_amount, 
        "status": "pending"
    })
    
    return jsonify({
        "status": "success", 
        "message": f"ውርርድዎ ተቀባይነት አግኝቷል! ትኬት ቁጥር: {ticket_id}\nሊያሸንፉ የሚችሉት: {round(possible_win, 2)} ብር"
    })
