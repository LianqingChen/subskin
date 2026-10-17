# AGENTS.md - SubSkin Project Guide

> This document provides coding agents with the context needed to work effectively in this repository.

## 🚨 CRITICAL: Staging vs Production Deployment Workflow

**This workflow is MANDATORY. Violations are zero-tolerance. Every agent working in this project MUST follow it.**

---

### 🔴 Zero-Tolerance Deployment Principles (3 Rules)

These 3 rules are the foundation of SubSkin's deployment workflow. **Every agent — regardless of tool, model, or framework — MUST follow them.**

**Rule 1: Sync Baseline — Staging = Production (except 4 intentional differences)**

As of **2026-06-08**, staging and production are EXACTLY identical in code content. The ONLY intentional differences are:
1. Nav bar color: staging = 深蓝 `bg-slate-800`, production = 天青色渐变 `from-primary-700 to-primary-500`（白字）
2. PWA app name: staging = "SubSkin [STAGING]", production = "SubSkin - 白癜风病友的AI手帐和分享社区"
3. version.json `env` field: staging = `"staging"`, production = `"production"`
4. Update banner text: staging = "测试环境有新版本可用", production = "有新版本可用"

**Everything else (功能、页面、组件、逻辑、API) is 100% identical.** This baseline is recorded in `DEPLOY_LOG.md` under "Environment Sync Baseline". Any future change must start from this synced state.

**Rule 2: All Changes Must Go to Staging FIRST — Then Production After User Confirmation**

