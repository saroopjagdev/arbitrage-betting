import requests
import os
import json
from datetime import datetime, timezone
from pathlib import Path

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")                  # #arb-alerts (subscribers, instant)
BIG_ARB_CHANNEL_ID = os.getenv("DISCORD_BIG_ARB_CHANNEL_ID")  # #big-arbs (≥4%, subscribers, instant)
FREE_CHANNEL_ID = os.getenv("DISCORD_FREE_CHANNEL_ID")        # #arb-preview (free, 30 min delay)

BIG_ARB_THRESHOLD = 0.04   # 4% — cross-post to #big-arbs
FREE_ARB_THRESHOLD = 0.03  # 3% — queue for free channel (delayed 30 min)

DISCORD_API = "https://discord.com/api/v10"
PENDING_FILE = Path("pending_free_alerts.json")


def _post_to_channel(channel_id: str, content: str, embed: dict | None = None):
    if not BOT_TOKEN or not channel_id:
        return False
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    payload: dict = {"content": content}
    if embed:
        payload["embeds"] = [embed]
    resp = requests.post(
        f"{DISCORD_API}/channels/{channel_id}/messages",
        headers=headers,
        json=payload,
        timeout=10,
    )
    if not resp.ok:
        print(f"[discord error] {resp.status_code}: {resp.text}")
    return resp.ok


def _queue_free_alert(embed: dict, profit: float):
    """Save alert to pending file so the delayed job can post it 30 min later."""
    pending = []
    if PENDING_FILE.exists():
        try:
            pending = json.loads(PENDING_FILE.read_text())
        except Exception:
            pass
    pending.append({
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "profit": profit,
        "embed": embed,
    })
    PENDING_FILE.write_text(json.dumps(pending, indent=2))


def send_alert(msg: str, embed: dict | None = None, profit: float = 0.0):
    if not BOT_TOKEN:
        print(f"[ALERT - no bot token] {msg}")
        return

    # Subscribers get it instantly
    _post_to_channel(CHANNEL_ID, msg, embed)

    # Big arbs get an @here ping in #big-arbs too
    if BIG_ARB_CHANNEL_ID and profit >= BIG_ARB_THRESHOLD:
        _post_to_channel(BIG_ARB_CHANNEL_ID, f"@here {msg}", embed)

    # Queue for free channel if above threshold — posted 30 min later by delayed job
    if FREE_CHANNEL_ID and embed and profit >= FREE_ARB_THRESHOLD:
        free_embed = {
            "title": embed["title"],
            "description": (
                embed.get("description", "").split("\n")[0] + "\n\n"
                "⚠️ *This alert was sent to subscribers 30 minutes ago.*\n"
                "Subscribe for real-time alerts → ko-fi.com/arbfactory"
            ),
            "color": embed.get("color", 0x3498db),
            "fields": embed.get("fields", []),
            "footer": {"text": embed.get("footer", {}).get("text", "")},
        }
        _queue_free_alert(free_embed, profit)


def flush_pending_free_alerts():
    """
    Called by the delayed GitHub Actions job (30 min after main scan).
    Posts any queued alerts to the free channel and clears the file.
    """
    if not PENDING_FILE.exists():
        print("[free alerts] nothing pending")
        return

    try:
        pending = json.loads(PENDING_FILE.read_text())
    except Exception:
        print("[free alerts] could not read pending file")
        return

    print(f"[free alerts] posting {len(pending)} delayed alerts")
    for item in pending:
        _post_to_channel(FREE_CHANNEL_ID, "", item["embed"])

    PENDING_FILE.write_text("[]")
