"""
Automated marketing module.

Handles:
  - Bluesky posts triggered by arb finds
  - Daily stats digest (Bluesky + Discord free channel)
  - Weekly SEO blog post to GitHub Pages (via repo commit)

Environment variables:
  BLUESKY_HANDLE      e.g. yourhandle.bsky.social
  BLUESKY_PASSWORD    Bluesky app password (not main password)
  DISCORD_BOT_TOKEN   (reused from discord_alerts)
  DISCORD_FREE_CHANNEL_ID
  DISCORD_INVITE_LINK Your server invite URL shown in posts
  ANTHROPIC_API_KEY   For auto-generating blog posts (optional)
  GITHUB_TOKEN        For committing blog posts (set automatically in Actions)
  GITHUB_REPO         e.g. saroopjagdev/arbitrage-betting
"""

import os
import json
import requests
from datetime import datetime, timezone

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FREE_CHANNEL_ID = os.getenv("DISCORD_FREE_CHANNEL_ID")
INVITE_LINK = os.getenv("DISCORD_INVITE_LINK", "https://discord.gg/your-invite")
KOFI_LINK = "https://ko-fi.com/arbfactory"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "saroopjagdev/arbitrage-betting")

# Only post to Bluesky for arbs above this threshold — small arbs vanish too fast
BLUESKY_MIN_PROFIT = 0.03  # 3%

# In-memory session cache (within one run)
_bsky_session: dict | None = None


# ---------------------------------------------------------------------------
# Bluesky
# ---------------------------------------------------------------------------

def _bsky_login() -> dict | None:
    global _bsky_session
    if _bsky_session:
        return _bsky_session
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        return None
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": BLUESKY_HANDLE, "password": BLUESKY_PASSWORD},
        timeout=10,
    )
    if resp.ok:
        _bsky_session = resp.json()
        return _bsky_session
    print(f"[bluesky] login failed: {resp.text}")
    return None


def _bsky_post(text: str) -> bool:
    session = _bsky_login()
    if not session:
        return False
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            },
        },
        timeout=10,
    )
    if not resp.ok:
        print(f"[bluesky] post failed: {resp.text}")
    return resp.ok


def post_arb_to_bluesky(
    home: str,
    away: str,
    profit_pct: float,
    sport_key: str,
) -> bool:
    """Post a teaser for a single arb find. Only fires if profit >= BLUESKY_MIN_PROFIT."""
    if profit_pct < BLUESKY_MIN_PROFIT:
        return False

    sport_label = sport_key.replace("_", " ").title()
    text = (
        f"🔔 {profit_pct:.1f}% guaranteed profit spotted\n"
        f"📊 {home} vs {away} ({sport_label})\n\n"
        f"Full details — bookmakers, stakes & links — in our Discord.\n"
        f"Subscribe: {KOFI_LINK}\n\n"
        f"#arbitrage #surebets #bettingtips #matchedbetting"
    )
    return _bsky_post(text)


# ---------------------------------------------------------------------------
# Daily digest
# ---------------------------------------------------------------------------

def post_daily_digest(arb_results: list[dict]) -> None:
    """
    Call after a full scan. arb_results is a list of dicts:
      {"home": str, "away": str, "profit": float, "sport": str}
    """
    if not arb_results:
        return

    count = len(arb_results)
    best = max(arb_results, key=lambda x: x["profit"])
    avg = sum(x["profit"] for x in arb_results) / count
    sports = set(x["sport"].split("_")[0].title() for x in arb_results)

    # Discord free channel embed
    if BOT_TOKEN and FREE_CHANNEL_ID:
        embed = {
            "title": "📈 Today's Arb Summary",
            "description": (
                f"**{count}** opportunities found across {', '.join(sports)}\n\n"
                f"**Best:** {best['profit']:.1f}% — {best['home']} vs {best['away']}\n"
                f"**Average:** {avg:.1f}%\n\n"
                f"*Full details, bookmaker names & bet sizes available to subscribers.*\n"
                f"👉 {KOFI_LINK}"
            ),
            "color": 0x2ecc71,
            "footer": {"text": f"Subscribe for real-time alerts → {KOFI_LINK}"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        headers = {
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json",
        }
        requests.post(
            f"https://discord.com/api/v10/channels/{FREE_CHANNEL_ID}/messages",
            headers=headers,
            json={"embeds": [embed]},
            timeout=10,
        )

    # Bluesky daily digest (only if best >= threshold)
    if best["profit"] >= BLUESKY_MIN_PROFIT:
        text = (
            f"📊 Today's arb scan results:\n"
            f"✅ {count} opportunities found\n"
            f"🏆 Best: {best['profit']:.1f}% ({best['home']} vs {best['away']})\n"
            f"📈 Average: {avg:.1f}%\n\n"
            f"Subscribe for real-time alerts 👇\n"
            f"{KOFI_LINK}\n\n"
            f"#arbitrage #surebets #matchedbetting #bettingtips"
        )
        _bsky_post(text)


# ---------------------------------------------------------------------------
# Weekly SEO blog post → GitHub Pages
# ---------------------------------------------------------------------------

def _generate_blog_post(week_arbs: list[dict]) -> str | None:
    """Use Claude to write a short SEO blog post about the week's finds."""
    if not ANTHROPIC_API_KEY:
        return None

    best = sorted(week_arbs, key=lambda x: x["profit"], reverse=True)[:3]
    examples = "\n".join(
        f"- {a['home']} vs {a['away']} ({a['sport']}): {a['profit']:.1f}%"
        for a in best
    )

    prompt = (
        "Write a short SEO blog post (300-400 words) about arbitrage betting opportunities "
        "found this week. Tone: educational, not salesy. Include:\n"
        "- A brief explanation of what arbitrage betting is\n"
        "- These real examples found this week:\n"
        f"{examples}\n"
        "- A section on how to act on arbs quickly before odds move\n"
        "- A natural CTA at the end mentioning a Discord community for real-time alerts\n"
        "Format as markdown. Title should be SEO-friendly. No made-up statistics."
    )

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    if resp.ok:
        return resp.json()["content"][0]["text"]
    print(f"[blog] Claude API error: {resp.text}")
    return None


def publish_weekly_blog(week_arbs: list[dict]) -> bool:
    """Commit a markdown blog post to docs/ in the GitHub repo."""
    if not GITHUB_TOKEN or not week_arbs:
        return False

    content = _generate_blog_post(week_arbs)
    if not content:
        return False

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"docs/_posts/{date_str}-arb-opportunities.md"

    # GitHub Contents API
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    # Check if file exists (to get its SHA for updates)
    check = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}",
        headers=headers,
        timeout=10,
    )
    sha = check.json().get("sha") if check.ok else None

    import base64
    payload = {
        "message": f"Weekly arb blog post {date_str}",
        "content": base64.b64encode(content.encode()).decode(),
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}",
        headers=headers,
        json=payload,
        timeout=10,
    )
    if resp.ok:
        print(f"[blog] Published: {filename}")
    else:
        print(f"[blog] Publish failed: {resp.text}")
    return resp.ok
