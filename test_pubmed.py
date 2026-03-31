#!/usr/bin/env python3
"""Very small test for PubMed crawling - 10 PMIDs max."""

import sys
import time
from src.crawlers.pubmed_crawler import PubMedCrawler
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

print("Testing PubMed crawling with max_results=10...")
print("This should complete quickly...")

start_time = time.time()
cache = Cache("test_cache.sqlite")
crawler = PubMedCrawler(
    cache=cache,
    requests_per_second=3.0 / 60.0,
    max_results=10,
)

count = 0
try:
    for paper in crawler.search_papers():
        count += 1
        print(f"\n✅ Paper {count}:")
        print(f"   Title: {paper.title}")
        print(f"   PMID: {paper.pmid}")
        print(f"   DOI: {paper.doi}")
        print(f"   Authors: {', '.join(paper.authors[:3])}" + ("..." if len(paper.authors) > 3 else ""))
        if paper.abstract:
            print(f"   Abstract: {paper.abstract[:200]}...")
    
    elapsed = time.time() - start_time
    print(f"\n🏁 Completed! Got {count} papers in {elapsed:.1f} seconds")
    
except Exception as e:
    elapsed = time.time() - start_time
    print(f"\n❌ Error after {elapsed:.1f} seconds: {e}")
    import traceback
    traceback.print_exc()
finally:
    cache.close()
