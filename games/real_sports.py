from flask import Blueprint, request, jsonify
import os
import requests
import json
import uuid
import time
from datetime import datetime, timedelta

# ከ config.py የምታመጣቸው 
from config import (
    redis,
    deduct_balance_safely,
    add_to_history,
    update_history_tx_status,
    telegram_auth_required,
    get_balance_safely,
    add_balance_safely
)

real_sports_bp = Blueprint('real_sports', __name__)

# አዲሱን የ The Odds API ቁልፍ መጠቀም
API_KEY = os.environ.get("THE_ODDS_API_KEY")

# የጋራ Redis Key
CACHE_KEY = "cached_real_sports_odds"
ADMIN_SECRET = os.environ.get("SPORTS_ADMIN_SECRET", "MySecret123")


def _normalize_selection(selection):
    if not isinstance(selection, dict):
        return None

    pick = str(selection.get("pick", "")).strip().lower()
    market = str(selection.get("market", "")).strip().lower()

    if not market:
        market = "double_chance" if pick in {"1x", "12", "x2"} else "1x2"

    valid_picks = {"home", "draw", "away", "1x", "12", "x2"}
    if pick not in valid_picks:
        return None

    try:
        odd = round(float(selection.get("odd", 0)), 2)
    except (TypeError, ValueError):
        return None

    if odd <= 1:
        return None

    return {
        "match_id": str(selection.get("match_id", "")).strip(),
        "pick": pick,
        "odd": odd,
        "team": str(selection.get("team", "")).strip() or pick.upper(),
        "home_team": str(selection.get("home_team", "")).strip(),
        "away_team": str(selection.get("away_team", "")).strip(),
        "league": str(selection.get("league", "")).strip() or "Unknown League",
        "market": market,
        "status": "pending"
    }


def _calculate_bonus_percent(selection_count):
    if selection_count >= 10:
        return 10
    if selection_count >= 5:
        return 7
    if selection_count >= 3:
        return 5
    return 0


def _decode_json_payload(payload):
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return json.loads(payload)


