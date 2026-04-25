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

## Architecture Principles

### PWA-First & Cross-Device Consistency (MANDATORY)

SubSkin is a PWA (Progressive Web App). All development and design decisions MUST follow PWA architecture and specifications to ensure users on any OS, any screen size — phones, tablets, iPad, desktop — get an equally excellent and consistent experience.

**Every change must satisfy these rules:**

1. **Responsive-first**: Design and implement for mobile first, then scale up to tablet/iPad/desktop. Use Tailwind breakpoints (`sm:`, `md:`, `lg:`, `xl:`). Never hardcode pixel widths that break on different screens.
2. **Touch-friendly**: All interactive elements must have minimum 44px touch targets. Buttons, links, and nav items must be comfortably tappable on mobile.
3. **Safe-area aware**: Handle iOS notch/home indicator with `env(safe-area-inset-*)` CSS variables. Use `safe-bottom` class for bottom-anchored elements. Detect iOS via `data-ios` attribute.
4. **Viewport units**: Use `dvh` (dynamic viewport height) instead of `vh` for full-height layouts to handle mobile browser address bar correctly.
5. **BottomNav for mobile**: Mobile navigation uses bottom tab bar (`md:hidden`). Desktop uses top header nav (`hidden md:flex`). Both must always be present and functional.
6. **No layout-breaking global styles**: Never apply `min-width: 44px` or `min-height: 44px` to ALL `<a>` tags — this breaks nav layouts. Apply touch targets via padding on nav-specific elements instead.
7. **SPA navigation**: Use `<router-link>` for internal navigation. Use `<a href>` ONLY for external links (encyclopedia). Never use `<a href="#">` or `@click.prevent` + `router.push()` for internal navigation — it causes blank-page bugs.
8. **PWA install & offline**: Service Worker, manifest, offline detection, and install prompt must remain functional after any change. Test `sw.js` and `manifest.webmanifest` after deployment.
9. **Theme consistency**: Dark/light mode toggle must work identically across ALL pages. Use `dark:` Tailwind variants everywhere.
10. **No page-transition glitches**: Do NOT use `<Transition mode="out-in">` on `<router-view>` — it causes blank-page bugs on slow connections. Let Vue Router handle view swaps directly.

**Before merging any frontend PR**: verify on 375px (iPhone SE), 768px (iPad), 1024px (iPad landscape), and 1440px (desktop) widths.

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

### User Privacy & Data Security (MANDATORY — 生死线)

User privacy and data security are the lifeblood of SubSkin. A single data leak can destroy user trust and the entire project. Violations of these rules are **unacceptable under any circumstances**.

**Data Classification (4 levels):**

| Level | Examples | Rule |
|-------|----------|------|
| 🔴 L4-Critical | 密码、银行卡号、身份证号、JWT token | **绝对不可出现在任何 API 响应、日志、前端代码、公开页面、GitHub。** 不可明文存储（密码必须 bcrypt hash，token 过期即废弃）。 |
| 🟠 L3-High | 手机号、邮箱、病情图片、个人照片、音频、视频、体检报告、真实姓名、家庭住址 | **不可暴露给任何第三方或其他用户。** API 返回时脱敏（手机号 `138****1234`，邮箱前2字符+`***@domain`）。图片/文件仅授权用户本人可访问。 |
| 🟡 L2-Medium | 用户昵称、头像、发表内容、收藏、评估历史摘要 | 用户自主选择公开/私密。社区分享由用户主动授权，**所有授权操作必须留不可篡改的审计记录**。 |
| 🟢 L1-Public | 百科内容、公开帖子、匿名统计数据 | 可公开访问，但数据采集仍需注明来源。 |

**Hard Rules (零容忍):**

