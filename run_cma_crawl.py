#!/usr/bin/env python3
"""
Run Chinese Medical Association (中华医学会) crawler for vitiligo articles.

Browsing the "科普图文" section which contains more health topics.
"""

import sys
import json
import re
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import requests
from bs4 import BeautifulSoup
from src.models.paper import Paper, PaperSource
from typing import Optional, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

# We'll browse the "科普图文" section (popular science articles)
BASE_COLUMN_URL = "https://www.cma.org.cn/col/col4584/index.html"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def crawl_article(url: str, title: str) -> Optional[Paper]:
    """Crawl a single article from cma.org.cn."""
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"      Status {response.status_code}, skipping")
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find content on cma.org.cn
        content = None
        content_selectors = [".art-con", "#zoom-content", "#content", ".content"]
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem and len(elem.get_text(strip=True)) > 100:
                content = elem
                break
        
        if not content:
            print(f"      No content found, skipping")
            return None
        
        # Extract and clean text
        text = content.get_text("\n", strip=True)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 20]
        abstract = "\n\n".join(paragraphs) if paragraphs else text
        
        if len(abstract) > 2000:
            abstract = abstract[:1997] + "..."
        
        # Extract date from URL
        pub_date = None
        date_match = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/", url)
        if date_match:
            year = date_match.group(1)
            month = date_match.group(2).zfill(2)
            day = date_match.group(3).zfill(2)
            pub_date = f"{year}-{month}-{day}"
        
        paper = Paper(
            title=title,
            abstract=abstract,
            authors=[],
            journal="中华医学会",
            pub_date=pub_date,
            source=PaperSource.OTHER,
            url=url,
            mesh_terms=["白癜风"],
            keywords=["白癜风"],
        )
        
        return paper
        
    except Exception as e:
        print(f"      Error: {str(e)}")
        return None


def find_vitiligo_from_column(page_num: int) -> List[Paper]:
    """Crawl a page of the column and collect articles about vitiligo."""
    url = f"{BASE_COLUMN_URL}?page={page_num}"
    print(f"   Checking page {page_num}: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"   Failed to load page, status {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find all article links
        articles: List[Paper] = []
        links = soup.find_all("a", href=True)
        
        found = 0
        for link in links:
            title = link.get_text(strip=True)
            if not title or "详细" in title or "更多" in title or len(title) < 4:
                continue
            
            if "白癜风" not in title:
                continue
            
            found += 1
            href = link["href"]
            if not href.startswith("http"):
                if href.startswith("/"):
                    href = "https://www.cma.org.cn" + href
                else:
                    href = "https://www.cma.org.cn/" + href
            
            print(f"   Found: {title}")
            paper = crawl_article(href, title)
            if paper:
                articles.append(paper)
                print(f"   ✅ Collected successfully")
        
        print(f"   Found {found} articles with '白癜风' in title, collected {len(articles)}")
        return articles
        
    except Exception as e:
            print(f"   Error: {str(e)}")
            return []


def main():
    print("🌿 Starting Chinese Medical Association (中华医学会) vitiligo crawler...")
    print("🔍 Browsing '科普图文' (Popular Science Articles) section for vitiligo articles...")
    
    all_papers: List[Paper] = []
    start_time = datetime.now()
    
    # Check first 15 pages
    max_pages = 15
    empty_pages = 0
    
    for page in range(1, max_pages + 1):
        papers = find_vitiligo_from_column(page)
        if papers:
            all_papers.extend(papers)
            empty_pages = 0
        else:
            empty_pages += 1
            if empty_pages >= 3:
                print(f"\n{empty_pages} consecutive empty pages, stopping")
                break
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n✅ Crawl completed in {duration:.1f} seconds.")
    print(f"📊 Total collected: {len(all_papers)} articles about vitiligo from中华医学会")
    
    # Save to file
    output_dir = project_root / "data/raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"cma_vitiligo_full_{timestamp}.json"
    
    papers_data = [paper.model_dump() for paper in all_papers]
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(papers_data, f, indent=2, default=str)
    
    print(f"💾 Saved to: {output_path}")
    
    # Print results
    if all_papers:
        print("\n📝 已成功收集的中华医学会白癜风科普文章:\n")
        for i, paper in enumerate(all_papers):
            print(f"{i+1}. **{paper.title}**")
            print(f"   来源: {paper.journal}")
            print(f"   发布日期: {paper.pub_date or '未知'}")
            if paper.abstract:
                preview = paper.abstract[:250] + ("..." if len(paper.abstract) > 250 else "")
                print(f"   内容预览:\n{preview}")
            print(f"   原文链接: {paper.url}")
            print()
    
    # Also save as incremental for today
    if all_papers:
        today = datetime.now().date().isoformat()
        inc_path = output_dir / f"cma_incremental_{today}.json"
        with open(inc_path, 'w', encoding='utf-8') as f:
            json.dump(papers_data, f, indent=2, default=str)
        print(f"📈 Saved incremental file for today: {inc_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