def _serialize_ticket(ticket_info):
    timestamp = ticket_info.get("timestamp", 0)
    return {
        "id": ticket_info.get("ticket_id"),
        "stake": ticket_info.get("stake"),
        "total_odds": ticket_info.get("total_odds", 0),
        "base_win": round(ticket_info.get("base_win", 0), 2),
        "bonus_percent": ticket_info.get("bonus_percent", 0),
        "bonus_amount": round(ticket_info.get("bonus_amount", 0), 2),
        "possible_win": round(ticket_info.get("possible_win", 0), 2),
        "status": ticket_info.get("status", "pending"),
        "result": ticket_info.get("result"),
        "timestamp": timestamp,
        "placed_at": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M") if timestamp else "",
        "selection_count": ticket_info.get("selection_count", len(ticket_info.get("selections", []))),
        "selections": ticket_info.get("selections", [])
    }


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
    secret = request.args.get("secret")
    if secret != "mypassword123":
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if not API_KEY:
        return jsonify({"status": "error", "message": "API Key አልተገኘም"}), 500

    try:
        url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={API_KEY}&regions=eu,uk&markets=h2h"
        response = requests.get(url, timeout=15)

        if response.status_code != 200:
            return jsonify({"status": "error", "message": f"API Error: {response.text}"}), response.status_code

        data = response.json()
        real_matches = []
        now_utc = datetime.utcnow() # ትክክለኛው የ UTC ሰዓት

        for item in data:
            match_id = item.get("id")
            home_team = item.get("home_team")
            away_team = item.get("away_team")
            commence_time_str = item.get("commence_time")
            league = item.get("sport_title", "Unknown League")

            try:
                # ከ API የመጣውን UTC ሰዓት ማንበብ
                match_time_utc = datetime.strptime(commence_time_str, "%Y-%m-%dT%H:%M:%SZ")
                
                # ጨዋታው ከጀመረ ዝለለው (በ UTC ነው የምናወዳድረው)
                if match_time_utc <= now_utc:
                    continue  

                # ወደ ኢትዮጵያ/Local ሰዓት (UTC+3) መቀየር (ተጠቃሚዎችህ ውጪ ከሆኑ ይሄን ማስተካከል ትችላለህ)
                local_time_obj = match_time_utc + timedelta(hours=3)
                clean_time = local_time_obj.strftime("%H:%M")
                match_date = local_time_obj.strftime("%Y-%m-%d")
                
                # ለ sorting እንዲመቸን ፎርማት የተደረገ ሙሉ ሰዓት
                sortable_time = match_time_utc.timestamp()

            except Exception:
                clean_time = "TBA"
                match_date = "TBA"
                sortable_time = float('inf')

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

            if "home" in odds_dict and "away" in odds_dict and "draw" in odds_dict:
                h = float(odds_dict["home"])
                d = float(odds_dict["draw"])
                a = float(odds_dict["away"])
                
                odds_dict["dc_1x"] = round((h * d) / (h + d), 2)
                odds_dict["dc_12"] = round((h * a) / (h + a), 2)
                odds_dict["dc_x2"] = round((d * a) / (d + a), 2)

                real_matches.append({
                    "fixture": {
                        "id": match_id,
                        "teams": {
                            "home": {"name": home_team},
                            "away": {"name": away_team}
                        },
                        "league": league,
                        "time": clean_time,
                        "date": match_date,
                        "sort_time": sortable_time # ለመደርደር ብቻ የሚያገለግል
                    },
                    "odds": odds_dict
                })

        if len(real_matches) > 0:
            # 🌟 ጨዋታዎችን በሰዓት ቅደም ተከተል (Upcoming) ከቅርብ ጊዜ ወደ ሩቅ ጊዜ ማደራጀት
            real_matches.sort(key=lambda x: x["fixture"]["sort_time"])
            
            # sort_time ለ ፊትለፊት ስለማያስፈልግ ማጥፋት እንችላለን (አማራጭ ነው)
            for m in real_matches:
                m["fixture"].pop("sort_time", None)

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
        tab_type = request.args.get('tab', 'top')
        
        # First try cached real API matches, if available
        cached_odds = redis.get(CACHE_KEY)
        if cached_odds:
            matches = json.loads(cached_odds)
            if tab_type == 'top':
                top_leagues = ['Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1', 'UEFA Champions League', 'Ethiopian Premier League']
                top_matches = [m for m in matches if any(league in m['fixture']['league'] for league in top_leagues)]
                if not top_matches:
                    top_matches = matches[:15]
                return jsonify({"status": "success", "matches": top_matches})
            return jsonify({"status": "success", "matches": matches})
            
        # Fallback to our stored admin matches
        stored_matches = get_all_sports_matches()
        # Convert our stored match format to what the frontend expects
        frontend_matches = []
        for m in stored_matches:
            if not m.get("active", True):
                continue
            start_time = int(m.get("start_time") or (time.time() + 3600))
            match_dt = datetime.fromtimestamp(start_time)
            # Convert odds
            odds = m.get("odds", {})
            home_odd = odds.get("1", 2.0)
            draw_odd = odds.get("X", 3.0)
            away_odd = odds.get("2", 2.5)
            # Add double chance odds
            try:
                dc_1x = round((home_odd * draw_odd) / (home_odd + draw_odd), 2)
            except:
                dc_1x = 1.5
            try:
                dc_x2 = round((draw_odd * away_odd) / (draw_odd + away_odd), 2)
            except:
                dc_x2 = 1.5
            try:
                dc_12 = round((home_odd * away_odd) / (home_odd + away_odd), 2)
            except:
                dc_12 = 1.5
                
            # Format for frontend
            frontend_matches.append({
                "fixture": {
                    "id": m.get("id"),
                    "teams": {
                        "home": {"name": m.get("home", "Home")},
                        "away": {"name": m.get("away", "Away")}
                    },
                    "league": m.get("league", "Unknown League"),
                    "time": match_dt.strftime("%H:%M"),
                    "date": match_dt.strftime("%Y-%m-%d"),
                    "sort_time": start_time
                },
                "bookmakers": [{
                    "markets": [{
                        "outcomes": [
                            {"name": m.get("home", "Home"), "price": home_odd},
                            {"name": "Draw", "price": draw_odd},
                            {"name": m.get("away", "Away"), "price": away_odd}
                        ]
                    }]
                }],
                "odds": {
                    "home": home_odd,
                    "draw": draw_odd,
                    "away": away_odd,
                    "dc_1x": dc_1x,
                    "dc_x2": dc_x2,
                    "dc_12": dc_12
                }
            })

        frontend_matches.sort(key=lambda item: item["fixture"].get("sort_time", 0))
        for item in frontend_matches:
            item["fixture"].pop("sort_time", None)
        
        if tab_type == 'top':
            top_leagues = ['Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1', 'UEFA Champions League', 'Ethiopian Premier League']
            top_matches = [m for m in frontend_matches if any(league in m['fixture']['league'] for league in top_leagues)]
            if not top_matches:
                top_matches = frontend_matches[:15]
            return jsonify({"status": "success", "matches": top_matches})
            
        return jsonify({"status": "success", "matches": frontend_matches})

    except Exception as e:
        print(f"Get Odds Error: {e}")
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
        data = request.json or {}
        user_id = str(data.get('user_id', '')).strip()
        bet_amount = data.get('bet_amount')
        selections = data.get('selections')
        
        if not user_id or not bet_amount or not selections:
            return jsonify({"status": "error", "message": "የተላከው መረጃ አልተሟላም!"}), 400

        if not isinstance(selections, list):
            return jsonify({"status": "error", "message": "የውርርድ ምርጫዎች በትክክል አልተላኩም!"}), 400
        
        bet_amount = float(bet_amount)
        if bet_amount < 10:
            return jsonify({"status": "error", "message": "ቢያንስ 10 ብር መወራረድ አለብዎት!"}), 400
        if bet_amount > 100000:
            return jsonify({"status": "error", "message": "ከፍተኛ የውርርድ መጠን ተፈቅዶ አይደለም!"}), 400

        normalized_selections = []
        total_odds = 1.0
        seen_match_ids = set()

        for raw_selection in selections:
            selection = _normalize_selection(raw_selection)
            if not selection:
                return jsonify({"status": "error", "message": "የተላከው የውርርድ ምርጫ ልክ አይደለም!"}), 400

            if not selection["match_id"] or selection["match_id"] in seen_match_ids:
                return jsonify({"status": "error", "message": "ተመሳሳይ ጨዋታ ከአንድ ጊዜ በላይ መምረጥ አይቻልም!"}), 400

            normalized_selections.append(selection)
            seen_match_ids.add(selection["match_id"])
            total_odds *= selection["odd"]

        if len(normalized_selections) > 20:
            return jsonify({"status": "error", "message": "በአንድ ቲኬት ከ20 በላይ ምርጫ አይፈቀድም!"}), 400
        
        result = deduct_balance_safely(str(user_id), bet_amount, "real")
        
        if result != "SUCCESS":
            return jsonify({"status": "error", "message": "በአካውንትዎ በቂ ቀሪ ሂሳብ የሎትም! እባክዎ ዲፖዚት ያድርጉ።"}), 400

        total_odds = round(total_odds, 2)
        base_win = round(bet_amount * total_odds, 2)
        bonus_percent = _calculate_bonus_percent(len(normalized_selections))
        bonus_amount = round(base_win * (bonus_percent / 100), 2)
        possible_win = round(base_win + bonus_amount, 2)
        ticket_id = f"RS-{str(uuid.uuid4())[:6].upper()}"
        current_balance = get_balance_safely(str(user_id), "real")
        
        bet_data = {
            "id": ticket_id,
            "ticket_id": ticket_id,
            "user_id": user_id,
            "stake": bet_amount,
            "total_odds": total_odds,
            "base_win": base_win,
            "bonus_percent": bonus_percent,
            "bonus_amount": bonus_amount,
            "possible_win": possible_win,
            "selection_count": len(normalized_selections),
            "selections": normalized_selections,
            "status": "pending",
            "result": None,
            "timestamp": time.time()
        }
        
        redis.hset(f"user_sports_bets:{user_id}", ticket_id, json.dumps(bet_data))
        
        history_entry = {
            "tx_id": ticket_id,
            "type": "Sports Bet",
            "action": f"Sports Bet x{len(normalized_selections)} (Ticket: {ticket_id})",
            "amount": bet_amount,
            "status": "pending"
        }
        add_to_history(str(user_id), history_entry)
        
        return jsonify({
            "status": "success", 
            "ticket_id": ticket_id,
            "selection_count": len(normalized_selections),
            "total_odds": total_odds,
            "base_win": base_win,
            "bonus_percent": bonus_percent,
            "bonus_amount": bonus_amount,
            "possible_win": possible_win,
            "balance": current_balance,
            "message": f"ውርርድዎ በተሳካ ሁኔታ ተቆርጧል!\n\nቲኬት: {ticket_id}\nምርጫዎች: {len(normalized_selections)}\nጠቅላላ ኦድስ: {total_odds:.2f}\nቦነስ: {bonus_percent}%\nሊያሸንፉ የሚችሉት: {possible_win:.2f} ብር"
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


# =========================================
# 7. የሊጎችን ዝርዝር (Menu) ከ A-Z የሚያመጣ
# =========================================
@real_sports_bp.route('/api/sports/leagues', methods=['GET'])
def get_leagues_menu():
    if not API_KEY:
        return jsonify({"status": "error", "message": "API Key አልተገኘም"}), 500
    
    try:
        url = f'https://api.the-odds-api.com/v4/sports/?apiKey={API_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "የሊግ ዝርዝር ማምጣት አልተቻለም"}), response.status_code
        
        leagues_list = response.json()
        
        # የእግር ኳስ (Soccer) ሊጎችን ብቻ መምረጥ
        soccer_leagues = [league for league in leagues_list if league.get("group") == "Soccer"]
        
        # ሊጎቹን በስማቸው (title) መሰረት ከ A-Z ማደራጀት
        soccer_leagues.sort(key=lambda x: x.get("title", ""))
        
        return jsonify({
            "status": "success", 
            "total_leagues": len(soccer_leagues),
            "leagues": soccer_leagues
        }), 200

    except Exception as e:
        print(f"API Leagues Fetching Exception: {e}")
        return jsonify({"status": "error", "message": "የሊጎችን ዝርዝር ማምጣት አልተቻለም"}), 500



# =========================================
# 8. የእኔ ቲኬቶች (My Bets) ማውጫ
# =========================================
@real_sports_bp.route('/api/sports/my_bets', methods=['GET'])
@telegram_auth_required
def get_my_bets():
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"status": "error", "message": "User ID አልተገኘም!"}), 400

        redis_key = f"user_sports_bets:{user_id}"
        user_bets_raw = redis.hgetall(redis_key) 
        
        tickets = []
        if user_bets_raw:
            for t_id, t_data in user_bets_raw.items():
                try:
                    ticket_info = _decode_json_payload(t_data)
                except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                    continue
                tickets.append(_serialize_ticket(ticket_info))
        
        tickets.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        return jsonify({"status": "success", "tickets": tickets}), 200

    except Exception as e:
        print(f"Get My Bets Error: {e}")
        return jsonify({"status": "error", "message": "ቲኬቶችን ማምጣት አልተቻለም!"}), 500


