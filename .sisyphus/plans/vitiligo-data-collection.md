# 白癜风医学资料收集系统 - 工作计划

## TL;DR

> **Quick Summary**: 构建一个完整的医学文献收集系统，从PubMed、Semantic Scholar、ClinicalTrials.gov爬取>1000篇白癜风相关论文，使用OpenAI翻译和总结，存储为JSON/Markdown格式，支持定期更新。
> 
> **Deliverables**:
> - 完整的Python爬虫项目结构
> - PubMed爬虫（基于metapub库）
> - Semantic Scholar集成
> - ClinicalTrials.gov集成
> - OpenAI翻译和总结模块
> - 定期更新机制
> - 完整的测试套件（pytest + TDD）
> - JSON/Markdown数据存储
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Project Setup → PubMed Crawler → Data Processing → Integration

---

## Context

### Original Request
用户希望高效收集白癜风相关的医学资料，构建一个知识库，为患者提供科普内容。需要从多个数据源收集>1000篇论文，使用LLM翻译和总结，支持定期更新。

### Interview Summary
**Key Discussions**:
- **数据源优先级**: PubMed（主要）+ Semantic Scholar（补充）+ ClinicalTrials.gov（临床试验）
- **数据规模**: 大规模（>1000篇）
- **更新策略**: 定期更新（每周/每月）
- **中文数据库**: 寻找免费替代方案（跳过付费万方/知网）
- **API密钥**: 先用免费额度（PubMed 3 req/s）
- **LLM选择**: OpenAI（翻译和总结）
- **存储方案**: Phase 1使用JSON/Markdown
- **测试策略**: TDD（测试驱动开发）+ pytest

**Research Findings**:
- **项目状态**: 完全空白，需要从零开始构建
- **PubMed E-utilities**: 官方API，免费额度3 req/s，有key可提升到10 req/s
- **Semantic Scholar**: 免费API（1000 req/s），替代Google Scholar，无法律风险
- **ClinicalTrials.gov**: 免费v2 API，JSON格式，关注JAK抑制剂等新药试验
- **metapub库**: 148 stars，最成熟的PubMed库，内置速率限制和缓存
- **paperscraper**: ~700 stars，多源爬虫参考，支持自动重试和回退机制

### Metis Review
**Identified Gaps** (addressed):
- **中文数据库**: 明确寻找免费替代方案，不使用付费万方/知网
- **API密钥管理**: 先用免费额度，后续可申请提升
- **错误处理**: 需要实现重试机制和优雅降级
- **数据去重**: 需要处理多数据源的重复论文
- **速率限制**: 需要实现速率限制器，避免API封禁
- **缓存策略**: 需要缓存API响应，避免重复请求

---

## Work Objectives

### Core Objective
构建一个完整的医学文献收集系统，能够：
1. 从PubMed、Semantic Scholar、ClinicalTrials.gov爬取白癜风相关论文和临床试验数据
2. 使用OpenAI翻译论文摘要并生成患者友好的总结
3. 存储为JSON/Markdown格式，便于后续处理和展示
4. 支持定期更新，保持知识库新鲜
5. 使用TDD方法开发，确保代码质量

### Concrete Deliverables
- `src/crawlers/pubmed_crawler.py` - PubMed爬虫
- `src/crawlers/semantic_scholar_crawler.py` - Semantic Scholar爬虫
- `src/crawlers/clinical_trials_crawler.py` - ClinicalTrials.gov爬虫
- `src/processors/translator.py` - OpenAI翻译模块
- `src/processors/summarizer.py` - OpenAI总结模块
- `src/models/paper.py` - 论文数据模型
- `src/models/trial.py` - 临床试验数据模型
- `src/utils/rate_limiter.py` - 速率限制器
- `src/utils/cache.py` - 缓存管理
- `tests/` - 完整的测试套件
- `data/raw/` - 原始数据存储
- `data/processed/` - 处理后数据存储
- `configs/.env.example` - 环境变量模板
- `requirements/base.txt` - 依赖管理

### Definition of Done
- [ ] 所有爬虫能够成功爬取数据并存储到JSON文件
- [ ] OpenAI模块能够翻译和总结论文
- [ ] 所有测试通过（pytest）
- [ ] 代码通过ruff和mypy检查
- [ ] 能够定期运行更新脚本

### Must Have
- PubMed爬虫实现（基于metapub库）
- Semantic Scholar集成
- ClinicalTrials.gov集成
- OpenAI翻译和总结功能
- JSON/Markdown数据存储
- TDD测试套件
- 速率限制和错误处理
- 缓存机制

### Must NOT Have (Guardrails)
- ❌ 全文下载（版权限制）
- ❌ 实时监控（资源消耗大）
- ❌ Google Scholar爬虫（法律风险）
- ❌ 付费中文数据库（万方/知网）
- ❌ 患者社区数据（论坛、社交媒体）
- ❌ PostgreSQL（Phase 2再考虑）
- ❌ 过度抽象（保持简单实用）
- ❌ 过度注释（避免AI slop）

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.
> Acceptance criteria requiring "user manually tests/confirms" are FORBIDDEN.

### Test Decision
- **Infrastructure exists**: NO
- **Automated tests**: YES (TDD)
- **Framework**: pytest
- **TDD Flow**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios (see TODO template below).
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Library/Module**: Use Bash (bun/node REPL) — Import, call functions, compare output
- **API Integration**: Use Bash (curl) — Send requests, assert status + response fields
- **Data Processing**: Use Bash (python) — Run scripts, validate output files

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.
> Target: 5-8 tasks per wave. Fewer than 3 per wave (except final) = under-splitting.

```
Wave 1 (Start Immediately — foundation + scaffolding):
├── Task 1: Project structure setup [quick]
├── Task 2: Dependencies and configuration [quick]
├── Task 3: Data models (Paper, Trial) [quick]
├── Task 4: Rate limiter utility [quick]
├── Task 5: Cache utility [quick]
├── Task 6: Test infrastructure setup [quick]
└── Task 7: Logging and error handling [quick]

Wave 2 (After Wave 1 — core crawlers, MAX PARALLEL):
├── Task 8: PubMed crawler (depends: 3, 4, 5) [deep]
├── Task 9: Semantic Scholar crawler (depends: 3, 4, 5) [unspecified-high]
├── Task 10: ClinicalTrials.gov crawler (depends: 3, 4, 5) [unspecified-high]
├── Task 11: Data deduplication (depends: 8, 9, 10) [deep]
├── Task 12: OpenAI translator (depends: 3) [unspecified-high]
├── Task 13: OpenAI summarizer (depends: 3, 12) [unspecified-high]
└── Task 14: Data export to JSON/Markdown (depends: 11) [quick]

Wave 3 (After Wave 2 — integration + automation):
├── Task 15: Update scheduler (depends: 8, 9, 10) [deep]
├── Task 16: CLI interface (depends: 8, 9, 10, 12, 13) [unspecified-high]
├── Task 17: Configuration management (depends: 2) [quick]
├── Task 18: Documentation (depends: all) [writing]
└── Task 19: Final integration test (depends: all) [deep]

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: Task 1 → Task 3 → Task 8 → Task 11 → Task 14 → Task 15 → F1-F4 → user okay
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 7 (Wave 1)
```

### Dependency Matrix

- **1-7**: — — 8-14, 1
- **8**: 3, 4, 5 — 11, 15, 16, 2
- **9**: 3, 4, 5 — 11, 15, 16, 2
- **10**: 3, 4, 5 — 11, 15, 16, 2
- **11**: 8, 9, 10 — 14, 3
- **12**: 3 — 13, 16, 2
- **13**: 3, 12 — 16, 2
- **14**: 11 — 15, 16, 3
- **15**: 8, 9, 10 — 16, 4
- **16**: 8, 9, 10, 12, 13 — 18, 4
- **17**: 2 — 18, 1
- **18**: all — 19, 1
- **19**: all — F1-F4, 1

