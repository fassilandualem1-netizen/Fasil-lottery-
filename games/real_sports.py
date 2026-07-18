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
    # 1. መጀመሪያ Redis ላይ መረጃው እንዳለ እንፈትሽ
    cached_matches = redis.get("cached_sports_matches")
    if cached_matches:
        # ካለ፣ ከ Redis ላይ በቀጥታ እናንብብ (API ጥሪ አያደርግም)
        return jsonify({"status": "success", "matches": json.loads(cached_matches)})

    # 2. ከሌለ ብቻ የ API ጥሪ እናድርግ
    url = "https://v3.football.api-sports.io/fixtures" 
    headers = {
        "x-apisports-key": API_KEY,
        "x-apisports-host": API_HOST
    }
    params = {
        "date": time.strftime("%Y-%m-%d"),
        "timezone": "Africa/Addis_Ababa" 
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        raw_data = response.json()

        matches = []
        # መረጃውን ማጣራት
        for fixture in raw_data.get('response', [])[:30]: 
            matches.append({
                "fixture": {
                    "id": fixture['fixture']['id'], 
                    "teams": fixture['teams'],
                    "league": fixture['league']['name'] 
                }
            })

        # 3. ያገኘነውን ውጤት ለ1 ሰዓት (3600 ሰከንድ) Redis ውስጥ እናስቀምጠው
        redis.setex("cached_sports_matches", 3600, json.dumps(matches))

        return jsonify({"status": "success", "matches": matches})
    except Exception as e:
        return jsonify({"status": "error", "message": "ጨዋታዎችን ማምጣት አልተቻለም"}), 500