# --- ADMIN HELPER: Settle a Bet ---
@real_sports_bp.route('/api/sports/admin/settle', methods=['POST'])
@real_sports_bp.route('/admin/settle', methods=['POST'])
def admin_settle_bet():
    """Admin-only endpoint to settle a bet (win/lose)."""
    try:
        data = request.get_json() or {}
        secret = str(data.get("secret", "")).strip()
        ticket_id = data.get("ticket_id")
        outcome = str(data.get("outcome", "")).strip().lower()
        
        if not ticket_id or outcome not in ["win", "lose"]:
            return jsonify({"status": "error", "message": "Invalid parameters (ticket_id and outcome 'win'/'lose' required)"}), 400
        if secret != ADMIN_SECRET:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
        user_id = str(data.get("user_id", "")).strip()
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        # Get user bets
        user_key = f"user_sports_bets:{user_id}"
        
        # Get ticket data
        ticket_data_raw = redis.hget(user_key, ticket_id)
        if not ticket_data_raw:
            return jsonify({"status": "error", "message": "Ticket not found"}), 404
        
        ticket = _decode_json_payload(ticket_data_raw)
        if ticket.get("status") != "pending":
            return jsonify({"status": "error", "message": "This ticket is already settled"}), 409
        
        # Update ticket
        ticket["status"] = "won" if outcome == "win" else "lost"
        ticket["result"] = outcome
        
        if outcome == "win":
            ticket["payout"] = ticket.get("possible_win", 0)
            # Credit user balance
            add_balance_safely(user_id, ticket.get("payout", 0), f"Sports settlement {ticket_id}")
        else:
            ticket["payout"] = 0

        for selection in ticket.get("selections", []):
            selection["status"] = "won" if outcome == "win" else "lost"
        
        # Save updated ticket
        redis.hset(user_key, ticket_id, json.dumps(ticket))
        
        # Update history
        update_history_tx_status(user_id, ticket.get("ticket_id", ticket_id), ticket["status"])
        
        new_balance = get_balance_safely(user_id)
        
        return jsonify({
            "status": "success",
            "ticket": _serialize_ticket(ticket),
            "new_balance": new_balance
        }), 200
        
    except Exception as e:
        print(f"Settle Bet Error: {e}")
        return jsonify({"status": "error", "message": "ቲኬቱን ማስተካከል አልተቻለም!"}), 500