### Agent Dispatch Summary

- **Wave 1**: **7** — T1-T4 → `quick`, T5-T7 → `quick`
- **Wave 2**: **7** — T8 → `deep`, T9-T10 → `unspecified-high`, T11 → `deep`, T12-T13 → `unspecified-high`, T14 → `quick`
- **Wave 3**: **5** — T15 → `deep`, T16 → `unspecified-high`, T17 → `quick`, T18 → `writing`, T19 → `deep`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [ ] 1. Project Structure Setup

  **What to do**:
  - Create directory structure: `src/crawlers/`, `src/processors/`, `src/models/`, `src/utils/`
  - Create data directories: `data/raw/`, `data/processed/`, `data/exports/`
  - Create test directory: `tests/`
  - Create `__init__.py` files for all Python packages
  - Create `.gitignore` for Python project
  - Create `README.md` with project overview

  **Must NOT do**:
  - Do NOT create any implementation files yet
  - Do NOT add any dependencies yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple directory and file creation, no complex logic
  - **Skills**: []
    - No special skills needed for this task

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4, 5, 6, 7)
  - **Blocks**: Tasks 8-19
  - **Blocked By**: None (can start immediately)

  **References**:
  - `AGENTS.md` - Recommended project structure
  - `https://docs.python.org/3/tutorial/modules.html` - Python package structure

  **Acceptance Criteria**:
  - [ ] All directories created: `src/crawlers/`, `src/processors/`, `src/models/`, `src/utils/`, `data/raw/`, `data/processed/`, `data/exports/`, `tests/`
  - [ ] All `__init__.py` files created
  - [ ] `.gitignore` created with Python patterns
  - [ ] `README.md` created with basic project info

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Directory structure verification
    Tool: Bash
    Preconditions: None
    Steps:
      1. ls -la src/ → verify crawlers/, processors/, models/, utils/ exist
      2. ls -la data/ → verify raw/, processed/, exports/ exist
      3. ls -la tests/ → verify directory exists
      4. find src -name "__init__.py" → verify all __init__.py files exist
    Expected Result: All directories and __init__.py files present
    Failure Indicators: Missing directories or __init__.py files
    Evidence: .sisyphus/evidence/task-1-structure.txt

  Scenario: .gitignore verification
    Tool: Bash
    Preconditions: .gitignore created
    Steps:
      1. cat .gitignore → verify contains Python patterns
      2. grep -E "(\\.pyc|__pycache__|\\.venv|\\.env)" .gitignore → verify patterns exist
    Expected Result: .gitignore contains standard Python patterns
    Failure Indicators: Missing essential patterns
    Evidence: .sisyphus/evidence/task-1-gitignore.txt
  ```

  **Evidence to Capture**:
  - [ ] Directory listing showing all created directories
  - [ ] .gitignore content verification

  **Commit**: YES (groups with Wave 1)
  - Message: `chore(setup): initialize project structure`
  - Files: All created directories and files
  - Pre-commit: None

- [ ] 2. Dependencies and Configuration

  **What to do**:
  - Create `requirements/base.txt` with core dependencies:
    - `metapub>=0.5.5` - PubMed API library
    - `requests>=2.31.0` - HTTP library
    - `openai>=1.0.0` - OpenAI API
    - `python-dotenv>=1.0.0` - Environment variables
  - Create `requirements/dev.txt` with dev dependencies:
    - `pytest>=7.4.0` - Testing framework
    - `pytest-cov>=4.1.0` - Coverage plugin
    - `ruff>=0.1.0` - Linting
    - `mypy>=1.5.0` - Type checking
    - `black>=23.0.0` - Code formatting
  - Create `configs/.env.example` with environment variable templates:
    - `NCBI_API_KEY=your_key_here`
    - `OPENAI_API_KEY=your_key_here`
    - `SEMANTIC_SCHOLAR_API_KEY=your_key_here`
  - Create `pyproject.toml` for project configuration

  **Must NOT do**:
  - Do NOT commit actual API keys
  - Do NOT install dependencies yet (user will do this)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file creation with dependency specifications
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5, 6, 7)
  - **Blocks**: Tasks 12, 13, 17
  - **Blocked By**: None (can start immediately)

  **References**:
  - `AGENTS.md` - Dependency management guidelines
  - `https://pip.pypa.io/en/stable/reference/requirements-file-format/` - Requirements file format
  - `https://github.com/metapub/metapub` - metapub library documentation

  **Acceptance Criteria**:
  - [ ] `requirements/base.txt` created with all core dependencies
  - [ ] `requirements/dev.txt` created with all dev dependencies
  - [ ] `configs/.env.example` created with all required environment variables
  - [ ] `pyproject.toml` created with project configuration

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Requirements files verification
    Tool: Bash
    Preconditions: requirements files created
    Steps:
      1. cat requirements/base.txt → verify contains metapub, requests, openai, python-dotenv
      2. cat requirements/dev.txt → verify contains pytest, ruff, mypy, black
      3. grep -E "metapub|requests|openai|python-dotenv" requirements/base.txt → verify each dependency
    Expected Result: All required dependencies listed
    Failure Indicators: Missing dependencies
    Evidence: .sisyphus/evidence/task-2-requirements.txt

  Scenario: .env.example verification
    Tool: Bash
    Preconditions: .env.example created
    Steps:
      1. cat configs/.env.example → verify contains NCBI_API_KEY, OPENAI_API_KEY, SEMANTIC_SCHOLAR_API_KEY
      2. grep -E "(NCBI_API_KEY|OPENAI_API_KEY|SEMANTIC_SCHOLAR_API_KEY)" configs/.env.example → verify each key
    Expected Result: All required environment variables present
    Failure Indicators: Missing environment variables
    Evidence: .sisyphus/evidence/task-2-env.txt
  ```

  **Evidence to Capture**:
  - [ ] Requirements files content verification
  - [ ] .env.example content verification

  **Commit**: YES (groups with Wave 1)
  - Message: `chore(setup): add dependencies and configuration`
  - Files: requirements/, configs/.env.example, pyproject.toml
  - Pre-commit: None

- [ ] 3. Data Models (Paper, Trial)

  **What to do**:
  - Create `src/models/paper.py` with Paper data model:
    - Fields: pmid, doi, title, abstract, authors, journal, pub_date, mesh_terms, keywords, source, crawled_at
    - Use dataclasses or Pydantic for validation
    - Add type hints for all fields
  - Create `src/models/trial.py` with ClinicalTrial data model:
    - Fields: nct_id, title, condition, interventions, phase, status, enrollment, sponsor, start_date, completion_date, locations, url
    - Use dataclasses or Pydantic for validation
    - Add type hints for all fields
  - Create tests in `tests/test_models.py`:
    - Test Paper creation with valid data
    - Test ClinicalTrial creation with valid data
    - Test validation for missing required fields

  **Must NOT do**:
  - Do NOT add methods beyond basic validation
  - Do NOT over-engineer with unnecessary abstractions

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple data model definitions with basic validation
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4, 5, 6, 7)
  - **Blocks**: Tasks 8, 9, 10, 11, 12, 13, 14
  - **Blocked By**: None (can start immediately)

  **References**:
  - `AGENTS.md` - Type annotation guidelines
  - `https://docs.python.org/3/library/dataclasses.html` - Python dataclasses
  - `https://pydantic-docs.helpmanual.io/` - Pydantic documentation
  - Research findings: Recommended metadata schema from librarian agent

  **Acceptance Criteria**:
  - [ ] `src/models/paper.py` created with Paper dataclass
  - [ ] `src/models/trial.py` created with ClinicalTrial dataclass
  - [ ] All fields have type hints
  - [ ] Tests created in `tests/test_models.py`
  - [ ] `pytest tests/test_models.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Paper model creation
    Tool: Bash (python)
    Preconditions: paper.py created
    Steps:
      1. python -c "from src.models.paper import Paper; p = Paper(pmid='12345', title='Test', abstract='...', authors=[], journal='Test', pub_date='2024-01-01', mesh_terms=[], keywords=[], source='pubmed', crawled_at='2024-01-01T00:00:00'); print(p.title)"
      2. Verify output is "Test"
    Expected Result: Paper object created successfully
    Failure Indicators: Import error or validation error
    Evidence: .sisyphus/evidence/task-3-paper.txt

  Scenario: ClinicalTrial model creation
    Tool: Bash (python)
    Preconditions: trial.py created
    Steps:
      1. python -c "from src.models.trial import ClinicalTrial; t = ClinicalTrial(nct_id='NCT12345', title='Test Trial', condition='Vitiligo', interventions=[], phase='PHASE2', status='RECRUITING', enrollment=100, sponsor='Test', start_date='2024-01-01', completion_date='2025-01-01', locations=[], url='http://test.com'); print(t.nct_id)"
      2. Verify output is "NCT12345"
    Expected Result: ClinicalTrial object created successfully
    Failure Indicators: Import error or validation error
    Evidence: .sisyphus/evidence/task-3-trial.txt

  Scenario: Test execution
    Tool: Bash
    Preconditions: test_models.py created
    Steps:
      1. pytest tests/test_models.py -v
      2. Verify all tests pass
    Expected Result: All tests pass
    Failure Indicators: Test failures
    Evidence: .sisyphus/evidence/task-3-tests.txt
  ```

  **Evidence to Capture**:
  - [ ] Paper model creation verification
  - [ ] ClinicalTrial model creation verification
  - [ ] Test execution results

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(models): add Paper and ClinicalTrial data models`
  - Files: src/models/paper.py, src/models/trial.py, tests/test_models.py
  - Pre-commit: pytest tests/test_models.py

- [ ] 4. Rate Limiter Utility

  **What to do**:
  - Create `src/utils/rate_limiter.py` with RateLimiter class:
    - Implement token bucket algorithm for rate limiting
    - Support configurable requests per second
    - Thread-safe implementation
    - Context manager support for easy use
  - Create tests in `tests/test_rate_limiter.py`:
    - Test rate limiting with 3 req/s (PubMed free tier)
    - Test rate limiting with 10 req/s (PubMed with key)
    - Test rate limiting with 1000 req/s (Semantic Scholar)
    - Test thread safety

  **Must NOT do**:
  - Do NOT use external rate limiting libraries (implement from scratch)
  - Do NOT over-engineer with unnecessary features

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple utility class with well-defined behavior
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 5, 6, 7)
  - **Blocks**: Tasks 8, 9, 10
  - **Blocked By**: None (can start immediately)

  **References**:
  - Research findings: PubMed rate limits (3 req/s free, 10 req/s with key)
  - Research findings: Semantic Scholar rate limits (1000 req/s)
  - `https://en.wikipedia.org/wiki/Token_bucket` - Token bucket algorithm

  **Acceptance Criteria**:
  - [ ] `src/utils/rate_limiter.py` created with RateLimiter class
  - [ ] Token bucket algorithm implemented
  - [ ] Thread-safe implementation
  - [ ] Context manager support
  - [ ] Tests created in `tests/test_rate_limiter.py`
  - [ ] `pytest tests/test_rate_limiter.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Rate limiter basic functionality
    Tool: Bash (python)
    Preconditions: rate_limiter.py created
    Steps:
      1. python -c "from src.utils.rate_limiter import RateLimiter; import time; limiter = RateLimiter(3); start = time.time(); [limiter.acquire() for _ in range(3)]; elapsed = time.time() - start; print(f'{elapsed:.2f}s'); assert 0.9 < elapsed < 1.1, f'Expected ~1s, got {elapsed}s'"
      2. Verify elapsed time is approximately 1 second
    Expected Result: 3 requests take ~1 second at 3 req/s
    Failure Indicators: Timing significantly off
    Evidence: .sisyphus/evidence/task-4-basic.txt

  Scenario: Rate limiter context manager
    Tool: Bash (python)
    Preconditions: rate_limiter.py created
    Steps:
      1. python -c "from src.utils.rate_limiter import RateLimiter; limiter = RateLimiter(10); with limiter: print('Context manager works')"
      2. Verify no errors
    Expected Result: Context manager works without errors
    Failure Indicators: Exception raised
    Evidence: .sisyphus/evidence/task-4-context.txt

  Scenario: Test execution
    Tool: Bash
    Preconditions: test_rate_limiter.py created
    Steps:
      1. pytest tests/test_rate_limiter.py -v
      2. Verify all tests pass
    Expected Result: All tests pass
    Failure Indicators: Test failures
    Evidence: .sisyphus/evidence/task-4-tests.txt
  ```

  **Evidence to Capture**:
  - [ ] Rate limiter basic functionality verification
  - [ ] Context manager verification
  - [ ] Test execution results

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(utils): add rate limiter utility`
  - Files: src/utils/rate_limiter.py, tests/test_rate_limiter.py
  - Pre-commit: pytest tests/test_rate_limiter.py

- [ ] 5. Cache Utility

  **What to do**:
  - Create `src/utils/cache.py` with Cache class:
    - Implement SQLite-based caching for API responses
    - Support TTL (time-to-live) for cache entries
    - Support cache invalidation
    - Thread-safe implementation
  - Create tests in `tests/test_cache.py`:
    - Test cache hit and miss
    - Test TTL expiration
    - Test cache invalidation
    - Test thread safety

  **Must NOT do**:
  - Do NOT use external caching libraries (implement from scratch)
  - Do NOT cache sensitive data (API keys, etc.)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple utility class with well-defined behavior
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4, 6, 7)
  - **Blocks**: Tasks 8, 9, 10
  - **Blocked By**: None (can start immediately)

  **References**:
  - Research findings: metapub uses SQLite caching
  - `https://docs.python.org/3/library/sqlite3.html` - Python SQLite documentation

  **Acceptance Criteria**:
  - [ ] `src/utils/cache.py` created with Cache class
  - [ ] SQLite-based caching implemented
  - [ ] TTL support implemented
  - [ ] Cache invalidation implemented
  - [ ] Tests created in `tests/test_cache.py`
  - [ ] `pytest tests/test_cache.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Cache hit and miss
    Tool: Bash (python)
    Preconditions: cache.py created
    Steps:
      1. python -c "from src.utils.cache import Cache; import time; cache = Cache(':memory:'); cache.set('key1', 'value1', ttl=60); result = cache.get('key1'); print(result); assert result == 'value1'"
      2. Verify cache hit works
      3. python -c "from src.utils.cache import Cache; cache = Cache(':memory:'); result = cache.get('nonexistent'); print(result); assert result is None"
      4. Verify cache miss returns None
    Expected Result: Cache hit returns value, cache miss returns None
    Failure Indicators: Incorrect values or exceptions
    Evidence: .sisyphus/evidence/task-5-hit-miss.txt

  Scenario: Cache TTL expiration
    Tool: Bash (python)
    Preconditions: cache.py created
    Steps:
      1. python -c "from src.utils.cache import Cache; import time; cache = Cache(':memory:'); cache.set('key1', 'value1', ttl=1); time.sleep(2); result = cache.get('key1'); print(result); assert result is None"
      2. Verify expired entry returns None
    Expected Result: Expired cache entry returns None
    Failure Indicators: Expired entry still returns value
    Evidence: .sisyphus/evidence/task-5-ttl.txt

  Scenario: Test execution
    Tool: Bash
    Preconditions: test_cache.py created
    Steps:
      1. pytest tests/test_cache.py -v
      2. Verify all tests pass
    Expected Result: All tests pass
    Failure Indicators: Test failures
    Evidence: .sisyphus/evidence/task-5-tests.txt
  ```

  **Evidence to Capture**:
  - [ ] Cache hit and miss verification
  - [ ] TTL expiration verification
  - [ ] Test execution results

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(utils): add cache utility`
  - Files: src/utils/cache.py, tests/test_cache.py
  - Pre-commit: pytest tests/test_cache.py

- [ ] 6. Test Infrastructure Setup

  **What to do**:
  - Create `pytest.ini` with pytest configuration:
    - Set test paths to `tests/`
    - Configure coverage reporting
    - Set minimum coverage threshold (80%)
  - Create `tests/conftest.py` with shared fixtures:
    - Fixture for temporary cache database
    - Fixture for mock API responses
    - Fixture for test data (sample Paper and ClinicalTrial objects)
  - Create `.github/workflows/test.yml` for CI:
    - Run tests on push and pull request
    - Run linting and type checking
    - Upload coverage report

  **Must NOT do**:
  - Do NOT add test cases for unimplemented features
  - Do NOT over-configure pytest

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple configuration file creation
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4, 5, 7)
  - **Blocks**: All subsequent test tasks
  - **Blocked By**: None (can start immediately)

  **References**:
  - `AGENTS.md` - Testing guidelines
  - `https://docs.pytest.org/` - Pytest documentation
  - `https://pytest-cov.readthedocs.io/` - Pytest-cov documentation

  **Acceptance Criteria**:
  - [ ] `pytest.ini` created with proper configuration
  - [ ] `tests/conftest.py` created with shared fixtures
  - [ ] `.github/workflows/test.yml` created for CI
  - [ ] `pytest --cov=src` runs successfully

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Pytest configuration verification
    Tool: Bash
    Preconditions: pytest.ini created
    Steps:
      1. cat pytest.ini → verify contains testpaths = tests
      2. grep -E "(testpaths|addopts)" pytest.ini → verify configuration
    Expected Result: pytest.ini contains required configuration
    Failure Indicators: Missing configuration
    Evidence: .sisyphus/evidence/task-6-pytest-ini.txt

  Scenario: Shared fixtures verification
    Tool: Bash (python)
    Preconditions: conftest.py created
    Steps:
      1. python -c "import tests.conftest; print('Fixtures loaded')"
      2. Verify no import errors
    Expected Result: conftest.py imports successfully
    Failure Indicators: Import errors
    Evidence: .sisyphus/evidence/task-6-conftest.txt

  Scenario: Test execution
    Tool: Bash
    Preconditions: All test files created
    Steps:
      1. pytest --cov=src --cov-report=term
      2. Verify tests run and coverage report generated
    Expected Result: Tests run successfully with coverage
    Failure Indicators: Test failures or coverage errors
    Evidence: .sisyphus/evidence/task-6-coverage.txt
  ```

  **Evidence to Capture**:
  - [ ] Pytest configuration verification
  - [ ] Shared fixtures verification
  - [ ] Test execution with coverage

  **Commit**: YES (groups with Wave 1)
  - Message: `chore(test): setup test infrastructure`
  - Files: pytest.ini, tests/conftest.py, .github/workflows/test.yml
  - Pre-commit: None

- [ ] 7. Logging and Error Handling

  **What to do**:
  - Create `src/utils/logger.py` with logging configuration:
    - Configure logging format with timestamps
    - Support different log levels (DEBUG, INFO, WARNING, ERROR)
    - Support file and console logging
  - Create `src/exceptions.py` with custom exceptions:
    - `CrawlerError` - Base exception for crawler errors
    - `APIError` - Exception for API errors
    - `RateLimitError` - Exception for rate limit exceeded
    - `CacheError` - Exception for cache errors
  - Create tests in `tests/test_logging.py`:
    - Test logging at different levels
    - Test custom exceptions

  **Must NOT do**:
  - Do NOT use print statements for logging
  - Do NOT create unnecessary exception classes

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple utility classes with well-defined behavior
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4, 5, 6)
  - **Blocks**: All subsequent tasks (logging is used everywhere)
  - **Blocked By**: None (can start immediately)

  **References**:
  - `AGENTS.md` - Error handling guidelines
  - `https://docs.python.org/3/library/logging.html` - Python logging documentation

  **Acceptance Criteria**:
  - [ ] `src/utils/logger.py` created with logging configuration
  - [ ] `src/exceptions.py` created with custom exceptions
  - [ ] Tests created in `tests/test_logging.py`
  - [ ] `pytest tests/test_logging.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Logger configuration
    Tool: Bash (python)
    Preconditions: logger.py created
    Steps:
      1. python -c "from src.utils.logger import get_logger; logger = get_logger('test'); logger.info('Test message'); print('Logger works')"
      2. Verify no errors
    Expected Result: Logger works without errors
    Failure Indicators: Import or configuration errors
    Evidence: .sisyphus/evidence/task-7-logger.txt

  Scenario: Custom exceptions
    Tool: Bash (python)
    Preconditions: exceptions.py created
    Steps:
      1. python -c "from src.exceptions import CrawlerError, APIError, RateLimitError; raise CrawlerError('test')"
      2. Verify exception is raised correctly
    Expected Result: Custom exceptions work correctly
    Failure Indicators: Import errors or incorrect behavior
    Evidence: .sisyphus/evidence/task-7-exceptions.txt

  Scenario: Test execution
    Tool: Bash
    Preconditions: test_logging.py created
    Steps:
      1. pytest tests/test_logging.py -v
      2. Verify all tests pass
    Expected Result: All tests pass
    Failure Indicators: Test failures
    Evidence: .sisyphus/evidence/task-7-tests.txt
  ```

  **Evidence to Capture**:
  - [ ] Logger configuration verification
  - [ ] Custom exceptions verification
  - [ ] Test execution results

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(utils): add logging and error handling`
  - Files: src/utils/logger.py, src/exceptions.py, tests/test_logging.py
  - Pre-commit: pytest tests/test_logging.py

- [ ] 8. PubMed Crawler

  **What to do**:
  - Create `src/crawlers/pubmed_crawler.py` with PubMedCrawler class:
    - Use metapub library for PubMed API access
    - Implement search with MeSH terms: `vitiligo[MeSH Terms]`
    - Implement pagination for large result sets (>1000 papers)
    - Use RateLimiter for 3 req/s (free tier)
    - Use Cache for API response caching
    - Handle errors gracefully with retries
    - Return list of Paper objects
  - Create tests in `tests/test_pubmed_crawler.py`:
    - Test search with mock API responses
    - Test pagination logic
    - Test rate limiting
    - Test error handling

  **Must NOT do**:
  - Do NOT download full text (copyright issues)
  - Do NOT exceed rate limits
  - Do NOT store API keys in code

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex integration with external API, requires careful error handling and rate limiting
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 3, 4, 5)
  - **Parallel Group**: Wave 2 (with Tasks 9, 10, 11, 12, 13, 14)
  - **Blocks**: Tasks 11, 15, 16
  - **Blocked By**: Tasks 3, 4, 5

  **References**:
  - Research findings: metapub library (148 stars), most production-ready
  - Research findings: PubMed E-utilities rate limits (3 req/s free, 10 req/s with key)
  - Research findings: MeSH term search syntax
  - `https://github.com/metapub/metapub` - metapub documentation
  - `src/models/paper.py` - Paper data model
  - `src/utils/rate_limiter.py` - RateLimiter utility
  - `src/utils/cache.py` - Cache utility

  **Acceptance Criteria**:
  - [ ] `src/crawlers/pubmed_crawler.py` created with PubMedCrawler class
  - [ ] Search with MeSH terms implemented
  - [ ] Pagination for large result sets implemented
  - [ ] Rate limiting implemented
  - [ ] Caching implemented
  - [ ] Error handling with retries implemented
  - [ ] Tests created in `tests/test_pubmed_crawler.py`
  - [ ] `pytest tests/test_pubmed_crawler.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: PubMed search with mock API
    Tool: Bash (python)
    Preconditions: pubmed_crawler.py created, tests with mocks
    Steps:
      1. pytest tests/test_pubmed_crawler.py::test_search -v
      2. Verify search returns Paper objects
    Expected Result: Search returns list of Paper objects
    Failure Indicators: Test failures or incorrect data
    Evidence: .sisyphus/evidence/task-8-search.txt

  Scenario: Pagination handling
    Tool: Bash (python)
    Preconditions: pubmed_crawler.py created
    Steps:
      1. pytest tests/test_pubmed_crawler.py::test_pagination -v
      2. Verify pagination works for >1000 results
    Expected Result: Pagination correctly handles large result sets
    Failure Indicators: Missing results or incorrect pagination
    Evidence: .sisyphus/evidence/task-8-pagination.txt

  Scenario: Rate limiting verification
    Tool: Bash (python)
    Preconditions: pubmed_crawler.py created
    Steps:
      1. pytest tests/test_pubmed_crawler.py::test_rate_limiting -v
      2. Verify rate limiting is enforced
    Expected Result: Rate limiting prevents exceeding 3 req/s
    Failure Indicators: Rate limit exceeded
    Evidence: .sisyphus/evidence/task-8-rate-limit.txt

  Scenario: Error handling
    Tool: Bash (python)
    Preconditions: pubmed_crawler.py created
    Steps:
      1. pytest tests/test_pubmed_crawler.py::test_error_handling -v
      2. Verify errors are handled gracefully
    Expected Result: Errors handled with retries
    Failure Indicators: Unhandled exceptions
    Evidence: .sisyphus/evidence/task-8-error.txt
  ```

  **Evidence to Capture**:
  - [ ] Search functionality verification
  - [ ] Pagination verification
  - [ ] Rate limiting verification
  - [ ] Error handling verification

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(crawlers): implement PubMed crawler`
  - Files: src/crawlers/pubmed_crawler.py, tests/test_pubmed_crawler.py
  - Pre-commit: pytest tests/test_pubmed_crawler.py

- [ ] 9. Semantic Scholar Crawler

  **What to do**:
  - Create `src/crawlers/semantic_scholar_crawler.py` with SemanticScholarCrawler class:
    - Use Semantic Scholar API (https://api.semanticscholar.org/)
    - Implement search for vitiligo papers
    - Use RateLimiter for 1000 req/s
    - Use Cache for API response caching
    - Handle errors gracefully with retries
    - Return list of Paper objects
  - Create tests in `tests/test_semantic_scholar_crawler.py`:
    - Test search with mock API responses
    - Test rate limiting
    - Test error handling

  **Must NOT do**:
  - Do NOT exceed rate limits
  - Do NOT store API keys in code

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration with external API, requires error handling
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 10, 11, 12, 13, 14)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 11, 15, 16
  - **Blocked By**: Tasks 3, 4, 5

  **References**:
  - Research findings: Semantic Scholar API (1000 req/s free)
  - Research findings: 214M+ papers, 2.49B+ citations
  - `https://api.semanticscholar.org/api-docs/` - Semantic Scholar API docs
  - `src/models/paper.py` - Paper data model
  - `src/utils/rate_limiter.py` - RateLimiter utility
  - `src/utils/cache.py` - Cache utility

  **Acceptance Criteria**:
  - [ ] `src/crawlers/semantic_scholar_crawler.py` created
  - [ ] Search implemented
  - [ ] Rate limiting implemented
  - [ ] Caching implemented
  - [ ] Error handling implemented
  - [ ] Tests created in `tests/test_semantic_scholar_crawler.py`
  - [ ] `pytest tests/test_semantic_scholar_crawler.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Semantic Scholar search
    Tool: Bash (python)
    Preconditions: semantic_scholar_crawler.py created
    Steps:
      1. pytest tests/test_semantic_scholar_crawler.py::test_search -v
      2. Verify search returns Paper objects
    Expected Result: Search returns list of Paper objects
    Failure Indicators: Test failures
    Evidence: .sisyphus/evidence/task-9-search.txt

  Scenario: Rate limiting verification
    Tool: Bash (python)
    Preconditions: semantic_scholar_crawler.py created
    Steps:
      1. pytest tests/test_semantic_scholar_crawler.py::test_rate_limiting -v
      2. Verify rate limiting is enforced
    Expected Result: Rate limiting prevents exceeding 1000 req/s
    Failure Indicators: Rate limit exceeded
    Evidence: .sisyphus/evidence/task-9-rate-limit.txt
  ```

  **Evidence to Capture**:
  - [ ] Search functionality verification
  - [ ] Rate limiting verification

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(crawlers): implement Semantic Scholar crawler`
  - Files: src/crawlers/semantic_scholar_crawler.py, tests/test_semantic_scholar_crawler.py
  - Pre-commit: pytest tests/test_semantic_scholar_crawler.py

- [ ] 10. ClinicalTrials.gov Crawler

  **What to do**:
  - Create `src/crawlers/clinical_trials_crawler.py` with ClinicalTrialsCrawler class:
    - Use ClinicalTrials.gov v2 API (https://clinicaltrials.gov/api/v2/studies)
    - Implement search for vitiligo trials
    - Filter for JAK inhibitor trials
    - Handle pagination with nextPageToken
    - Use Cache for API response caching
    - Handle errors gracefully
    - Return list of ClinicalTrial objects
  - Create tests in `tests/test_clinical_trials_crawler.py`:
    - Test search with mock API responses
    - Test pagination logic
    - Test error handling

  **Must NOT do**:
  - Do NOT exceed rate limits
  - Do NOT store API keys in code

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration with external API, requires error handling
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 9, 11, 12, 13, 14)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 11, 15, 16
  - **Blocked By**: Tasks 3, 4, 5

  **References**:
  - Research findings: ClinicalTrials.gov v2 API (free, JSON format)
  - Research findings: NCT ID, phase, status, interventions fields
  - `https://clinicaltrials.gov/data-api/api` - ClinicalTrials.gov API docs
  - `src/models/trial.py` - ClinicalTrial data model
  - `src/utils/cache.py` - Cache utility

  **Acceptance Criteria**:
  - [ ] `src/crawlers/clinical_trials_crawler.py` created
  - [ ] Search implemented
  - [ ] Pagination implemented
  - [ ] Caching implemented
  - [ ] Error handling implemented
  - [ ] Tests created in `tests/test_clinical_trials_crawler.py`
  - [ ] `pytest tests/test_clinical_trials_crawler.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: ClinicalTrials.gov search
    Tool: Bash (python)
    Preconditions: clinical_trials_crawler.py created
    Steps:
      1. pytest tests/test_clinical_trials_crawler.py::test_search -v
      2. Verify search returns ClinicalTrial objects
    Expected Result: Search returns list of ClinicalTrial objects
    Failure Indicators: Test failures
    Evidence: .sisyphus/evidence/task-10-search.txt

  Scenario: Pagination handling
    Tool: Bash (python)
    Preconditions: clinical_trials_crawler.py created
    Steps:
      1. pytest tests/test_clinical_trials_crawler.py::test_pagination -v
      2. Verify pagination works correctly
    Expected Result: Pagination correctly handles large result sets
    Failure Indicators: Missing results
    Evidence: .sisyphus/evidence/task-10-pagination.txt
  ```

  **Evidence to Capture**:
  - [ ] Search functionality verification
  - [ ] Pagination verification

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(crawlers): implement ClinicalTrials.gov crawler`
  - Files: src/crawlers/clinical_trials_crawler.py, tests/test_clinical_trials_crawler.py
  - Pre-commit: pytest tests/test_clinical_trials_crawler.py

- [ ] 11. Data Deduplication

  **What to do**:
  - Create `src/processors/deduplicator.py` with Deduplicator class:
    - Deduplicate papers from multiple sources (PubMed, Semantic Scholar)
    - Use DOI and PMID for deduplication
    - Merge metadata from different sources
    - Track source attribution
  - Create tests in `tests/test_deduplicator.py`:
    - Test deduplication with duplicate papers
    - Test metadata merging
    - Test source attribution

  **Must NOT do**:
  - Do NOT lose data during deduplication
  - Do NOT create overly complex merging logic

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex logic for merging data from multiple sources
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 8, 9, 10)
  - **Parallel Group**: Wave 2 (with Tasks 12, 13, 14)
  - **Blocks**: Task 14
  - **Blocked By**: Tasks 8, 9, 10

  **References**:
  - `src/models/paper.py` - Paper data model
  - Research findings: DOI and PMID as unique identifiers

  **Acceptance Criteria**:
  - [ ] `src/processors/deduplicator.py` created
  - [ ] Deduplication by DOI and PMID implemented
  - [ ] Metadata merging implemented
  - [ ] Source attribution implemented
  - [ ] Tests created in `tests/test_deduplicator.py`
  - [ ] `pytest tests/test_deduplicator.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Deduplication with duplicate papers
    Tool: Bash (python)
    Preconditions: deduplicator.py created
    Steps:
      1. pytest tests/test_deduplicator.py::test_deduplication -v
      2. Verify duplicate papers are removed
    Expected Result: Duplicate papers removed, unique papers retained
    Failure Indicators: Duplicates not removed or data lost
    Evidence: .sisyphus/evidence/task-11-dedup.txt

  Scenario: Metadata merging
    Tool: Bash (python)
    Preconditions: deduplicator.py created
    Steps:
      1. pytest tests/test_deduplicator.py::test_merge -v
      2. Verify metadata from different sources is merged
    Expected Result: Metadata correctly merged
    Failure Indicators: Data lost or incorrect merging
    Evidence: .sisyphus/evidence/task-11-merge.txt
  ```

  **Evidence to Capture**:
  - [ ] Deduplication verification
  - [ ] Metadata merging verification

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(processors): add data deduplication`
  - Files: src/processors/deduplicator.py, tests/test_deduplicator.py
  - Pre-commit: pytest tests/test_deduplicator.py

