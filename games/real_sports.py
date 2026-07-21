import os
import json
import time
import uuid
import requests
from datetime import datetime, timedelta, timezone

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

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if user_id:
        return str(user_id)

    return None


def _get_balance(user_id):
    try:
        raw = redis.get(f"user_balance:{user_id}")
        if raw is None:
            return 1000.0
        return float(raw)
    except Exception:
        return 1000.0


def _set_balance(user_id, balance):
    try:
        redis.set(f"user_balance:{user_id}", float(balance))
    except Exception:
        pass


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


def _sample_matches():
    now = datetime.utcnow()
    return [
        {
            "fixture": {
                "id": "sample-1",
                "teams": {"home": {"name": "Barcelona"}, "away": {"name": "Real Madrid"}},
                "league": "La Liga",
                "date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
                "time": "19:00"
            },
            "odds": {"home": 1.90, "draw": 3.40, "away": 4.20}
        },
        {
            "fixture": {
                "id": "sample-2",
                "teams": {"home": {"name": "Manchester City"}, "away": {"name": "Arsenal"}},
                "league": "Premier League",
                "date": (now + timedelta(days=2)).strftime("%Y-%m-%d"),
                "time": "17:30"
            },
            "odds": {"home": 1.70, "draw": 3.60, "away": 4.50}
        },
        {
            "fixture": {
                "id": "sample-3",
                "teams": {"home": {"name": "Bayern"}, "away": {"name": "Dortmund"}},
                "league": "Bundesliga",
                "date": (now + timedelta(days=3)).strftime("%Y-%m-%d"),
                "time": "20:00"
            },
            "odds": {"home": 1.80, "draw": 3.50, "away": 4.10}
        },
        {
            "fixture": {
                "id": "sample-4",
                "teams": {"home": {"name": "Inter"}, "away": {"name": "Milan"}},
                "league": "Serie A",
                "date": (now + timedelta(days=4)).strftime("%Y-%m-%d"),
                "time": "19:45"
            },
            "odds": {"home": 2.10, "draw": 3.20, "away": 3.40}
        },
    ]


def _normalize_matches(raw_data):
    matches = []
    for item in raw_data or []:
        try:
            match_id = item.get("id") or item.get("fixture", {}).get("id")
            home = item.get("home_team") or item.get("homeTeam") or (item.get("teams", {}).get("home", {}).get("name"))
            away = item.get("away_team") or item.get("awayTeam") or (item.get("teams", {}).get("away", {}).get("name"))
            league = item.get("sport_title") or item.get("league") or "Football"
            commence_time = item.get("commence_time") or item.get("date")

            if not match_id or not home or not away or not commence_time:
                continue

            try:
                dt = datetime.fromisoformat(str(commence_time).replace("Z", "+00:00"))
            except Exception:
                continue

            if dt <= datetime.now(timezone.utc):
                continue

            fixture = {
                "id": str(match_id),
                "teams": {"home": {"name": home}, "away": {"name": away}},
                "league": league,
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M"),
            }

            odds = {
                "home": item.get("home_odds") or item.get("odds", {}).get("home"),
                "draw": item.get("draw_odds") or item.get("odds", {}).get("draw"),
                "away": item.get("away_odds") or item.get("odds", {}).get("away"),
            }

            if odds["home"] and odds["draw"] and odds["away"]:
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

    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code != 200:
            raise Exception(response.text)
        data = response.json()
        return _normalize_matches(data)
    except Exception:
        return None


def _is_future_match(match):
    raw_date = match.get("fixture", {}).get("date")
    if not raw_date:
        return True
    try:
        dt = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc)
    except Exception:
        return True


