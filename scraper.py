"""
OddsPortal scraper — drop-in replacement for The Odds API.

Returns data in the same format as get_odds_data() so arb_finder.py
works unchanged.
"""

import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Maps our sport keys to OddsPortal listing page URLs.
# Each entry can be a single URL or a list of URLs (multiple tournaments).
SPORT_URLS = {
    # Tennis
    "tennis_atp": [
        "https://www.oddsportal.com/tennis/germany/atp-halle/",
        "https://www.oddsportal.com/tennis/united-kingdom/atp-wimbledon/",
        "https://www.oddsportal.com/tennis/usa/atp-us-open/",
        "https://www.oddsportal.com/tennis/france/atp-french-open/",
        "https://www.oddsportal.com/tennis/australia/atp-australian-open/",
    ],
    "tennis_wta": [
        "https://www.oddsportal.com/tennis/united-kingdom/wta-eastbourne/",
        "https://www.oddsportal.com/tennis/united-kingdom/wta-wimbledon/",
        "https://www.oddsportal.com/tennis/usa/wta-us-open/",
        "https://www.oddsportal.com/tennis/france/wta-french-open/",
        "https://www.oddsportal.com/tennis/australia/wta-australian-open/",
    ],
    # Soccer
    "soccer_epl": ["https://www.oddsportal.com/soccer/england/premier-league/"],
    "soccer_uefa_champs_league": ["https://www.oddsportal.com/soccer/europe/champions-league/"],
    "soccer_spain_la_liga": ["https://www.oddsportal.com/soccer/spain/laliga/"],
    "soccer_germany_bundesliga": ["https://www.oddsportal.com/soccer/germany/bundesliga/"],
    "soccer_italy_serie_a": ["https://www.oddsportal.com/soccer/italy/serie-a/"],
    "soccer_france_ligue_one": ["https://www.oddsportal.com/soccer/france/ligue-1/"],
    "soccer_world_cup": ["https://www.oddsportal.com/soccer/world/world-cup/"],
    "soccer_uefa_europa_league": ["https://www.oddsportal.com/soccer/europe/europa-league/"],
    "soccer_uefa_europa_conference_league": ["https://www.oddsportal.com/soccer/europe/conference-league/"],
    "soccer_netherlands_eredivisie": ["https://www.oddsportal.com/soccer/netherlands/eredivisie/"],
    "soccer_portugal_primeira_liga": ["https://www.oddsportal.com/soccer/portugal/primeira-liga/"],
    "soccer_usa_mls": ["https://www.oddsportal.com/soccer/usa/mls/"],
    "soccer_brazil_campeonato": ["https://www.oddsportal.com/soccer/brazil/serie-a/"],
    "soccer_argentina_primera_division": ["https://www.oddsportal.com/soccer/argentina/primera-division/"],
    "soccer_uefa_european_championship": ["https://www.oddsportal.com/soccer/europe/european-championship/"],
    # Basketball
    "basketball_nba": ["https://www.oddsportal.com/basketball/usa/nba/"],
    "basketball_euroleague": ["https://www.oddsportal.com/basketball/europe/euroleague/"],
    "basketball_ncaab": ["https://www.oddsportal.com/basketball/usa/ncaa/"],
    "basketball_wnba": ["https://www.oddsportal.com/basketball/usa/wnba/"],
    # Baseball
    "baseball_mlb": ["https://www.oddsportal.com/baseball/usa/mlb/"],
    "baseball_npb": ["https://www.oddsportal.com/baseball/japan/npb/"],
    "baseball_kbo": ["https://www.oddsportal.com/baseball/south-korea/kbo-league/"],
    # American Football
    "americanfootball_nfl": ["https://www.oddsportal.com/american-football/usa/nfl/"],
    "americanfootball_ncaaf": ["https://www.oddsportal.com/american-football/usa/ncaa/"],
    "americanfootball_ufl": ["https://www.oddsportal.com/american-football/usa/ufl/"],
    # Combat sports
    "mma_mixed_martial_arts": ["https://www.oddsportal.com/mma/"],
    "boxing_boxing": ["https://www.oddsportal.com/boxing/"],
    # Hockey
    "icehockey_nhl": ["https://www.oddsportal.com/hockey/usa/nhl/"],
    "icehockey_sweden_hockey_league": ["https://www.oddsportal.com/hockey/sweden/shl/"],
    "icehockey_sweden_allsvenskan": ["https://www.oddsportal.com/hockey/sweden/hockeyallsvenskan/"],
    # Rugby
    "rugbyleague_nrl": ["https://www.oddsportal.com/rugby-league/australia/nrl/"],
    "rugbyunion_six_nations": ["https://www.oddsportal.com/rugby-union/europe/six-nations/"],
    # Cricket
    "cricket_ipl": ["https://www.oddsportal.com/cricket/india/ipl/"],
    "cricket_big_bash": ["https://www.oddsportal.com/cricket/australia/big-bash-league/"],
    "cricket_odi": ["https://www.oddsportal.com/cricket/world/odi/"],
    "cricket_t20_blast": ["https://www.oddsportal.com/cricket/england/t20-blast/"],
}

