import requests
import os
import sys
from datetime import datetime, timezone
from arb_calculation import *
from discord_alerts import send_alert
from scraper import get_odds_data_scraped, SPORT_URLS as SCRAPER_SPORT_URLS
from marketing import post_arb_to_bluesky, post_daily_digest


API_KEY = os.getenv("API_KEY")

# Set USE_SCRAPER=1 in environment to use OddsPortal scraper instead of the API.
USE_SCRAPER = os.getenv("USE_SCRAPER", "1") == "1"

# Collects arbs found during this run for the daily digest
_arb_log: list[dict] = []

# Minimum profit threshold (1% = 0.01)
MIN_PROFIT = 0.01

# Minimum meaningful stake proportion (0.5% of bankroll)
MIN_STAKE_PROP = 0.005


# Sports to track. Add any key from SPORT_TYPES or SCRAPER_SPORT_URLS.
ACTIVE_SPORTS = [
    # Autumn calendar (Oct-Dec). Each sport costs Odds API credits whenever the
    # scraper falls back, so keep this list to what is actually in season.
    "americanfootball_nfl",
    "americanfootball_ncaaf",
    "baseball_mlb",          # postseason through Oct
    "basketball_nba",        # season starts mid-Oct
    "icehockey_nhl",         # season starts early Oct
    "soccer_epl",
    "soccer_uefa_champs_league",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
    "mma_mixed_martial_arts",
    "boxing_boxing",
]

# Full dictionary for future flexibility
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

    # 🎾 Tennis (2-way)
    "tennis_atp": "2way",
    "tennis_wta": "2way",

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

    # 🏒 Hockey (3-way)
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
    if USE_SCRAPER and sport in SCRAPER_SPORT_URLS:
        print(f"  [scraper] fetching {sport}")
        data = get_odds_data_scraped(sport)
        if data or not API_KEY:
            return data
        print(f"  [scraper] 0 matches for {sport} — falling back to The Odds API")

    # The Odds API (requires API_KEY): used when the scraper is off or came back empty
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "uk",
        "markets": "h2h",
        "oddsFormat": "decimal",
        "includeLinks": "true",
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"  [odds-api] {sport}: {len(data)} events "
              f"(credits remaining: {response.headers.get('x-requests-remaining', '?')})")
        return data
    except Exception as e:
        print(f"Error fetching data for {sport}: {e}")
        return []


def find_three_way_arbs(data, sport_key="soccer"):
    for match in data:
        home = match["home_team"]
        away = match["away_team"]
        commence_time = match.get("commence_time", "")

        best_home = {"bookie": None, "odds": 0, "link": ""}
        best_draw = {"bookie": None, "odds": 0, "link": ""}
        best_away = {"bookie": None, "odds": 0, "link": ""}

        for bm in match["bookmakers"]:
            if not bm["markets"]:
                continue

            outcomes = bm["markets"][0]["outcomes"]
            odds_map = {o["name"]: o["price"] for o in outcomes}
            link = bm.get("link", "")

            if home in odds_map and odds_map[home] > best_home["odds"]:
                best_home = {"bookie": bm["title"], "odds": odds_map[home], "link": link}
            if away in odds_map and odds_map[away] > best_away["odds"]:
                best_away = {"bookie": bm["title"], "odds": odds_map[away], "link": link}
            if "Draw" in odds_map and odds_map["Draw"] > best_draw["odds"]:
                best_draw = {"bookie": bm["title"], "odds": odds_map["Draw"], "link": link}

        if all([best_home["odds"], best_draw["odds"], best_away["odds"]]):
            total_inverse = (
                (1 / best_home["odds"]) +
                (1 / best_draw["odds"]) +
                (1 / best_away["odds"])
            )
            profit = (1 / total_inverse) - 1

            # Calculate stake proportions
            stake_home = (1 / best_home["odds"]) / total_inverse
            stake_draw = (1 / best_draw["odds"]) / total_inverse
            stake_away = (1 / best_away["odds"]) / total_inverse

            if find_arb_three_way(
                best_home["odds"], best_draw["odds"], best_away["odds"]
            ):
                if (
                    profit > MIN_PROFIT and
                    stake_home >= MIN_STAKE_PROP and
                    stake_draw >= MIN_STAKE_PROP and
                    stake_away >= MIN_STAKE_PROP
                ):
                    message, embed = get_arb_details_three_way(
                        home,
                        away,
                        best_home["odds"],
                        best_draw["odds"],
                        best_away["odds"],
                        best_home["bookie"],
                        best_draw["bookie"],
                        best_away["bookie"],
                        best_home["link"],
                        best_draw["link"],
                        best_away["link"],
                        commence_time=commence_time,
                        sport_key=sport_key
                    )
                    send_alert(message, embed=embed, profit=profit)
                    post_arb_to_bluesky(home, away, profit, sport_key)
                    _arb_log.append({"home": home, "away": away, "profit": profit, "sport": sport_key})
                    print(message)
                    print("-" * 60)


