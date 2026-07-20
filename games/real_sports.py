import os
import json
import time
import uuid
from datetime import datetime, timedelta

import requests
from flask import Blueprint, request, jsonify

from config import (
    redis,
    deduct_balance_safely,
    add_to_history,
    telegram_auth_required,
    get_user_id_from_request,
)

real_sports_bp = Blueprint("real_sports", __name__)

API_KEY = os.environ.get("THE_ODDS_API_KEY")
CACHE_KEY = "cached_real_sports_odds"


def _get_current_user_id():
    user_id = get_user_id_from_request()
    if user_id:
        return str(user_id)

    user_id = request.args.get("user_id") or request.headers.get("X-User-Id")
    if user_id:
        return str(user_id)

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if user_id:
        return str(user_id)

    return None


def _sample_matches():
    now = datetime.utcnow()
    return [
        {
            "fixture": {
                "id": "sample-1",
                "teams": {
                    "home": {"name": "Barcelona"},
                    "away": {"name": "Real Madrid"}
                },
                "league": "La Liga",
                "date": now.strftime("%Y-%m-%d"),
                "time": (now + timedelta(hours=2)).strftime("%H:%M")
            },
            "odds": {
                "home": 1.90,
                "draw": 3.40,
                "away": 4.20,
                "dc_1x": 1.45,
                "dc_12": 1.80,
                "dc_x2": 2.10
            }
        }
    ]


def _read_cache():
    try:
        cached = redis.get(CACHE_KEY)
        if not cached:
            return None
        if isinstance(cached, (bytes, bytearray)):
            cached = cached.decode("utf-8")
        return json.loads(cached)
    except Exception:
        return None


def _write_cache(matches):
    try:
        redis.set(CACHE_KEY, json.dumps(matches))
    except Exception:
        pass


def _normalize_matches(raw_data):
    matches = []
    now_utc = datetime.utcnow()

    for item in raw_data or []:
        try:
            match_id = item.get("id")
            home_team = item.get("home_team") or "Home"
            away_team = item.get("away_team") or "Away"
            commence_time = item.get("commence_time")
            league = item.get("sport_title") or "Unknown League"

            if not commence_time:
                continue

            try:
                dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
            except Exception:
                continue

            if dt <= now_utc:
                continue

            local_dt = dt + timedelta(hours=3)
            fixture = {
                "id": match_id,
                "teams": {
                    "home": {"name": home_team},
                    "away": {"name": away_team}
                },
                "league": league,
                "date": local_dt.strftime("%Y-%m-%d"),
                "time": local_dt.strftime("%H:%M")
            }

            odds = {}
            for bookmaker in item.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        name = outcome.get("name")
                        price = outcome.get("price")
                        if name == home_team:
                            odds["home"] = price
                        elif name == away_team:
                            odds["away"] = price
                        elif name == "Draw":
                            odds["draw"] = price

            if odds.get("home") and odds.get("away") and odds.get("draw"):
                odds["dc_1x"] = round((odds["home"] * odds["draw"]) / (odds["home"] + odds["draw"]), 2)
                odds["dc_12"] = round((odds["home"] * odds["away"]) / (odds["home"] + odds["away"]), 2)
                odds["dc_x2"] = round((odds["draw"] * odds["away"]) / (odds["draw"] + odds["away"]), 2)

                matches.append({"fixture": fixture, "odds": odds})
        except Exception:
            continue

    return matches


def _fetch_odds_from_api():
    if not API_KEY:
        return None

    url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }

    response = requests.get(url, params=params, timeout=20)
    if response.status_code != 200:
        raise Exception(response.text)

    data = response.json()
    return _normalize_matches(data)


@real_sports_bp.route("/api/internal/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200


@real_sports_bp.route("/api/sports/odds", methods=["GET"])
def get_odds():
    try:
        cached = _read_cache()
        if cached:
            matches = cached
        else:
            matches = _fetch_odds_from_api()
            if matches is None:
                matches = _sample_matches()
            _write_cache(matches)

        return jsonify({
            "status": "success",
            "matches": matches,
            "count": len(matches)
        }), 200
    except Exception as e:
        print("Get Odds Error:", e)
        return jsonify({
            "status": "error",
            "matches": _sample_matches(),
            "count": 1,
            "message": "Could not load odds from API"
        }), 500


@real_sports_bp.route("/api/sports/place_bet", methods=["POST"])
@telegram_auth_required
def place_bet():
    try:
        data = request.get_json(silent=True) or {}
        user_id = _get_current_user_id()

        bet_amount = data.get("bet_amount")
        selections = data.get("selections")

        if not user_id:
            return jsonify({"status": "error", "message": "User not found"}), 400

        if not bet_amount or not selections:
            return jsonify({"status": "error", "message": "Missing data"}), 400

        bet_amount = float(bet_amount)
        if bet_amount < 10:
            return jsonify({"status": "error", "message": "Minimum bet is 10 ETB"}), 400

        result = deduct_balance_safely(str(user_id), bet_amount)
        if result != "SUCCESS":
            return jsonify({"status": "error", "message": "Insufficient balance"}), 400

        total_odds = 1.0
        for sel in selections:
            total_odds *= float(sel.get("odd", 1))

        possible_win = bet_amount * total_odds
        ticket_id = f"RS-{uuid.uuid4().hex[:6].upper()}"

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

        add_to_history(str(user_id), {
            "action": f"Sports Bet ({ticket_id})",
            "amount": bet_amount,
            "status": "pending"
        })

        return jsonify({
            "status": "success",
            "message": f"Bet placed successfully!\nTicket: {ticket_id}\nPossible win: {possible_win:.2f} ETB"
        }), 200

    except Exception as e:
        print("Place Bet Error:", e)
        return jsonify({"status": "error", "message": "Server error"}), 500


@real_sports_bp.route("/api/sports/my_bets", methods=["GET"])
@telegram_auth_required
def get_my_bets():
    try:
        user_id = _get_current_user_id()
        if not user_id:
            return jsonify({"status": "error", "message": "User not found"}), 400

        raw_bets = redis.hgetall(f"user_sports_bets:{user_id}")
        tickets = []

        for ticket_id, ticket_data in raw_bets.items():
            data = json.loads(ticket_data)
            tickets.append({
                "id": data.get("ticket_id", ticket_id),
                "stake": round(float(data.get("amount", 0)), 2),
                "possible_win": round(float(data.get("possible_win", 0)), 2),
                "status": data.get("status", "Pending"),
                "timestamp": data.get("timestamp", 0),
                "selections": data.get("selections", [])
            })

        tickets.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return jsonify({"status": "success", "tickets": tickets}), 200

    except Exception as e:
        print("Get My Bets Error:", e)
        return jsonify({"status": "error", "message": "Could not load tickets"}), 500