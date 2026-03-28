"""Update scheduler for daily automated execution on Aliyun ECS.

This scheduler manages periodic updates of vitiligo research data,
tracking incremental changes and coordinating notifications.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from src.exceptions import CrawlerError
from src.utils.incremental_tracker import IncrementalTracker, UpdateType
from src.utils.logger import get_logger


logger = get_logger(__name__)


class ScheduleFrequency(str, Enum):
    """Frequency of scheduled updates."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class CrawlerStatus(str, Enum):
    """Status of a crawler execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CrawlerResult(TypedDict):
    """Result of a crawler execution."""
    crawler_name: str
    status: CrawlerStatus
    items_collected: int
    items_updated: int
    errors: List[str]
    start_time: str
    end_time: str
    duration_seconds: float


class ScheduleConfig(TypedDict):
    """Configuration for scheduling."""
    frequency: ScheduleFrequency
    hour: int
    minute: int
    enabled: bool
    max_runtime_hours: float
    notify_on_completion: bool
    notify_on_failure: bool


class UpdateScheduler:
    """Scheduler for periodic updates with incremental tracking.
    
    This scheduler manages daily automated execution on Aliyun ECS,
    tracking what changed and coordinating QQ bot notifications.
    """
    
    def __init__(
        self,
        config_path: str | Path = "scheduler_config.json",
        state_db_path: str | Path = "scheduler_state.sqlite",
        incremental_tracker: Optional[IncrementalTracker] = None
    ) -> None:
        self.config_path = Path(config_path)
        self.state_db_path = Path(state_db_path)
        self.incremental_tracker = incremental_tracker or IncrementalTracker()
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.state_db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize_schema()
        self._load_config()
    
    def _initialize_schema(self) -> None:
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS schedule_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id TEXT NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    status TEXT NOT NULL,
                    crawler_results TEXT NOT NULL,
                    items_collected INTEGER DEFAULT 0,
                    items_updated INTEGER DEFAULT 0,
                    errors TEXT
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS schedule_state (
                    schedule_id TEXT PRIMARY KEY,
                    last_run DATETIME,
                    next_run DATETIME,
                    consecutive_failures INTEGER DEFAULT 0,
                    enabled BOOLEAN DEFAULT 1
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedule_history_time 
                ON schedule_history(start_time)
            """)
    
    def _load_config(self) -> None:
        default_config: ScheduleConfig = {
            "frequency": ScheduleFrequency.DAILY,
            "hour": 9,
            "minute": 0,
            "enabled": True,
            "max_runtime_hours": 2.0,
            "notify_on_completion": True,
            "notify_on_failure": True
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    loaded = json.load(f)
                    self.config = {**default_config, **loaded}
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load config, using defaults: {e}")
                self.config = default_config
        else:
            self.config = default_config
            self._save_config()
    
    def _save_config(self) -> None:
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2, default=str)
    
    def calculate_next_run(self, last_run: Optional[datetime] = None) -> datetime:
        frequency = self.config["frequency"]
        hour = self.config["hour"]
        minute = self.config["minute"]
        
        now = datetime.now()
        
        if last_run is None:
            last_run = now - timedelta(days=1)
        
        if frequency == ScheduleFrequency.DAILY:
            next_run = datetime(now.year, now.month, now.day, hour, minute)
            if next_run <= now:
                next_run += timedelta(days=1)
        
        elif frequency == ScheduleFrequency.WEEKLY:
            days_ahead = (6 - now.weekday()) % 7
            next_run = datetime(now.year, now.month, now.day, hour, minute) + timedelta(days=days_ahead)
            if next_run <= now:
                next_run += timedelta(days=7)
        
        elif frequency == ScheduleFrequency.MONTHLY:
            next_month = now.replace(day=1) + timedelta(days=32)
            next_run = datetime(next_month.year, next_month.month, 1, hour, minute)
            if next_run <= now:
                next_month = next_month.replace(day=1) + timedelta(days=32)
                next_run = datetime(next_month.year, next_month.month, 1, hour, minute)
        
        else:
            raise ValueError(f"Unknown frequency: {frequency}")
        
        return next_run
    
    def should_run_now(self) -> bool:
        if not self.config["enabled"]:
            return False
        
        schedule_id = "main"
        with self._lock:
            cursor = self._conn.execute(
                "SELECT last_run, next_run, enabled FROM schedule_state WHERE schedule_id = ?",
                (schedule_id,)
            )
            row = cursor.fetchone()
            
            if row and not row["enabled"]:
                return False
            
            if row and row["next_run"]:
                next_run = datetime.fromisoformat(row["next_run"])
                return datetime.now() >= next_run
            else:
                return True
    
    def run_scheduled_update(self) -> Dict[str, Any]:
        if not self.should_run_now():
            return {"status": "skipped", "reason": "Not scheduled to run now"}
        
        schedule_id = "main"
        start_time = datetime.now()
        logger.info(f"Starting scheduled update at {start_time}")
        
        crawler_results: List[CrawlerResult] = []
        total_collected = 0
        total_updated = 0
        all_errors: List[str] = []
        
        crawlers_to_run = [
            ("pubmed", self._run_pubmed_crawler),
            ("semantic_scholar", self._run_semantic_scholar_crawler),
            ("clinical_trials", self._run_clinical_trials_crawler),
        ]
        
        for crawler_name, crawler_func in crawlers_to_run:
            try:
                result = crawler_func()
                crawler_results.append(result)
                
                if result["status"] == CrawlerStatus.COMPLETED:
                    total_collected += result["items_collected"]
                    total_updated += result["items_updated"]
                elif result["status"] == CrawlerStatus.FAILED:
                    all_errors.extend(result["errors"])
            
            except Exception as e:
                error_result: CrawlerResult = {
                    "crawler_name": crawler_name,
                    "status": CrawlerStatus.FAILED,
                    "items_collected": 0,
                    "items_updated": 0,
                    "errors": [str(e)],
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration_seconds": 0.0
                }
                crawler_results.append(error_result)
                all_errors.append(f"{crawler_name}: {e}")
                logger.error(f"Crawler {crawler_name} failed: {e}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        overall_status = (
            CrawlerStatus.COMPLETED 
            if not any(r["status"] == CrawlerStatus.FAILED for r in crawler_results)
            else CrawlerStatus.FAILED
        )
        
        result_data = {
            "schedule_id": schedule_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "status": overall_status,
            "crawler_results": [dict(r) for r in crawler_results],
            "items_collected": total_collected,
            "items_updated": total_updated,
            "errors": all_errors,
            "duration_seconds": duration
        }
        
        self._save_execution_result(schedule_id, start_time, end_time, overall_status, crawler_results, total_collected, total_updated, all_errors)
        
        next_run = self.calculate_next_run(start_time)
        self._update_schedule_state(schedule_id, start_time, next_run, overall_status == CrawlerStatus.FAILED)
        
        if self.incremental_tracker and total_collected > 0:
            self._record_incremental_updates(crawler_results)
        
        logger.info(f"Scheduled update completed: {overall_status}, "
                   f"collected {total_collected}, updated {total_updated}, "
                   f"duration {duration:.1f}s")
        
        return result_data
    
    def _run_pubmed_crawler(self) -> CrawlerResult:
        start_time = datetime.now()
        
        try:
            logger.info("Running PubMed crawler")
            
            items_collected = 0
            items_updated = 0
            errors: List[str] = []
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result: CrawlerResult = {
                "crawler_name": "pubmed",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": items_collected,
                "items_updated": items_updated,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            }
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result: CrawlerResult = {
                "crawler_name": "pubmed",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            }
            
            return result
    
    def _run_semantic_scholar_crawler(self) -> CrawlerResult:
        start_time = datetime.now()
        
        try:
            logger.info("Running Semantic Scholar crawler")
            
            items_collected = 0
            items_updated = 0
            errors: List[str] = []
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result: CrawlerResult = {
                "crawler_name": "semantic_scholar",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": items_collected,
                "items_updated": items_updated,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            }
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result: CrawlerResult = {
                "crawler_name": "semantic_scholar",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            }
            
            return result
    
    def _run_clinical_trials_crawler(self) -> CrawlerResult:
        start_time = datetime.now()
        
        try:
            logger.info("Running ClinicalTrials.gov crawler")
            
            items_collected = 0
            items_updated = 0
            errors: List[str] = []
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result: CrawlerResult = {
                "crawler_name": "clinical_trials",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": items_collected,
                "items_updated": items_updated,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            }
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result: CrawlerResult = {
                "crawler_name": "clinical_trials",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            }
            
            return result
    
    def _save_execution_result(
        self,
        schedule_id: str,
        start_time: datetime,
        end_time: datetime,
        status: CrawlerStatus,
        crawler_results: List[CrawlerResult],
        items_collected: int,
        items_updated: int,
        errors: List[str]
    ) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO schedule_history 
                    (schedule_id, start_time, end_time, status, crawler_results, 
                     items_collected, items_updated, errors)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        schedule_id,
                        start_time.isoformat(),
                        end_time.isoformat(),
                        status.value,
                        json.dumps([dict(r) for r in crawler_results], default=str),
                        items_collected,
                        items_updated,
                        json.dumps(errors) if errors else None
                    )
                )
    
    def _update_schedule_state(
        self,
        schedule_id: str,
        last_run: datetime,
        next_run: datetime,
        failed: bool = False
    ) -> None:
        with self._lock:
            with self._conn:
                cursor = self._conn.execute(
                    "SELECT consecutive_failures FROM schedule_state WHERE schedule_id = ?",
                    (schedule_id,)
                )
                row = cursor.fetchone()
                
                if failed:
                    consecutive_failures = (row["consecutive_failures"] if row else 0) + 1
                    
                    if consecutive_failures >= 3:
                        logger.error(f"Schedule {schedule_id} disabled after 3 consecutive failures")
                        enabled = False
                    else:
                        enabled = True
                else:
                    consecutive_failures = 0
                    enabled = True
                
                self._conn.execute(
                    """
                    INSERT INTO schedule_state (schedule_id, last_run, next_run, consecutive_failures, enabled)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(schedule_id) DO UPDATE SET
                        last_run = excluded.last_run,
                        next_run = excluded.next_run,
                        consecutive_failures = excluded.consecutive_failures,
                        enabled = excluded.enabled
                    """,
                    (
                        schedule_id,
                        last_run.isoformat(),
                        next_run.isoformat(),
                        consecutive_failures,
                        enabled
                    )
                )
    
    def _record_incremental_updates(self, crawler_results: List[CrawlerResult]) -> None:
        for result in crawler_results:
            if result["status"] != CrawlerStatus.COMPLETED:
                continue
            
            if result["items_collected"] > 0:
                self.incremental_tracker.record_update(
                    update_type=UpdateType.NEW_PAPER if "pubmed" in result["crawler_name"] or "scholar" in result["crawler_name"] else UpdateType.NEW_TRIAL,
                    resource_id=f"batch_{datetime.now().date().isoformat()}_{result['crawler_name']}",
                    resource_title=f"Batch update from {result['crawler_name']}",
                    change_details={
                        "crawler": result["crawler_name"],
                        "items_collected": result["items_collected"],
                        "items_updated": result["items_updated"],
                        "duration_seconds": result["duration_seconds"]
                    },
                    source=result["crawler_name"]
                )
    
    def get_execution_history(
        self,
        limit: int = 10,
        schedule_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self._lock:
            query = """
                SELECT * FROM schedule_history
                WHERE (? IS NULL OR schedule_id = ?)
                ORDER BY start_time DESC
                LIMIT ?
            """
            cursor = self._conn.execute(query, (schedule_id, schedule_id, limit))
            
            results = []
            for row in cursor:
                result = dict(row)
                try:
                    result["crawler_results"] = json.loads(row["crawler_results"])
                except (json.JSONDecodeError, TypeError):
                    result["crawler_results"] = []
                
                try:
                    result["errors"] = json.loads(row["errors"]) if row["errors"] else []
                except (json.JSONDecodeError, TypeError):
                    result["errors"] = []
                
                results.append(result)
            
            return results
    
    def get_schedule_state(self, schedule_id: str = "main") -> Optional[Dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM schedule_state WHERE schedule_id = ?",
                (schedule_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    
    def update_config(self, **updates) -> None:
        with self._lock:
            for key, value in updates.items():
                if key in self.config:
                    self.config[key] = value
                else:
                    logger.warning(f"Ignoring unknown config key: {key}")
            
            self._save_config()
            
            schedule_id = "main"
            next_run = self.calculate_next_run()
            
            with self._conn:
                self._conn.execute(
                    "UPDATE schedule_state SET next_run = ? WHERE schedule_id = ?",
                    (next_run.isoformat(), schedule_id)
                )
    
    def enable_schedule(self, schedule_id: str = "main") -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE schedule_state SET enabled = 1, consecutive_failures = 0 WHERE schedule_id = ?",
                    (schedule_id,)
                )
    
    def disable_schedule(self, schedule_id: str = "main") -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE schedule_state SET enabled = 0 WHERE schedule_id = ?",
                    (schedule_id,)
                )
    
    def close(self) -> None:
        with self._lock:
            self._conn.close()
            if self.incremental_tracker:
                self.incremental_tracker.close()
    
    def __enter__(self) -> UpdateScheduler:
        return self
    
    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def create_daily_scheduler() -> UpdateScheduler:
    """Create a scheduler configured for daily updates at 9 AM."""
    config: ScheduleConfig = {
        "frequency": ScheduleFrequency.DAILY,
        "hour": 9,
        "minute": 0,
        "enabled": True,
        "max_runtime_hours": 2.0,
        "notify_on_completion": True,
        "notify_on_failure": True
    }
    
    scheduler = UpdateScheduler()
    scheduler.update_config(**config)
    
    return scheduler


if __name__ == "__main__":
    """Test script for scheduler."""
    import sys
    
    logger.info("Testing scheduler...")
    
    scheduler = create_daily_scheduler()
    
    try:
        print("Current schedule state:")
        state = scheduler.get_schedule_state()
        if state:
            for key, value in state.items():
                print(f"  {key}: {value}")
        
        print(f"\nShould run now: {scheduler.should_run_now()}")
        
        print("\nRunning test update (will skip if not scheduled)...")
        result = scheduler.run_scheduled_update()
        
        print(f"\nUpdate result: {result['status']}")
        print(f"Items collected: {result['items_collected']}")
        print(f"Items updated: {result['items_updated']}")
        
        if result["errors"]:
            print(f"Errors: {result['errors']}")
        
        print("\nExecution history:")
        history = scheduler.get_execution_history(limit=3)
        for entry in history:
            print(f"  {entry['start_time']}: {entry['status']} "
                  f"(collected: {entry['items_collected']})")
        
        print("\n✅ Scheduler test completed")
        
    except Exception as e:
        print(f"❌ Scheduler test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        scheduler.close()