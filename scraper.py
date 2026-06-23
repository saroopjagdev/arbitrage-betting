"""
OddsPortal scraper — drop-in replacement for The Odds API.

Returns data in the same format as get_odds_data() so arb_finder.py
works unchanged.
"""

import asyncio
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

PARALLEL_PAGES = 8   # concurrent match pages per sport
MIN_BOOKMAKERS = 5   # skip match pages with fewer bookmakers than this
MAX_MATCHES = 25     # max match pages to scrape per listing page

# For tennis we discover active tournaments dynamically from the sport root.
# For everything else, a single listing URL is enough.
SPORT_URLS = {
    "tennis_atp":  "https://www.oddsportal.com/tennis/",
    "tennis_wta":  "https://www.oddsportal.com/tennis/",
    "soccer_epl":  "https://www.oddsportal.com/soccer/england/premier-league/",
    "soccer_uefa_champs_league": "https://www.oddsportal.com/soccer/europe/champions-league/",
    "soccer_spain_la_liga":      "https://www.oddsportal.com/soccer/spain/laliga/",
    "soccer_germany_bundesliga": "https://www.oddsportal.com/soccer/germany/bundesliga/",
    "soccer_italy_serie_a":      "https://www.oddsportal.com/soccer/italy/serie-a/",
    "soccer_france_ligue_one":   "https://www.oddsportal.com/soccer/france/ligue-1/",
    "soccer_world_cup":          "https://www.oddsportal.com/soccer/world/world-cup/",
    "soccer_uefa_europa_league": "https://www.oddsportal.com/soccer/europe/europa-league/",
    "soccer_uefa_europa_conference_league": "https://www.oddsportal.com/soccer/europe/conference-league/",
    "soccer_netherlands_eredivisie":    "https://www.oddsportal.com/soccer/netherlands/eredivisie/",
    "soccer_portugal_primeira_liga":    "https://www.oddsportal.com/soccer/portugal/primeira-liga/",
    "soccer_usa_mls":                   "https://www.oddsportal.com/soccer/usa/mls/",
    "soccer_brazil_campeonato":         "https://www.oddsportal.com/soccer/brazil/serie-a/",
    "soccer_argentina_primera_division":"https://www.oddsportal.com/soccer/argentina/primera-division/",
    "soccer_uefa_european_championship":"https://www.oddsportal.com/soccer/europe/european-championship/",
    "basketball_nba":       "https://www.oddsportal.com/basketball/usa/nba/",
    "basketball_euroleague":"https://www.oddsportal.com/basketball/europe/euroleague/",
    "basketball_ncaab":     "https://www.oddsportal.com/basketball/usa/ncaa/",
    "basketball_wnba":      "https://www.oddsportal.com/basketball/usa/wnba/",
    "baseball_mlb":         "https://www.oddsportal.com/baseball/usa/mlb/",
    "baseball_npb":         "https://www.oddsportal.com/baseball/japan/npb/",
    "baseball_kbo":         "https://www.oddsportal.com/baseball/south-korea/kbo-league/",
    "americanfootball_nfl": "https://www.oddsportal.com/american-football/usa/nfl/",
    "americanfootball_ncaaf":"https://www.oddsportal.com/american-football/usa/ncaa/",
    "americanfootball_ufl": "https://www.oddsportal.com/american-football/usa/ufl/",
    "mma_mixed_martial_arts":"https://www.oddsportal.com/mma/",
    "boxing_boxing":         "https://www.oddsportal.com/boxing/",
    "icehockey_nhl":                 "https://www.oddsportal.com/hockey/usa/nhl/",
    "icehockey_sweden_hockey_league":"https://www.oddsportal.com/hockey/sweden/shl/",
    "icehockey_sweden_allsvenskan":  "https://www.oddsportal.com/hockey/sweden/hockeyallsvenskan/",
    "rugbyleague_nrl":    "https://www.oddsportal.com/rugby-league/australia/nrl/",
    "rugbyunion_six_nations":"https://www.oddsportal.com/rugby-union/europe/six-nations/",
    "cricket_ipl":       "https://www.oddsportal.com/cricket/india/ipl/",
    "cricket_big_bash":  "https://www.oddsportal.com/cricket/australia/big-bash-league/",
    "cricket_odi":       "https://www.oddsportal.com/cricket/world/odi/",
    "cricket_t20_blast": "https://www.oddsportal.com/cricket/england/t20-blast/",
}

