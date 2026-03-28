"""Command-line interface for SubSkin vitiligo data collection.

This module provides a CLI for running crawlers, processing data,
and managing scheduled updates.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.config import settings
from src.crawlers.pubmed_crawler import PubMedCrawler
from src.crawlers.semantic_scholar_crawler import SemanticScholarCrawler
from src.crawlers.clinical_trials_crawler import ClinicalTrialsCrawler
from src.processors.deduplicator import Deduplicator
from src.processors.translator import Translator
from src.processors.summarizer import Summarizer
from src.exporters.json_exporter import JSONExporter
from src.exporters.markdown_exporter import MarkdownExporter
from src.scheduler.update_scheduler import UpdateScheduler, create_daily_scheduler
from src.utils.logger import get_logger

logger = get_logger(__name__)


def crawl_pubmed(args):
    """Run PubMed crawler."""
    logger.info("Starting PubMed crawler...")

    crawler = PubMedCrawler()
    papers = crawler.search(args.query, limit=args.limit)

    logger.info(f"Found {len(papers)} papers")

    if papers:
        exporter = JSONExporter(export_dir=Path(args.output).parent)
        output_path = exporter.export_papers(papers, filename=Path(args.output).name)
        logger.info(f"Saved results to {output_path}")
        print(f"✓ Saved {len(papers)} papers to {output_path}")
    else:
        logger.warning("No papers found")
        print("⚠ No papers found")

    return 0


def crawl_scholar(args):
    """Run Semantic Scholar crawler."""
    logger.info("Starting Semantic Scholar crawler...")

    crawler = SemanticScholarCrawler()
    papers = crawler.search(args.query, limit=args.limit)

    logger.info(f"Found {len(papers)} papers")

    if papers:
        exporter = JSONExporter(export_dir=Path(args.output).parent)
        output_path = exporter.export_papers(papers, filename=Path(args.output).name)
        logger.info(f"Saved results to {output_path}")
        print(f"✓ Saved {len(papers)} papers to {output_path}")
    else:
        logger.warning("No papers found")
        print("⚠ No papers found")

    return 0


def crawl_trials(args):
    """Run ClinicalTrials.gov crawler."""
    logger.info("Starting ClinicalTrials.gov crawler...")

    crawler = ClinicalTrialsCrawler()
    trials = crawler.search(args.condition, limit=args.limit)

    logger.info(f"Found {len(trials)} trials")

    if trials:
        exporter = JSONExporter(export_dir=Path(args.output).parent)
        # TODO: Add trial export to JSON exporter
        output_path = Path(args.output)
        import json

        with open(output_path, "w") as f:
            json.dump([t.model_dump() for t in trials], f, indent=2, default=str)
        logger.info(f"Saved results to {output_path}")
        print(f"✓ Saved {len(trials)} trials to {output_path}")
    else:
        logger.warning("No trials found")
        print("⚠ No trials found")

    return 0


def process(args):
    """Process raw data with translation and summarization."""
    logger.info(f"Processing data from {args.input} to {args.output}...")

    # TODO: Implement full processing pipeline
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    print("⚠ Processing pipeline not fully implemented yet")
    print(f"  Input: {input_path}")
    print(f"  Output: {output_path}")

    return 0


def run_update(args):
    """Run scheduled update."""
    logger.info("Running scheduled update...")

    scheduler = create_daily_scheduler()

    try:
        result = scheduler.run_scheduled_update()
        print(f"\nUpdate result: {result['status']}")
        print(f"Items collected: {result['items_collected']}")
        print(f"Items updated: {result['items_updated']}")

        if result["errors"]:
            print(f"\nErrors:")
            for error in result["errors"]:
                print(f"  - {error}")

        scheduler.close()
        return 0 if result["status"] == "completed" else 1

    except Exception as e:
        logger.error(f"Update failed: {e}", exc_info=True)
        print(f"❌ Update failed: {e}")
        scheduler.close()
        return 1


def check_status(args):
    """Check current scheduler status."""
    scheduler = create_daily_scheduler()

    try:
        state = scheduler.get_schedule_state()
        if state:
            print("📊 Current schedule state:")
            for key, value in state.items():
                print(f"  {key}: {value}")
        else:
            print("No schedule state found")

        history = scheduler.get_execution_history(limit=args.history)
        if history:
            print(f"\nLast {len(history)} executions:")
            for entry in history:
                print(
                    f"  {entry['start_time'][:10]} - {entry['status']} - {entry['items_collected']} items"
                )

        scheduler.close()
        return 0

    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        print(f"❌ Status check failed: {e}")
        scheduler.close()
        return 1


def export_markdown(args):
    """Export papers to Markdown format."""
    import json

    input_path = Path(args.input)
    output_path = Path(args.output)

    with open(input_path, "r") as f:
        data = json.load(f)

    from src.models.paper import Paper

    # Parse papers from JSON
    papers: List[Paper] = []
    if isinstance(data, list):
        for item in data:
            papers.append(Paper(**item))
    elif "papers" in data:
        for item in data["papers"]:
            papers.append(Paper(**item))

    if not papers:
        print("⚠ No papers found in input file")
        return 1

    exporter = MarkdownExporter(export_dir=output_path)

    if args.collection:
        # Export as deduplicated collection
        output_dir = exporter.export_deduplicated_papers(
            papers, collection_name=args.collection
        )
        print(f"✓ Exported {len(papers)} papers to collection: {output_dir}")
    else:
        # Export individual papers
        output_paths = exporter.export_papers(papers)
        print(f"✓ Exported {len(output_paths)} papers to {output_path}")

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SubSkin - Vitiligo knowledge base data collection tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli crawl-pubmed --query "vitiligo" --output data/raw/pubmed.json --limit 100
  python -m src.cli crawl-scholar --query "vitiligo treatment" --output data/raw/scholar.json
  python -m src.cli crawl-trials --condition "vitiligo" --output data/raw/trials.json
  python -m src.cli process --input data/raw/ --output data/processed/
  python -m src.cli update
  python -m src.cli status
  python -m src.cli export-markdown --input data/raw/papers.json --output data/exports/
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True

    # crawl-pubmed command
    parser_crawl_pubmed = subparsers.add_parser(
        "crawl-pubmed", help="Crawl papers from PubMed"
    )
    parser_crawl_pubmed.add_argument(
        "--query", default="vitiligo", help="Search query (default: vitiligo)"
    )
    parser_crawl_pubmed.add_argument(
        "--output", required=True, help="Output JSON file path"
    )
    parser_crawl_pubmed.add_argument(
        "--limit", type=int, default=100, help="Maximum number of papers to fetch"
    )
    parser_crawl_pubmed.set_defaults(func=crawl_pubmed)

    # crawl-scholar command
    parser_crawl_scholar = subparsers.add_parser(
        "crawl-scholar", help="Crawl papers from Semantic Scholar"
    )
    parser_crawl_scholar.add_argument(
        "--query", default="vitiligo", help="Search query (default: vitiligo)"
    )
    parser_crawl_scholar.add_argument(
        "--output", required=True, help="Output JSON file path"
    )
    parser_crawl_scholar.add_argument(
        "--limit", type=int, default=100, help="Maximum number of papers to fetch"
    )
    parser_crawl_scholar.set_defaults(func=crawl_scholar)

    # crawl-trials command
    parser_crawl_trials = subparsers.add_parser(
        "crawl-trials", help="Crawl clinical trials from ClinicalTrials.gov"
    )
    parser_crawl_trials.add_argument(
        "--condition",
        default="vitiligo",
        help="Condition to search (default: vitiligo)",
    )
    parser_crawl_trials.add_argument(
        "--output", required=True, help="Output JSON file path"
    )
    parser_crawl_trials.add_argument(
        "--limit", type=int, default=50, help="Maximum number of trials to fetch"
    )
    parser_crawl_trials.set_defaults(func=crawl_trials)

    # process command
    parser_process = subparsers.add_parser(
        "process", help="Process raw data with translation and summarization"
    )
    parser_process.add_argument(
        "--input", required=True, help="Input directory with raw JSON files"
    )
    parser_process.add_argument(
        "--output", required=True, help="Output directory for processed data"
    )
    parser_process.set_defaults(func=process)

    # update command
    parser_update = subparsers.add_parser("update", help="Run scheduled update")
    parser_update.set_defaults(func=run_update)

    # status command
    parser_status = subparsers.add_parser("status", help="Check scheduler status")
    parser_status.add_argument(
        "--history", type=int, default=10, help="Number of history entries to show"
    )
    parser_status.set_defaults(func=check_status)

    # export-markdown command
    parser_export = subparsers.add_parser(
        "export-markdown", help="Export papers to Markdown format"
    )
    parser_export.add_argument(
        "--input", required=True, help="Input JSON file with papers"
    )
    parser_export.add_argument(
        "--output", required=True, help="Output directory for Markdown files"
    )
    parser_export.add_argument(
        "--collection",
        help="Export as named collection (creates subdirectory with index)",
    )
    parser_export.set_defaults(func=export_markdown)

    args = parser.parse_args()

    # Validate settings
    if not settings.validate():
        print("❌ Configuration error: Please check your .env file")
        print(f"   Required: {', '.join(settings.missing_keys())}")
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
