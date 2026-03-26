# AGENTS.md - SubSkin Project Guide

> This document provides coding agents with the context needed to work effectively in this repository.

## Project Overview

**SubSkin** is a vitiligo (白癜风) knowledge base project that leverages AI to bridge the gap between medical research and patients. The project aims to:
- Automatically collect vitiligo-related papers from PubMed, Google Scholar
- Use LLMs to translate and summarize medical papers into accessible Chinese content
- Track drug development progress (JAK inhibitors, clinical trials)
- Build a structured dataset for future ML research

## Tech Stack

| Layer | Technology |
|-------|------------|
| Data Collection | Python (Scrapy, BeautifulSoup, requests) |
| AI Processing | OpenAI API, Anthropic API |
| Data Storage | JSON/Markdown (Phase 1) → PostgreSQL (Phase 2) |
| Frontend | VitePress/Docsify (planned) |
| Package Manager | pip + venv / poetry (recommended) |

## Project Structure (Recommended)

```
subskin/
├── src/
│   ├── crawlers/          # Scrapy spiders for PubMed, Google Scholar
│   ├── processors/        # LLM-based summarization & translation
│   ├── models/            # Data models and schemas
│   └── utils/             # Shared utilities
├── data/
│   ├── raw/               # Raw scraped data
│   ├── processed/         # AI-processed content
│   └── exports/           # Exported datasets
├── docs/                  # VitePress/Docsify content
├── tests/                 # Unit and integration tests
├── scripts/               # One-off scripts and automation
├── configs/               # Configuration files
└── requirements/          # Python dependencies
    ├── base.txt
    ├── dev.txt
    └── prod.txt
```

## Build/Lint/Test Commands

### Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements/dev.txt
```

### Linting & Formatting
```bash
# Format code with black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Lint with ruff (fast, replaces flake8 + many plugins)
ruff check src/ tests/

# Type check with mypy
mypy src/

# Run all checks
ruff check src/ tests/ && black --check src/ tests/ && mypy src/
```

### Testing
```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_crawlers.py

# Run a single test function
pytest tests/test_crawlers.py::test_pubmed_parser

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific marker
pytest -m "not slow"
```

### Data Processing
```bash
# Run crawler
scrapy crawl pubmed -o data/raw/pubmed.json

# Process with LLM
python scripts/process_papers.py --input data/raw/pubmed.json --output data/processed/
```

## Code Style Guidelines

### Python Style

**Formatting:**
- Use `black` for code formatting (line length: 88)
- Use `isort` for import sorting
- Use `ruff` for linting

**Imports:**
```python
# Standard library
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

# Third-party
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# Local imports
from src.models.paper import Paper
from src.utils.http import retry_request
```

**Type Annotations:**
- Always use type hints for function signatures
- Use `Optional[T]` for optional parameters
- Use `list[T]`, `dict[str, Any]` (Python 3.9+ style)

```python
def fetch_paper(pmid: str, timeout: int = 30) -> Optional[Paper]:
    """Fetch paper metadata from PubMed API.
    
    Args:
        pmid: PubMed ID of the paper
        timeout: Request timeout in seconds
        
    Returns:
        Paper object if found, None otherwise
    """
    ...
```

**Naming Conventions:**
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

**Error Handling:**
```python
# Use specific exceptions
from src.exceptions import CrawlerError, APIError

try:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
except requests.Timeout:
    raise CrawlerError(f"Timeout fetching {url}")
except requests.HTTPError as e:
    raise APIError(f"HTTP error: {e.response.status_code}")
```

**Docstrings:**
- Use Google-style docstrings
- Include Args, Returns, Raises, Examples when relevant

```python
def summarize_paper(paper: Paper, model: str = "gpt-4") -> str:
    """Generate a patient-friendly summary of a medical paper.
    
    Args:
        paper: Paper object containing title, abstract, etc.
        model: LLM model to use for summarization
        
    Returns:
        Chinese summary suitable for patients
        
    Raises:
        APIError: If LLM API call fails
        
    Example:
        >>> paper = Paper(title="JAK inhibitors...", abstract="...")
        >>> summary = summarize_paper(paper)
    """
    ...
```

### Markdown Style

- Use Chinese for content (patient-facing)
- Use English for technical documentation
- Include proper frontmatter for VitePress/Docsify

```markdown
---
title: JAK抑制剂研究进展
date: 2026-03-26
tags: [JAK, 临床试验, 新药]
---

# JAK抑制剂研究进展

> 本文为患者科普，不构成医疗建议。
```

## Git Workflow

### Commit Messages
```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `crawler`, `ai`

**Examples:**
```
crawler(pubmed): add pagination support for large result sets
ai(summary): improve Chinese translation quality with few-shot examples
fix(processor): handle empty abstract gracefully
docs: add contribution guidelines
```

### Branch Naming
- `feature/<name>` - New features
- `fix/<name>` - Bug fixes
- `crawler/<name>` - New crawlers
- `docs/<name>` - Documentation updates

## Important Notes

### Medical Content Guidelines
- **Always** include disclaimer: "本文不构成医疗建议"
- Use patient-friendly language, avoid jargon
- Cite sources with PubMed IDs
- Flag content that needs medical review

### API Keys & Secrets
- Store API keys in `.env` (never commit)
- Use `python-dotenv` to load environment variables
- Document required environment variables in `.env.example`

### Data Handling
- Respect robots.txt and rate limits
- Cache API responses to minimize costs
- Store raw data before processing (for reproducibility)
- Include metadata (source, timestamp, version)

## Quick Reference

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements/dev.txt` |
| Format code | `black src/ tests/` |
| Lint | `ruff check src/ tests/` |
| Type check | `mypy src/` |
| Run tests | `pytest` |
| Single test | `pytest tests/test_file.py::test_name` |
| Run crawler | `scrapy crawl <spider_name>` |