# --- ADMIN HELPER: Get all recent sports tickets (for admin panel) ---
@real_sports_bp.route('/api/sports/admin/tickets', methods=['POST'])
@real_sports_bp.route('/admin/tickets', methods=['POST'])
def admin_fetch_tickets():
    """Admin-only: fetch recent sports tickets with optional user_id filter"""
    try:
        data = request.get_json() or {}
        secret = data.get("secret")
        user_id_filter = data.get("user_id")  # optional
        if not secret or secret != ADMIN_SECRET:
            return jsonify({"status": "error", "message": "Invalid secret"}), 403

        tickets = []
        all_user_keys = []
        
        # Scan for user ticket keys: user_sports_bets:*
        try:
            cursor = 0
            while True:
                scan_result = redis.scan(cursor, match="user_sports_bets:*", count=1000)
                cursor, batch_keys = scan_result
                all_user_keys.extend(batch_keys)
                if cursor == 0:
                    break
        except Exception as e:
            print(f"Redis scan failed: {e}")
            all_user_keys = []

        for key in all_user_keys:
            try:
                user_id_part = key.decode().replace("user_sports_bets:", "")
                if user_id_filter and user_id_part != str(user_id_filter):
                    continue
                
                # Get all ticket IDs for this user
                ticket_ids = redis.hkeys(key)
                for tid_bytes in ticket_ids:
                    tid = tid_bytes.decode()
                    ticket_raw = redis.hget(key, tid)
                    if ticket_raw:
                        ticket = _decode_json_payload(ticket_raw)
                        ticket['user_id'] = user_id_part
                        tickets.append(_serialize_ticket(ticket))
            except Exception as e:
                print(f"Processing ticket key {key} failed: {e}")
                continue
        
        # Sort tickets by timestamp (newest first)
        tickets.sort(key=lambda t: t.get("timestamp", 0), reverse=True)

        # Limit to last 100 tickets to avoid overload
        return jsonify({"status": "success", "tickets": tickets[:100]}), 200
    except Exception as e:
        print(f"Fetching sports tickets failed: {e}")
        return jsonify({"status": "error", "message": "የቲኬቶች ዝርዝር ማምጣት አልተቻለም!"}), 500

