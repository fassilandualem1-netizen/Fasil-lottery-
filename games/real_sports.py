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
# 1. ኦድ (Odds) ለማምጣት - ራውቱን እና ስሙን ቀየርነው
# =========================================
@real_sports_bp.route('/api/sports/odds', methods=['GET'])
def get_odds():
    # ከ API ማምጣቱን ትተን፣ ራሳችን የፈጠርነውን የሙከራ ዳታ እንልካለን
    mock_matches = [
        {
            "fixture": {
                "id": 101,
                "teams": {
                    "home": {"name": "Arsenal"},
                    "away": {"name": "Chelsea"}
                }
            },
            "odds": {"home": 2.15, "draw": 3.10, "away": 2.80}
        },
        {
            "fixture": {
                "id": 102,
                "teams": {
                    "home": {"name": "Real Madrid"},
                    "away": {"name": "Barcelona"}
                }
            },
            "odds": {"home": 1.95, "draw": 3.40, "away": 3.20}
        },
        {
            "fixture": {
                "id": 103,
                "teams": {
                    "home": {"name": "St. George"},
                    "away": {"name": "Ethiopian Coffee"}
                }
            },
            "odds": {"home": 2.50, "draw": 2.80, "away": 2.60}
        }
    ]

    return jsonify({"status": "success", "matches": mock_matches})

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
