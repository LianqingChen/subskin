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

from src.config import settings
from src.exceptions import CrawlerError
from src.utils.cache import Cache
from src.utils.incremental_tracker import IncrementalTracker, UpdateType, DailySummary
from src.utils.logger import get_logger

# Project root for running scrapy
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Notification support
if settings.WECHAT_NOTIFICATION_ENABLED:
    from src.notifications.wechat_notifier import WeChatNotifier


# Use dedicated scheduler log file with 7-day rotation
logger = get_logger(
    __name__,
    log_file="logs/scheduler.log",
    rotate_days=7
)


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
        """Check if scheduler should run now based on configured schedule."""
        if not self.config["enabled"]:
            logger.debug(f"Schedule is disabled, skipping check")
            return False
        
        schedule_id = "main"
        with self._lock:
            cursor = self._conn.execute(
                "SELECT last_run, next_run, enabled FROM schedule_state WHERE schedule_id = ?",
                (schedule_id,)
            )
            row = cursor.fetchone()
            
            if row and not row["enabled"]:
                logger.debug(f"Schedule {schedule_id} is disabled in database")
                return False
            
            if row and row["next_run"]:
                next_run = datetime.fromisoformat(row["next_run"])
                now = datetime.now()
                should_run = now >= next_run
                logger.info(f"Time check: now={now}, next_run={next_run}, should_run={should_run}")
                return should_run
            else:
                logger.debug(f"No next_run found, scheduler should run")
                return True
    
    def run_scheduled_update(self) -> Dict[str, Any]:
        """Execute scheduled data collection update."""
        if not self.should_run_now():
            logger.info("Skipping scheduled update - not scheduled to run now")
            return {"status": "skipped", "reason": "Not scheduled to run now"}
        
        schedule_id = "main"
        start_time = datetime.now()
        
        # Visual separator for better log readability
        logger.info("=" * 60)
        logger.info(f"Starting scheduled update at {start_time}")
        
        crawler_results: List[CrawlerResult] = []
        total_collected = 0
        total_updated = 0
        all_errors: List[str] = []
        
        logger.debug(f"Initialized: crawler_results empty, total_collected=0, total_updated=0")
        
        # Visual separator for better log readability
        # Visual separator for better log readability
        logger.info("".join(["="] * 60))        
        # Run crawlers by information source category
        # Category mapping: pubmed/crossref/semantic_scholar -> academic papers
        # cma -> medical association, clinical_trials -> drug trials
        # foundation_news -> research orgs & media, omicsdi -> bioinformatics
        crawlers_to_run = [
            ("pubmed", self._run_pubmed_crawler),
            ("pubmed_fulltext", self._run_pubmed_fulltext),
            ("cma", self._run_cma_crawler),
            ("crossref", self._run_crossref_crawler),
            ("semantic_scholar", self._run_semantic_scholar_crawler),
            ("clinical_trials", self._run_clinical_trials_crawler),
            ("foundation_news", self._run_foundation_news_crawler),
            ("omicsdi", self._run_omicsdi_crawler),
            ("medical_content", self._run_medical_content_crawler),
        ]
        
        CRAWLER_TIMEOUT_SECONDS = 3600  # 60 minutes max per crawler (PubMed needs ~55min)

        for crawler_name, crawler_func in crawlers_to_run:
            result = None
            exc = None

            def _run():
                nonlocal result, exc
                try:
                    result = crawler_func()
                except Exception as e:
                    exc = e

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join(timeout=CRAWLER_TIMEOUT_SECONDS)

            if exc:
                logger.error("Crawler %s failed: %s", crawler_name, exc)
                result = {
                    "crawler_name": crawler_name,
                    "status": CrawlerStatus.FAILED,
                    "items_collected": 0,
                    "items_updated": 0,
                    "errors": [str(exc)],
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration_seconds": 0.0,
                }
            elif result is None:
                logger.error("Crawler %s timed out after %ds", crawler_name, CRAWLER_TIMEOUT_SECONDS)
                result = {
                    "crawler_name": crawler_name,
                    "status": CrawlerStatus.FAILED,
                    "items_collected": 0,
                    "items_updated": 0,
                    "errors": [f"Timed out after {CRAWLER_TIMEOUT_SECONDS}s"],
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration_seconds": float(CRAWLER_TIMEOUT_SECONDS),
                }

            crawler_results.append(result)
            if result["status"] == CrawlerStatus.COMPLETED:
                total_collected += result["items_collected"]
                total_updated += result["items_updated"]
            elif result["status"] == CrawlerStatus.FAILED:
                all_errors.extend(result["errors"])
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Update execution completed in {duration:.1f}s")
        
        # Determine overall status
        completed_count = sum(1 for r in crawler_results if r["status"] == CrawlerStatus.COMPLETED)
        failed_count = sum(1 for r in crawler_results if r["status"] == CrawlerStatus.FAILED)
        
        overall_status = (
            CrawlerStatus.COMPLETED 
            if not any(r["status"] == CrawlerStatus.FAILED for r in crawler_results)
            else CrawlerStatus.FAILED
        )
        
        logger.info(f"Overall status: {overall_status.value} (completed: {completed_count}, failed: {failed_count})")
        
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
        logger.info(f"Calculated next run time: {next_run}")
        
        self._update_schedule_state(schedule_id, start_time, next_run, overall_status == CrawlerStatus.FAILED)
        
        if self.incremental_tracker and total_collected > 0:
            self._record_incremental_updates(crawler_results)
        
        logger.info(f"Scheduled update completed: {overall_status}, "
                   f"collected {total_collected}, updated {total_updated}, "
                   f"duration {duration:.1f}s")

        if total_collected > 0:
            try:
                imported = self._import_crawled_data_to_rag()
                if imported > 0:
                    logger.info("Imported %d new documents into RAG knowledge base", imported)
            except Exception as e:
                logger.error("Failed to import data to RAG: %s", str(e))
        
        # Send notification if enabled
        if settings.WECHAT_NOTIFICATION_ENABLED and self.config.get("notify_on_completion", True):
            try:
                crawl_summary = {"date": datetime.now().date().isoformat(), "details": []}
                for cr in crawler_results:
                    crawl_summary["details"].append({
                        "source": cr["crawler_name"],
                        "change_details": {"items_collected": cr["items_collected"]},
                        "resource_title": "",
                    })

                notifier = WeChatNotifier(
                    channel="openclaw-weixin",
                    target="o9cq80xDxxnZ9B-8BCXQkbOXnPag@im.wechat",
                    openclaw_path="openclaw",
                )
                success = notifier.send_daily_summary(crawl_summary)
                if success:
                    logger.info("Daily briefing sent to WeChat successfully")
                else:
                    logger.warning("Failed to send daily briefing to WeChat")
            except Exception as e:
                logger.error("Error sending WeChat notification: %s", str(e))

        return result_data
    
    def _run_pubmed_crawler(self) -> CrawlerResult:
        """Execute PubMed crawler with detailed logging."""
        start_time = datetime.now()
        
        try:
            logger.info(f"{'='*60}")
            logger.info("Running PubMed crawler (metapub)")
            import json
            from src.crawlers.pubmed_crawler import PubMedCrawler
            from src.models.paper import Paper
            
            # Initialize crawler and search
            # Full crawl (default 10,000 papers) for initial collection
            crawler = PubMedCrawler()
            papers = crawler.search_papers()
            
            items_collected = len(papers)
            items_updated = 0
            errors: List[str] = []
            
            # Save raw data to json
            output_dir = PROJECT_ROOT / "data/raw"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"pubmed_incremental_{datetime.now().date().isoformat()}.json"
            
            # Save papers to JSON
            papers_data = [paper.model_dump() for paper in papers]
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(papers_data, f, indent=2, default=str)
            
            logger.info(f"Saved {items_collected} papers to {output_path}")
            
            # All are new on first run
            items_updated = items_collected
            
            status = CrawlerStatus.COMPLETED
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"PubMed crawler completed: {items_collected} items collected in {duration:.1f}s")
            
            result: CrawlerResult = {
                "crawler_name": "pubmed",
                "status": status,
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
    
    def _run_pubmed_fulltext(self) -> CrawlerResult:
        """Fetch PMC full text for newly crawled PubMed papers with PMCID."""
        start_time = datetime.now()
        
        try:
            logger.info("Running PubMed full-text fetcher")
            import json
            from src.crawlers.pubmed_fulltext import PubmedFulltextFetcher
            
            # Read today's PubMed data to find papers with PMCID
            today = datetime.now().date().isoformat()
            pubmed_file = PROJECT_ROOT / "data/raw" / f"pubmed_incremental_{today}.json"
            
            if not pubmed_file.exists():
                logger.info("No PubMed data file for today, skipping full-text fetch")
                return {
                    "crawler_name": "pubmed_fulltext",
                    "status": CrawlerStatus.SKIPPED,
                    "items_collected": 0,
                    "items_updated": 0,
                    "errors": [],
                    "start_time": start_time.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration_seconds": 0,
                }
            
            with open(pubmed_file) as f:
                papers = json.load(f)
            
            pmcids = [p["pmcid"] for p in papers if p.get("pmcid")]
            logger.info(f"Found {len(pmcids)} papers with PMCID out of {len(papers)}")
            
            if not pmcids:
                return {
                    "crawler_name": "pubmed_fulltext",
                    "status": CrawlerStatus.COMPLETED,
                    "items_collected": 0,
                    "items_updated": 0,
                    "errors": [],
                    "start_time": start_time.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                }
            
            fetcher = PubmedFulltextFetcher(data_dir=str(PROJECT_ROOT / "data/fulltext"))
            deduped = list(set(pmcids))
            results = fetcher.fetch_batch(deduped)
            
            success = sum(1 for v in results.values() if v is not None)
            failed = len(results) - success
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(
                f"Full-text fetch complete: {success}/{len(results)} papers "
                f"({success/len(results)*100:.1f}%) in {duration:.1f}s"
            )
            
            errors: list[str] = []
            if failed > 0:
                errors.append(f"{failed} papers had no full text available")
            
            return {
                "crawler_name": "pubmed_fulltext",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": success,
                "items_updated": success,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
            }
            
        except Exception as e:
            end_time = datetime.now()
            logger.warning(f"Full-text fetch failed: {e}", exc_info=True)
            return {
                "crawler_name": "pubmed_fulltext",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
    
    def _run_cma_crawler(self) -> CrawlerResult:
        start_time = datetime.now()
        
        try:
            logger.info("Running CMA (中华医学会) crawler - direct page crawl")
            import json, re
            import requests
            from bs4 import BeautifulSoup
            
            items_collected = 0
            errors: List[str] = []
            articles = []
            
            cma_pages = [
                "https://www.cma.org.cn/col/col12/index.html",
            ]
            
            for url in cma_pages:
                try:
                    resp = requests.get(url, timeout=15, headers={
                        "User-Agent": "Mozilla/5.0 (compatible; SubSkin/2.0)"
                    })
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for link in soup.select("a[href]"):
                        title = link.get_text(strip=True)
                        href = link.get("href", "")
                        if not title or len(title) < 6:
                            continue
                        if "白癜风" not in title and "皮肤" not in title:
                            continue
                        if href.startswith("/"):
                            href = "https://www.cma.org.cn" + href
                        articles.append({
                            "title": title[:300],
                            "url": href,
                            "source": "中华医学会",
                            "source_tier": "C",
                            "authority_weight": 0.8,
                        })
                except Exception as e:
                    errors.append(str(e))
            
            items_collected = len(articles)
            
            output_dir = PROJECT_ROOT / "data/raw"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"cma_incremental_{datetime.now().date().isoformat()}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(articles, f, indent=2, default=str)
            
            logger.info(f"Saved {items_collected} CMA articles to {output_path}")
            
            end_time = datetime.now()
            return {
                "crawler_name": "cma",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": items_collected,
                "items_updated": items_collected,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
            
        except Exception as e:
            end_time = datetime.now()
            return {
                "crawler_name": "cma",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
    
    def _run_semantic_scholar_crawler(self) -> CrawlerResult:
        start_time = datetime.now()
        
        try:
            logger.info("Running Semantic Scholar crawler")
            # Semantic Scholar crawler is implemented but not enabled in incremental updates
            # For now, skip and return 0 (handled by full crawl)
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
            logger.info("Running ClinicalTrials.gov crawler (API v2)")
            import json
            from src.crawlers.clinical_trials_crawler import ClinicalTrialsCrawler
            
            crawler = ClinicalTrialsCrawler(cache=Cache())
            trials = crawler.search_vitiligo_trials(max_results=100)
            
            items_collected = len(trials)
            errors: List[str] = []
            
            output_dir = PROJECT_ROOT / "data/raw"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"clinical_trials_{datetime.now().date().isoformat()}.json"
            
            trials_data = [t.model_dump() for t in trials]
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(trials_data, f, indent=2, default=str)
            
            logger.info(f"Saved {items_collected} trials to {output_path}")
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "crawler_name": "clinical_trials",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": items_collected,
                "items_updated": items_collected,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
            }
            
        except Exception as e:
            end_time = datetime.now()
            return {
                "crawler_name": "clinical_trials",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
    
    def _run_crossref_crawler(self) -> CrawlerResult:
        start_time = datetime.now()
        
        try:
            logger.info("Running CrossRef crawler")
            import json
            from src.crawlers.crossref_crawler import CrossRefCrawler
            
            crawler = CrossRefCrawler()
            papers = crawler.search(query="vitiligo", max_results=200)
            
            items_collected = len(papers)
            errors: List[str] = []
            
            output_dir = PROJECT_ROOT / "data/raw"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"crossref_incremental_{datetime.now().date().isoformat()}.json"
            
            papers_data = [paper.model_dump() for paper in papers]
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(papers_data, f, indent=2, default=str)
            
            logger.info(f"Saved {items_collected} papers to {output_path}")
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "crawler_name": "crossref",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": items_collected,
                "items_updated": items_collected,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
            }
            
        except Exception as e:
            end_time = datetime.now()
            return {
                "crawler_name": "crossref",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
    
    def _run_foundation_news_crawler(self) -> CrawlerResult:
        start_time = datetime.now()
        
        try:
            logger.info("Running Foundation News crawler")
            import json
            from src.crawlers.foundation_news_crawler import FoundationNewsCrawler
            
            crawler = FoundationNewsCrawler()
            articles = crawler.crawl_all()
            
            items_collected = len(articles)
            errors: List[str] = []
            
            output_dir = PROJECT_ROOT / "data/raw"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"foundation_news_{datetime.now().date().isoformat()}.json"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(articles, f, indent=2, default=str)
            
            logger.info(f"Saved {items_collected} news articles to {output_path}")
            
            end_time = datetime.now()
            
            return {
                "crawler_name": "foundation_news",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": items_collected,
                "items_updated": items_collected,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
            
        except Exception as e:
            end_time = datetime.now()
            return {
                "crawler_name": "foundation_news",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
    
    def _run_omicsdi_crawler(self) -> CrawlerResult:
        start_time = datetime.now()
        
        try:
            logger.info("Running OmicsDI crawler")
            import json
            from src.crawlers.omicsdi_crawler import OmicsDICrawler
            
            crawler = OmicsDICrawler()
            datasets = crawler.search_datasets(query="vitiligo", max_results=100)
            
            items_collected = len(datasets)
            errors: List[str] = []
            
            output_dir = PROJECT_ROOT / "data/raw"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"omicsdi_{datetime.now().date().isoformat()}.json"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(datasets, f, indent=2, default=str)
            
            logger.info(f"Saved {items_collected} datasets to {output_path}")
            
            end_time = datetime.now()
            
            return {
                "crawler_name": "omicsdi",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": items_collected,
                "items_updated": items_collected,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
            
        except Exception as e:
            end_time = datetime.now()
            return {
                "crawler_name": "omicsdi",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
    
    def _run_medical_content_crawler(self) -> CrawlerResult:
        start_time = datetime.now()
        
        try:
            logger.info("Running Medical Content crawler (MSD, DXY, Dove, Broad, Haodf, AVRF)")
            import json
            from src.crawlers.medical_content_crawler import MedicalContentCrawler
            
            crawler = MedicalContentCrawler()
            articles = crawler.crawl_all()
            
            items_collected = len(articles)
            errors: List[str] = []
            
            output_dir = PROJECT_ROOT / "data/raw"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"medical_content_{datetime.now().date().isoformat()}.json"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(articles, f, indent=2, default=str)
            
            logger.info(f"Saved {items_collected} articles to {output_path}")
            
            end_time = datetime.now()
            
            return {
                "crawler_name": "medical_content",
                "status": CrawlerStatus.COMPLETED,
                "items_collected": items_collected,
                "items_updated": items_collected,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
            
        except Exception as e:
            end_time = datetime.now()
            return {
                "crawler_name": "medical_content",
                "status": CrawlerStatus.FAILED,
                "items_collected": 0,
                "items_updated": 0,
                "errors": [str(e)],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
    
    def _import_crawled_data_to_rag(self) -> int:
        """Import today's crawled JSON files into the RAG knowledge base.

        Reads all incremental JSON files from data/raw/ for today's date,
        extracts title+abstract+source info, and adds them to the RAG
        document store with proper source tier and authority weighting.

        Returns:
            Number of documents imported.
        """
        import json as _json
        import os as _os

        today = datetime.now().date().isoformat()
        raw_dir = PROJECT_ROOT / "data/raw"
        if not raw_dir.exists():
            return 0

        tier_map = {
            "pubmed": ("A", 1.2),
            "pubmed_fulltext": ("A", 1.3),
            "crossref": ("A", 1.1),
            "scholar": ("A", 1.2),
            "clinical_trials": ("B", 1.0),
            "foundation_news": ("B", 1.0),
            "omicsdi": ("B", 1.0),
            "cma": ("C", 0.8),
            "medical_content": ("C", 0.8),
        }

        try:
            from web.backend.database.database import get_db
            from web.backend.database.models import Document
            from web.backend.services.rag import add_document

            db = next(get_db())
        except Exception:
            logger.warning("Cannot connect to RAG database for import")
            return 0

        # === 增量去重：预加载 DB 中已有的 source_url 和 title，避免重复 embedding ===
        # 注意：之前的实现仅用进程内 set 去重，跨执行完全失效，导致每天对几千条
        # 历史文献重新调用 text-embedding-v4，造成 API 费用浪费。这里改为读取 DB
        # 实际已入库的指纹，命中即跳过 embedding 调用。
        try:
            existing_urls = {
                row[0] for row in db.query(Document.source_url).filter(
                    Document.source_url.isnot(None),
                    Document.source_url != "",
                ).all()
            }
            existing_titles = {
                row[0] for row in db.query(Document.title).all()
            }
            logger.info(
                "RAG dedup baseline: %d existing URLs, %d existing titles",
                len(existing_urls), len(existing_titles)
            )
        except Exception as e:
            logger.warning("Failed to load existing doc fingerprints, falling back to in-memory dedup: %s", e)
            existing_urls = set()
            existing_titles = set()

        total_imported = 0
        total_skipped_existing = 0
        total_skipped_empty = 0
        seen_titles_this_run = set()

        for fname in _os.listdir(str(raw_dir)):
            if today not in fname or not fname.endswith(".json"):
                continue

            crawler_id = fname.split("_")[0]
            tier, weight = tier_map.get(crawler_id, ("C", 1.0))
            fpath = raw_dir / fname

            try:
                with open(fpath, "r") as f:
                    data = _json.load(f)
            except (_json.JSONDecodeError, IOError):
                continue

            if not isinstance(data, list):
                continue

            for item in data:
                if not isinstance(item, dict):
                    continue

                title = item.get("title", "")
                if not title:
                    total_skipped_empty += 1
                    continue

                # 三层去重：本次运行内 + DB 已有 title + DB 已有 url
                if title in seen_titles_this_run:
                    total_skipped_existing += 1
                    continue
                seen_titles_this_run.add(title)

                url = item.get("url", "")

                # 命中已有指纹 → 直接跳过，不调 embedding，不花钱
                if (url and url in existing_urls) or title in existing_titles:
                    total_skipped_existing += 1
                    continue

                abstract = item.get("abstract") or item.get("description") or item.get("content") or ""
                source = item.get("source_name") or item.get("source") or crawler_id
                pub_date = item.get("pub_date") or item.get("publicationDate") or ""

                content = f"标题: {title}\n\n摘要: {abstract}"
                if "authors" in item:
                    authors = item["authors"]
                    if isinstance(authors, list):
                        content += f"\n\n作者: {', '.join(authors[:5])}"
                if "journal" in item:
                    content += f"\n\n期刊: {item['journal']}"

                try:
                    add_document(
                        db=db,
                        title=title[:500],
                        content=content[:8000],
                        source=source,
                        source_url=url,
                        category="academic_paper",
                        source_tier=tier,
                        authority_weight=weight,
                        pub_date=pub_date,
                        compute_embedding=False,  # 改为手动触发向量化，不再自动 embedding
                    )
                    total_imported += 1
                    # 更新内存指纹，防止同一次运行内同 url/title 在不同 JSON 中重复
                    if url:
                        existing_urls.add(url)
                    existing_titles.add(title)
                except Exception as e:
                    logger.debug("Skipping duplicate or invalid doc: %s", str(e)[:80])
                    continue

        logger.info(
            "RAG import complete: %d new documents imported, %d skipped (already in DB), "
            "%d skipped (empty title), from %d crawler files",
            total_imported, total_skipped_existing, total_skipped_empty,
            sum(1 for fname in _os.listdir(str(raw_dir)) if today in fname and fname.endswith(".json"))
        )
        return total_imported
    
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
        """Update schedule state in database with detailed logging."""
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
                
                logger.info(f"Updating schedule state: last_run={last_run}, next_run={next_run}, "
                           f"consecutive_failures={consecutive_failures}, enabled={enabled}")
                
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
                
                logger.debug(f"Schedule state updated successfully for {schedule_id}")
    
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
    """Create a scheduler that loads its frequency/hour/minute from scheduler_config.json.

    Historical note: this function used to hard-code daily 02:00 and overwrite the
    on-disk config — which silently defeated any external schedule changes. Now it
    just instantiates UpdateScheduler (which already loads scheduler_config.json
    via __init__) and returns it as-is. The function name is kept for backwards
    compat with existing callers / systemd entry point.
    """
    scheduler = UpdateScheduler()
    logger.info(
        "Scheduler loaded from config: frequency=%s, hour=%02d:%02d, enabled=%s",
        scheduler.config["frequency"],
        scheduler.config["hour"],
        scheduler.config["minute"],
        scheduler.config["enabled"],
    )
    return scheduler


def run_forever() -> None:
    """Run scheduler forever, checking periodically if it's time to run."""
    import time
    
    scheduler = create_daily_scheduler()
    logger.info("Starting continuous scheduler run...")
    
    try:
        while True:
            # Check every 60 seconds if it's time to run
            if scheduler.should_run_now():
                logger.info("It's time to run scheduled update...")
                scheduler.run_scheduled_update()
            
            # Sleep for 1 minute before checking again
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    finally:
        scheduler.close()


if __name__ == "__main__":
    """Main entry point - run continuously for systemd."""
    import sys
    
    # Check if we're running as a service or just testing
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test mode - run once and exit
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
            
            print(f"\nUpdate result: {result.get('status', 'unknown')}")
            if 'items_collected' in result:
                print(f"Items collected: {result['items_collected']}")
                print(f"Items updated: {result['items_updated']}")
            
            if result.get("errors"):
                print(f"Errors: {result['errors']}")
            
            print("\nExecution history:")
            history = scheduler.get_execution_history(limit=3)
            for entry in history:
                print(f"  {entry['start_time']}: {entry['status']} "
                      f"(collected: {entry.get('items_collected', 'N/A')})")
            
            print("\n✅ Scheduler test completed")
            
        except Exception as e:
            print(f"❌ Scheduler test failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
        finally:
            scheduler.close()
    else:
        # Service mode - run forever
        run_forever()