#!/usr/bin/env python3
"""Fast initial crawl - only fetch IDs, no detail requests initially."""

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
    """Run fast initial crawl."""
    print("🚀 Starting FAST initial crawl (only search, no detail requests)...")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize shared components
    cache = Cache("crawl_fast_cache.sqlite")
    
    total_collected = 0
    
    # 1. PubMed crawl - only get PMID list
    print("\n📚 Step 1: PubMed search for vitiligo...")
    pubmed = PubMedCrawler(
        cache=cache,
        requests_per_second=3.0 / 60.0,
        max_results=100,
    )
    
    try:
        # Manually do pagination to just get PMIDs
        pmids = pubmed._search_pmids_with_pagination(pubmed.DEFAULT_QUERY)
        print(f"   ✅ PubMed: found {len(pmids)} PMIDs")
        total_collected += len(pmids)
    except Exception as e:
        print(f"   ❌ PubMed search failed: {e}")
        import traceback
        traceback.print_exc()
        pmids = []
    
    # 2. Semantic Scholar search
    print("\n🔍 Step 2: Semantic Scholar search for vitiligo...")
    scholar = SemanticScholarCrawler(
        cache=cache,
        rate_limiter=RateLimiter(3.0 / 60.0),
        max_results=50,
    )
    
    try:
        scholar_papers = list(scholar.search("vitiligo"))
        print(f"   ✅ Semantic Scholar: collected {len(scholar_papers)} papers")
        total_collected += len(scholar_papers)
    except Exception as e:
        print(f"   ❌ Semantic Scholar search failed: {e}")
        import traceback
        traceback.print_exc()
        scholar_papers = []
    
    # 3. ClinicalTrials.gov crawl
    print("\n💊 Step 3: ClinicalTrials.gov search...")
    trials_crawler = ClinicalTrialsCrawler(
        cache=cache,
        rate_limiter=RateLimiter(3.0 / 60.0),
    )
    
    try:
        trials = list(trials_crawler.search_vitiligo_trials())
        print(f"   ✅ ClinicalTrials.gov: collected {len(trials)} trials")
        total_collected += len(trials)
    except Exception as e:
        print(f"   ❌ ClinicalTrials.gov search failed: {e}")
        import traceback
        traceback.print_exc()
        trials = []
    
    # Summary
    print(f"\n📊 Fast search completed!")
    print(f"   Total results found: {total_collected}")
    print(f"   - PubMed: {len(pmids)} PMIDs")
    print(f"   - Semantic Scholar: {len(scholar_papers)} papers")
    print(f"   - Clinical Trials: {len(trials)} trials")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    cache.close()
    
    print(f"\n⚠️  Note: Only search completed. Full paper details will be fetched")
    print(f"  gradually by the daily scheduler to respect rate limits.")
    
    return total_collected


if __name__ == "__main__":
    main()
