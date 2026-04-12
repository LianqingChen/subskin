#!/usr/bin/env python
"""Test PubMed crawler data collection"""

from src.crawlers.pubmed_crawler import PubMedCrawler

def test_crawler():
    print('=== 测试完整数据收集流程 ===')
    crawler = PubMedCrawler(requests_per_second=0.5, max_results=5)
    papers = crawler.search_papers()
    print(f'✓ 成功获取 {len(papers)} 篇文献')

    if papers:
        print(f'  第一篇文章: {papers[0].title[:60]}...')
        print(f'  来源: {papers[0].source}')
    print('')
    print('✓ 测试完成')
    print('')

if __name__ == '__main__':
    test_crawler()