# Tennis sport root → filter links by ATP or WTA
TENNIS_FILTERS = {
    "tennis_atp": "atp",
    "tennis_wta": "wta",
}

EXCHANGES = {"betfair exchange", "smarkets", "matchbook", "betdaq"}


def fractional_to_decimal(frac_str: str) -> float | None:
    frac_str = frac_str.strip()
    if "/" in frac_str:
        try:
            num, den = frac_str.split("/")
            return round(int(num) / int(den) + 1, 4)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        val = float(frac_str)
        if "." in frac_str and val > 1.01:
            return round(val, 4)
        return round(val + 1, 4)
    except ValueError:
        return None


def parse_bookmaker_row(row_text: str) -> tuple[str, list[float]] | None:
    parts = [p.strip() for p in row_text.split("\n") if p.strip()]
    if not parts:
        return None
    bookie_name = parts[0]
    if bookie_name.lower() in EXCHANGES:
        return None
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


async def _wait_for_page(page, timeout=8000):
    """Wait for OddsPortal content to load — faster than a fixed sleep."""
    try:
        await page.wait_for_selector(
            '[data-testid="over-under-expanded-row"], [data-testid="matches"]',
            timeout=timeout,
        )
    except PlaywrightTimeout:
        pass


async def _get_hrefs(page) -> list[str]:
    links = await page.query_selector_all("a[href]")
    return [await l.get_attribute("href") or "" for l in links]


async def get_match_links(page, listing_url: str, tennis_filter: str = "") -> list[str]:
    """Return all upcoming match URLs from a listing page.

    For tennis, listing_url is the sport root (/tennis/).
    We first discover active tournament sub-pages (filtered by atp/wta),
    then collect h2h match links from each.
    """
    try:
        await page.goto(listing_url, timeout=20000)
        await _wait_for_page(page)
    except PlaywrightTimeout:
        print(f"  [timeout] {listing_url}")
        return []

    hrefs = await _get_hrefs(page)
    skip = ("/results", "/standings", "/outrights", "/draws")

    # Tennis: root page contains tournament sub-page links — find those first
    if tennis_filter:
        tournament_pages = [
            h for h in hrefs
            if tennis_filter in h.lower()
            and h.count("/") >= 3
            and not any(s in h for s in skip)
            and not "/h2h/" in h
        ]
        # Remove duplicates, keep only tournament-level paths (3-4 segments)
        tournament_pages = list(dict.fromkeys(
            h for h in tournament_pages
            if 3 <= h.count("/") <= 4 and "itf" not in h.lower()
        ))
        print(f"  Active {tennis_filter.upper()} tournaments: {len(tournament_pages)}")

        match_links = set()
        for t_url in tournament_pages:
            full = f"https://www.oddsportal.com{t_url}" if t_url.startswith("/") else t_url
            try:
                await page.goto(full, timeout=20000)
                await _wait_for_page(page)
            except Exception:
                continue
            for href in await _get_hrefs(page):
                if "/h2h/" in href and not any(s in href for s in skip):
                    match_links.add(href)
        return list(match_links)

    # All other sports: collect h2h links or deep match links directly
    base_path = listing_url.rstrip("/").replace("https://www.oddsportal.com", "")
    match_links = set()
    for href in hrefs:
        if any(s in href for s in skip):
            continue
        is_h2h = "/h2h/" in href
        is_deep = (
            href.startswith(base_path)
            and href.rstrip("/") != base_path
            and len(href.rstrip("/").split("/")) > base_path.count("/") + 1
        )
        if is_h2h or is_deep:
            match_links.add(href)
    return list(match_links)