1. **No L4/L3 data in git**: 密码、token、身份证号、银行卡号、**手机号、邮箱、真实姓名** **永远不提交到 Git**，不放 `.env.example`，不写测试 fixture，不进 PR review 截图。所有敏感信息必须通过环境变量或 `.env` 文件（已加入 `.gitignore`）传入。
2. **No hardcoded PII in scripts**: 脚本文件中禁止硬编码任何用户手机号、邮箱、真实姓名等个人数据。必须使用环境变量（如 `os.environ.get("VAR_NAME")`）引用。`.env.example` 中只能放占位值。
3. **L3 data must be redacted in API responses**: 手机号脱敏 `138****1234`，邮箱脱敏 `li***@example.com`，病情图片 URL 仅所有者可访问（需鉴权）。
4. **Never expose user data to other users**: 用户 A 不能看到用户 B 的 L3 数据，除非 B 主动授权分享。
5. **User-authorized sharing requires immutable audit trail**: 用户每执行一次「公开」「分享」「授权」操作，必须创建不可修改、不可删除的审计记录（`AuditLog` 表），记录 who/what/when/scope/revokeable。
6. **Right to be forgotten**: 用户请求删除账户时，必须在 30 天内彻底删除所有个人数据（L2-L4），仅保留匿名化统计数据。
7. **HTTPS everywhere**: 所有 API 必须 HTTPS，所有前端资源 HTTPS。
8. **Minimize data collection**: 只收集功能必需的数据，不收集「以后可能有用」的数据。

### Data Handling
- Respect robots.txt and rate limits
- Cache API responses to minimize costs
- Store raw data before processing (for reproducibility)
- Include metadata (source, timestamp, version)

## UI/Design Unity Principles (MANDATORY)

All new features and modifications MUST follow these principles to maintain a unified, consistent experience:

1. **Consistent Container Widths**: All content pages use `max-w-6xl mx-auto px-4` as the outer container. Chat uses `max-w-4xl`. This ensures the header, content, and footer feel like one coherent layout — not disconnected strips.

2. **In-Page Navigation = Left Sidebar**: Page-internal navigation (tabs, categories, history lists) MUST use a collapsible left sidebar pattern on desktop (`md:` and up), consistent across all pages:
   - **Sidebar width**: `w-52` (208px) expanded, thin strip when collapsed
   - **Active item**: `bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium rounded-lg`
   - **Inactive item**: `text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg`
   - **Collapse toggle**: Small vertical bar with chevron icon at sidebar edge
   - **Mobile**: Horizontal scrollable tabs or drawer overlay (NEVER left sidebar on mobile)

3. **Naming Consistency**: Use the same names across ALL surfaces (nav, title, header, body text):
   - 模块名: 小白助手 / 小白追踪 / 小白社区 / 小白百科
   - NEVER mix "病友社区" and "小白社区" for the same concept
   - NEVER mix "病情追踪" and "小白追踪" for the same concept
   - When referring to users within the community, "病友" is acceptable as a term of address

4. **Theme Color System**: All primary/accent colors use CSS variables (`--color-primary-*`). NEVER hardcode hex colors like `#10b981`, `#34d399`, or Tailwind's `emerald-*` classes. Use `primary-*` Tailwind classes instead.

5. **Component Patterns**: Reuse the same component patterns for common UI elements:
   - Cards: `card dark:bg-gray-800 p-5`
   - Section titles: `section-title` class
   - Section descriptions: `section-desc` class
   - Buttons: `btn-primary`, `btn-ghost`

6. **AI Navigation Sync (MANDATORY)**: 小白助手 is the central entry point for the entire website. When ANY new feature, page, or module is added, the following MUST be updated in sync:
   - **System prompt** in `web/backend/services/rag.py` (`_build_llm_messages` function): Add the new feature to the site navigation guide table, including path and description
   - **`SITE_FEATURE_KEYWORDS`** in `web/backend/services/rag.py`: Add keywords users might use to ask about the new feature
   - **Navigation components** (`BottomNav.vue`, `AppHeader.vue`): If it's a top-level module
   - **Router** (`router/index.ts`): The route must exist before the AI can reference it
   - NEVER allow the AI to recommend features or routes that don't exist
   - NEVER reference community board names that don't match the actual DB categories in `web/backend/database/init_db.py`

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
