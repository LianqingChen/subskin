# Findings & Analysis: SubSkin Refactoring

## Requirements
<!-- Captured from user request -->
- Full project refactoring using installed global skills
- Use superpowers standard development workflow
- Use planning-with-files to maintain task_plan.md, analysis.md, progress tracking
- Use @fro.bot/systematic for engineering review (architecture, security, performance)
- Use oh-my-opencode for multi-agent collaboration if needed
- Use find-skills to search for additional skills if required
- First analyze: technical stack, directory structure, main modules
- Generate refactoring plan with priorities, impact/risk assessment
- Execute incrementally, confirm after each step
- All file changes must be listed in plan before execution

## Current Project State

### Overview
SubSkin is a vitiligo knowledge base project that:
- Collects papers from PubMed, Semantic Scholar, ClinicalTrials.gov
- Uses LLMs (OpenAI/Anthropic/Volcengine) to translate and summarize into patient-friendly Chinese content
- Tracks drug development progress (JAK inhibitors, clinical trials)
- Planned: VitePress-based frontend website with community features

### Technical Stack Assessment
| Layer | Technology | Status | Notes |
|-------|------------|--------|-------|
| **Language** | Python 3.10+ | ✅ Good | Already configured in pyproject.toml |
| **Data Collection** | Scrapy, BeautifulSoup, requests, metapub | ✅ Good | PubMed crawler implemented |
| **AI Processing** | OpenAI API, Anthropic API | ✅ Good | summarizer.py implemented with proper error handling |
| **Data Validation** | Pydantic 2.x | ✅ Good | Settings and data models use Pydantic |
| **Web Framework** | FastAPI + Uvicorn | ⚠️ Partial | Structure defined but not fully implemented |
| **Database** | SQLite → PostgreSQL | ⚠️ Planned | SQLAlchemy declared, not fully integrated |
| **Testing** | pytest | ✅ Good | Good test coverage for implemented modules |
| **Code Quality** | black, ruff, mypy | ✅ Good | Properly configured in pyproject.toml |

### Directory Structure vs Planned Structure

Updated: 2026-04-02 after full exploration

| Path | Planned | Implemented | Status | Notes |
|------|---------|-------------|--------|-------|
| `src/crawlers/` | ✅ | ✅ | ✅ Complete | `pubmed_crawler.py` ✅, `semantic_scholar_crawler.py` ✅ **actually fully implemented** (was incorrectly marked incomplete), `clinical_trials_crawler.py` ✅ **actually fully implemented** |
| `src/processors/` | ✅ | ✅ | ✅ Complete | `translator.py`, `summarizer.py`, `deduplicator.py` all exist and implemented |
| `src/generators/` | ✅ | ⚪ | ❌ Missing | Weekly digest, HTML templates, video script not implemented - still needs skeleton |
| `src/web/` | ✅ | ✅ | ✅ **Actually complete** - separate project in `/web/` | Core backend already implemented in `/web/backend/` (FastAPI), frontend in `/web/vitepress/` - not in `src/web/` as originally planned |
| `src/scheduler/` | ✅ | ✅ | ⚠️ Partial | `update_scheduler.py` exists |
| `src/models/` | ✅ | ✅ | ✅ Good | `paper.py`, `trial.py`, `data_source.py` done |
| `src/utils/` | ✅ | ✅ | ✅ Good | `cache.py`, `rate_limiter.py`, `logger.py` etc. implemented |
| `src/cli.py` | ✅ | ✅ | ⚠️ Partial | Exists but needs more commands |
| `scripts/` | ✅ | ✅ | ✅ Good | `run_crawlers.py`, `generate_weekly.py`, `deploy_website.py` |
| `tests/` | ✅ | ✅ | ✅ Good | Good test coverage for implemented modules |
| `data/` | ✅ | ✅ | ✅ Good | `raw/` has sample data |
| `requirements/` | ✅ | ✅ | ✅ Good | Split into base/dev/web/ai |
| `configs/` | ✅ | ✅ | ✅ Complete | `.env.example`, `crawler_config.yaml`, `data_sources.yaml`, `web_config.yaml` all exist |
| `docs/` | ✅ | ⚪ | ⚠️ Minimal | Mostly in root |
| **`web/backend/`** | ✅ | ✅ | ⚠️ **Mostly complete** | FastAPI backend with: JWT auth, SMS login, comments, RAG QA, database models. Some endpoints are stubs (`/content/latest`). GitHub OAuth not implemented. |
| **`web/vitepress/`** | ✅ | ✅ | ✅ **Content structure complete** | VitePress static site with encyclopedia content structure already populated. AI chat page implemented. |

## Code Quality Analysis

### Strengths
1. **Good type hinting** - Most functions have proper type annotations following PEP 484
2. **Proper error handling** - Custom exception hierarchy, specific exceptions, good retry logic in crawlers and API clients
3. **Good test coverage** - Existing functionality has comprehensive pytest tests with mocking
4. **Follows Python best practices** - Snake case naming, proper docstrings (Google style), Pydantic validation
5. **Configuration** - Good typed settings with pydantic, fallback for when pydantic not available, environment variable loading
6. **Thread safety** - Rate limiter and cache use proper locking for concurrent access
7. **Caching** - SQLite-backed persistent cache with TTL support implemented properly