# Exchanges to skip (they have a different back/lay format)
EXCHANGES = {"betfair exchange", "smarkets", "matchbook", "betdaq"}


def fractional_to_decimal(frac_str: str) -> float | None:
    """Convert '17/10' → 2.7, or '2' → 2.0. Returns None if unparseable."""
    frac_str = frac_str.strip()
    if "/" in frac_str:
        try:
            num, den = frac_str.split("/")
            return round(int(num) / int(den) + 1, 4)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        val = float(frac_str)
        # If it looks like a decimal already (> 1.01 and has a decimal point)
        if "." in frac_str and val > 1.01:
            return round(val, 4)
        # Integer fractional like "2" means 2/1 = 3.0
        return round(val + 1, 4)
    except ValueError:
        return None


def parse_bookmaker_row(row_text: str) -> tuple[str, list[float]] | None:
    """
    Parse a bookmaker row like:
      'bet365\n\nCLAIM BONUS\n11/25\n7/4\n94.5%'
    Returns (bookmaker_name, [odds1, odds2, ...]) or None if unparseable.
    """
    parts = [p.strip() for p in row_text.split("\n") if p.strip()]
    if not parts:
        return None

    bookie_name = parts[0]

    # Skip exchanges
    if bookie_name.lower() in EXCHANGES:
        return None

    # Remove non-odds entries: 'CLAIM BONUS', payout '94.5%', 'N/A', buttons
    odds_raw = []
    for p in parts[1:]:
        if "CLAIM" in p or "BONUS" in p or "%" in p or p == "N/A":
            continue
        if re.match(r"^\d+/\d+$", p) or re.match(r"^\d+(\.\d+)?$", p):
            odds_raw.append(p)

    if len(odds_raw) < 2:
        return None

    decimals = [fractional_to_decimal(o) for o in odds_raw]
    if any(d is None or d <= 1.0 for d in decimals):
        return None

    return bookie_name, decimals


async def get_match_links(page, listing_url: str) -> list[str]:
    """
    Navigate to a tournament listing page and return all upcoming match URLs.
    """
    try:
        await page.goto(listing_url, timeout=20000)
        await page.wait_for_timeout(3000)
    except PlaywrightTimeout:
        print(f"  [timeout] {listing_url}")
        return []

    # Find match links — OddsPortal uses /h2h/ for most sports; soccer uses
    # a path-based slug like /soccer/england/premier-league/team-a-team-b-hash/
    all_links = await page.query_selector_all("a[href]")
    base_path = listing_url.rstrip("/").replace("https://www.oddsportal.com", "")

    match_links = set()
    for link in all_links:
        href = await link.get_attribute("href")
        if not href:
            continue
        # Exclude listing/result/standing pages; keep only deep match URLs
        if any(x in href for x in ("/results", "/standings", "/outrights", "/draws")):
            continue
        # Must be deeper than the listing URL
        if href.startswith(base_path) and href.rstrip("/") != base_path:
            segments = href.rstrip("/").split("/")
            if len(segments) > base_path.count("/") + 1:
                match_links.add(href)
        # Tennis h2h pattern
        elif "/h2h/" in href:
            match_links.add(href)

    return list(match_links)


