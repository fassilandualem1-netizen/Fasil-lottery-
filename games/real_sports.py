from flask import Blueprint, request, jsonify
import os
import requests
import json
import uuid
import time
from datetime import datetime, timedelta

# ከ config.py የምታመጣቸው 
from config import redis, deduct_balance_safely, add_to_history, telegram_auth_required

real_sports_bp = Blueprint('real_sports', __name__)

# አዲሱን የ The Odds API ቁልፍ መጠቀም
API_KEY = os.environ.get("THE_ODDS_API_KEY")

# የጋራ Redis Key
CACHE_KEY = "cached_real_sports_odds"


# =========================================
# 1. ሰርቨርን ነቅቶ እንዲጠብቅ የሚያደርግ (Ping)
# =========================================
@real_sports_bp.route('/api/internal/ping', methods=['GET'])
def ping():
    return jsonify({"status": "alive"}), 200


# =========================================
# 2. የጀርባ አገልጋይ (Google App Script የሚጠራው - ዳታ የሚያመጣው)
# =========================================
@real_sports_bp.route('/api/internal/update_sports_data', methods=['GET'])
def update_sports_data():
    # ሚስጥራዊ ቁልፍ (GAS ላይ ሊንኩን ስታስገባ ?secret=mypassword123 ብለህ አስገባ)
    secret = request.args.get("secret")
    if secret != "mypassword123":
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if not API_KEY:
        return jsonify({"status": "error", "message": "API Key አልተገኘም"}), 500

    try:
        # 'upcoming' በማለት በአለም ላይ ያሉ የቅርብ ጊዜ እውነተኛ ጨዋታዎችን በሙሉ ማምጣት
        url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={API_KEY}&regions=eu&markets=h2h"
        response = requests.get(url, timeout=15)
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": f"API Error: {response.text}"}), response.status_code

        data = response.json()
        real_matches = []
        now_time = datetime.now()

        for item in data:
            match_id = item.get("id")
            home_team = item.get("home_team")
            away_team = item.get("away_team")
            commence_time_str = item.get("commence_time")
            league = item.get("sport_title", "Unknown League")
            
            # ሰዓቱን ማስተካከል እና ያለፉ ጨዋታዎችን ማጣራት
            try:
                # API የሚያመጣው ሰዓት በ UTC ነው (ለምሳሌ 2024-07-20T14:30:00Z)
                match_time_obj = datetime.strptime(commence_time_str, "%Y-%m-%dT%H:%M:%SZ")
                if match_time_obj <= now_time:
                    continue  # ጨዋታው ከጀመረ ወይም ካለፈ ዝለለው
                
                clean_time = match_time_obj.strftime("%H:%M")
                match_date = match_time_obj.strftime("%Y-%m-%d")
            except Exception:
                clean_time = "TBA"
                match_date = "TBA"

            # የውርርድ መጠን (Odds) ማውጣት
            odds_dict = {}
            bookmakers = item.get("bookmakers", [])
            if bookmakers:
                markets = bookmakers[0].get("markets", [])
                if markets:
                    outcomes = markets[0].get("outcomes", [])
                    for o in outcomes:
                        if o["name"] == home_team:
                            odds_dict["home"] = o["price"]
                        elif o["name"] == away_team:
                            odds_dict["away"] = o["price"]
                        else:
                            odds_dict["draw"] = o["price"]

            # ሆም እና አዌይ ኦድስ ካለው ብቻ ወደ ሪዲስ ማስገባት (Frontend እንዳይበላሽ የድሮውን ፎርማት ተጠቅመናል)
            if "home" in odds_dict and "away" in odds_dict:
                real_matches.append({
                    "fixture": {
                        "id": match_id,
                        "teams": {
                            "home": {"name": home_team},
                            "away": {"name": away_team}
                        },
                        "league": league,
                        "time": clean_time,
                        "date": match_date
                    },
                    "odds": odds_dict
                })

        if len(real_matches) > 0:
            # ዳታውን ወስዶ Redis ላይ ያስቀምጠዋል
            redis.set(CACHE_KEY, json.dumps(real_matches))

        return jsonify({"status": "success", "message": f"✅ {len(real_matches)} ጨዋታዎች ተዘጋጅተው Redis ላይ ገብተዋል።"}), 200

    except Exception as e:
        print(f"API Odds Fetching Exception: {e}")
        return jsonify({"status": "error", "message": "እውነተኛ ኦዶችን ማምጣት አልተቻለም"}), 500


