#!/usr/bin/env python3
"""Manual run of daily update for testing."""

from src.scheduler.update_scheduler import create_daily_scheduler
from src.config import settings

print("Starting manual daily update...")
print(f"WeChat notification: {'Enabled' if settings.WECHAT_NOTIFICATION_ENABLED else 'Disabled'}")

with create_daily_scheduler() as scheduler:
    # Force run regardless of next schedule
    result = scheduler.run_scheduled_update(force=True)
    print(f"\nUpdate result: {result}")
