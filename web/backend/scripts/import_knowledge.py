"""
Import PubMed crawled data into the knowledge base (documents table).

This script:
1. Loads PubMed JSON data from data/raw/
2. Deduplicates by PMID across all files
3. Filters to papers with abstracts
4. Generates embeddings via Volcengine API
5. Inserts into the documents table for RAG Q&A

Usage:
    cd web/backend
    python -m scripts.import_knowledge --limit 200
    python -m scripts.import_knowledge --all
"""

import json
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from web.backend.database.database import SessionLocal, engine
from web.backend.database.models import Base, Document
from web.backend.services.rag import add_document

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "raw")


def load_pubmed_files(data_dir: str) -> list[dict]:
    all_papers = []
    seen_pmids = set()

    import glob

    files = sorted(glob.glob(os.path.join(data_dir, "pubmed_*.json")))
    print(f"Found {len(files)} PubMed files")

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                papers = json.load(f)
            if not isinstance(papers, list):
                continue
            for paper in papers:
                pmid = paper.get("pmid")
                if pmid and pmid not in seen_pmids:
                    seen_pmids.add(pmid)
                    all_papers.append(paper)
        except Exception as e:
            print(f"  Error loading {os.path.basename(filepath)}: {e}")

    print(f"Loaded {len(all_papers)} unique papers (deduplicated from PMID)")
    return all_papers


def paper_to_document(paper: dict) -> dict:
    pmid = paper.get("pmid", "")
    doi = paper.get("doi", "")
    title = paper.get("title", "") or ""
    abstract = paper.get("abstract", "") or ""
    keywords = paper.get("keywords", []) or []
    mesh_terms = paper.get("mesh_terms", []) or []
    journal = paper.get("journal", "") or ""
    pub_date = paper.get("pub_date", "") or ""
    authors = paper.get("authors", []) or []
    citation_count = paper.get("citation_count") or 0

    if not title and not abstract:
        return None

    source_url = (
        f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        if pmid
        else (f"https://doi.org/{doi}" if doi else "")
    )

    content_parts = []
    if title:
        content_parts.append(f"# {title}")
    if authors:
        author_str = ", ".join(authors[:10])
        if len(authors) > 10:
            author_str += f" et al. ({len(authors)} authors)"
        content_parts.append(f"Authors: {author_str}")
    if journal:
        content_parts.append(f"Journal: {journal}")
    if pub_date:
        content_parts.append(f"Published: {pub_date}")
    if abstract:
        content_parts.append(f"\n## Abstract\n{abstract}")
    if keywords:
        content_parts.append(f"\nKeywords: {', '.join(keywords)}")
    if mesh_terms:
        content_parts.append(f"MeSH Terms: {', '.join(mesh_terms[:20])}")
    if citation_count:
        content_parts.append(f"Citations: {citation_count}")

    content = "\n".join(content_parts)

    category = "research"
    kw_set = set(k.lower() for k in (keywords or []))
    mesh_set = set(k.lower() for k in (mesh_terms or []))
    all_terms = kw_set | mesh_set
    if any(t in all_terms for t in ["treatment", "therapy", "therapeutics"]):
        category = "treatment"
    elif any(t in all_terms for t in ["diagnosis", "diagnostic"]):
        category = "diagnosis"
    elif any(t in all_terms for t in ["diet", "nutrition"]):
        category = "diet"

    return {
        "title": title,
        "content": content,
        "source": f"PubMed PMID:{pmid}",
        "source_url": source_url,
        "category": category,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Import PubMed data into knowledge base"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max papers to import (default: all with abstracts)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Import all papers including those without abstracts",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="Skip embedding generation (faster, for testing)",
    )
    parser.add_argument(
        "--data-dir", type=str, default=None, help="Path to data/raw directory"
    )
    args = parser.parse_args()

    data_dir = args.data_dir or DATA_DIR

    Base.metadata.create_all(bind=engine)
    print("Database tables created")

    papers = load_pubmed_files(data_dir)

    doc_dicts = []
    for paper in papers:
        doc_dict = paper_to_document(paper)
        if doc_dict and (args.all or len(doc_dict["content"]) > 50):
            doc_dicts.append(doc_dict)

    doc_dicts.sort(key=lambda d: len(d["content"]), reverse=True)
    print(f"Papers suitable for import: {len(doc_dicts)}")

    if args.limit:
        doc_dicts = doc_dicts[: args.limit]
        print(f"Limiting to {args.limit} papers")

    db = SessionLocal()

    try:
        existing_count = db.query(Document).count()
        print(f"Existing documents in DB: {existing_count}")

        imported = 0
        failed = 0
        for i, doc_dict in enumerate(doc_dicts):
            try:
                source_key = doc_dict["source"]
                existing = (
                    db.query(Document).filter(Document.source == source_key).first()
                )
                if existing:
                    if (i + 1) % 100 == 0:
                        print(
                            f"  [{i + 1}/{len(doc_dicts)}] Skipped duplicate: {source_key}"
                        )
                    continue

                if args.skip_embedding:
                    doc = Document(
                        title=doc_dict["title"],
                        content=doc_dict["content"],
                        source=doc_dict["source"],
                        source_url=doc_dict["source_url"],
                        category=doc_dict["category"],
                        embedding=None,
                    )
                    db.add(doc)
                    db.commit()
                else:
                    add_document(
                        db=db,
                        title=doc_dict["title"],
                        content=doc_dict["content"],
                        source=doc_dict["source"],
                        source_url=doc_dict["source_url"],
                        category=doc_dict["category"],
                    )

                imported += 1
                if (i + 1) % 10 == 0:
                    print(
                        f"  [{i + 1}/{len(doc_dicts)}] Imported: {doc_dict['title'][:60]}"
                    )
            except Exception as e:
                failed += 1
                print(f"  [{i + 1}] Failed: {str(e)[:100]}")
                db.rollback()
                continue

        print(f"\nImport complete: {imported} imported, {failed} failed")
        total = db.query(Document).count()
        print(f"Total documents in DB: {total}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
