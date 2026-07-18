import os
import requests
import json
from config import redis # ከ config ፋይልህ ነው የምንጠራው

def get_football_matches():
    url = "https://v3.football.api-sports.io/fixtures"
    # ዛሬ የሚደረጉ ጨዋታዎችን ማምጣት
    headers = {"x-apisports-key": os.environ.get("API_FOOTBALL_KEY"), "x-rapidapi-host": "v3.football.api-sports.io"}
    response = requests.get(url, headers=headers, params={"date": "2026-07-18"})
    return response.json().get("response", [])
