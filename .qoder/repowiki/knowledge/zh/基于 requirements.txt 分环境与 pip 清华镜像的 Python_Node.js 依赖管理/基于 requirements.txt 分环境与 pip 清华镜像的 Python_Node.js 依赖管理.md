---
kind: dependency_management
name: 基于 requirements.txt 分环境与 pip 清华镜像的 Python/Node.js 依赖管理
category: dependency_management
scope:
    - '**'
source_files:
    - requirements/base.txt
    - requirements/web.txt
    - requirements/ai.txt
    - requirements/dev.txt
    - pyproject.toml
    - web/admin/package.json
    - web/app/package.json
    - web/vitepress/package.json
    - .opencode/package.json
    - scripts/deploy.sh
    - .pre-commit-config.yaml
---

## 1. 使用的系统与工具

- **Python 依赖**：采用 `pip` + 按环境拆分的 `requirements/*.txt` 清单（`base.txt`、`web.txt`、`ai.txt`、`dev.txt`），未使用 `poetry`、`pipenv`、`Pipfile` 或 `uv`。
- **构建/打包元数据**：根目录 `pyproject.toml` 仅声明包名、版本、`requires-python >= 3.9`、`build-backend = setuptools.build_meta`，以及 `black`、`isort`、`pytest`、`coverage` 等工具配置；没有 `[project.dependencies]` 字段，运行时依赖仍由 `requirements/*.txt` 管理。
- **前端依赖**：三个独立的 Node.js 子项目各自维护 `package.json`：
  - `web/admin/package.json`（Vue3 + Vite + NaiveUI 管理后台）
  - `web/app/package.json`（Vue3 + Vite + PWA 用户端站点）
  - `web/vitepress/package.json`（VitePress 文档站）
  - `.opencode/package.json`（AI 插件）
  各子项目均使用 `^` / `~` 语义化版本范围，未使用 `pnpm-lock.yaml`、`yarn.lock` 或 `package-lock.json`（`.opencode` 下存在 `package-lock.json`，但仓库其他位置无统一锁文件）。
- **私有源/镜像**：部署脚本通过 `-i https://pypi.tuna.tsinghua.edu.cn/simple` 指定清华 PyPI 镜像安装依赖；未发现 `PIP_INDEX_URL`、`extra-index-url`、`pip.conf`、`setup.cfg` 中 `index-url` 等全局配置。
- **模型权重**：本地大模型权重以 Git LFS 风格存放在 `models/thomas/SAM-Med2D/`，配合 `.lock/` 与 `._____temp` 临时目录，不属于常规包管理器范畴。

## 2. 关键文件

| 文件 | 作用 |
|---|---|
| `requirements/base.txt` | 爬虫、AI 客户端、FastAPI、SQLAlchemy、Redis、阿里云视觉 SDK 等核心依赖 |
| `requirements/web.txt` | Web 后端增强依赖：JWT、bcrypt、Alembic、Meilisearch、Whoosh、Pillow、Sentry 等 |
| `requirements/ai.txt` | 可选 AI/ML 依赖：OpenAI/Anthropic/Cohere、Llama.cpp、Transformers、PyTorch、ChromaDB、LangChain、Whisper 等 |
| `requirements/dev.txt` | 测试、格式化、类型检查、安全扫描、构建发布工具，并在末尾重复声明了 web 后端常用依赖的最小版本 |
| `pyproject.toml` | 包元数据、`requires-python`、`black`/`isort`/`pytest`/`coverage` 工具配置、`setuptools` 构建后端 |
| `web/admin/package.json` | 管理后台前端依赖 |
| `web/app/package.json` | 用户端前端依赖（含 PWA、微信 JS-SDK、TipTap 编辑器） |
| `web/vitepress/package.json` | 文档站依赖（VitePress + ECharts） |
| `.opencode/package.json` | OpenCode AI 插件依赖 |
| `scripts/deploy.sh` | 部署时通过清华镜像 `pip install -r requirements/*.txt` |
| `.pre-commit-config.yaml` | pre-commit 钩子（detect-secrets），间接约束提交产物 |

## 3. 架构与约定

- **分层依赖策略**：`base.txt` 定义跨模块共享依赖；`web.txt` 叠加 Web API 所需扩展；`ai.txt` 作为可选 AI 能力集；`dev.txt` 仅用于开发/测试。部署脚本会依次安装 base → dev，体现“基础 + 开发”的组合方式。
- **版本约束风格**：全部使用 `>=X.Y.Z` 的宽松下限约束（如 `fastapi>=0.100.0`、`sqlalchemy>=2.0.0`、`openai>=1.0.0`），仅在个别包上限定上限（如 `bcrypt>=4.0.1,<5.0.0`），未见固定到精确版本的实践。
- **多前端工程隔离**：每个前端子应用独立 `package.json`，不存在 monorepo 式的 workspace 或共享依赖锁定文件；Node 依赖由各自 `node_modules` 管理。
- **构建入口**：`Makefile` 与 `pyproject.toml` 中的 `[project.scripts]` 暴露 `test`、`format`、`lint` 命令，但依赖解析本身仍走 `pip`。

## 4. 约定与约束

- **Python 依赖必须通过 `requirements/*.txt` 声明**：所有第三方库在四个 `requirements/*.txt` 中以 `>=` 形式列出，`pyproject.toml` 不承载运行时依赖列表。
- **部署强制使用清华 PyPI 镜像**：`scripts/deploy.sh` 在安装前执行 `pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple`，并以相同镜像安装 `base.txt` 与 `dev.txt`；该行为是部署流程的硬性约束。
- **Python 版本要求 ≥ 3.9**：由 `pyproject.toml` 的 `requires-python = ">=3.9"` 声明，任何低于 3.9 的环境无法安装本包。
- **前端依赖使用语义化版本范围**：`web/admin`、`web/app`、`web/vitepress` 的 `package.json` 普遍使用 `^`（兼容次版本更新）和 `~`（仅兼容补丁更新，如 `typescript: ~5.6.3`），未提交 lock 文件，因此每次 `npm install` 可能解析出不同具体版本。
- **可选依赖分组明确**：AI 相关库（LLM 客户端、本地推理框架、向量数据库、NLP 工具）集中在 `ai.txt`，Web 功能（认证、搜索、邮件、监控）集中在 `web.txt`，便于按需安装。
- **预提交阶段进行安全扫描**：`.pre-commit-config.yaml` 引入 `detect-secrets`，排除 `.venv`、`node_modules`、`.git`、`data`、`logs`，防止密钥随代码提交。
- **无 vendoring**：仓库未包含 `vendor/` 或 `third_party/` 形式的源码级依赖拷贝；所有 Python 依赖通过 pip 在线安装。
- **无私有 PyPI 注册表配置**：未发现 `extra-index-url`、`trusted-host`、`pip.conf` 等指向内部仓库的配置，所有依赖均来自公开 PyPI（经清华镜像代理）。