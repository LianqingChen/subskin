"""Incremental update tracker for daily automated execution.

This module tracks what content changed each day, enabling detailed
notification reporting for QQ bot messages.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from src.exceptions import CacheError


class UpdateType(str, Enum):
    """Types of content updates."""
    NEW_PAPER = "new_paper"
    NEW_TRIAL = "new_trial"
    UPDATED_PAPER = "updated_paper"
    UPDATED_TRIAL = "updated_trial"
    FAILED_CRAWL = "failed_crawl"
    SYSTEM_INFO = "system_info"


class UpdateRecord(TypedDict):
    """Record of a single update event."""
    id: int
    update_type: UpdateType
    resource_id: str
    resource_title: str
    change_details: Dict[str, Any]
    timestamp: str
    source: str


class DailySummary(TypedDict):
    """Summary of updates for a specific day."""
    date: str
    total_updates: int
    new_papers: int
    new_trials: int
    updated_papers: int
    updated_trials: int
    failed_crawls: int
    details: List[UpdateRecord]


class IncrementalTracker:
    """Tracks incremental updates for daily reporting.
    
    This tracker records what changed each day, enabling detailed
    notifications about daily updates.
    """
    
    def __init__(self, db_path: str | Path = "incremental_updates.sqlite") -> None:
        """Initialize the incremental tracker.
        
        Args:
            db_path: SQLite database path.
        """
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize_schema()
    
    def _initialize_schema(self) -> None:
        """Create the necessary database tables."""
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    update_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    resource_title TEXT NOT NULL,
                    change_details TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    source TEXT NOT NULL,
                    processed BOOLEAN DEFAULT 0
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_updates_date 
                ON daily_updates(date(timestamp))
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_updates_type 
                ON daily_updates(update_type)
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_updates_processed 
                ON daily_updates(processed)
            """)
    
    def record_update(
        self,
        update_type: UpdateType,
        resource_id: str,
        resource_title: str,
        change_details: Dict[str, Any],
        source: str
    ) -> None:
        """Record a single update event.
        
        Args:
            update_type: Type of update (new paper, updated trial, etc.)
            resource_id: Unique identifier for the resource (PMID, NCT ID)
            resource_title: Human-readable title of the resource
            change_details: JSON-serializable details about what changed
            source: Source of the update (pubmed, semantic_scholar, clinical_trials)
        """
        try:
            details_json = json.dumps(change_details, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise CacheError(f"Failed to serialize change details: {e}") from e
        
        with self._lock:
            with self._conn:
                self._conn.execute("""
                    INSERT INTO daily_updates 
                    (update_type, resource_id, resource_title, change_details, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (update_type.value, resource_id, resource_title, details_json, source))
    
    def get_todays_summary(self) -> DailySummary:
        """Get summary of updates for today.
        
        Returns:
            DailySummary with counts and details of today's updates.
        """
        today = datetime.now().date().isoformat()
        return self.get_daily_summary(today)
    
    def get_daily_summary(self, date_str: str) -> DailySummary:
        """Get summary of updates for a specific date.
        
        Args:
            date_str: Date in ISO format (YYYY-MM-DD)
            
        Returns:
            DailySummary with counts and details for the specified date.
        """
        with self._lock:
            cursor = self._conn.execute("""
                SELECT 
                    id, update_type, resource_id, resource_title, 
                    change_details, timestamp, source
                FROM daily_updates 
                WHERE date(timestamp) = ?
                ORDER BY timestamp DESC
            """, (date_str,))
            
            records = []
            counts = {
                UpdateType.NEW_PAPER: 0,
                UpdateType.NEW_TRIAL: 0,
                UpdateType.UPDATED_PAPER: 0,
                UpdateType.UPDATED_TRIAL: 0,
                UpdateType.FAILED_CRAWL: 0,
                UpdateType.SYSTEM_INFO: 0,
            }
            
            for row in cursor:
                try:
                    change_details = json.loads(row["change_details"])
                except json.JSONDecodeError:
                    change_details = {"error": "Failed to parse change details"}
                
                record: UpdateRecord = {
                    "id": row["id"],
                    "update_type": UpdateType(row["update_type"]),
                    "resource_id": row["resource_id"],
                    "resource_title": row["resource_title"],
                    "change_details": change_details,
                    "timestamp": row["timestamp"],
                    "source": row["source"],
                }
                records.append(record)
                
                update_type = UpdateType(row["update_type"])
                counts[update_type] += 1
            
            summary: DailySummary = {
                "date": date_str,
                "total_updates": len(records),
                "new_papers": counts[UpdateType.NEW_PAPER],
                "new_trials": counts[UpdateType.NEW_TRIAL],
                "updated_papers": counts[UpdateType.UPDATED_PAPER],
                "updated_trials": counts[UpdateType.UPDATED_TRIAL],
                "failed_crawls": counts[UpdateType.FAILED_CRAWL],
                "details": records,
            }
            
            return summary
    
    def get_unprocessed_updates(self) -> List[UpdateRecord]:
        """Get all unprocessed update records.
        
        Returns:
            List of update records that haven't been marked as processed.
        """
        with self._lock:
            cursor = self._conn.execute("""
                SELECT 
                    id, update_type, resource_id, resource_title, 
                    change_details, timestamp, source
                FROM daily_updates 
                WHERE processed = 0
                ORDER BY timestamp ASC
            """)
            
            records = []
            for row in cursor:
                try:
                    change_details = json.loads(row["change_details"])
                except json.JSONDecodeError:
                    change_details = {"error": "Failed to parse change details"}
                
                record: UpdateRecord = {
                    "id": row["id"],
                    "update_type": UpdateType(row["update_type"]),
                    "resource_id": row["resource_id"],
                    "resource_title": row["resource_title"],
                    "change_details": change_details,
                    "timestamp": row["timestamp"],
                    "source": row["source"],
                }
                records.append(record)
            
            return records
    
    def mark_as_processed(self, update_ids: List[int]) -> None:
        """Mark update records as processed.
        
        Args:
            update_ids: List of update record IDs to mark as processed.
        """
        if not update_ids:
            return
        
        with self._lock:
            with self._conn:
                placeholders = ",".join("?" * len(update_ids))
                self._conn.execute(
                    f"UPDATE daily_updates SET processed = 1 WHERE id IN ({placeholders})",
                    update_ids
                )
    
    def cleanup_old_records(self, days_to_keep: int = 30) -> None:
        """Remove old update records.
        
        Args:
            days_to_keep: Number of days to keep records (default: 30).
        """
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).date().isoformat()
        
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "DELETE FROM daily_updates WHERE date(timestamp) < ?",
                    (cutoff_date,)
                )
    
    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()
    
    def __enter__(self) -> IncrementalTracker:
        """Return the tracker instance for context manager usage."""
        return self
    
    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Close the tracker when leaving a context manager."""
        self.close()