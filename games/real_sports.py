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

# የጋራ Redis Key (በየቀኑ እንዳይቀያየር አንድ ቋሚ Key ብንጠቀም ይመረጣል ምክንያቱም በየ 10 ደቂቃው አዲስ ስለሚሆን)
CACHE_KEY = "cached_real_sports_odds"


# =========================================
# 1. የጀርባ አገልጋይ (Google App Script የሚጠራው - ዳታ የሚያመጣው)
# =========================================
@real_sports_bp.route('/api/internal/update_sports_data', methods=['GET'])
def update_sports_data():
    # ሚስጥራዊ ቁልፍ (GAS ላይ ሊንኩን ስታስገባ ?secret=mypassword123 ብለህ አስገባ)
    secret = request.args.get("secret")
    if secret != "mypassword123":
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    target_dates = [today_str, tomorrow_str]

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
                    "time": f['fixture']['date']
                }

        real_matches = []
        now_time = datetime.now()

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
                    
                    try:
                        raw_time = fixture_info["time"]
                        match_time_obj = datetime.fromisoformat(raw_time.replace('Z', '+03:00'))
                        if match_time_obj.replace(tzinfo=None) <= now_time:
                            continue
                    except Exception:
                        continue 

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
            # ዳታውን ወስዶ Redis ላይ ያስቀምጠዋል (GAS በየ 10 ደቂቃው ስለሚያድሰው ጊዜ መወሰን አያስፈልግም)
            redis.set(CACHE_KEY, json.dumps(real_matches))

        return jsonify({"status": "success", "message": f"✅ {len(real_matches)} ጨዋታዎች ተዘጋጅተው Redis ላይ ገብተዋል።"})

    except Exception as e:
        print(f"API Odds Fetching Exception: {e}")
        return jsonify({"status": "error", "message": "እውነተኛ ኦዶችን ማምጣት አልተቻለም"}), 500


# =========================================
# 2. ዌብሳይቱ (Frontend) ዳታ የሚወስድበት (እጅግ ፈጣኑ ራውት)
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
            # ገና ዳታ ከ API ተጎትቶ ካልመጣ
            return jsonify({"status": "success", "matches": []})

    except Exception as e:
        return jsonify({"status": "error", "message": "የዳታቤዝ ስህተት"}), 500


# =========================================
# 3. የ አድሚን Cache ማጥፊያ
# =========================================
@real_sports_bp.route('/api/admin/clear_cache', methods=['GET'])
def clear_cache_admin():
    secret_key = request.args.get('key')
    if secret_key != "MySecret123":
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    redis.delete(CACHE_KEY)
    return jsonify({"status": "success", "message": "Cache በተሳካ ሁኔታ ጠፍቷል!"})


# =========================================
# 4. ውርርድ መቁረጫ (Place Bet) 
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