# --- ADMIN HELPER: Manage Sports Matches & Odds ---
import time

SPORTS_MATCHES_KEY = "sports:matches:list"

def get_all_sports_matches():
    """Get all stored sports matches, or default demo matches if none exist"""
    try:
        raw = redis.get(SPORTS_MATCHES_KEY)
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"Get matches failed: {e}")
    # Default demo matches (Ethiopian Premier League for local market)
    return [
        {
            "id": "match-1",
            "league": "Ethiopian Premier League",
            "home": "Saint George",
            "away": "Ethiopian Coffee",
            "start_time": int(time.time()) + 3600,
            "odds": {"1": 1.8, "X": 3.4, "2": 4.2, "1X": 1.2, "X2": 2.2},
            "active": True
        },
        {
            "id": "match-2",
            "league": "Ethiopian Premier League",
            "home": "Fasil Kenema",
            "away": "Bahir Dar Kenema",
            "start_time": int(time.time()) + 7200,
            "odds": {"1": 2.1, "X": 3.2, "2": 3.5, "1X": 1.3, "X2": 2.1},
            "active": True
        },
        {
            "id": "match-3",
            "league": "Ethiopian Premier League",
            "home": "Dedebit",
            "away": "Welayta Dicha",
            "start_time": int(time.time()) + 10800,
            "odds": {"1": 2.5, "X": 3.1, "2": 2.9, "1X": 1.4, "X2": 1.9},
            "active": True
        }
    ]

