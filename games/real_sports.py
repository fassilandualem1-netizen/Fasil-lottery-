from flask import Blueprint, request, jsonify
import os
import requests
import json
import uuid
import time
from config import redis, deduct_balance_safely, add_to_history, telegram_auth_required

real_sports_bp = Blueprint('real_sports', __name__)

API_KEY = os.environ.get("API_FOOTBALL_KEY")
API_HOST = "v3.football.api-sports.io"

@real_sports_bp.route('/api/sports/matches', methods=['GET'])
def get_matches():
    # ቶፕ ሊጎች (39=EPL, 140=LaLiga, 135=SerieA, 78=Bundesliga, 61=Ligue1)
    url = "https://v3.football.api-sports.io/odds" 
    
    headers = {
        "x-apisports-key": API_KEY,
        "x-apisports-host": API_HOST
    }
    
    # ፊልተር ማድረግ (የዛሬ ጨዋታዎች ብቻ እና ቶፕ ሊጎች)
    params = {
        "date": time.strftime("%Y-%m-%d"),
        "league": "39,140,135,78,61", 
        "season": "2026"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        raw_data = response.json()
        
        # API-Sports ዳታው የተወሳሰበ ስለሆነ ለFrontend ቀላል እንዲሆንልን ማስተካከል (Mapping)
        processed_matches = []
        for item in raw_data.get('response', [])[:10]: # የመጀመሪያዎቹን 10 ጨዋታዎች ብቻ
            fixture = item.get('fixture', {})
            # Bookmaker 1 = Bet365 (ብዙውን ጊዜ ኦድ የሚገኝበት ነው)
            bookmakers = item.get('bookmakers', [])
            odds_data = {"home": 2.0, "draw": 3.0, "away": 2.0} # Default
            
            if bookmakers:
                bets = bookmakers[0].get('bets', [])
                if bets:
                    values = bets[0].get('values', [])
                    # Mapping: 1, X, 2
                    for v in values:
                        if v['value'] == 'Home': odds_data['home'] = v['odd']
                        if v['value'] == 'Draw': odds_data['draw'] = v['odd']
                        if v['value'] == 'Away': odds_data['away'] = v['odd']
            
            processed_matches.append({
                "fixture": {"id": fixture['id'], "teams": fixture['teams']},
                "odds": odds_data
            })
        
        return jsonify({"status": "success", "matches": processed_matches})
        
    except Exception as e:
        return jsonify({"status": "error", "message": "ጨዋታዎችን ማምጣት አልተቻለም"}), 500

# 2. ውርርድ መቀበያ (Place Bet)
@real_sports_bp.route('/api/sports/matches', methods=['GET'])
def get_matches():
    url = "https://v3.football.api-sports.io/fixtures" # ለጨዋታዎች ዝርዝር
    
    headers = {
        "x-apisports-key": API_KEY,
        "x-apisports-host": API_HOST
    }
    
    # ማጣሪያውን (League Filter) አጥፍተነዋል፣ በቀን ብቻ እንጠራለን
    # በዚህ መልኩ ማንኛውም የዛሬ ጨዋታ (World Cup, Friendly, League) ይመጣል
    params = {
        "date": time.strftime("%Y-%m-%d"),
        "timezone": "Africa/Addis_Ababa" 
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        raw_data = response.json()
        
        # የ API-Sports ዳታን ማዘጋጀት
        matches = []
        for fixture in raw_data.get('response', [])[:30]: # የመጀመሪያዎቹን 30 ጨዋታዎች (ቶፕ 30) ብቻ
            matches.append({
                "fixture": {
                    "id": fixture['fixture']['id'], 
                    "teams": fixture['teams'],
                    "league": fixture['league']['name'] # ሊጉን ለማሳየት
                }
            })
        
        return jsonify({"status": "success", "matches": matches})
    except Exception as e:
        return jsonify({"status": "error", "message": "ጨዋታዎችን ማምጣት አልተቻለም"}), 500
