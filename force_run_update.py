#!/usr/bin/env python3
"""Force run full daily update now."""

from src.scheduler.update_scheduler import create_daily_scheduler, CrawlerStatus
from src.config import settings
from datetime import datetime

print("Force running FULL daily update now...")
print(f"WeChat notification: {'Enabled' if settings.WECHAT_NOTIFICATION_ENABLED else 'Disabled'}")

with create_daily_scheduler() as scheduler:
    # Override the should_run_now check by directly executing
    start_time = datetime.now()
    print(f"\nStarting at: {start_time}")
    
    # Run all crawlers manually
    crawler_results = []
    total_collected = 0
    total_updated = 0
    all_errors = []
    
    print("\n1. Running PubMed crawler...")
    result = scheduler._run_pubmed_crawler()
    crawler_results.append(result)
    total_collected += result["items_collected"]
    total_updated += result["items_updated"]
    if result["status"] == CrawlerStatus.FAILED:
        all_errors.extend(result["errors"])
    print(f"   Done: {result['status']}, collected={result['items_collected']}, updated={result['items_updated']}")
    
    print("\n2. Running Semantic Scholar crawler...")
    result = scheduler._run_semantic_scholar_crawler()
    crawler_results.append(result)
    total_collected += result["items_collected"]
    total_updated += result["items_updated"]
    if result["status"] == CrawlerStatus.FAILED:
        all_errors.extend(result["errors"])
    print(f"   Done: {result['status']}, collected={result['items_collected']}, updated={result['items_updated']}")
    
    print("\n3. Running ClinicalTrials.gov crawler...")
    result = scheduler._run_clinical_trials_crawler()
    crawler_results.append(result)
    total_collected += result["items_collected"]
    total_updated += result["items_updated"]
    if result["status"] == CrawlerStatus.FAILED:
        all_errors.extend(result["errors"])
    print(f"   Done: {result['status']}, collected={result['items_collected']}, updated={result['items_updated']}")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    overall_status = (
        CrawlerStatus.COMPLETED 
        if not any(r["status"] == CrawlerStatus.FAILED for r in crawler_results)
        else CrawlerStatus.FAILED
    )
    
    print(f"\nAll crawlers completed.")
    print(f"Total duration: {duration:.1f}s")
    print(f"Overall status: {overall_status}")
    print(f"Total collected: {total_collected}")
    print(f"Total updated: {total_updated}")
    
    if all_errors:
        print(f"\nErrors: {all_errors}")
    
    # Record incremental updates
    if scheduler.incremental_tracker and total_collected > 0:
        scheduler._record_incremental_updates(crawler_results)
    
    # Save execution history
    scheduler._save_execution_result(
        "main",
        start_time,
        end_time,
        overall_status,
        crawler_results,
        total_collected,
        total_updated,
        all_errors
    )
    
    # Update schedule state for next run
    next_run = scheduler.calculate_next_run(start_time)
    scheduler._update_schedule_state("main", start_time, next_run, overall_status == CrawlerStatus.FAILED)
    
    # Send notification if enabled
    if settings.WECHAT_NOTIFICATION_ENABLED and scheduler.config.get("notify_on_completion", True):
        print(f"\nSending notification to WeChat...")
        try:
            if scheduler.incremental_tracker:
                from datetime import datetime
                today_iso = datetime.now().date().isoformat()
                summary = scheduler.incremental_tracker.get_daily_summary(today_iso)
                
                # Add totals
                from src.utils.incremental_tracker import UpdateType
                summary_dict = dict(summary)
                summary_dict["total_papers"] = scheduler.incremental_tracker.count_total_by_type(UpdateType.NEW_PAPER)
                summary_dict["total_trials"] = scheduler.incremental_tracker.count_total_by_type(UpdateType.NEW_TRIAL)
                summary_dict["new_papers_with_summary"] = 0
                
                from src.notifications.wechat_notifier import WeChatNotifier
                notifier = WeChatNotifier(
                    channel="openclaw-weixin",
                    target="o9cq80xDxxnZ9B-8BCXQkbOXnPag@im.wechat",
                    openclaw_path="openclaw"
                )
                success = notifier.send_daily_summary(summary_dict)
                if success:
                    print("✅ Notification sent to WeChat successfully")
                else:
                    print("⚠️ Failed to send notification to WeChat")
        except Exception as e:
            print(f"❌ Error sending notification: {str(e)}")
            import traceback
            traceback.print_exc()
