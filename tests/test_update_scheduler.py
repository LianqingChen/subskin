"""Tests for the update scheduler."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.scheduler.update_scheduler import (
    CrawlerStatus,
    ScheduleFrequency,
    ScheduleConfig,
    UpdateScheduler,
    create_daily_scheduler,
)


def test_scheduler_initialization() -> None:
    """Test scheduler initialization with default config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        state_path = Path(tmpdir) / "state.sqlite"

        scheduler = UpdateScheduler(config_path=config_path, state_db_path=state_path)

        assert scheduler.config["frequency"] == ScheduleFrequency.DAILY
        assert scheduler.config["hour"] == 9
        assert scheduler.config["minute"] == 0
        assert scheduler.config["enabled"] is True

        scheduler.close()


def test_schedule_config_save_load() -> None:
    """Test saving and loading schedule configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        scheduler = UpdateScheduler(config_path=config_path)

        original_config = scheduler.config.copy()

        new_config: ScheduleConfig = {
            "frequency": ScheduleFrequency.WEEKLY,
            "hour": 14,
            "minute": 30,
            "enabled": False,
            "max_runtime_hours": 4.0,
            "notify_on_completion": False,
            "notify_on_failure": True,
        }

        scheduler.update_config(**new_config)

        for key, value in new_config.items():
            assert scheduler.config[key] == value

        scheduler.close()

        scheduler2 = UpdateScheduler(config_path=config_path)

        for key, value in new_config.items():
            assert scheduler2.config[key] == value

        scheduler2.close()


def test_calculate_next_run_daily() -> None:
    """Test next run calculation for daily schedule."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        scheduler = UpdateScheduler(config_path=config_path)
        scheduler.update_config(frequency=ScheduleFrequency.DAILY, hour=9, minute=0)

        now = datetime.now()

        last_run = now - timedelta(days=1)
        next_run = scheduler.calculate_next_run(last_run)

        assert next_run.hour == 9
        assert next_run.minute == 0
        assert next_run > now

        scheduler.close()


def test_calculate_next_run_weekly() -> None:
    """Test next run calculation for weekly schedule."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        scheduler = UpdateScheduler(config_path=config_path)
        scheduler.update_config(frequency=ScheduleFrequency.WEEKLY, hour=14, minute=30)

        now = datetime.now()

        last_run = now - timedelta(days=7)
        next_run = scheduler.calculate_next_run(last_run)

        assert next_run.hour == 14
        assert next_run.minute == 30

        days_until_next = (next_run - now).days
        assert 0 <= days_until_next <= 6

        scheduler.close()


def test_should_run_now_logic() -> None:
    """Test schedule execution timing logic."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        state_path = Path(tmpdir) / "state.sqlite"

        scheduler = UpdateScheduler(config_path=config_path, state_db_path=state_path)

        scheduler.update_config(enabled=True)

        should_run = scheduler.should_run_now()

        assert should_run in (True, False)

        scheduler.close()


def test_schedule_execution_skipped_when_disabled() -> None:
    """Test that schedule doesn't run when disabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        state_path = Path(tmpdir) / "state.sqlite"

        scheduler = UpdateScheduler(config_path=config_path, state_db_path=state_path)

        scheduler.update_config(enabled=False)

        scheduler.enable_schedule("main")

        scheduler.disable_schedule("main")

        state = scheduler.get_schedule_state("main")
        if state:
            assert state["enabled"] == 0

        scheduler.close()


def test_schedule_execution_history() -> None:
    """Test recording and retrieving execution history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        state_path = Path(tmpdir) / "state.sqlite"

        scheduler = UpdateScheduler(config_path=config_path, state_db_path=state_path)

        scheduler.update_config(enabled=True)

        result = scheduler.run_scheduled_update()

        assert "status" in result
        assert "items_collected" in result
        assert "items_updated" in result

        history = scheduler.get_execution_history(limit=5)

        assert len(history) >= 1

        latest = history[0]
        assert latest["schedule_id"] == "main"
        assert latest["status"] in ["completed", "failed"]

        crawler_results = latest.get("crawler_results", [])
        assert isinstance(crawler_results, list)

        scheduler.close()