- Every code change (frontend, backend, config) MUST be deployed to staging first
- After staging deployment, tell the user: "已部署到测试环境" + list changes
- **NEVER deploy to production without the user's explicit confirmation**
- The user must test on staging (https://staging.subskin.cn) and then say "推送到正式环境" or "更新到正式环境"

**Rule 3: "推送到正式环境" / "更新到正式环境" = FULL SYNC, Not Incremental**

When the user says "推送到正式环境" or "更新到正式环境", it means:
- **Find the last production deployment timestamp** (in `DEPLOY_LOG.md`)
- **Collect ALL changes since that timestamp** — every staging build, every backend restart
- **Deploy ALL of them to production as ONE batch** — not just the latest change
- This is a **full sync** operation: staging → production = complete code alignment
- After production deployment, rebuild staging from same source to ensure both environments remain identical

**NEVER do selective/partial production deployments.** If 5 changes accumulated on staging, ALL 5 go to production together.

---

### Architecture Overview

```
                    ┌──────────────────────────────────────────┐
                    │           Shared Backend (port 8000)     │
                    │  FastAPI + SQLAlchemy (single instance)  │
                    │  ┌────────────────────────────────────┐  │
                    │  │  SQLite DB (single shared database) │  │
                    │  └────────────────────────────────────┘  │
                    └───────▲──────────────────────▲───────────┘
                            │                      │
                    /api/*  │              /api/*  │
                            │                      │
┌───────────────────────────┴──┐    ┌──────────────┴──────────────┐
│  Staging Frontend            │    │  Production Frontend        │
│  staging.subskin.cn          │    │  subskin.cn                 │
│  /usr/share/nginx/html/      │    │  /usr/share/nginx/html/     │
│    subskin-staging/          │    │    subskin/                 │
│  Nav: 深蓝色 bg-slate-800   │    │  Nav: 天青色渐变(primary)   │
│  PWA: "SubSkin [STAGING]"   │    │  PWA: "SubSkin - 白癜风病友的AI手帐和分享社区" │
│  __APP_ENV__ = 'staging'    │    │  __APP_ENV__ = 'production' │
└──────────────────────────────┘    └─────────────────────────────┘
```

**⚠️ Critical implications of shared backend:**
- Frontend-only changes (UI, CSS, pages) are SAFE to deploy independently
- Backend changes (API, DB schema) affect BOTH environments simultaneously — there is no staging backend
- Database migrations are IMMEDIATE and IRREVERSIBLE for all users
- Any backend change MUST be treated with extra caution

---

### The Two Environments

| Environment | URL | Frontend Build Command | Deploy Target |
|-------------|-----|------------------------|---------------|
| **Staging** | https://staging.subskin.cn | `npm run build` | `/usr/share/nginx/html/subskin-staging/` |
| **Production** | https://subskin.cn | `npm run deploy:prod` | `/usr/share/nginx/html/subskin/` |

**Shared between both:**
- Backend: `uvicorn` on `127.0.0.1:8000` (single instance, single DB)
- Nginx: `subskin.conf` (prod) + `subskin-staging.conf` (staging)

---

### Mandatory Workflow (NO EXCEPTIONS)

#### ⚡ IMMEDIATE STAGING DEPLOY (ZERO-TOLERANCE)

**After EVERY code change — no matter how small — the agent MUST immediately deploy to staging. Do NOT wait for the user to ask. Staging exists for rapid testing; every second of delay defeats its purpose.**

| Change Type | Action | Command |
|---|---|---|
| **Frontend** (`.vue`, `.ts`, `.css`, `types`, `composables`, etc.) | Rebuild & deploy | `npm run build` in `/root/subskin/web/app` |
| **Backend** (`.py`) | Restart uvicorn | `systemctl restart subskin-backend` |
| **Both** | Do both | Build first, then restart |

**Post-deploy checklist (MANDATORY):**
- [ ] `cat /usr/share/nginx/html/subskin-staging/version.json` — verify `buildTime` updated
- [ ] `curl -s http://127.0.0.1:8000/api/health` — verify backend healthy
- [ ] Record changes in `DEPLOY_LOG.md`

**Why this is non-negotiable:**
- Staging is the ONLY way to verify changes before production
- Delayed staging deploys create a false sense of "tested"
- Testers must see changes within SECONDS of code completion
- If you can't deploy to staging, you haven't finished the task

```
┌──────────────────────────────────────────────────────────────────────┐
│  STAGE 1: DEVELOP & DEPLOY TO STAGING                                │
│                                                                      │
│  1. Make code changes                                                │
│     - Frontend: /root/subskin/web/app/src/                          │
│     - Backend:  /root/subskin/web/backend/                          │
│  2. If backend changes exist:                                        │
│     ⚠️  ALERT user: "后端修改会影响正式环境，请确认"                │
│     - Backend changes go live IMMEDIATELY for all users              │
│     - There is NO staging backend — backend = production             │
│  3. Record each change in DEPLOY_LOG.md "Pending Changes"           │
│  4. Run `npm run build` → deploys to staging.subskin.cn             │
│  5. Tell user: "已部署到测试环境" + list pending changes            │
│  6. Staging PWA auto-prompts testers to update                      │
├──────────────────────────────────────────────────────────────────────┤
│  STAGE 2: USER TESTING ON STAGING                                    │
│                                                                      │
│  7. User tests on https://staging.subskin.cn                         │
│  8. If issues found → fix and re-deploy to staging (back to Stage 1)│
│  9. If all OK → user explicitly says:                                │
│     "推送到正式环境" / "更新到正式环境" / "deploy to prod"           │
├──────────────────────────────────────────────────────────────────────┤
│  STAGE 3: DEPLOY TO PRODUCTION (ONLY after Stage 2)                  │
│                                                                      │
│  10. Show user the FULL "Pending Changes" list from DEPLOY_LOG.md   │
│  11. Get explicit confirmation for the complete change set           │
│  12. Run `npm run deploy:prod` → deploys to subskin.cn             │
│  13. Verify production deployment:                                   │
│      - Check version.json buildTime matches                         │
│      - Check key pages load correctly                               │
│  14. Move ALL items from "Pending" → "Production History" in log    │
│  15. Tell user: "已部署到正式环境" + list all changes pushed        │
│  16. Production PWA auto-prompts all users to update                │
├──────────────────────────────────────────────────────────────────────┤
│  STAGE 4: POST-DEPLOY VERIFICATION                                   │
│                                                                      │
│  17. Verify production site is functional:                           │
│      - https://subskin.cn loads correctly                           │
│      - PWA update banner appears for existing users                  │
│      - Key user flows work (login, AI chat, community, etc.)        │
│  18. If critical issue found:                                        │
│      - Assess severity (see Rollback section below)                 │
│      - Fix on staging first → then emergency production deploy      │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Change Tracking via DEPLOY_LOG.md

**Every code change MUST be recorded in `/root/subskin/DEPLOY_LOG.md`** before building.

The file has three sections:

1. **Pending Changes** — Changes deployed to staging but NOT yet to production. **Accumulates** across multiple staging deploys.
2. **Production Deployment History** — Record of what was pushed to production, with buildTime reference.
3. **Staging Deployment History** — Record of each staging build.

**Rules:**

| Action | What to do |
|--------|-----------|
| Deploy to staging | Add row(s) to "Pending Changes" with description + buildTime |
| Multiple staging deploys | Keep ADDING to "Pending Changes" — don't remove previous entries |
| Deploy to production | Move ALL pending items → "Production History" as ONE batch. Clear "Pending Changes" |
| Hotfix to production | Same workflow — staging first, then prod. Record in log. |

**Why this matters**: Multiple staging deploys may accumulate before a single production push. The log ensures NOTHING is forgotten or missed when pushing to production. The user must see the COMPLETE list of changes before approving.

---

### Update Notification Rules

| Event | Staging Users | Production Users |
|-------|--------------|-----------------|
| Frontend deployed to staging | ✅ Auto-prompt: "测试环境有新版本可用" | ❌ No notification |
| Frontend deployed to production | N/A | ✅ Auto-prompt: "有新版本可用" |
| Backend restarted/changed | Immediate for all | Immediate for all (shared backend) |
| Hotfix/emergency | Same workflow: staging → prod | Same workflow |

**Key principle**: Staging updates are for testing. Production updates are for all users. These are SEPARATE events with SEPARATE notifications.

---

### Rollback & Emergency Procedures

#### Frontend Rollback (Safe)

If a production frontend deploy has critical issues:

1. **Quick rollback**: Revert code changes → rebuild → `npm run deploy:prod`
2. **Previous version**: The service worker's `clientsClaim: true` means the old version is gone once the new SW activates. Users who haven't refreshed may still be on the old version briefly.
3. **PWA cache**: Some users may be on the old version for up to 30 seconds (version.json polling interval) before seeing the update banner.

#### Backend Rollback (Dangerous)

Since the backend is shared (no staging backend):

1. **Database schema changes are IRREVERSIBLE** — columns added cannot be removed without data loss
2. **API behavior changes affect all users immediately** — there's no gradual rollout
3. **If a backend change breaks production**: Revert code → restart uvicorn → verify
4. **Emergency restart**: `systemctl restart subskin-backend` or `pkill -f uvicorn && bash /root/subskin/web/backend/start.sh`

#### Severity Assessment

| Severity | Example | Action |
|----------|---------|--------|
| 🔴 P0 Critical | Site down, data loss, security breach | Emergency fix → staging → prod ASAP. Notify user immediately. |
| 🟠 P1 High | Major feature broken, many users affected | Fix → staging → prod within hours. User approval required. |
| 🟡 P2 Medium | Minor feature broken, workaround exists | Fix → staging → normal workflow. No rush. |
| 🟢 P3 Low | Cosmetic issue, edge case | Fix → staging → normal workflow. Next production push. |

---

### Backend Change Protocol

**Because there is NO staging backend, backend changes require EXTRA caution:**

1. **Before making backend changes**: Tell user "⚠️ 后端修改会立即影响所有正式环境用户"
2. **Database schema changes**: Must be additive only (add columns/tables, never remove or rename). Use migration scripts in `/root/subskin/web/backend/`.
3. **API behavior changes**: Keep backward compatibility. New fields = OK. Removing/changing fields = breaking change.
4. **Configuration changes**: Backend `.env` is shared. Any change affects both staging and production API responses.

---

### Pre-Deploy Checklist

Before deploying to production, verify ALL of the following:

```
□ All changes recorded in DEPLOY_LOG.md
□ Staging tested and confirmed by user
□ `npm run type-check` passes (vue-tsc --noEmit)
□ `npm run build` succeeds without errors
□ version.json buildTime is updated
□ Pending Changes list reviewed with user
□ User has explicitly approved production deployment
```

---

### ⛔ NEVER DO THIS (Zero Tolerance)

- **NEVER** run `npm run deploy:prod` without user's explicit verbal confirmation
- **NEVER** deploy to production before deploying to staging first
- **NEVER** assume the user wants production deployment — even if it "seems obvious"
- **NEVER** skip staging verification — every change must be tested on staging first
- **NEVER** deploy staging and production in the same command or step
- **NEVER** deploy to staging without recording the change in DEPLOY_LOG.md
- **NEVER** push to production without reviewing the full "Pending Changes" list with the user
- **NEVER** make destructive DB schema changes (drop column, rename table) — additive only
- **NEVER** ignore backend change warnings — shared backend = immediate production impact

### Build Configs

| Config File | Environment | Output Dir | `__APP_ENV__` |
|-------------|-------------|------------|---------------|
| `vite.config.ts` | Staging (default) | `/usr/share/nginx/html/subskin-staging/` | `'staging'` |
| `vite.config.staging.ts` | Staging (explicit) | `/usr/share/nginx/html/subskin-staging/` | `'staging'` |
| `vite.config.prod.ts` | Production | `/usr/share/nginx/html/subskin/` | `'production'` |

### How to Tell Staging from Production

| Feature | Staging | Production |
|---------|---------|------------|
| Nav bar | Dark blue (`bg-slate-800`) | 天青色渐变 (`from-primary-700 to-primary-500`，白字) |
| PWA name | "SubSkin [STAGING]" | "SubSkin - 白癜风病友的AI手帐和分享社区" |
| PWA theme_color | `#1e293b` (slate — status bar) | `#26A69A` (teal — status bar) |
| PWA background_color | `#ffffff` (white — same as prod) | `#ffffff` (white) |
| version.json | `{"env":"staging"}` | `{"env":"production"}` |
| `__APP_ENV__` | `'staging'` | `'production'` |

## 🔧 Available Skills (统一 Skill 库)

**所有 agent 工具共享同一个 skill 目录：`.agents/skills/`。** 这是本项目唯一的 skill 存放位置。

任何 agent（Claude Code、OpenCode、Codex、Hermes、Cursor、Windsurf、Qoder 等）进入本项目时，都应读取并遵守这些 skill。禁止在其他位置（如 `web/.agents/`、`.opencode/skills/`、`.claude/skills/`）创建竞争性 skill 副本。

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `frontend-architect` | 前端架构审查与质量标准 | 任何前端代码审查、新功能、新页面、新组件、重构 |
| `backend-architect` | 后端架构审查与质量标准 | 任何后端代码审查、新增API、服务层修改、Python代码 |
| `ui-audit` | UI/UX 一致性审计 | 设计审查、视觉一致性检查、pre-merge UI QA |
| `brainstorming` | 需求探索与设计 | 创建功能、构建组件前 |
| `planning-with-files` | 文件化任务规划 | 复杂多步骤任务 |
| `deploy-verification` | 部署验证（staging vs production） | 每次部署后对比环境一致性 |
| `pwa-verification` | PWA 架构验证 | 部署后验证 manifest/SW/version.json |
| `vue-tsc-guard` | TypeScript 类型守门员 | 编辑 Vue/TS 文件后防止类型错误阻塞部署 |
| `nginx-config` | Nginx 配置管理 | 修改 nginx 配置、SSL、路由、反向代理 |
| `llm-testing` | AI/LLM 功能测试 | RAG 向量化、智能问答、VASI 评估测试 |
| `3d-model-work` | 3D 模型工作 | 数字人/熊猫模型的加载和渲染 |

**IMPORTANT**: Before any frontend work, load the `frontend-architect` skill to ensure compliance with project standards. Before any backend work, load the `backend-architect` skill to ensure compliance with project standards.

### Skill 维护规则

1. **唯一位置**: 所有 skill 必须放在 `.agents/skills/<skill-name>/SKILL.md`
2. **统一格式**: 每个 skill 必须有 YAML frontmatter（`name` + `description`），禁止 `compatibility` 字段绑定特定工具
3. **新增 skill**: 任何 agent 新增 skill 时必须放在此目录，并更新本表
4. **禁止重复**: 不允许在子目录（`web/`、`src/` 等）中创建独立的 `.agents/skills/` 分支
5. **工具无关**: Skill 内容不得引用特定 AI 工具的私有 API 或命令格式

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
7. **SPA navigation**: Use `<router-link>` for internal navigation. Use `<a href>` ONLY for external links (e.g., 论文/文献引用源). Never use `<a href="#">` or `@click.prevent` + `router.push()` for internal navigation — it causes blank-page bugs.
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
| 🟢 L1-Public | 知识库内容、公开帖子、匿名统计数据 | 可公开访问，但数据采集仍需注明来源。 |

**Hard Rules (零容忍):**

1. **No L4/L3 data in git**: 密码、token、身份证号、银行卡号、**手机号、邮箱、真实姓名** **永远不提交到 Git**，不放 `.env.example`，不写测试 fixture，不进 PR review 截图。所有敏感信息必须通过环境变量或 `.env` 文件（已加入 `.gitignore`）传入。
2. **No hardcoded PII in scripts**: 脚本文件中禁止硬编码任何用户手机号、邮箱、真实姓名等个人数据。必须使用环境变量（如 `os.environ.get("VAR_NAME")`）引用。`.env.example` 中只能放占位值。
3. **L3 data must be redacted in API responses**: 手机号脱敏 `138****1234`，邮箱脱敏 `li***@example.com`，病情图片 URL 仅所有者可访问（需鉴权）。
4. **Never expose user data to other users**: 用户 A 不能看到用户 B 的 L3 数据，除非 B 主动授权分享。
5. **User-authorized sharing requires immutable audit trail**: 用户每执行一次「公开」「分享」「授权」操作，必须创建不可修改、不可删除的审计记录（`AuditLog` 表），记录 who/what/when/scope/revokeable。
6. **Right to be forgotten**: 用户请求删除账户时，必须在 30 天内彻底删除所有个人数据（L2-L4），仅保留匿名化统计数据。
7. **HTTPS everywhere**: 所有 API 必须 HTTPS，所有前端资源 HTTPS。
8. **Minimize data collection**: 只收集功能必需的数据，不收集「以后可能有用」的数据。
9. **`privacy_mode` naming warning**: DB 列 `privacy_mode` 语义为 `True = 可被发现 (open)`，`False = 隐藏 (hidden)`——与字面含义相反。API 层已添加 `is_discoverable` 别名。新代码应优先使用 `is_discoverable`，避免因 "privacy mode" 的字面含义写出反逻辑。

### Data Handling
- Respect robots.txt and rate limits
- Cache API responses to minimize costs
- Store raw data before processing (for reproducibility)
- Include metadata (source, timestamp, version)

## UI/Design Unity Principles (MANDATORY)

> 📘 **Authoritative Design System Specification**: `/root/subskin/docs/specs/2026-10-17-subskin-design-system.md`
> Every agent modifying or creating any page, component, external share view, or generated poster MUST read and strictly follow `docs/specs/2026-10-17-subskin-design-system.md`.

All new features and modifications MUST follow these principles to maintain a unified, consistent experience inspired by **Cursor & GitHub's modern tech aesthetic combined with clinical warmth**:

1. **Consistent Container Widths & Responsive Layout**: All content pages use the shared `.page` (`72rem`), `.page-wide` (`80rem`), or `.page-narrow` (`48rem`) classes defined in `web/app/src/styles/main.css` as the outer container — NEVER hand-write `max-w-* px-*` or hardcode `max-width: NNNpx` in scoped CSS. Page backgrounds must inherit the app canvas (`#f6f8fa` in light mode, `#0b0f17` in dark mode; never hardcode `#f5f7fa`).
   - **Desktop navigation**: `1024–1279px` = `72px` icon rail (icon + small label), `≥1280px` = full `224px` sidebar, `<1024px` = header + `BottomNav`. Width comes from `--app-sidebar-w`; fixed bottom bars MUST use `.app-fixed-x` (`left: var(--app-sidebar-w); right: 0;`) so they never cover the desktop sidebar.
   - **Bottom sheets & modals on desktop**: Mobile bottom sheets (`fixed inset-x-0 bottom-0`) MUST constrain width on tablet/desktop (`sm:max-w-md sm:mx-auto sm:bottom-6 sm:rounded-2xl`) so they never stretch across the full desktop screen.

2. **In-Page Navigation = Left Sidebar**: Page-internal navigation (tabs, categories, history lists) MUST use a collapsible left sidebar pattern on desktop (`md:` / `lg:` and up), consistent across all pages:
   - **Sidebar width**: `w-52` (208px) expanded, thin strip when collapsed
   - **Active item**: `bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium rounded-lg`
   - **Inactive item**: `text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg`
   - **Collapse toggle**: Small vertical bar with chevron icon at sidebar edge
   - **Mobile**: Horizontal scrollable tabs or drawer overlay (NEVER left sidebar on mobile)

3. **Naming Consistency (Single Source of Truth)**: Use the exact same module names across ALL surfaces (nav, title, header, body text, share sheets, and Canvas posters):
   - 功能模块命名以 `web/shared/site-modules.json` 和 `web/shared/page-names.json` 为**唯一事实来源**（当前在线模块：问答 `/`、日记 `/assessment`、发现 `/community`、同行 `/contribution`、就医经验 `/hospitals`、体检解读 `/assessment/exam`、调养 `/care`、个人中心 `/profile`）。前端导航（BottomNav / AppSidebar / AppHeader / 小白管家）与后端 AI 导航（`rag.py`）均从它派生，禁止硬编码其他模块名。
   - 旧命名（`白友圈`、`小白助手`、`小白追踪`、`小白社区`、`小白百科`、`小白手账`、`小白日记`、`AI病情日记`、`小白知识库`、`病情追踪`、`手帐`、`测评`、`医评`、`公益`）仅作后端搜索历史关键词别名，**严禁**作为 UI 或海报中的模块名。
   - 小白百科已下线（内容融入智能问答 / 小白管家），不得向用户透出独立百科入口或页面。
   - When referring to users within the community, "病友" is acceptable as a term of address.

4. **Theme Color System & Dark Mode Completeness**:
   - All primary/accent colors use CSS variables (`--color-primary-*`, refined clinical teal `#0d9488` / `#14b8a6` / `#0f766e`). NEVER hardcode hex colors like `#10b981`, `#34d399`, or Tailwind's `blue-*`/`purple-*`/`emerald-*` classes for brand UI. Use `primary-*` Tailwind classes instead.
   - Community category badges MUST use `getCategoryColor(name)` from `@/utils/colors`.
   - Every view, card, modal, input, and toast MUST have complete `dark:*` variants tested against the `#0b0f17` / `#111827` dark canvas.
   - Numerical metrics, scores, percentages, and dates MUST use `tabular-nums` (`font-variant-numeric: tabular-nums`).

5. **Component Patterns & Cross-Browser / WebView Compatibility**:
   - Reuse standard classes in `main.css`: `.card`, `.card-hover`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.control-slim`, `.menu-slim`, `.input-field`, `.surface-glass`, `.page-title`, `.section-title`.
   - **WeChat WebView & Huawei Browser rules**:
     - Always provide `vh` fallback before `dvh`/`svh` in custom CSS (`height: 100vh; height: 100dvh;`).
     - Always add `min-w-0` to `<input class="flex-1">` inside flex containers.
     - Include `"HarmonyOS Sans SC"` and `"PingFang SC"` in font stacks (including Canvas `ctx.font`).
     - **NEVER** call `ctx.roundRect()` directly in Canvas code (crashes older WeChat/Android WebViews); always use `traceRoundedRect` with `arcTo`.

6. **Unified External Share Pages & Generated Posters**:
   - All external share pages (`/share/report/:token`, `/collection/:slug`) and generated Canvas posters (`PageSharePoster.vue`, `SkinReportPoster.vue`, `DiaryWeeklyPoster.vue`, `render.ts`) MUST follow the same design tokens (`#0f766e` → `#0d9488` header gradient, `#f8fafc` inner cards, `#0f172a` titles, `'SubSkin · 白癜风病友的AI记录和分享社区'` brand subtitle, valid QR code routes, and medical disclaimer).

7. **AI Navigation Sync (MANDATORY)**: 小白管家（漂浮入口）+ 问答（`/`）is the central entry point for the entire website. When ANY new feature, page, or module is added, the following MUST be updated in sync:
   - `web/shared/site-modules.json` & `web/shared/page-names.json`
   - **System prompt** & **`SITE_FEATURE_KEYWORDS`** in `web/backend/services/rag.py`
   - **Navigation components** (`BottomNav.vue`, `AppSidebar.vue`, `AppHeader.vue`)
   - **Router** (`router/index.ts`): The route must exist before the AI can reference it

8. **Icon System — RemixIcon (MANDATORY)**: ALL icons across the project MUST use [RemixIcon](https://remixicon.com/) for visual consistency. NEVER use emoji characters (📱🔒📷✨🔥 etc.) or inline SVGs for UI icons.
   - **Package**: `remixicon` (CSS font approach, imported in `main.ts`)
   - **Usage**: `<i class="ri-icon-name"></i>` (line variant) or `<i class="ri-icon-name-fill"></i>` (filled variant)
   - **Loading spinners**: Always use `<i class="ri-loader-4-line animate-spin"></i>` instead of inline `<svg>` spinners.
   - **Common mapping**:

     | Concept | RemixIcon Class |
     |---------|----------------|
     | 手机/添加桌面 | `ri-smartphone-line` |
     | 锁/隐私 | `ri-lock-line` |
     | 相机/照片 | `ri-camera-line` |
     | 通知 | `ri-notification-3-line` |
     | 主题/调色 | `ri-palette-line` |
     | 图表/追踪 | `ri-bar-chart-2-line` |
     | 显微镜/体检 | `ri-microscope-line` |
     | 团队/白友 | `ri-team-line` |
     | 编辑 | `ri-edit-line` |
     | 删除 | `ri-delete-bin-line` |
     | 退出 | `ri-logout-box-r-line` |
     | 刷新/更新 | `ri-refresh-line` |
     | 提示/灯泡 | `ri-lightbulb-line` |
     | 警告 | `ri-error-warning-line` |
     | 设置 | `ri-settings-3-line` |
     | 用户 | `ri-user-line` |
     | 聊天/评论 | `ri-chat-3-line` |
     | 文件/笔记 | `ri-file-edit-line` |
     | 收藏/星 | `ri-star-line` |
     | 密钥 | `ri-key-2-line` |
     | 安全 | `ri-shield-keyhole-line` |
     | 搜索 | `ri-search-line` |
     | 图片 | `ri-image-line` |
     | 文档 | `ri-file-text-line` |
     | 公开/全球 | `ri-global-line` |
     | 医学/胶囊 | `ri-capsule-line` |
     | 文件夹 | `ri-folder-3-line` |
     | 点赞/心 | `ri-heart-3-line` |
     | 链接 | `ri-link` |
     | 叶子/自然 | `ri-leaf-line` |

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

<!-- CODEGRAPH_START -->
## CodeGraph

This project has a CodeGraph MCP server (`codegraph_*` tools) configured. CodeGraph is a tree-sitter-parsed knowledge graph of every symbol, edge, and file. Reads are sub-millisecond and return structural information grep cannot.

### When to prefer codegraph over native search

Use codegraph for **structural** questions — what calls what, what would break, where is X defined, what is X's signature. Use native grep/read only for **literal text** queries (string contents, comments, log messages) or after you already have a specific file open.

| Question | Tool |
|---|---|
| "Where is X defined?" / "Find symbol named X" | `codegraph_search` |
| "What calls function Y?" | `codegraph_callers` |
| "What does Y call?" | `codegraph_callees` |
| "What would break if I changed Z?" | `codegraph_impact` |
| "Show me Y's signature / source / docstring" | `codegraph_node` |
| "Give me focused context for a task/area" | `codegraph_context` |
| "Survey an unfamiliar module/topic" | `codegraph_explore` |
| "What files exist under path/" | `codegraph_files` |
| "Is the index healthy?" | `codegraph_status` |

### ⚡ Auto-Sync After Code Changes (MANDATORY)

**After EVERY batch of file edits, run `codegraph sync` before using ANY codegraph tool.** The MCP server's built-in file watcher has ~500ms debounce — not reliable during rapid agent edits. Explicit sync guarantees the index reflects your changes.

```bash
# Run after completing a logical unit of edits, before codegraph_* queries
codegraph sync
```

**Workflow:**
1. Make code edits (edit tool, write tool)
2. **Immediately run `codegraph sync`** (sub-second for incremental changes)
3. Now use `codegraph_search` / `codegraph_callers` / `codegraph_impact` with confidence

**Anti-pattern:** Using `codegraph_impact` to check blast radius without syncing first → stale results, wrong conclusions.

### Rules of thumb

- **Sync first, query second.** Always `codegraph sync` after edits before using codegraph tools.
- **Trust codegraph results.** They come from a full AST parse. Do NOT re-verify them with grep — that's slower, less accurate, and wastes context.
- **Don't grep first** when looking up a symbol by name. `codegraph_search` is faster and returns kind + location + signature in one call.
- **Don't chain `codegraph_search` + `codegraph_node`** when you just want context — `codegraph_context` is one call.
- **`codegraph_explore` is the heavy hitter** for unfamiliar areas — it returns full source from all relevant files in one call, but is token-heavy. If your harness supports parallel subagents (e.g., Claude Code's Task tool), spawn one for explore-class questions to keep main session context clean.

### If `.codegraph/` doesn't exist

The MCP server returns "not initialized." Ask the user: *"I notice this project doesn't have CodeGraph initialized. Want me to run `codegraph init -i` to build the index?"*
## Agent Governance & Cleanup Rules

### Single Source of Truth

**AGENTS.md is the ONE AND ONLY canonical instruction file for this project.**

- `CLAUDE.md` is a pointer only — it redirects to AGENTS.md.
- All other agent entry files (OPENCODE_INSTRUCTIONS.md, START_HERE.md, .opencode_instructions.txt, etc.) have been removed.
- Any agent tool entering this project (Claude Code, OpenCode, Codex, Hermes, Cursor, Windsurf, Qoder, etc.) MUST read AGENTS.md first and treat it as authoritative.
- If an agent tool creates its own instruction file, it MUST be a short pointer to AGENTS.md — never a competing copy.

### Unified Skill System (统一 Skill 体系)

**`.agents/skills/` is the ONE AND ONLY skill directory for this project.**

| Rule | Description |
|------|-------------|
| 唯一位置 | 所有 skill 必须放在 `.agents/skills/<name>/SKILL.md` |
| 工具无关 | 禁止 `compatibility` 字段绑定特定工具，所有 skill 对所有 agent 通用 |
| 禁止分支 | 不允许在 `web/`、`src/` 等子目录创建独立的 `.agents/skills/` |
| 禁止重复 | 不允许创建与现有 skill 功能重叠的竞争性文件 |
| 更新同步 | 新增/修改 skill 后必须同步更新 AGENTS.md 中的 Skills 表 |
| 格式统一 | YAML frontmatter (`name` + `description`) + Markdown 内容 |

### Cross-Agent Context Sharing (跨 Agent 上下文共享)

所有 agent 工具共享以下信息源，确保前后逻辑和上下文通用：

| 信息类型 | 唯一位置 | 说明 |
|----------|----------|------|
| 项目规范 | `AGENTS.md` | 部署流程、代码规范、架构原则（根入口宪章） |
| **全栈开发与维护标准库** | `docs/standards/` | **8 大模块化权威规范（同步渲染于管理后台 `/#/dev-docs`「开发文档」栏目）** |
| Skill 库 | `.agents/skills/` | 前端/后端/部署/测试等所有 skill |
| 实施计划 | `hermes_plan/` | 所有 agent 的任务规划文件 |
| 部署日志 | `DEPLOY_LOG.md` | staging/production 变更记录 |
| 设计文档 | `docs/specs/` | 功能设计规格（含 `2026-10-17-subskin-design-system.md`） |
| 解决方案 | `docs/solutions/` | 已解决问题的经验文档 |

### 📚 Modular Development & Handover Standards (`docs/standards/` & Admin `/#/dev-docs`)

To guarantee seamless multi-agent handover, maintenance, upgrades, and refactoring across any LLM or coding tool, all engineering, UX, design, privacy, security, and operational standards are organized into **8 canonical modules** under `/root/subskin/docs/standards/` and rendered directly in the Admin Panel's **「开发文档」** (`https://admin.subskin.cn/#/dev-docs`):

| ID | Standard File | Mandatory Scope |
|----|---------------|-----------------|
| `STD-00` | `docs/standards/00-agent-handover-governance.md` | Multi-agent 5-step onboarding SOP, single source of truth matrix, skill triggers, handover prompt |
| `STD-01` | `docs/standards/01-product-ux-user-journey.md` | Canonical module names (`site-modules.json`), 6 core user journeys, de-escalation medical UX & disclaimers |
| `STD-02` | `docs/standards/02-ui-design-cross-platform.md` | Cursor & GitHub × clinical warmth design tokens, RemixIcon, WeChat WebView & Huawei browser rules, share posters |
| `STD-03` | `docs/standards/03-privacy-security-compliance.md` | L1–L4 data classification, 10 zero-tolerance security rules, `UserConsent`, `AuditLog`, `is_discoverable` vs `privacy_mode` |
| `STD-04` | `docs/standards/04-frontend-pwa-architecture.md` | `web/app` vs `web/admin` boundary, Vue 3 + TS <500 lines rule, `vue-tsc` gate, PWA update mechanism, `DigitalHuman` |
| `STD-05` | `docs/standards/05-backend-ai-data-architecture.md` | Shared backend caution, 3-layer `api -> services -> models/utils`, domain exceptions, Python 3.9, additive DB migrations, RAG & CV worker |
| `STD-06` | `docs/standards/06-environments-deployment-ops.md` | Three-environment topology, staging-first & full-sync production rules, Nginx & emergency rollback SOP |
| `STD-07` | `docs/standards/07-testing-quality-checklists.md` | Automated quality gate commands and 5 scenario-based delivery & handover checklists |

**Mandatory Sync Rule for All Agents**:
Whenever you add/rename a route or module, change architectural patterns, or update security/design rules:
1. Update the corresponding file(s) in `docs/standards/` and `AGENTS.md`.
2. Rebuild the Admin Panel (`cd /root/subskin/web/admin && npx vite build`) so that `https://admin.subskin.cn/#/dev-docs` stays 100% in sync with the repository.

**禁止行为：**
- ❌ 在各自工具的私有目录中维护规则副本（如 `.opencode/rules/`、`.claude/rules/`、`.cursor/rules/`）
- ❌ 创建与 AGENTS.md 内容冲突的独立指令文件
- ❌ 在工具私有目录中存放应共享的 skill 或规范
- ❌ 一次性任务指令文件留在项目根目录（应放入 `hermes_plan/` 或删除）

### Tool-Specific Config (工具私有配置)

以下文件是各工具私有的运行时配置，已 gitignore，不影响其他 agent：

| 文件/目录 | 工具 | 用途 |
|-----------|------|------|
| `.claude/settings.local.json` | Claude Code | 权限配置 |
| `opencode.jsonc` | OpenCode | MCP 服务器配置 |
| `.opencode/` | OpenCode | 运行时状态 |
| `.codegraph/` | CodeGraph | 代码索引 |
| `.superpowers/` | Superpowers | 头脑风暴运行时 |
| `.hermes/` | Hermes | 运行时状态 |

这些文件可以存在，但**不得包含与 AGENTS.md 冲突的规则或指令**。

### Plan Directory

**All implementation plans go in `hermes_plan/`** — one directory, one naming convention:

- Filename format: `YYYY-MM-DD-description.md` (e.g., `2026-06-04-admin-dashboard.md`)
- Do NOT create plans in `.hermes/plans/`, `.sisyphus/plans/`, `docs/plans/`, or any other location.
- After a plan is executed and the task is complete, leave the plan file in place — it serves as project history.

### Agent Artifact Cleanup

Agent tools naturally create runtime state directories. These are gitignored but can accumulate disk waste. **Every agent task session MUST clean up after itself:**

1. **Delete intermediate task files** when a task is complete (temporary delegation stubs, scratch files).
2. **Agent state directories** (`.opencode/`, `.codegraph/`, `.claude/`, `.sisyphus/`, `.playwright-mcp/`, `.hermes/`) are gitignored but may grow large. Periodically prune stale session state, caches, and WAL files from these directories.
3. **Logs in `logs/`** — keep only the last 7 days. Delete older `scheduler.log.YYYY-MM-DD` files.
4. **Never commit** agent runtime state, browser snapshots, or session caches.

### Cross-Agent Consistency Checklist

Before declaring a task "done", verify:

- [ ] All plan files are in `hermes_plan/` (not scattered across agent dotdirs)
- [ ] No stale intermediate task files remain (check `.hermes/opencode_tasks/`, `.hermes/goals/`, `.sisyphus/drafts/`, etc.)
- [ ] No one-time instruction files left in project root (e.g., `.opencode_instructions.txt`, `START_HERE.md`)
- [ ] `.gitignore` covers any new agent tool's state directory
- [ ] If a new agent tool was used, its entry file is a pointer to AGENTS.md, not a competing instruction set
- [ ] Any new skill is placed in `.agents/skills/` (not in subdirectories or tool-private dirs)
- [ ] AGENTS.md Skills table is up-to-date if skills were added/modified
- [ ] No skill contains `compatibility:` field binding to a specific tool

### Repository Sanity Baseline

| Concern | Rule |
|---------|------|
| Agent instruction | AGENTS.md only. CLAUDE.md is a pointer. No other instruction files. |
| Skills | `.agents/skills/` only. Tool-agnostic. YAML frontmatter required. |
| Plans | `hermes_plan/` only. Date-named. |
| Agent state dirs | Gitignored. Prune stale session/cache/WAL periodically. |
| Old logs | Delete >7 days old from `logs/`. |
| Task stubs | Delete on completion. Don't accumulate. |
| One-time instructions | Delete after task completion, or move to `hermes_plan/` as history. |

<!-- CODEGRAPH_END -->


## 🏗️ Three-Environment Architecture (UPDATED)

> **This is the authoritative environment definition. ALL agents MUST read and follow this section.**

### Environment Overview — THREE DISTINCT ENTITIES

These three environments are **completely different applications/purposes**. They must NEVER be confused or cross-deployed.

| # | Environment | URL | What It Is | Codebase | Deploy Target |
|---|-------------|-----|------------|----------|---------------|
| **1** | **Production** | https://subskin.cn / https://www.subskin.cn | **正式环境** — 面向所有用户的线上产品。只有经过测试确认无误的功能才能上线。 | `web/app/` | `/usr/share/nginx/html/subskin/` |
| **2** | **Staging** | https://staging.subskin.cn | **测试环境** — 我们高频修改和验证的环境。新功能先部署到这里，确认没问题后由 LianqingChan 确认再同步到正式环境。 | `web/app/` | `/usr/share/nginx/html/subskin-staging/` |
| **3** | **Admin** | https://admin.subskin.cn | **管理后台** — 独立模块，只有管理员可登录。**不存在测试/正式环境区分**，任何修改直接部署生效。 | `web/admin/` | `/usr/share/nginx/html/subskin-admin/` |

**All three share the same backend** (`127.0.0.1:8000`, single SQLite DB).

### ⛔ CRITICAL: Admin is a STANDALONE Application

**Admin (`web/admin/`) is a COMPLETELY SEPARATE frontend project from the main app (`web/app/`).**

| | Main App (`web/app/`) | Admin (`web/admin/`) |
|---|---|---|
| **Purpose** | User-facing app (production + staging) | Internal admin panel |
| **Login** | User login flow | Admin-only login (`/#/login`) |
| **UI Framework** | Custom components + PWA | NaiveUI + ECharts |
| **Routing** | History mode | Hash mode (`/#/dashboard`) |
| **PWA / Service Worker** | Yes | **No** — explicitly unregisters SW |
| **Title** | "SubSkin - 白癜风病友的AI手帐和分享社区" | "SubSkin 管理后台" |
| **Environments** | Production + Staging | **Single** — no staging/prod split |

**❌ NEVER deploy the main app (`web/app/`) to the admin directory.**
**❌ NEVER deploy the admin app (`web/admin/`) to staging or production directories.**

### Deployment Rules (ZERO TOLERANCE)

#### Rule 1: Admin Panel → `web/admin/` build, deploy directly

| Action | Command |
|--------|---------|
| Build & deploy admin | `cd /root/subskin/web/admin && npx vite build` |
| Dev server | `cd /root/subskin/web/admin && npm run dev` (port 5174) |

**Why:** The admin panel is a standalone SPA for internal operators. No staging exists. Every build goes directly to `/usr/share/nginx/html/subskin-admin/`.

#### Rule 2: User-Facing Features → Staging FIRST, then Production

| Step | Command |
|------|---------|
| 1. Deploy to staging | `cd /root/subskin/web/app && npm run build` → deploys to `/usr/share/nginx/html/subskin-staging/` |
| 2. Test on staging | Visit `https://staging.subskin.cn` |
| 3. User confirms | LianqingChan reviews and approves |
| 4. Deploy to production | `cd /root/subskin/web/app && npm run deploy:prod` → deploys to `/usr/share/nginx/html/subskin/` |
| 5. Notify users | Remind users to refresh/update |

**Why:** User-facing changes must be verified on staging before reaching all users.

#### Rule 3: Backend Changes → EXTREME CAUTION (shared backend!)

| Action | Rule |
|--------|------|
| Backend Python code (API, services, models) | ⚠️ ALERT user first — changes affect ALL three environments immediately |
| Database schema changes | Additive only (add columns/tables, never delete/rename) |
| Config / .env changes | Affects all environments at once |

#### Rule 4: NEVER Cross-Deploy — THREE STRIKES AND YOU'RE OUT

| ❌ FORBIDDEN (and why) | ✅ CORRECT |
|---|---|
| Deploy `web/app/` build to `/usr/share/nginx/html/subskin-admin/` — admin is a different app! | Build admin from `web/admin/` with `npx vite build` |
| Copy staging build to admin directory — different codebases! | Each environment has its own source and build process |
| Copy admin build to production/staging — admin is not user-facing! | Keep admin and main app completely separate |
| Deploy `web/app/` production build to staging | Use `npm run build` (staging config) for staging |

### How to Identify Each Environment (Visual Cues)

| | Production | Staging | Admin |
|---|---|---|---|
| **Page title** | "SubSkin - 白癜风病友的AI手帐和分享社区" | "SubSkin - 白癜风病友的AI手帐和分享社区" | **"SubSkin 管理后台"** |
| **URL** | subskin.cn / www.subskin.cn | staging.subskin.cn | admin.subskin.cn |
| **PWA** | Yes (teal theme) | Yes ("[STAGING]") | **No PWA** |
| **Login page** | Main app login flow | Main app login flow | **`/#/login` — standalone admin login** |
| **3D assets** | Yes (金斑蝶/梅花鹿 3D 形象) | Yes (金斑蝶/梅花鹿 3D 形象) | **No** — lightweight |
| **Access** | All users | Internal testing | **Admin-only** |

### Quick Reference — ALL Build Commands

```bash
# ── Admin Panel (admin.subskin.cn) ──
# Standalone app in web/admin/ — NO staging/production split
cd /root/subskin/web/admin
npx vite build          # Build & deploy to /usr/share/nginx/html/subskin-admin/
npm run dev             # Dev server on port 5174

# ── Staging (staging.subskin.cn) ──
# Test environment in web/app/
cd /root/subskin/web/app
npm run build           # Build & deploy to /usr/share/nginx/html/subskin-staging/

# ── Production (subskin.cn) ──
# Live user-facing site in web/app/
cd /root/subskin/web/app
npm run deploy:prod     # Build & deploy to /usr/share/nginx/html/subskin/
```

### Nginx Configuration (Server-Side Reference)

| Config File | Server Name | Root Directory | SSL |
|-------------|-------------|----------------|-----|
| `/etc/nginx/conf.d/subskin.conf` | `subskin.cn`, `www.subskin.cn` | `/usr/share/nginx/html/subskin/` | Yes (443) |
| `/etc/nginx/conf.d/subskin-staging.conf` | `staging.subskin.cn` | `/usr/share/nginx/html/subskin-staging/` | Yes (443) |
| `/etc/nginx/conf.d/subskin-admin.conf` | `admin.subskin.cn` | `/usr/share/nginx/html/subskin-admin/` | Yes (443) |

Repo templates are in `web/deploy/` — server configs may differ slightly. Server configs are the source of truth.
