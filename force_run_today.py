#!/usr/bin/env python3
"""Force run today's data collection and save output."""

from src.scheduler.update_scheduler import UpdateScheduler
from datetime import datetime
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

scheduler = UpdateScheduler()
now = datetime.now()

# Force set to run today
with scheduler._lock:
    with scheduler._conn:
        scheduler._conn.execute(
            'UPDATE schedule_state SET last_run = ?, next_run = ? WHERE schedule_id = ?',
            ('2026-04-02T00:00:00', now.isoformat(), 'main')
        )

print("🚀 Starting forced data collection for today...")
result = scheduler.run_scheduled_update()

print(f"\n📝 Result: {result['status']}")
print(f"Items collected: {result['items_collected']}")
print(f"Items updated: {result['items_updated']}")

if result['errors']:
    print(f"Errors: {result['errors']}")

scheduler.close()

print("\n✅ Done!")
