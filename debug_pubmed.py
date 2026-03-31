#!/usr/bin/env python3
"""Debug PubMed connection."""

import sys
from src.crawlers.pubmed_crawler import PubMedCrawler
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

print("Testing PubMed connection...")

cache = Cache("debug_cache.sqlite")
crawler = PubMedCrawler(
    cache=cache,
    requests_per_second=3.0 / 60.0,
    max_results=10
)

print("Starting search...")
try:
    count = 0
    for paper in crawler.search_papers():
        count += 1
        print(f"  Paper {count}: {paper.title[:80]}...")
        print(f"    PMID: {paper.pmid}, DOI: {paper.doi}")
    
    print(f"\nDone! Total: {count} papers")
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
finally:
    cache.close()