def find_two_way_arbs(data, sport_key="tennis"):
    for match in data:
        home = match["home_team"]
        away = match["away_team"]
        commence_time = match.get("commence_time", "")

        best_home = {"bookie": None, "odds": 0, "link": ""}
        best_away = {"bookie": None, "odds": 0, "link": ""}

        for bm in match["bookmakers"]:
            if not bm["markets"]:
                continue

            outcomes = bm["markets"][0]["outcomes"]
            odds_map = {o["name"]: o["price"] for o in outcomes}
            link = bm.get("link", "")

            if home in odds_map and odds_map[home] > best_home["odds"]:
                best_home = {"bookie": bm["title"], "odds": odds_map[home], "link": link}
            if away in odds_map and odds_map[away] > best_away["odds"]:
                best_away = {"bookie": bm["title"], "odds": odds_map[away], "link": link}

        if best_home["odds"] and best_away["odds"]:
            if find_arb(best_home["odds"], best_away["odds"]):
                total_inverse = (
                    (1 / best_home["odds"]) +
                    (1 / best_away["odds"])
                )
                profit = (1 / total_inverse) - 1

                stake_home = (1 / best_home["odds"]) / total_inverse
                stake_away = (1 / best_away["odds"]) / total_inverse

                if (
                    profit > MIN_PROFIT and
                    stake_home >= MIN_STAKE_PROP and
                    stake_away >= MIN_STAKE_PROP
                ):
                    message, embed = get_bet_info(
                        home,
                        away,
                        best_home["odds"],
                        best_away["odds"],
                        best_home["bookie"],
                        best_away["bookie"],
                        best_home["link"],
                        best_away["link"],
                        commence_time=commence_time,
                        sport_key=sport_key
                    )
                    send_alert(message, embed=embed, profit=profit)
                    post_arb_to_bluesky(home, away, profit, sport_key)
                    _arb_log.append({"home": home, "away": away, "profit": profit, "sport": sport_key})
                    print(message)
                    print("-" * 60)


def run_arbitrage_tracker(sports_list):
    """Returns the total number of matches fetched across all sports."""
    total_matches = 0
    for sport in sports_list:
        print(f"\nChecking arbitrage for {sport}...\n")
        data = get_odds_data(sport)
        if not data:
            continue
        total_matches += len(data)

        sport_type = SPORT_TYPES.get(sport, "2way")

        if sport_type == "3way":
            find_three_way_arbs(data, sport)
        else:
            find_two_way_arbs(data, sport)

    return total_matches


if __name__ == "__main__":
    total = run_arbitrage_tracker(ACTIVE_SPORTS)
    print(f"\nTotal matches scraped this run: {total}")

    # Post daily digest once per day (only on the midnight run)
    if datetime.now(timezone.utc).hour == 0:
        post_daily_digest(_arb_log)

    # A run that scrapes nothing is a broken scraper, not "no arbs" — make it red in Actions.
    if total == 0:
        print("ERROR: scraped 0 matches across all sports — scraper is likely broken or blocked.")
        sys.exit(1)