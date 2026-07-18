from flask import Blueprint, request, jsonify
import os
import requests
import json
import uuid
import time
# (ከ config.py የምታመጣቸው ነገሮች እንዳሉ ሆነው)
from config import redis, deduct_balance_safely, add_to_history, telegram_auth_required

real_sports_bp = Blueprint('real_sports', __name__)

API_KEY = os.environ.get("API_FOOTBALL_KEY")
API_HOST = "v3.football.api-sports.io"

# =========================================
# 1. ኦድ (Odds) ለማምጣት - እውነተኛ መረጃ (Real API Data)
# =========================================
@real_sports_bp.route('/api/sports/odds', methods=['GET'])
def get_odds():
    # 1. መጀመሪያ ኦዶች Redis ላይ ተቀምጠው (Cache) ከሆነ እንፈትሽ
    cached_odds = redis.get("cached_real_odds")
    if cached_odds:
        return jsonify({"status": "success", "matches": json.loads(cached_odds)})

    try:
        headers = {
            "x-apisports-key": API_KEY,
            "x-apisports-host": API_HOST
        }
        
        # 2. የዛሬን እውነተኛ ኦድ (Match Winner / 1x2) እንጠይቃለን
        url_odds = "https://v3.football.api-sports.io/odds"
        params_odds = {
            "date": time.strftime("%Y-%m-%d"),
            "bookmaker": 8, # Bet365
            "bet": 1 # Match Winner
        }
        response_odds = requests.get(url_odds, headers=headers, params=params_odds, timeout=10)
        odds_data = response_odds.json().get('response', [])

        # 3. የቡድኖችን ስም ለማግኘት መጀመሪያ የ Fixtures መረጃን እናመጣለን
        cached_matches = redis.get("cached_sports_matches")
        fixtures_dict = {}
        
        if cached_matches:
            for m in json.loads(cached_matches):
                fixtures_dict[m['fixture']['id']] = m['fixture']['teams']
        else:
            url_fixtures = "https://v3.football.api-sports.io/fixtures"
            params_fixtures = {"date": time.strftime("%Y-%m-%d"), "timezone": "Africa/Addis_Ababa"}
            res_fixtures = requests.get(url_fixtures, headers=headers, params=params_fixtures, timeout=10)
            for f in res_fixtures.json().get('response', []):
                fixtures_dict[f['fixture']['id']] = f['teams']

        # 4. ኦዱን (Odds) እና የቡድኖችን ስም (Teams) ማጣመር
        real_matches = []
        for item in odds_data:
            fixture_id = item['fixture']['id']
            
            if fixture_id not in fixtures_dict:
                continue
                
            teams = fixtures_dict[fixture_id]
            
            if not item['bookmakers'] or not item['bookmakers'][0]['bets']:
                continue
                
            bets = item['bookmakers'][0]['bets'][0]['values']
            odds_dict = {}
            
            for bet in bets:
                val = bet['value']
                odd = float(bet['odd'])
                if val == "Home": odds_dict["home"] = odd
                elif val == "Draw": odds_dict["draw"] = odd
                elif val == "Away": odds_dict["away"] = odd

            if "home" in odds_dict and "away" in odds_dict:
                real_matches.append({
                    "fixture": {
                        "id": fixture_id,
                        "teams": teams
                    },
                    "odds": odds_dict
                })
            
            if len(real_matches) >= 30:
                break
                
        # 5. መረጃውን Redis ውስጥ Cache እናደርገዋለን
        redis.setex("cached_real_odds", 3600, json.dumps(real_matches))
        
        return jsonify({"status": "success", "matches": real_matches})
        
    except Exception as e:
        print(f"API Odds Error: {e}")
        return jsonify({"status": "error", "message": "እውነተኛ ኦዶችን ማምጣት አልተቻለም"}), 500


# =========================================
# 2. የጨዋታ ዝርዝር (Fixtures) ለማምጣት - በ Redis Caching የተሻሻለ
# =========================================
@real_sports_bp.route('/api/sports/matches', methods=['GET'])
def get_matches():
    # Redis ቁልፍን በየቀኑ እንዲቀየር እናድርገው (በቀን አንድ ጊዜ ብቻ እንዲያዘምን)
    today = time.strftime("%Y-%m-%d")
    cache_key = f"sports_matches:{today}"
    
    cached_matches = redis.get(cache_key)
    if cached_matches:
        return jsonify({"status": "success", "matches": json.loads(cached_matches)})

    url = "https://v3.football.api-sports.io/fixtures" 
    headers = {"x-apisports-key": API_KEY, "x-apisports-host": API_HOST}
    params = {"date": today, "timezone": "Africa/Addis_Ababa"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        raw_data = response.json()
        
        matches = []
        for fixture in raw_data.get('response', [])[:30]: 
            # ሰዓትን እና ሊግን ጨምረን እንላክ
            matches.append({
                "fixture": {
                    "id": fixture['fixture']['id'], 
                    "teams": fixture['teams'],
                    "league": fixture['league']['name'],
                    "time": fixture['fixture']['date'] # የጨዋታ ሰዓት
                }
            })

        redis.setex(cache_key, 86400, json.dumps(matches)) # ለ24 ሰዓት ያህል ይቆይ
        return jsonify({"status": "success", "matches": matches})
    except Exception as e:
        return jsonify({"status": "error", "message": "ጨዋታዎችን ማምጣት አልተቻለም"}), 500

# =========================================
# 3. ውርርድ መቁረጫ (Place Bet) ራውት
# =========================================
@real_sports_bp.route('/api/sports/place_bet', methods=['POST'])
@telegram_auth_required  # 🛡️ የደህንነት ማጣሪያ (Security Decorator)
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

        # 🛠️ ማስተካከያ 1: deduct_balance_safely የሚመልሰው አንድ ቃል (String) ነው
        result = deduct_balance_safely(str(user_id), bet_amount, "real")
        
        if result != "SUCCESS":
            return jsonify({"status": "error", "message": "በአካውንትዎ በቂ ቀሪ ሂሳብ የሎትም! እባክዎ ዲፖዚት ያድርጉ።"}), 400

        # 2. ጠቅላላ ኦድ እና ሊያሸንፉ የሚችሉትን ብር (Possible Win) ማስላት
        total_odds = 1.0
        for sel in selections:
            total_odds *= float(sel['odd'])
            
        possible_win = bet_amount * total_odds

        # 3. የቲኬት ቁጥር መፍጠር
        ticket_id = f"RS-{str(uuid.uuid4())[:6].upper()}"

        # 4. ቲኬቱን Redis ላይ ሴቭ ማድረግ 
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

        # 🛠️ ማስተካከያ 2: ታሪክ ውስጥ Dictionary ፎርማት መላክ አለበት
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