@real_sports_bp.route("/api/internal/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200


@real_sports_bp.route("/api/sports/odds", methods=["GET"])
def get_odds():
    try:
        limit = int(request.args.get("limit", 12))
        cached = _read_cache()

        if cached:
            matches = [m for m in cached if _is_future_match(m)][:limit]
        else:
            matches = _fetch_odds_from_api() or _sample_matches()
            matches = [m for m in matches if _is_future_match(m)]
            _write_cache(matches)

        if len(matches) < limit:
            fallback = [m for m in _sample_matches() if _is_future_match(m)]
            for item in fallback:
                if len(matches) >= limit:
                    break
                if item not in matches:
                    matches.append(item)

        return jsonify({"status": "success", "matches": matches[:limit], "count": len(matches[:limit])}), 200
    except Exception as e:
        print("Get Odds Error:", e)
        return jsonify({"status": "error", "matches": _sample_matches()[:6], "count": 1, "message": "Could not load odds"}), 500


@real_sports_bp.route("/api/get_balance", methods=["POST"])
def get_balance():
    try:
        user_id = _get_current_user_id()
        if not user_id:
            return jsonify({"status": "error", "balance": 0.0, "message": "User not found"}), 400
        balance = _get_balance(user_id)
        return jsonify({"status": "success", "balance": round(balance, 2)}), 200
    except Exception as e:
        print("Balance error:", e)
        return jsonify({"status": "error", "balance": 0.0, "message": "Could not read balance"}), 500


@real_sports_bp.route("/api/sports/place_bet", methods=["POST"])
def place_bet():
    try:
        data = request.get_json(silent=True) or {}
        user_id = _get_current_user_id()

        if not user_id:
            return jsonify({"status": "error", "message": "User not found"}), 400

        bet_amount = float(data.get("bet_amount", 0))
        selections = data.get("selections", [])

        if bet_amount < 10:
            return jsonify({"status": "error", "message": "Minimum bet is 10 ETB"}), 400

        if not selections:
            return jsonify({"status": "error", "message": "No matches selected"}), 400

        balance = _get_balance(user_id)

        try:
            result = deduct_balance_safely(str(user_id), bet_amount)
            if result != "SUCCESS":
                return jsonify({"status": "error", "message": "Insufficient balance"}), 400
        except Exception:
            if balance < bet_amount:
                return jsonify({"status": "error", "message": "Insufficient balance"}), 400
            _set_balance(user_id, balance - bet_amount)

        total_odds = 1.0
        for item in selections:
            total_odds *= float(item.get("odd", 1))

        possible_win = round(bet_amount * total_odds, 2)
        ticket_id = f"RS-{uuid.uuid4().hex[:6].upper()}"

        ticket = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "stake": bet_amount,
            "total_odds": total_odds,
            "possible_win": possible_win,
            "status": "pending",
            "selections": selections,
            "timestamp": time.time(),
        }

        redis.hset(f"user_sports_bets:{user_id}", ticket_id, json.dumps(ticket))
        add_to_history(str(user_id), {"type": "Sports Bet", "amount": bet_amount, "status": "pending"})

        return jsonify({
            "status": "success",
            "message": f"Bet placed successfully! Ticket: {ticket_id}",
            "possible_win": possible_win
        }), 200

    except Exception as e:
        print("Place Bet Error:", e)
        return jsonify({"status": "error", "message": "Server error"}), 500


@real_sports_bp.route("/api/sports/my_bets", methods=["GET"])
def my_bets():
    try:
        user_id = _get_current_user_id()
        if not user_id:
            return jsonify({"status": "error", "message": "User not found"}), 400

        raw = redis.hgetall(f"user_sports_bets:{user_id}")
        tickets = []

        for ticket_id, payload in raw.items():
            try:
                data = json.loads(payload)
                tickets.append({
                    "id": data.get("ticket_id", ticket_id),
                    "stake": round(float(data.get("stake", 0)), 2),
                    "possible_win": round(float(data.get("possible_win", 0)), 2),
                    "status": data.get("status", "pending"),
                    "timestamp": data.get("timestamp", 0),
                })
            except Exception:
                continue

        tickets.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return jsonify({"status": "success", "tickets": tickets}), 200
    except Exception as e:
        print("My Bets Error:", e)
        return jsonify({"status": "error", "message": "Could not load tickets"}), 500