- [ ] 12. OpenAI Translator

  **What to do**:
  - Create `src/processors/translator.py` with Translator class:
    - Use OpenAI API for translation
    - Translate paper abstracts from English to Chinese
    - Handle rate limits and errors
    - Cache translations to avoid redundant API calls
  - Create tests in `tests/test_translator.py`:
    - Test translation with mock OpenAI API
    - Test error handling
    - Test caching

  **Must NOT do**:
  - Do NOT store API keys in code
  - Do NOT make real API calls in tests

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration with external API, requires error handling
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 11, 13, 14)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 13, 16
  - **Blocked By**: Task 3

  **References**:
  - Research findings: OpenAI API for translation
  - `https://platform.openai.com/docs/api-reference` - OpenAI API docs
  - `src/models/paper.py` - Paper data model
  - `src/utils/cache.py` - Cache utility

  **Acceptance Criteria**:
  - [ ] `src/processors/translator.py` created
  - [ ] Translation implemented
  - [ ] Error handling implemented
  - [ ] Caching implemented
  - [ ] Tests created in `tests/test_translator.py`
  - [ ] `pytest tests/test_translator.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Translation with mock API
    Tool: Bash (python)
    Preconditions: translator.py created
    Steps:
      1. pytest tests/test_translator.py::test_translate -v
      2. Verify translation returns Chinese text
    Expected Result: Translation returns Chinese text
    Failure Indicators: Test failures or incorrect language
    Evidence: .sisyphus/evidence/task-12-translate.txt

  Scenario: Error handling
    Tool: Bash (python)
    Preconditions: translator.py created
    Steps:
      1. pytest tests/test_translator.py::test_error_handling -v
      2. Verify errors are handled gracefully
    Expected Result: Errors handled with retries
    Failure Indicators: Unhandled exceptions
    Evidence: .sisyphus/evidence/task-12-error.txt
  ```

  **Evidence to Capture**:
  - [ ] Translation functionality verification
  - [ ] Error handling verification

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(processors): add OpenAI translator`
  - Files: src/processors/translator.py, tests/test_translator.py
  - Pre-commit: pytest tests/test_translator.py

- [ ] 13. OpenAI Summarizer

  **What to do**:
  - Create `src/processors/summarizer.py` with Summarizer class:
    - Use OpenAI API for summarization
    - Generate patient-friendly summaries in Chinese
    - Extract key information (treatment, results, conclusions)
    - Handle rate limits and errors
    - Cache summaries
  - Create tests in `tests/test_summarizer.py`:
    - Test summarization with mock OpenAI API
    - Test error handling
    - Test caching

  **Must NOT do**:
  - Do NOT store API keys in code
  - Do NOT make real API calls in tests
  - Do NOT generate medical advice

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration with external API, requires error handling
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 11, 12, 14)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 16
  - **Blocked By**: Tasks 3, 12

  **References**:
  - Research findings: OpenAI API for summarization
  - `https://platform.openai.com/docs/api-reference` - OpenAI API docs
  - `src/models/paper.py` - Paper data model
  - `src/utils/cache.py` - Cache utility

  **Acceptance Criteria**:
  - [ ] `src/processors/summarizer.py` created
  - [ ] Summarization implemented
  - [ ] Error handling implemented
  - [ ] Caching implemented
  - [ ] Tests created in `tests/test_summarizer.py`
  - [ ] `pytest tests/test_summarizer.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Summarization with mock API
    Tool: Bash (python)
    Preconditions: summarizer.py created
    Steps:
      1. pytest tests/test_summarizer.py::test_summarize -v
      2. Verify summarization returns Chinese summary
    Expected Result: Summarization returns patient-friendly Chinese summary
    Failure Indicators: Test failures or incorrect format
    Evidence: .sisyphus/evidence/task-13-summarize.txt

  Scenario: Error handling
    Tool: Bash (python)
    Preconditions: summarizer.py created
    Steps:
      1. pytest tests/test_summarizer.py::test_error_handling -v
      2. Verify errors are handled gracefully
    Expected Result: Errors handled with retries
    Failure Indicators: Unhandled exceptions
    Evidence: .sisyphus/evidence/task-13-error.txt
  ```

  **Evidence to Capture**:
  - [ ] Summarization functionality verification
  - [ ] Error handling verification

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(processors): add OpenAI summarizer`
  - Files: src/processors/summarizer.py, tests/test_summarizer.py
  - Pre-commit: pytest tests/test_summarizer.py

- [ ] 14. Data Export to JSON/Markdown

  **What to do**:
  - Create `src/exporters/json_exporter.py` with JSONExporter class:
    - Export deduplicated papers to JSON files
    - Organize by date, source, or topic
    - Include metadata (crawled_at, source, etc.)
  - Create `src/exporters/markdown_exporter.py` with MarkdownExporter class:
    - Export papers to Markdown files
    - Use frontmatter for metadata
    - Include Chinese translations and summaries
    - Add disclaimer: "本文不构成医疗建议"
  - Create tests in `tests/test_exporters.py`:
    - Test JSON export
    - Test Markdown export
    - Test file organization

  **Must NOT do**:
  - Do NOT create overly complex file organization
  - Do NOT include full text (copyright issues)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file writing with structured format
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 11, 12, 13)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 15
  - **Blocked By**: Task 11

  **References**:
  - `src/models/paper.py` - Paper data model
  - `AGENTS.md` - Markdown style guidelines
  - Research findings: JSON/Markdown storage for Phase 1

  **Acceptance Criteria**:
  - [ ] `src/exporters/json_exporter.py` created
  - [ ] `src/exporters/markdown_exporter.py` created
  - [ ] JSON export implemented
  - [ ] Markdown export implemented
  - [ ] Tests created in `tests/test_exporters.py`
  - [ ] `pytest tests/test_exporters.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: JSON export
    Tool: Bash (python)
    Preconditions: json_exporter.py created
    Steps:
      1. pytest tests/test_exporters.py::test_json_export -v
      2. Verify JSON files are created correctly
    Expected Result: JSON files created with correct structure
    Failure Indicators: Missing files or incorrect format
    Evidence: .sisyphus/evidence/task-14-json.txt

  Scenario: Markdown export
    Tool: Bash (python)
    Preconditions: markdown_exporter.py created
    Steps:
      1. pytest tests/test_exporters.py::test_markdown_export -v
      2. Verify Markdown files are created correctly
    Expected Result: Markdown files created with frontmatter and content
    Failure Indicators: Missing files or incorrect format
    Evidence: .sisyphus/evidence/task-14-markdown.txt
  ```

  **Evidence to Capture**:
  - [ ] JSON export verification
  - [ ] Markdown export verification

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(exporters): add JSON and Markdown exporters`
  - Files: src/exporters/json_exporter.py, src/exporters/markdown_exporter.py, tests/test_exporters.py
  - Pre-commit: pytest tests/test_exporters.py

