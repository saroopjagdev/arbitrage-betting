"""Run by the delayed GitHub Actions job to flush queued free-tier alerts."""
from discord_alerts import flush_pending_free_alerts
flush_pending_free_alerts()
