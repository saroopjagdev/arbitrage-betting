import requests
from dotenv import load_dotenv
import os
from arb_calculation import find_arb, get_bet_info, find_arb_three_way, get_arb_details_three_way
load_dotenv()

API_KEY = os.getenv("api_key")

SPORT = "soccer_epl"
URL = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"


params = {
    "apiKey": API_KEY,
    "regions": "uk,eu",   # Bookmakers in these regions
    "markets": "h2h",     # 'head-to-head' = win/lose odds
    "oddsFormat": "decimal"
}

response = requests.get(URL, params=params)
data = response.json()
print(data)

for match in data:
    home = match['home_team']
    away = match['away_team']

    best_home = {'bookie': None, 'odds': 0}
    best_draw = {'bookie': None, 'odds': 0}
    best_away = {'bookie': None, 'odds': 0}

    for bm in match['bookmakers']:
        if not bm['markets']:
            continue

        outcomes = bm['markets'][0]['outcomes']
        odds_map = {o['name']: o['price'] for o in outcomes}

        if home in odds_map and odds_map[home] > best_home['odds']:
            best_home = {'bookie': bm['title'], 'odds': odds_map[home]}
        if away in odds_map and odds_map[away] > best_away['odds']:
            best_away = {'bookie': bm['title'], 'odds': odds_map[away]}
        if "Draw" in odds_map and odds_map["Draw"] > best_draw['odds']:
            best_draw = {'bookie': bm['title'], 'odds': odds_map["Draw"]}

    # Check for arbitrage across best odds
    if all([best_home['odds'], best_draw['odds'], best_away['odds']]):
        if find_arb_three_way(best_home['odds'], best_draw['odds'], best_away['odds']):
            print(get_arb_details_three_way(
                home, away,
                best_home['odds'], best_draw['odds'], best_away['odds'],
                best_home['bookie'], best_draw['bookie'], best_away['bookie']
            ))
            print("-" * 60)