- [ ] 15. Update Scheduler

  **What to do**:
  - Create `src/scheduler/update_scheduler.py` with UpdateScheduler class:
    - Schedule periodic updates (weekly/monthly)
    - Track last update time
    - Implement incremental updates (only fetch new papers)
    - Use date filters in API queries
    - Send notifications on update completion
  - Create tests in `tests/test_update_scheduler.py`:
    - Test scheduling logic
    - Test incremental updates
    - Test date filtering

  **Must NOT do**:
  - Do NOT implement real-time monitoring
  - Do NOT create overly complex scheduling logic

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex scheduling logic with state management
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 8, 9, 10)
  - **Parallel Group**: Wave 3 (with Tasks 16, 17, 18, 19)
  - **Blocks**: Task 16
  - **Blocked By**: Tasks 8, 9, 10

  **References**:
  - `src/crawlers/pubmed_crawler.py` - PubMed crawler
  - `src/crawlers/semantic_scholar_crawler.py` - Semantic Scholar crawler
  - `src/crawlers/clinical_trials_crawler.py` - ClinicalTrials.gov crawler
  - Research findings: Incremental update strategy

  **Acceptance Criteria**:
  - [ ] `src/scheduler/update_scheduler.py` created
  - [ ] Periodic scheduling implemented
  - [ ] Incremental updates implemented
  - [ ] Date filtering implemented
  - [ ] Tests created in `tests/test_update_scheduler.py`
  - [ ] `pytest tests/test_update_scheduler.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Scheduling logic
    Tool: Bash (python)
    Preconditions: update_scheduler.py created
    Steps:
      1. pytest tests/test_update_scheduler.py::test_scheduling -v
      2. Verify scheduling works correctly
    Expected Result: Scheduling correctly plans next update
    Failure Indicators: Incorrect scheduling
    Evidence: .sisyphus/evidence/task-15-schedule.txt

  Scenario: Incremental updates
    Tool: Bash (python)
    Preconditions: update_scheduler.py created
    Steps:
      1. pytest tests/test_update_scheduler.py::test_incremental -v
      2. Verify only new papers are fetched
    Expected Result: Incremental updates fetch only new papers
    Failure Indicators: Duplicate papers or missing new papers
    Evidence: .sisyphus/evidence/task-15-incremental.txt
  ```

  **Evidence to Capture**:
  - [ ] Scheduling logic verification
  - [ ] Incremental updates verification

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(scheduler): add update scheduler`
  - Files: src/scheduler/update_scheduler.py, tests/test_update_scheduler.py
  - Pre-commit: pytest tests/test_update_scheduler.py

- [ ] 16. CLI Interface

  **What to do**:
  - Create `src/cli.py` with CLI interface:
    - Use argparse or click for command-line parsing
    - Commands:
      - `crawl-pubmed --query "vitiligo" --output data/raw/pubmed.json`
      - `crawl-scholar --query "vitiligo" --output data/raw/scholar.json`
      - `crawl-trials --condition "vitiligo" --output data/raw/trials.json`
      - `process --input data/raw/ --output data/processed/`
      - `update --last-update 2024-01-01`
    - Add help text and examples
  - Create tests in `tests/test_cli.py`:
    - Test each command
    - Test argument parsing
    - Test error handling

  **Must NOT do**:
  - Do NOT create overly complex CLI
  - Do NOT add unnecessary commands

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration of multiple components into CLI
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 8, 9, 10, 12, 13)
  - **Parallel Group**: Wave 3 (with Tasks 15, 17, 18, 19)
  - **Blocks**: Task 18
  - **Blocked By**: Tasks 8, 9, 10, 12, 13

  **References**:
  - `src/crawlers/` - All crawlers
  - `src/processors/` - All processors
  - `src/exporters/` - All exporters
  - `https://docs.python.org/3/library/argparse.html` - argparse documentation

  **Acceptance Criteria**:
  - [ ] `src/cli.py` created with CLI interface
  - [ ] All commands implemented
  - [ ] Help text and examples added
  - [ ] Tests created in `tests/test_cli.py`
  - [ ] `pytest tests/test_cli.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: CLI crawl-pubmed command
    Tool: Bash
    Preconditions: cli.py created
    Steps:
      1. python -m src.cli crawl-pubmed --query "vitiligo" --output test_output.json --limit 10
      2. Verify JSON file is created
      3. cat test_output.json → verify contains paper data
    Expected Result: JSON file created with paper data
    Failure Indicators: Command fails or no output
    Evidence: .sisyphus/evidence/task-16-cli-pubmed.txt

  Scenario: CLI process command
    Tool: Bash
    Preconditions: cli.py created, test data available
    Steps:
      1. python -m src.cli process --input data/raw/ --output data/processed/
      2. Verify processed files are created
    Expected Result: Processed files created
    Failure Indicators: Command fails or no output
    Evidence: .sisyphus/evidence/task-16-cli-process.txt
  ```

  **Evidence to Capture**:
  - [ ] CLI crawl-pubmed command verification
  - [ ] CLI process command verification

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(cli): add CLI interface`
  - Files: src/cli.py, tests/test_cli.py
  - Pre-commit: pytest tests/test_cli.py

- [ ] 17. Configuration Management

  **What to do**:
  - Create `src/config.py` with configuration management:
    - Load environment variables from .env file
    - Validate required environment variables
    - Provide default values for optional settings
    - Support different environments (dev, prod)
  - Create tests in `tests/test_config.py`:
    - Test environment variable loading
    - Test validation
    - Test default values

  **Must NOT do**:
  - Do NOT commit actual API keys
  - Do NOT hardcode configuration values

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple configuration loading and validation
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 15, 16, 18, 19)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 18
  - **Blocked By**: Task 2

  **References**:
  - `configs/.env.example` - Environment variable template
  - `https://pypi.org/project/python-dotenv/` - python-dotenv documentation

  **Acceptance Criteria**:
  - [ ] `src/config.py` created
  - [ ] Environment variable loading implemented
  - [ ] Validation implemented
  - [ ] Default values provided
  - [ ] Tests created in `tests/test_config.py`
  - [ ] `pytest tests/test_config.py` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Configuration loading
    Tool: Bash (python)
    Preconditions: config.py created, .env file exists
    Steps:
      1. python -c "from src.config import Config; config = Config(); print(config.NCBI_API_KEY)"
      2. Verify environment variables are loaded
    Expected Result: Environment variables loaded correctly
    Failure Indicators: Import errors or missing values
    Evidence: .sisyphus/evidence/task-17-config.txt

  Scenario: Validation
    Tool: Bash (python)
    Preconditions: config.py created
    Steps:
      1. pytest tests/test_config.py::test_validation -v
      2. Verify validation works
    Expected Result: Validation catches missing required variables
    Failure Indicators: Validation not working
    Evidence: .sisyphus/evidence/task-17-validation.txt
  ```

  **Evidence to Capture**:
  - [ ] Configuration loading verification
  - [ ] Validation verification

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(config): add configuration management`
  - Files: src/config.py, tests/test_config.py
  - Pre-commit: pytest tests/test_config.py