### Identified Issues for Refactoring

#### 1. Incomplete Modules (Updated after full exploration)
- **`src/crawlers/`** - ✅ **All complete**: `semantic_scholar_crawler.py` and `clinical_trials_crawler.py` are actually fully implemented (only needed tests)
- **`src/generators/`** - Directory created but no implementation - still needs skeleton
- **`src/web/`** - ✅ **Actually implemented in `/web/` directory** (separate backend/frontend project outside src/) - not in src/ as originally planned
- **`configs/`** - ✅ **Complete**: `.env.example`, `crawler_config.yaml`, `data_sources.yaml`, `web_config.yaml` all exist
- **`web/backend/`** - ⚠️ **Mostly complete**: Some endpoints are stubs (`/content/latest`), GitHub OAuth not implemented, RAG needs hardening
- **`web/vitepress/`** - ✅ **Content structure complete**: Encyclopedia content already populated

#### 2. Dependency Issues
- **`requirements/`** split into multiple files but `pyproject.toml` already includes all dependencies - duplication
- Some dependencies are declared in both places which can cause inconsistency

#### 3. Code Style
- `src/__init__.py` is empty - should either declare exports or use implicit namespace package
- Few modules don't have module docstrings

#### 4. Architecture
- **`config.py`** is quite large (522 lines) - could be split into multiple smaller modules
- The fallback implementation for pydantic when not available increases complexity - can we remove this since pydantic is a required dependency?

#### 5. Testing
- Good coverage for PubMed crawler, but other modules lack tests
- No CI configuration visible (should be in `.github/workflows/`)

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Keep black line length at 88 | Already configured matches AGENTS.md guide |
| Keep ruff + mypy configuration | Already properly configured matches project guidelines |
| Consolidate dependencies to pyproject.toml | Remove duplication from requirements/*.txt |
| Split large config.py into smaller modules | Improve maintainability |
| Add missing __init__.py exports | Better package structure |
| Add module docstrings where missing | Improve documentation |
| Create missing config files from template | Help users get started |

## Resources
- AGENTS.md: `/root/subskin/AGENTS.md` - project guide with coding standards
- PROJECT_FRAMEWORK.md: `/root/subskin/PROJECT_FRAMEWORK.md` - architecture design
- IMPLEMENTATION_PLAN.md: `/root/subskin/IMPLEMENTATION_PLAN.md` - implementation roadmap
- pyproject.toml: Already properly configured with modern Python standards

---
*Update this file after every 2 view/browser/search operations*

 ## Web/Community Site Analysis (Added 2026-04-02)

 After full review by visual-engineering agent, key findings:

 ### Overall Assessment
 - **Good foundation**: FastAPI backend + VitePress frontend is a cohesive stack that aligns with project mission
 - Backend already implements: JWT auth, SMS login, comments, admin moderation, RAG AI Q&A, ORM models with SQLAlchemy
 - Frontend already has: encyclopedia content structure, AI chat page, deployment ready with Docker + Nginx
 - **Missing**: cohesive medical-tech design system, some API endpoints are stubs, GitHub OAuth not implemented, RAG robustness needs improvement

 ### Strengths
 - Modular architecture: clear separation between api, models, services, database
 - Proper security: JWT authentication with expiration, password hashing
 - RAG already implemented with multi-turn conversation and source citations
 - Docker-compose deployment ready for production
 - Content structure already populated with encyclopedia articles

 ### Issues Identified
 1. **Design/Aesthetics**: No formal design system, relies on default VitePress styling - needs medical-tech aesthetic (calm blues/teals, accessible typography)
 2. **Functionality gaps**: `/api/content/latest` is a stub, no admin UI for managing RAG documents, GitHub OAuth not implemented
 3. **RAG robustness**: Embeddings stored as JSON strings in DB with minimal error handling; needs validation and fallback
 4. **Testing**: No tests for web backend; missing CI/CD

 ### Technical Decisions
 | Decision | Rationale |
 |----------|-----------|
 | Requirement: keep requirements/*.txt for reference per user confirmation | User prefers to keep them |
 | SemanticScholar and ClinicalTrials crawlers are already complete - add tests instead of rewriting | Code already good quality, just missing tests |
 | Split config.py to multiple modules while keeping backward compatibility | Easier maintenance, existing imports still work |
 | Focus web refactoring on: add minimal design system, fix stub endpoints, harden RAG, improve medical aesthetic | Addresses user's priority on community website development |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
|       |            |

## Resources
- AGENTS.md: /root/subskin/AGENTS.md - already contains project overview, tech stack, structure, code style guidelines
- GitHub: SubSkin project root at /root/subskin

## Visual/Browser Findings
<!-- CRITICAL: Update after every 2 view/browser operations -->
<!-- Multimodal content must be captured as text immediately -->
-

---
*Update this file after every 2 view/browser/search operations*
*This prevents visual information from being lost*