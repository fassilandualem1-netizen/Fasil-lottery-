from flask import Blueprint, request, jsonify
import os
import requests
import json
import uuid
import time
from datetime import datetime, timedelta # 👈 የ 48 ሰዓት ቀናትን ለማስላት የተጨመረ

# (ከ config.py የምታመጣቸው ነገሮች እንዳሉ ሆነው)
from config import redis, deduct_balance_safely, add_to_history, telegram_auth_required

real_sports_bp = Blueprint('real_sports', __name__)

API_KEY = os.environ.get("API_FOOTBALL_KEY")
API_HOST = "v3.football.api-sports.io"


# =========================================
# 1. ኦድ (Odds) ለማምጣት - የ 48 ሰዓት መረጃ (Today & Tomorrow)
# =========================================
@real_sports_bp.route('/api/sports/odds', methods=['GET'])
def get_odds():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    target_dates = [today_str, tomorrow_str]

    cache_key = f"cached_real_odds_48h_{today_str}"
    
    # 1. መጀመሪያ Cache የተደረገ ዳታ ካለ እንፈትሻለን
    cached_odds = redis.get(cache_key)
    if cached_odds:
        matches = json.loads(cached_odds)
        # 🚀 ማስተካከያ 1፡ Cache የተደረገው ዳታ ባዶ ካልሆነ ብቻ መልስ
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
            
            # API Error ቼክ ማድረግ
            if res_fixtures.status_code != 200 or not res_fixtures.json().get('response'):
                print(f"API Fixture Error for {d}: {res_fixtures.text}")
                continue

            for f in res_fixtures.json().get('response', []):
                fixtures_dict[f['fixture']['id']] = {
                    "teams": f['teams'],
                    "league": f['league']['name'],
                    "time": f['fixture']['date']
                }

        real_matches = []
        for d in target_dates:
            url_odds = "https://v3.football.api-sports.io/odds"
            # 🚀 ማስተካከያ 2፡ "bookmaker": 8 የሚለውን አጠፋነው። ያገኘውን ኦድ ሁሉ ያመጣል።
            params_odds = {
                "date": d,
                "bet": 1 # Match Winner
            }
            response_odds = requests.get(url_odds, headers=headers, params=params_odds, timeout=10)
            
            if response_odds.status_code != 200:
                print(f"API Odds Error for {d}: {response_odds.text}")
                continue
                
            odds_data = response_odds.json().get('response', [])

            for item in odds_data:
                fixture_id = item['fixture']['id']

                if fixture_id not in fixtures_dict:
                    continue

                fixture_info = fixtures_dict[fixture_id]

                # የትኛውም bookmaker ቢሆን የመጀመሪያውን ኦድ እንወስዳለን
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
                            "teams": fixture_info["teams"],
                            "league": fixture_info["league"],
                            "time": fixture_info["time"]
                        },
                        "odds": odds_dict
                    })

                if len(real_matches) >= 50:
                    break
            
            if len(real_matches) >= 50:
                break

        # 🚀 ማስተካከያ 3፡ ጨዋታዎች ከተገኙ ብቻ Cache እናደርጋለን! (ባዶውን እንዳይይዝ)
        if len(real_matches) > 0:
            redis.setex(cache_key, 3600, json.dumps(real_matches))
        else:
            print("Warning: No matches with odds found for today/tomorrow.")

        return jsonify({"status": "success", "matches": real_matches})

    except Exception as e:
        print(f"API Odds Fetching Exception: {e}")
        return jsonify({"status": "error", "message": "እውነተኛ ኦዶችን ማምጣት አልተቻለም"}), 500

# place_bet ራውትህ ትክክል ነው፣ እሱን መንካት አይጠበቅብህም!

# =========================================
# 2. ውርርድ መቁረጫ (Place Bet) ራውት
# =========================================
@real_sports_bp.route('/api/sports/place_bet', methods=['POST'])
@telegram_auth_required  # 🛡️ የደህንነት ማጣሪያ
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

        # ቀሪ ሂሳብ መቀነስ
        result = deduct_balance_safely(str(user_id), bet_amount, "real")

        if result != "SUCCESS":
            return jsonify({"status": "error", "message": "በአካውንትዎ በቂ ቀሪ ሂሳብ የሎትም! እባክዎ ዲፖዚት ያድርጉ።"}), 400

        # ጠቅላላ ኦድ እና ሊያሸንፉ የሚችሉትን ብር (Possible Win) ማስላት
        total_odds = 1.0
        for sel in selections:
            total_odds *= float(sel['odd'])

        possible_win = bet_amount * total_odds

        # የቲኬት ቁጥር መፍጠር
        ticket_id = f"RS-{str(uuid.uuid4())[:6].upper()}"

        # ቲኬቱን Redis ላይ ሴቭ ማድረግ 
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

        # ታሪክ ውስጥ መመዝገብ
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
