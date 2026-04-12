#!/usr/bin/env python
"""
导入 PubMed 收集的数据到 RAG 知识库
"""

import sys
import os
import json
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv

load_dotenv()

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.backend.database.database import get_db
from web.backend.services.rag import add_document
from sqlalchemy.orm import Session

# 数据目录
DATA_DIR = Path("../../data/raw")


def process_pubmed_json(file_path: str, db: Session):
    """处理 PubMed JSON 文件，导入每篇论文"""
    with open(file_path, "r", encoding="utf-8") as f:
        papers = json.load(f)

    count = 0
    for paper in papers:
        # 提取内容
        title = paper.get("title", "No title")
        abstract = paper.get("abstract", "")

        if not abstract:
            continue  # 跳过没有摘要的

        # 组合标题+摘要
        content = f"标题: {title}\n\n摘要: {abstract}"
        if "authors" in paper:
            content += f"\n\n作者: {', '.join(paper['authors'][:5])}"
        if "journal" in paper:
            content += f"\n\n期刊: {paper['journal']}"
        if "pub_date" in paper:
            content += f"\n\n发表时间: {paper['pub_date']}"

        source = "PubMed"
        source_url = (
            f"https://pubmed.ncbi.nlm.nih.gov/{paper.get('pmid', '')}/"
            if paper.get("pmid")
            else None
        )
        category = "academic_paper"

        try:
            add_document(
                db=db,
                title=title,
                content=content,
                source=source,
                source_url=source_url,
                category=category,
            )
            count += 1
            print(f"✓ 已导入: {title[:60]}...")
        except Exception as e:
            print(f"✗ 导入失败 {title[:60]}: {e}")
            continue

    return count


def main():
    db = next(get_db())

    # 查找所有 pubmed json 文件
    data_dir = Path("../../data/raw")
    json_files = list(data_dir.glob("pubmed*.json"))

    print(f"找到 {len(json_files)} 个数据文件")

    total = 0
    for json_file in json_files:
        print(f"\n开始处理 {json_file} ...")
        count = process_pubmed_json(json_file, db)
        total += count
        print(f"完成 {json_file}, 导入 {count} 篇")

    print(f"\n=== 导入完成 ===")
    print(f"总计导入: {total} 篇论文到 RAG 知识库")


if __name__ == "__main__":
    main()