async def scrape_match(page, match_url: str) -> dict | None:
    """Scrape a single match page. Returns Odds API-compatible dict or None."""
    full_url = (
        match_url if match_url.startswith("http")
        else f"https://www.oddsportal.com{match_url}"
    )
    try:
        await page.goto(full_url, timeout=20000)
        await _wait_for_page(page)
    except Exception:
        return None

    host_el = await page.query_selector('[data-testid="game-host"]')
    guest_el = await page.query_selector('[data-testid="game-guest"]')
    if not host_el or not guest_el:
        return None

    home_team = (await host_el.inner_text()).strip()
    away_team = (await guest_el.inner_text()).strip()

    time_el = await page.query_selector('[data-testid="game-time-item"]')
    commence_time = " ".join((await time_el.inner_text()).split()) if time_el else ""

    rows = await page.query_selector_all('[data-testid="over-under-expanded-row"]')
    if not rows:
        return None

    bookmakers = []
    for row in rows:
        parsed = parse_bookmaker_row(await row.inner_text())
        if not parsed:
            continue
        bookie_name, odds = parsed
        outcome_names = [home_team, "Draw", away_team] if len(odds) > 2 else [home_team, away_team]
        bookmakers.append({
            "title": bookie_name,
            "link": full_url,
            "markets": [{"outcomes": [
                {"name": n, "price": p} for n, p in zip(outcome_names, odds)
            ]}],
        })

    if len(bookmakers) < MIN_BOOKMAKERS:
        return None  # too few bookmakers — arb very unlikely, skip

    return {"home_team": home_team, "away_team": away_team,
            "commence_time": commence_time, "bookmakers": bookmakers}


async def scrape_sport(sport_key: str) -> list[dict]:
    listing_url = SPORT_URLS.get(sport_key)
    if not listing_url:
        print(f"No URL mapping for sport: {sport_key}")
        return []

    tennis_filter = TENNIS_FILTERS.get(sport_key, "")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        ctx = await browser.new_context(user_agent=ua)

        # --- Step 1: collect all match links (single page, sequential) ---
        listing_page = await ctx.new_page()
        print(f"  Listing: {listing_url}")
        match_links = await get_match_links(listing_page, listing_url, tennis_filter)
        await listing_page.close()
        print(f"  Found {len(match_links)} match links — scraping in parallel ({PARALLEL_PAGES} at a time)")

        # --- Step 2: scrape match pages in parallel batches ---
        results = []
        seen = set()
        unique_links = [l for l in match_links if l not in seen and not seen.add(l)][:MAX_MATCHES]

        async def worker(links_chunk):
            page = await ctx.new_page()
            chunk_results = []
            for link in links_chunk:
                data = await scrape_match(page, link)
                if data:
                    chunk_results.append(data)
                    print(f"    + {data['home_team']} vs {data['away_team']} ({len(data['bookmakers'])} bookmakers)")
            await page.close()
            return chunk_results

        # Split links into PARALLEL_PAGES chunks and run concurrently
        chunks = [unique_links[i::PARALLEL_PAGES] for i in range(PARALLEL_PAGES)]
        chunk_results = await asyncio.gather(*[worker(chunk) for chunk in chunks])
        for r in chunk_results:
            results.extend(r)

        await browser.close()

    return results


def get_odds_data_scraped(sport_key: str) -> list[dict]:
    """Synchronous wrapper — drop-in replacement for get_odds_data()."""
    try:
        return asyncio.run(scrape_sport(sport_key))
    except Exception as e:
        print(f"  [scraper error] {sport_key}: {e}")
        return []


if __name__ == "__main__":
    import sys
    sport = sys.argv[1] if len(sys.argv) > 1 else "tennis_wta"
    print(f"Scraping {sport}...\n")
    import time
    t = time.time()
    data = get_odds_data_scraped(sport)
    elapsed = time.time() - t
    print(f"\nTotal matches: {len(data)} in {elapsed:.0f}s")
    for m in data:
        print(f"  {m['home_team']} vs {m['away_team']} — {len(m['bookmakers'])} bookmakers")