def save_sports_matches(matches):
    """Save sports matches to Redis"""
    try:
        redis.set(SPORTS_MATCHES_KEY, json.dumps(matches))
        return True
    except Exception as e:
        print(f"Save matches failed: {e}")
        return False

@real_sports_bp.route('/admin/matches', methods=['GET'])
def admin_get_matches():
    """Get all sports matches for admin management"""
    try:
        secret = request.args.get("secret")
        ADMIN_SECRET = os.getenv("SPORTS_ADMIN_SECRET", "MySecret123")
        if not secret or secret != ADMIN_SECRET:
            return jsonify({"status": "error", "message": "Invalid secret"}), 403
        return jsonify({"status": "success", "matches": get_all_sports_matches()}), 200
    except Exception as e:
        print(f"Get matches failed: {e}")
        return jsonify({"status": "error", "message": "የማታች ዝርዝር ማምጣት አልተቻለም!"}), 500

@real_sports_bp.route('/admin/matches', methods=['POST'])
def admin_save_matches():
    """Save updated sports matches/odds"""
    try:
        data = request.get_json()
        secret = data.get("secret")
        matches = data.get("matches")
        ADMIN_SECRET = os.getenv("SPORTS_ADMIN_SECRET", "MySecret123")
        if not secret or secret != ADMIN_SECRET or not isinstance(matches, list):
            return jsonify({"status": "error", "message": "Invalid request"}), 400
        if save_sports_matches(matches):
            # Update the global matches used in /api/sports/odds too!
            global MOCK_MATCHES
            MOCK_MATCHES = get_all_sports_matches()
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "error", "message": "Saving failed"}), 500
    except Exception as e:
        print(f"Save matches failed: {e}")
        return jsonify({"status": "error", "message": "ማታችን አስተካከል አልተቻለም!"}), 500