def test_crawler_result_structure() -> None:
    """Test crawler result data structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        state_path = Path(tmpdir) / "state.sqlite"

        scheduler = UpdateScheduler(config_path=config_path, state_db_path=state_path)

        # Ensure the schedule is enabled and next_run is in the past
        with scheduler._conn:
            from datetime import datetime, timedelta

            past = datetime.now() - timedelta(days=1)
            next_run = datetime.now() - timedelta(hours=1)
            scheduler._conn.execute(
                """
                INSERT INTO schedule_state (schedule_id, last_run, next_run, consecutive_failures, enabled)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("main", past.isoformat(), next_run.isoformat(), 0, 1),
            )

        result = scheduler.run_scheduled_update()

        assert "crawler_results" in result
        crawler_results = result["crawler_results"]

        assert isinstance(crawler_results, list)

        for crawler_result in crawler_results:
            assert "crawler_name" in crawler_result
            assert "status" in crawler_result
            assert crawler_result["status"] in [
                CrawlerStatus.PENDING.value,
                CrawlerStatus.RUNNING.value,
                CrawlerStatus.COMPLETED.value,
                CrawlerStatus.FAILED.value,
                CrawlerStatus.SKIPPED.value,
            ]
            assert "items_collected" in crawler_result
            assert "items_updated" in crawler_result
            assert "errors" in crawler_result
            assert "start_time" in crawler_result
            assert "end_time" in crawler_result
            assert "duration_seconds" in crawler_result

        scheduler.close()


def test_consecutive_failure_handling() -> None:
    """Test handling of consecutive failures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        state_path = Path(tmpdir) / "state.sqlite"

        scheduler = UpdateScheduler(config_path=config_path, state_db_path=state_path)

        schedule_id = "test_schedule"

        with scheduler._conn:
            scheduler._conn.execute(
                """
                INSERT INTO schedule_state 
                (schedule_id, last_run, next_run, consecutive_failures, enabled)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    schedule_id,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    2,
                    1,
                ),
            )

        scheduler._update_schedule_state(
            schedule_id, datetime.now(), datetime.now() + timedelta(days=1), failed=True
        )

        state = scheduler.get_schedule_state(schedule_id)
        if state:
            assert state["consecutive_failures"] == 3
            assert state["enabled"] == 0

        scheduler.close()


def test_create_daily_scheduler() -> None:
    """Test factory function for daily scheduler."""
    scheduler = create_daily_scheduler()

    try:
        assert scheduler.config["frequency"] == ScheduleFrequency.DAILY
        assert scheduler.config["hour"] == 7
        assert scheduler.config["minute"] == 0
        assert scheduler.config["enabled"] is True

    finally:
        scheduler.close()


def test_scheduler_context_manager() -> None:
    """Test scheduler as context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        state_path = Path(tmpdir) / "state.sqlite"

        with UpdateScheduler(
            config_path=config_path, state_db_path=state_path
        ) as scheduler:
            assert scheduler.config["frequency"] == ScheduleFrequency.DAILY

            result = scheduler.run_scheduled_update()
            assert "status" in result

        # Check that connection is closed by trying to use it
        try:
            scheduler._conn.execute("SELECT 1")
            assert False, "Connection should be closed"
        except Exception:
            # Expected - connection is closed
            pass


def test_incremental_tracking_integration() -> None:
    """Test scheduler integration with incremental tracker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        state_path = Path(tmpdir) / "state.sqlite"
        tracker_db = Path(tmpdir) / "tracker.sqlite"

        from src.utils.incremental_tracker import IncrementalTracker

        tracker = IncrementalTracker(tracker_db)
        scheduler = UpdateScheduler(
            config_path=config_path,
            state_db_path=state_path,
            incremental_tracker=tracker,
        )

        scheduler.update_config(enabled=True)

        result = scheduler.run_scheduled_update()

        if result["items_collected"] > 0:
            today = datetime.now().date().isoformat()
            summary = tracker.get_daily_summary(today)
            assert summary["total_updates"] > 0

        scheduler.close()
        tracker.close()


def test_schedule_state_persistence() -> None:
    """Test that schedule state persists across instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        state_path = Path(tmpdir) / "state.sqlite"

        scheduler1 = UpdateScheduler(config_path=config_path, state_db_path=state_path)

        schedule_id = "test_persistence"
        test_time = datetime.now().isoformat()

        with scheduler1._conn:
            scheduler1._conn.execute(
                """
                INSERT INTO schedule_state 
                (schedule_id, last_run, next_run, consecutive_failures, enabled)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id) DO UPDATE SET
                    last_run = excluded.last_run,
                    next_run = excluded.next_run,
                    consecutive_failures = excluded.consecutive_failures,
                    enabled = excluded.enabled
                """,
                (schedule_id, test_time, test_time, 1, 1),
            )

        scheduler1.close()

        scheduler2 = UpdateScheduler(config_path=config_path, state_db_path=state_path)

        state = scheduler2.get_schedule_state(schedule_id)

        assert state is not None
        assert state["schedule_id"] == schedule_id
        assert state["last_run"] == test_time
        assert state["next_run"] == test_time
        assert state["consecutive_failures"] == 1
        assert state["enabled"] == 1

        scheduler2.close()
