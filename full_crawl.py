#!/usr/bin/env python3
"""Full initial crawl for all three data sources."""

import logging
from datetime import datetime
from src.crawlers.pubmed_crawler import PubMedCrawler
from src.crawlers.semantic_scholar_crawler import SemanticScholarCrawler
from src.crawlers.clinical_trials_crawler import ClinicalTrialsCrawler
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter
from src.utils.logger import get_logger

logger = get_logger(__name__)
logging.basicConfig(level=logging.INFO)


def main():
    """Run full initial crawl."""
    print("🚀 Starting full initial crawl for SubSkin...")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize shared components
    cache = Cache("crawl_cache.sqlite")
    
    total_collected = 0
    
    # 1. PubMed crawl
    print("\n📚 Step 1: PubMed crawl for vitiligo...")
    pubmed = PubMedCrawler(
        cache=cache,
        requests_per_second=3.0 / 60.0,  # 3 requests per minute (free tier without API key)
        max_results=100,  # Start with 100 for first crawl (faster for testing)
    )
    
    try:
        pubmed_papers = list(pubmed.search_papers())
        print(f"   ✅ PubMed: collected {len(pubmed_papers)} papers")
        total_collected += len(pubmed_papers)
    except Exception as e:
        print(f"   ❌ PubMed crawl failed: {e}")
        import traceback
        traceback.print_exc()
        pubmed_papers = []
    
    # 2. Semantic Scholar crawl
    print("\n🔍 Step 2: Semantic Scholar crawl for vitiligo...")
    scholar = SemanticScholarCrawler(
        cache=cache,
        rate_limiter=RateLimiter(3.0 / 60.0),
        max_results=50,  # Start with 50 for first crawl
    )
    
    try:
        scholar_papers = list(scholar.search("vitiligo"))
        print(f"   ✅ Semantic Scholar: collected {len(scholar_papers)} papers")
        total_collected += len(scholar_papers)
    except Exception as e:
        print(f"   ❌ Semantic Scholar crawl failed: {e}")
        import traceback
        traceback.print_exc()
        scholar_papers = []
    
    # 3. ClinicalTrials.gov crawl
    print("\n💊 Step 3: ClinicalTrials.gov crawl...")
    trials_crawler = ClinicalTrialsCrawler(
        cache=cache,
        rate_limiter=RateLimiter(3.0 / 60.0),
    )
    
    try:
        trials = list(trials_crawler.search_vitiligo_trials())
        print(f"   ✅ ClinicalTrials.gov: collected {len(trials)} trials")
        total_collected += len(trials)
    except Exception as e:
        print(f"   ❌ ClinicalTrials.gov crawl failed: {e}")
        import traceback
        traceback.print_exc()
        trials = []
    
    # Summary
    print(f"\n📊 Full crawl completed!")
    print(f"   Total items collected: {total_collected}")
    print(f"   - PubMed: {len(pubmed_papers)}")
    print(f"   - Semantic Scholar: {len(scholar_papers)}")
    print(f"   - Clinical Trials: {len(trials)}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    cache.close()
    
    return total_collected


if __name__ == "__main__":
    main()