# =========================================
# 3. ዌብሳይቱ (Frontend) ዳታ የሚወስድበት (ፈጣኑ ራውት)
# =========================================
@real_sports_bp.route('/api/sports/odds', methods=['GET'])
def get_odds():
    try:
        # ምንም አይነት 3rd Party API አይጠይቅም! በቀጥታ ከ Redis ላይ ብቻ ያነባል።
        cached_odds = redis.get(CACHE_KEY)

        if cached_odds:
            matches = json.loads(cached_odds)
            return jsonify({"status": "success", "matches": matches})
        else:
            return jsonify({"status": "success", "matches": []})

    except Exception as e:
        return jsonify({"status": "error", "message": "የዳታቤዝ ስህተት"}), 500


# =========================================
# 4. የ አድሚን Cache ማጥፊያ
# =========================================
@real_sports_bp.route('/api/admin/clear_cache', methods=['GET'])
def clear_cache_admin():
    secret_key = request.args.get('key')
    if secret_key != "MySecret123":
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    redis.delete(CACHE_KEY)
    return jsonify({"status": "success", "message": "Cache በተሳካ ሁኔታ ጠፍቷል!"})


# =========================================
# 5. ውርርድ መቁረጫ (Place Bet) 
# =========================================
@real_sports_bp.route('/api/sports/place_bet', methods=['POST'])
@telegram_auth_required
def place_bet():
    try:
        data = request.json
        user_id = data.get('user_id')
        bet_amount = data.get('bet_amount')
        selections = data.get('selections') 

        if not user_id or not bet_amount or not selections:
            return jsonify({"status": "error", "message": "የተላከው መረጃ አልተሟላም!"}), 400

        bet_amount = float(bet_amount)
        if bet_amount < 10:
            return jsonify({"status": "error", "message": "ቢያንስ 10 ብር መወራረድ አለብዎት!"}), 400

        result = deduct_balance_safely(str(user_id), bet_amount, "real")

        if result != "SUCCESS":
            return jsonify({"status": "error", "message": "በአካውንትዎ በቂ ቀሪ ሂሳብ የሎትም! እባክዎ ዲፖዚት ያድርጉ።"}), 400

        total_odds = 1.0
        for sel in selections:
            total_odds *= float(sel['odd'])

        possible_win = bet_amount * total_odds
        ticket_id = f"RS-{str(uuid.uuid4())[:6].upper()}"

        bet_data = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "amount": bet_amount,
            "total_odds": total_odds,
            "possible_win": possible_win,
            "selections": selections,
            "status": "pending", 
            "timestamp": time.time()
        }

        redis.hset(f"user_sports_bets:{user_id}", ticket_id, json.dumps(bet_data))

        history_entry = {
            "action": f"Sports Bet (Ticket: {ticket_id})", 
            "amount": bet_amount, 
            "status": "pending"
        }
        add_to_history(str(user_id), history_entry)

        return jsonify({
            "status": "success", 
            "message": f"ውርርድዎ በተሳካ ሁኔታ ተቆርጧል!\n\n🎟 ቲኬት: {ticket_id}\n💰 ሊያሸንፉ የሚችሉት: {possible_win:.2f} ብር"
        })

    except Exception as e:
        print(f"Place Bet Error: {e}")
        return jsonify({"status": "error", "message": "በሰርቨር ላይ የቴክኒክ ችግር አጋጥሟል!"}), 500


# =========================================
# 6. የ Redis ጤንነት መመርመሪያ (Debug)
# =========================================
@real_sports_bp.route('/api/debug/check_redis', methods=['GET'])
def debug_redis():
    data = redis.get(CACHE_KEY)
    if data:
        return jsonify({"status": "found", "data_length": len(json.loads(data))})
    return jsonify({"status": "empty"})