async def scrape_match(page, match_url: str) -> dict | None:
    """
    Scrape a single match page and return Odds API-compatible match data.
    Returns None if the page has no usable odds.
    """
    full_url = (
        match_url
        if match_url.startswith("http")
        else f"https://www.oddsportal.com{match_url}"
    )

    try:
        await page.goto(full_url, timeout=20000)
        await page.wait_for_timeout(3000)
    except PlaywrightTimeout:
        print(f"  [timeout] {full_url}")
        return None

    # Team names
    host_el = await page.query_selector('[data-testid="game-host"]')
    guest_el = await page.query_selector('[data-testid="game-guest"]')
    if not host_el or not guest_el:
        return None

    home_team = (await host_el.inner_text()).strip()
    away_team = (await guest_el.inner_text()).strip()

    # Match time
    time_el = await page.query_selector('[data-testid="game-time-item"]')
    commence_time = (await time_el.inner_text()).strip() if time_el else ""
    commence_time = " ".join(commence_time.split())  # collapse whitespace

    # Bookmaker rows — each row has testid="over-under-expanded-row"
    rows = await page.query_selector_all('[data-testid="over-under-expanded-row"]')
    if not rows:
        return None

    bookmakers = []
    for row in rows:
        row_text = await row.inner_text()
        parsed = parse_bookmaker_row(row_text)
        if parsed is None:
            continue
        bookie_name, odds = parsed

        # Build outcomes list: first odds = home team, second = away team,
        # third (if present) = Draw (for 3-way markets)
        outcome_names = [home_team, away_team]
        if len(odds) > 2:
            outcome_names = [home_team, "Draw", away_team]
            # reorder: oddsportal 3-way order is 1 (home), X (draw), 2 (away)

        outcomes = [
            {"name": name, "price": price}
            for name, price in zip(outcome_names, odds)
        ]

        bookmakers.append({
            "title": bookie_name,
            "link": full_url,
            "markets": [{"outcomes": outcomes}],
        })

    if not bookmakers:
        return None

    return {
        "home_team": home_team,
        "away_team": away_team,
        "commence_time": commence_time,
        "bookmakers": bookmakers,
    }


async def scrape_sport(sport_key: str) -> list[dict]:
    """
    Scrape all upcoming matches for a sport key (e.g. 'tennis_atp').
    Returns a list of match dicts in Odds API format.
    """
    listing_urls = SPORT_URLS.get(sport_key)
    if not listing_urls:
        print(f"No URL mapping for sport: {sport_key}")
        return []

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await ctx.new_page()

        for listing_url in listing_urls:
            print(f"  Listing: {listing_url}")
            match_links = await get_match_links(page, listing_url)
            print(f"  Found {len(match_links)} match links")

            seen = set()
            for link in match_links:
                if link in seen:
                    continue
                seen.add(link)
                match_data = await scrape_match(page, link)
                if match_data:
                    results.append(match_data)
                    print(f"    + {match_data['home_team']} vs {match_data['away_team']} ({len(match_data['bookmakers'])} bookmakers)")

        await browser.close()

    return results


def get_odds_data_scraped(sport_key: str) -> list[dict]:
    """Synchronous wrapper — use this as a replacement for get_odds_data()."""
    return asyncio.run(scrape_sport(sport_key))


if __name__ == "__main__":
    import sys
    sport = sys.argv[1] if len(sys.argv) > 1 else "tennis_atp"
    print(f"Scraping {sport}...\n")
    data = get_odds_data_scraped(sport)
    print(f"\nTotal matches: {len(data)}")
    for m in data:
        print(f"  {m['home_team']} vs {m['away_team']} — {len(m['bookmakers'])} bookmakers")
        if m["bookmakers"]:
            bk = m["bookmakers"][0]
            print(f"    e.g. {bk['title']}: {[o['name'] + '=' + str(o['price']) for o in bk['markets'][0]['outcomes']]}")
