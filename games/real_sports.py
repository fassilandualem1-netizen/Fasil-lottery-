from flask import Blueprint, request, jsonify
import os
import requests
import json
import uuid
import time
from datetime import datetime, timedelta

# (ከ config.py የምታመጣቸው ነገሮች እንዳሉ ሆነው)
from config import redis, deduct_balance_safely, add_to_history, telegram_auth_required

real_sports_bp = Blueprint('real_sports', __name__)

API_KEY = os.environ.get("API_FOOTBALL_KEY")
API_HOST = "v3.football.api-sports.io"


# ይህንን ከሌሎች route-ዎች በታች ጨምር
@real_sports_bp.route('/api/admin/clear_cache', methods=['GET'])
def clear_cache_admin():
    # ሚስጥራዊ ቁልፍ (ከመረጥክ በኋላ ሊንኩን ስትጠራ በ browser ላይ ይህንን ታስገባለህ)
    secret_key = request.args.get('key')
    if secret_key != "MySecret123": # የፈለግከውን ፓስወርድ እዚህ ቀይረው
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    # ዛሬ ያለውን ቀን እና የ cache key-ውን እናውቃለን
    today_str = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"cached_real_odds_v2_{today_str}"
    
    # Redis ላይ ማጥፋት
    redis.delete(cache_key)
    
    return jsonify({"status": "success", "message": f"Cache {cache_key} በተሳካ ሁኔታ ጠፍቷል!"})

# =========================================
# 1. ኦድ (Odds) ለማምጣት
# =========================================
@real_sports_bp.route('/api/sports/odds', methods=['GET'])
def get_odds():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    target_dates = [today_str, tomorrow_str]

    cache_key = f"cached_real_odds_v2_{today_str}"

    cached_odds = redis.get(cache_key)
    if cached_odds:
        matches = json.loads(cached_odds)
        if len(matches) > 0:
            return jsonify({"status": "success", "matches": matches})

    try:
        headers = {
            "x-apisports-key": API_KEY,
            "x-apisports-host": API_HOST
        }

        fixtures_dict = {}
        for d in target_dates:
            url_fixtures = "https://v3.football.api-sports.io/fixtures"
            params_fixtures = {"date": d, "timezone": "Africa/Addis_Ababa"}
            res_fixtures = requests.get(url_fixtures, headers=headers, params=params_fixtures, timeout=10)

            if res_fixtures.status_code != 200 or not res_fixtures.json().get('response'):
                continue

            for f in res_fixtures.json().get('response', []):
                fixtures_dict[f['fixture']['id']] = {
                    "teams": f['teams'],
                    "league": f['league']['name'],
                    "time": f['fixture']['date'] # ISO Format string
                }

        real_matches = []
        now_time = datetime.now() # የጨዋታዎችን ሰዓት ለማጣራት የአሁኑን ሰዓት እንይዛለን

        for d in target_dates:
            for page in range(1, 11):  
                url_odds = "https://v3.football.api-sports.io/odds"
                params_odds = {
                    "date": d,
                    "bet": 1,
                    "bookmaker": 8,
                    "page": page
                }
                response_odds = requests.get(url_odds, headers=headers, params=params_odds, timeout=10)

                if response_odds.status_code != 200:
                    break

                res_json = response_odds.json()
                odds_data = res_json.get('response', [])

                if not odds_data:
                    break 

                for item in odds_data:
                    fixture_id = item['fixture']['id']

                    if fixture_id not in fixtures_dict:
                        continue

                    fixture_info = fixtures_dict[fixture_id]
                    
                    # --- ለ Betting የተስተካከለ የሰዓት ማጣሪያ (Strict Time Filter) ---
                    try:
                        raw_time = fixture_info["time"]
                        # ከ API የመጣውን ሰዓት ወደ datetime object መቀየር
                        match_time_obj = datetime.fromisoformat(raw_time.replace('Z', '+03:00'))
                        
                        # የጨዋታው ሰዓት አሁን ካለንበት ሰዓት ጋር እኩል ከሆነ ወይም ካለፈ (ያለቀ/የተጀመረ) እናስወግደዋለን
                        if match_time_obj.replace(tzinfo=None) <= now_time:
                            continue
                    except Exception:
                        continue # ሰዓቱን ማንበብ ካልቻለ ለጥንቃቄ ሲባል ጨዋታውን ይዘለዋል
                    # -----------------------------------------------------------------

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

                    # ለተጠቃሚው በሚያምር ሁኔታ ለማሳየት ሰዓቱን ብቻ መውሰድ (ምሳሌ፡ "15:30")
                    clean_time = match_time_obj.strftime("%H:%M")

                    if "home" in odds_dict and "away" in odds_dict:
                        real_matches.append({
                            "fixture": {
                                "id": fixture_id,
                                "teams": fixture_info["teams"],
                                "league": fixture_info["league"],
                                "time": clean_time,
                                "date": d
                            },
                            "odds": odds_dict
                        })

                    if len(real_matches) >= 150:
                        break

                if len(real_matches) >= 150:
                    break

        if len(real_matches) > 0:
            # Cache ለ 6 ሰዓት (21600 seconds) ይቀመጣል
            redis.setex(cache_key, 21600, json.dumps(real_matches))

        return jsonify({"status": "success", "matches": real_matches})

    except Exception as e:
        print(f"API Odds Fetching Exception: {e}")
        return jsonify({"status": "error", "message": "እውነተኛ ኦዶችን ማምጣት አልተቻለም"}), 500

# =========================================
# 2. ውርርድ መቁረጫ (Place Bet) ራውት
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