- [ ] 18. Documentation

  **What to do**:
  - Update `README.md` with:
    - Project overview and goals
    - Installation instructions
    - Usage examples for all CLI commands
    - Configuration guide
    - Development setup
  - Create `docs/CONTRIBUTING.md` with:
    - How to contribute
    - Code style guidelines
    - Testing guidelines
    - Pull request process
  - Create `docs/API.md` with:
    - API documentation for each module
    - Examples and use cases

  **Must NOT do**:
  - Do NOT create overly long documentation
  - Do NOT include sensitive information

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation writing task
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 15, 16, 17, 19)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 19
  - **Blocked By**: All previous tasks

  **References**:
  - `AGENTS.md` - Project guidelines
  - `src/cli.py` - CLI interface
  - `src/config.py` - Configuration management

  **Acceptance Criteria**:
  - [ ] `README.md` updated with complete documentation
  - [ ] `docs/CONTRIBUTING.md` created
  - [ ] `docs/API.md` created
  - [ ] All documentation is clear and accurate

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: README completeness
    Tool: Bash
    Preconditions: README.md updated
    Steps:
      1. cat README.md → verify contains installation, usage, configuration
      2. grep -E "(Installation|Usage|Configuration)" README.md → verify sections exist
    Expected Result: README contains all required sections
    Failure Indicators: Missing sections
    Evidence: .sisyphus/evidence/task-18-readme.txt

  Scenario: CONTRIBUTING guide
    Tool: Bash
    Preconditions: CONTRIBUTING.md created
    Steps:
      1. cat docs/CONTRIBUTING.md → verify contains contribution guidelines
      2. grep -E "(How to contribute|Code style|Testing)" docs/CONTRIBUTING.md → verify sections exist
    Expected Result: CONTRIBUTING contains all required sections
    Failure Indicators: Missing sections
    Evidence: .sisyphus/evidence/task-18-contributing.txt
  ```

  **Evidence to Capture**:
  - [ ] README completeness verification
  - [ ] CONTRIBUTING guide verification

  **Commit**: YES (groups with Wave 3)
  - Message: `docs: add comprehensive documentation`
  - Files: README.md, docs/CONTRIBUTING.md, docs/API.md
  - Pre-commit: None

- [ ] 19. Final Integration Test

  **What to do**:
  - Create `tests/test_integration.py` with end-to-end tests:
    - Test complete workflow: crawl → process → export
    - Test with small dataset (10 papers)
    - Verify all components work together
    - Test error scenarios
  - Run full test suite and verify all tests pass
  - Run linting and type checking
  - Generate coverage report

  **Must NOT do**:
  - Do NOT make real API calls in tests
  - Do NOT skip any test scenarios

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex integration testing across all components
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on all previous tasks)
  - **Parallel Group**: Wave 3
  - **Blocks**: Final Verification Wave
  - **Blocked By**: All previous tasks

  **References**:
  - All previous modules and tests

  **Acceptance Criteria**:
  - [ ] `tests/test_integration.py` created
  - [ ] End-to-end tests implemented
  - [ ] All tests pass: `pytest` → PASS
  - [ ] Linting passes: `ruff check src/ tests/` → PASS
  - [ ] Type checking passes: `mypy src/` → PASS
  - [ ] Coverage ≥80%: `pytest --cov=src` → ≥80%

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: End-to-end workflow
    Tool: Bash
    Preconditions: All components implemented
    Steps:
      1. pytest tests/test_integration.py::test_end_to_end -v
      2. Verify complete workflow works
    Expected Result: End-to-end test passes
    Failure Indicators: Test failures
    Evidence: .sisyphus/evidence/task-19-e2e.txt

  Scenario: Full test suite
    Tool: Bash
    Preconditions: All tests created
    Steps:
      1. pytest --cov=src --cov-report=term
      2. Verify all tests pass and coverage ≥80%
    Expected Result: All tests pass, coverage ≥80%
    Failure Indicators: Test failures or low coverage
    Evidence: .sisyphus/evidence/task-19-full-suite.txt

  Scenario: Code quality checks
    Tool: Bash
    Preconditions: All code written
    Steps:
      1. ruff check src/ tests/
      2. mypy src/
      3. Verify no errors
    Expected Result: All checks pass
    Failure Indicators: Linting or type errors
    Evidence: .sisyphus/evidence/task-19-quality.txt
  ```

  **Evidence to Capture**:
  - [ ] End-to-end workflow verification
  - [ ] Full test suite results
  - [ ] Code quality check results

  **Commit**: YES (groups with Wave 3)
  - Message: `test(integration): add final integration tests`
  - Files: tests/test_integration.py
  - Pre-commit: pytest

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
>
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check src/ tests/` + `mypy src/` + `pytest`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (features working together, not isolation). Test edge cases: empty state, invalid input, rapid actions. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `chore(setup): initialize project structure and dependencies` — all Wave 1 files
- **Wave 2**: `feat(crawlers): implement PubMed, Semantic Scholar, and ClinicalTrials.gov crawlers` — all Wave 2 files
- **Wave 3**: `feat(integration): add update scheduler, CLI, and documentation` — all Wave 3 files

---

## Success Criteria

### Verification Commands
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_pubmed_crawler.py

# Run with coverage
pytest --cov=src --cov-report=html

# Lint code
ruff check src/ tests/

# Type check
mypy src/

# Run crawler
python -m src.crawlers.pubmed_crawler --query "vitiligo" --output data/raw/pubmed.json

# Process data
python scripts/process_papers.py --input data/raw/pubmed.json --output data/processed/
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] Code passes ruff and mypy
- [ ] Data successfully collected from all sources
- [ ] OpenAI translation and summarization working
- [ ] JSON/Markdown files generated correctly
