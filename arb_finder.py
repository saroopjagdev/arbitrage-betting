import requests
import os
from arb_calculation import *
from discord_alerts import send_alert


API_KEY = os.getenv("API_KEY")




SPORT_TYPES = {
    # ⚽ Soccer (3-way: win/draw/lose)
    "soccer_epl": "3way",
    "soccer_uefa_champs_league": "3way",
    "soccer_spain_la_liga": "3way",
    "soccer_germany_bundesliga": "3way",
    "soccer_italy_serie_a": "3way",
    "soccer_france_ligue_one": "3way",
    "soccer_portugal_primeira_liga": "3way",
    "soccer_brazil_campeonato": "3way",
    "soccer_argentina_primera_division": "3way",
    "soccer_netherlands_eredivisie": "3way",
    "soccer_usa_mls": "3way",
    "soccer_world_cup": "3way",
    "soccer_uefa_europa_league": "3way",
    "soccer_uefa_europa_conference_league": "3way",
    "soccer_uefa_european_championship": "3way",

    # 🎾 Tennis (2-way: win/lose)
    "tennis_atp_wimbledon": "2way",
    "tennis_atp_us_open": "2way",
    "tennis_atp_french_open": "2way",
    "tennis_atp_australian_open": "2way",
    "tennis_atp_miami_open": "2way",
    "tennis_wta_wimbledon": "2way",
    "tennis_wta_us_open": "2way",
    "tennis_wta_french_open": "2way",
    "tennis_wta_australian_open": "2way",

    # 🏀 Basketball (2-way)
    "basketball_nba": "2way",
    "basketball_euroleague": "2way",
    "basketball_ncaab": "2way",
    "basketball_wnba": "2way",

    # ⚾ Baseball (2-way)
    "baseball_mlb": "2way",
    "baseball_npb": "2way",
    "baseball_kbo": "2way",

    # 🏈 American Football (2-way)
    "americanfootball_nfl": "2way",
    "americanfootball_ncaaf": "2way",
    "americanfootball_ufl": "2way",

    # 🥊 Combat Sports (2-way)
    "mma_mixed_martial_arts": "2way",
    "boxing_boxing": "2way",

    # 🏒 Hockey (3-way, due to OT possibility)
    "icehockey_nhl": "3way",
    "icehockey_sweden_hockey_league": "3way",
    "icehockey_sweden_allsvenskan": "3way",

    # 🏉 Rugby (2-way)
    "rugbyleague_nrl": "2way",
    "rugbyunion_six_nations": "2way",

    # 🏏 Cricket (2-way)
    "cricket_odi": "2way",
    "cricket_t20_blast": "2way",
    "cricket_ipl": "2way",
    "cricket_big_bash": "2way",
}

def get_odds_data(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "uk",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    response = requests.get(url, params=params)
    data = response.json()
    print(data)
    return data

def find_three_way_arbs(data):
    for match in data:
        home = match["home_team"]
        away = match["away_team"]

        best_home = {"bookie": None, "odds": 0}
        best_draw = {"bookie": None, "odds": 0}
        best_away = {"bookie": None, "odds": 0}

        for bm in match["bookmakers"]:
            if not bm["markets"]:
                continue

            outcomes = bm["markets"][0]["outcomes"]
            odds_map = {o["name"]: o["price"] for o in outcomes}

            if home in odds_map and odds_map[home] > best_home["odds"]:
                best_home = {"bookie": bm["title"], "odds": odds_map[home]}
            if away in odds_map and odds_map[away] > best_away["odds"]:
                best_away = {"bookie": bm["title"], "odds": odds_map[away]}
            if "Draw" in odds_map and odds_map["Draw"] > best_draw["odds"]:
                best_draw = {"bookie": bm["title"], "odds": odds_map["Draw"]}

        if all([best_home["odds"], best_draw["odds"], best_away["odds"]]):
            if find_arb_three_way(
                best_home["odds"], best_draw["odds"], best_away["odds"]
            ):
                print(
                    get_arb_details_three_way(
                        home,
                        away,
                        best_home["odds"],
                        best_draw["odds"],
                        best_away["odds"],
                        best_home["bookie"],
                        best_draw["bookie"],
                        best_away["bookie"],
                    )
                )
                print("-" * 60)
            
        
def find_two_way_arbs(data):
    for match in data:
        home = match["home_team"]
        away = match["away_team"]

        best_home = {"bookie": None, "odds": 0}
        best_away = {"bookie": None, "odds": 0}

        for bm in match["bookmakers"]:
            if not bm["markets"]:
                continue

            outcomes = bm["markets"][0]["outcomes"]
            odds_map = {o["name"]: o["price"] for o in outcomes}

            if home in odds_map and odds_map[home] > best_home["odds"]:
                best_home = {"bookie": bm["title"], "odds": odds_map[home]}
            if away in odds_map and odds_map[away] > best_away["odds"]:
                best_away = {"bookie": bm["title"], "odds": odds_map[away]}

        if best_home["odds"] and best_away["odds"]:
            if find_arb(best_home["odds"], best_away["odds"]):
                message = get_bet_info(
                    home,
                    away,
                    best_home["odds"],
                    best_away["odds"],
                    best_home["bookie"],
                    best_away["bookie"]
                )


                send_alert(message)



            
def run_arbitrage_tracker(sport):
    if sport not in SPORT_TYPES:
        print(f"Unsupported sport: {sport}")
        return

    data = get_odds_data(sport)
    if not data:
        print(f"No data available for {sport}")
        return

    print(f"\nChecking arbitrage for {sport}...\n")
    sport_type = SPORT_TYPES[sport]
    if sport_type == "3way":
        find_three_way_arbs(data)
    else:
        find_two_way_arbs(data)


if __name__ == "__main__":
    run_arbitrage_tracker("basketball_nba")

