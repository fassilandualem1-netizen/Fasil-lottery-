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
    # 1. ኦድ ከማምጣት ይልቅ ጨዋታዎችን (Fixtures) እንዲያመጣ ቀይረነዋል (ስሞቹን ለማግኘት)
    url = "https://v3.football.api-sports.io/fixtures" 

    headers = {
        "x-apisports-key": API_KEY,
        "x-apisports-host": API_HOST
    }

    # 2. የሊግ ገደቡን አንስተነዋል፣ የዛሬን ማንኛውም ጨዋታ እንዲያመጣ
    params = {
        "date": time.strftime("%Y-%m-%d"),
        "timezone": "Africa/Addis_Ababa"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        raw_data = response.json()

        processed_matches = []
        
        # 3. የመጀመሪያዎቹን 10 ጨዋታዎች ብቻ እንወስዳለን
        for item in raw_data.get('response', [])[:10]:
            fixture = item.get('fixture', {})
            teams = item.get('teams', {})
            
            # 4. ለሙከራ (Testing) የሚሆኑ ኦዶች
            # (እውነተኛ ኦድ ከ API-Football ለማምጣት ውስብስብ እና የነፃውን ፓኬጅ ቶሎ ስለሚጨርስ ለአሁኑ ይሄኛው ይመረጣል)
            odds_data = {
                "home": 2.15, 
                "draw": 3.10, 
                "away": 2.80
            }

            processed_matches.append({
                "fixture": {
                    "id": fixture.get('id'), 
                    "teams": teams
                },
                "odds": odds_data
            })

        return jsonify({"status": "success", "matches": processed_matches})

    except Exception as e:
        return jsonify({"status": "error", "message": "ጨዋታዎችን ማምጣት አልተቻለም"}), 500

# =========================================
# 2. የጨዋታ ዝርዝር (Fixtures) ለማምጣት
# =========================================
@real_sports_bp.route('/api/sports/matches', methods=['GET'])
def get_matches():
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
        for fixture in raw_data.get('response', [])[:30]: 
            matches.append({
                "fixture": {
                    "id": fixture['fixture']['id'], 
                    "teams": fixture['teams'],
                    "league": fixture['league']['name'] 
                }
            })

        return jsonify({"status": "success", "matches": matches})
    except Exception as e:
        return jsonify({"status": "error", "message": "ጨዋታዎችን ማምጣት አልተቻለም"}), 500
