# arbitrage-betting

Finds sports-betting arbitrage opportunities (guaranteed-profit price discrepancies across bookmakers) and posts them to Discord.

## How it works
1. `scraper.py` scrapes OddsPortal with Playwright (parallel match pages) and returns odds in the same shape as The Odds API.
2. `arb_finder.py` checks 3-way markets (e.g. football) and 2-way markets (e.g. tennis) for arbitrage and computes stakes (`arb_calculation.py`).
3. `discord_alerts.py` posts alerts; some are queued and flushed later as delayed "free" alerts (`post_free_alerts.py`).
4. `marketing.py` posts daily digests to Bluesky and drafts a weekly blog post with the Anthropic API.
5. `main.py` runs the tracker.

## Setup
```
pip install -r requirements.txt
playwright install chromium
python main.py
```
Configure Discord, Bluesky and Anthropic credentials via environment variables (see the top of `discord_alerts.py` and `marketing.py`). Tests: `python test_rounding.py`. Bookmaker terms may restrict arbitrage betting; use responsibly.
