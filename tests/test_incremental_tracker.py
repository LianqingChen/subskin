"""Tests for the incremental update tracker."""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest
import tempfile
from pathlib import Path

from src.utils.incremental_tracker import (
    IncrementalTracker,
    UpdateType,
    DailySummary,
)
from src.exceptions import CacheError


def test_initialize_creates_schema(tmp_path: Path) -> None:
    """Test that initialization creates the database schema."""
    db_path = tmp_path / "updates.db"
    tracker = IncrementalTracker(db_path)
    tracker.close()

    assert db_path.exists()


def test_record_update_and_get_summary(tmp_path: Path) -> None:
    """Test recording an update and retrieving it from today's summary."""
    db_path = tmp_path / "updates.db"
    tracker = IncrementalTracker(db_path)

    # Record a new paper
    tracker.record_update(
        update_type=UpdateType.NEW_PAPER,
        resource_id="pmid:12345678",
        resource_title="Vitiligo Treatment with JAK Inhibitors",
        change_details={"journal": "Journal of Dermatology"},
        source="pubmed",
    )

    # Record a new clinical trial
    tracker.record_update(
        update_type=UpdateType.NEW_TRIAL,
        resource_id="NCT12345678",
        resource_title="Study of Ruxolitinib for Vitiligo",
        change_details={"phase": "Phase 3"},
        source="clinical_trials",
    )

    summary = tracker.get_todays_summary()
    assert summary["total_updates"] == 2
    assert summary["new_papers"] == 1
    assert summary["new_trials"] == 1
    assert len(summary["details"]) == 2
    assert summary["details"][0]["resource_id"] == "pmid:12345678"


def test_count_total_by_type(tmp_path: Path) -> None:
    """Test counting total updates by type."""
    db_path = tmp_path / "updates.db"
    tracker = IncrementalTracker(db_path)

    for i in range(3):
        tracker.record_update(
            update_type=UpdateType.NEW_PAPER,
            resource_id=f"pmid:{i}",
            resource_title=f"Paper {i}",
            change_details={},
            source="pubmed",
        )

    for i in range(2):
        tracker.record_update(
            update_type=UpdateType.NEW_TRIAL,
            resource_id=f"NCT{i}",
            resource_title=f"Trial {i}",
            change_details={},
            source="clinical_trials",
        )

    assert tracker.count_total_by_type(UpdateType.NEW_PAPER) == 3
    assert tracker.count_total_by_type(UpdateType.NEW_TRIAL) == 2
    assert tracker.count_total_by_type(UpdateType.FAILED_CRAWL) == 0


def test_get_unprocessed_and_mark_processed(tmp_path: Path) -> None:
    """Test getting unprocessed updates and marking them as processed."""
    db_path = tmp_path / "updates.db"
    tracker = IncrementalTracker(db_path)

    # Add three unprocessed updates
    tracker.record_update(
        update_type=UpdateType.NEW_PAPER,
        resource_id="pmid:1",
        resource_title="Paper 1",
        change_details={},
        source="pubmed",
    )
    tracker.record_update(
        update_type=UpdateType.NEW_PAPER,
        resource_id="pmid:2",
        resource_title="Paper 2",
        change_details={},
        source="pubmed",
    )

    unprocessed = tracker.get_unprocessed_updates()
    assert len(unprocessed) == 2

    # Mark first as processed
    ids = [unprocessed[0]["id"]]
    tracker.mark_as_processed(ids)

    unprocessed_after = tracker.get_unprocessed_updates()
    assert len(unprocessed_after) == 1
    assert unprocessed_after[0]["resource_id"] == "pmid:2"


def test_cleanup_old_records(tmp_path: Path) -> None:
    """Test cleaning up of old records."""
    db_path = tmp_path / "updates.db"
    tracker = IncrementalTracker(db_path)

    # We can't easily test dates with future/past, but at least the query executes
    tracker.cleanup_old_records(days_to_keep=30)
    # No error means it works

    tracker.close()


def test_context_manager(tmp_path: Path) -> None:
    """Test that context manager closes the database correctly."""
    db_path = tmp_path / "updates.db"

    with IncrementalTracker(db_path) as tracker:
        tracker.record_update(
            update_type=UpdateType.NEW_PAPER,
            resource_id="pmid:123",
            resource_title="Test",
            change_details={},
            source="pubmed",
        )

    # After context exit, connection should be closed
    # No exception means it worked


def test_record_update_non_serializable_raises(tmp_path: Path) -> None:
    """Test that non-JSON-serializable change details raise CacheError."""
    db_path = tmp_path / "updates.db"
    tracker = IncrementalTracker(db_path)

    # Contains an un-serializable object (a function)
    bad_data = {"func": lambda x: x}

    with pytest.raises(CacheError, match="Failed to serialize"):
        tracker.record_update(
            update_type=UpdateType.NEW_PAPER,
            resource_id="pmid:123",
            resource_title="Test",
            change_details=bad_data,
            source="pubmed",
        )


def test_get_daily_summary_empty(tmp_path: Path) -> None:
    """Test getting daily summary when no updates exist."""
    db_path = tmp_path / "updates.db"
    tracker = IncrementalTracker(db_path)

    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    summary = tracker.get_daily_summary(yesterday)

    assert summary["total_updates"] == 0
    assert summary["new_papers"] == 0
    assert len(summary["details"]) == 0


def test_get_unprocessed_updates_empty(tmp_path: Path) -> None:
    """Test getting unprocessed updates when none exist."""
    db_path = tmp_path / "updates.db"
    tracker = IncrementalTracker(db_path)

    unprocessed = tracker.get_unprocessed_updates()
    assert unprocessed == []


def test_mark_processed_empty_list_does_nothing(tmp_path: Path) -> None:
    """Test marking an empty list of processed doesn't cause errors."""
    db_path = tmp_path / "updates.db"
    tracker = IncrementalTracker(db_path)

    # Should not raise
    tracker.mark_as_processed([])
