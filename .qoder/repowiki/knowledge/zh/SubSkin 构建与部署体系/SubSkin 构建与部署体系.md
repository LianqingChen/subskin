---
kind: build_system
name: SubSkin 构建与部署体系
category: build_system
scope:
    - '**'
source_files:
    - Makefile
    - pyproject.toml
    - .github/workflows/ci.yml
    - .github/workflows/test.yml
    - .github/workflows/weekly.yml
    - scripts/deploy.sh
    - subskin-scheduler.service
    - web/backend/Dockerfile
    - requirements/base.txt
    - requirements/dev.txt
---

## 构建系统概览

SubSkin 项目采用 Python 生态的标准构建方案，以 `pyproject.toml` + `setuptools` 为核心，配合 `Makefile` 提供统一命令入口，通过 GitHub Actions 实现 CI/CD 流水线，支持本地开发、测试、打包和阿里云 ECS 部署。

## 核心构建工具链

**包管理与依赖管理**
- 使用 `pyproject.toml` 定义项目元数据（name: subskin, version: 1.0.0）和构建配置
- 构建后端为 `setuptools.build_meta`，Python 版本要求 >=3.9
- 依赖按功能分层：`requirements/base.txt`（核心依赖）、`requirements/dev.txt`（开发依赖）、`requirements/web.txt`（Web 依赖）、`requirements/ai.txt`（AI 依赖）
- 可选依赖组：`[dev,web,ai]` 通过 `pip install -e ".[dev,web,ai]"` 安装

**代码质量工具**
- Linting: `ruff check src/ tests/`（替代 flake8/isort）
- 格式化: `black`（行宽88，目标版本 py39）
- 类型检查: `mypy src/`
- 覆盖率: `pytest --cov=src --cov-report=term-missing`

## Makefile 命令体系

```bash
make setup          # 创建虚拟环境 .venv
make install        # 安装所有依赖（base + web + ai）
make dev-install    # 仅安装开发依赖
make test           # 运行 pytest 并生成覆盖率报告
make lint           # ruff 检查 + 格式校验
make format         # black 自动格式化
make type-check     # mypy 类型检查
make clean          # 清理缓存和临时文件
make run-dev        # 启动 uvicorn 开发服务器
make crawl-all      # 运行所有爬虫任务
make docs-build     # 构建文档站点
```

## CI/CD 流水线

**GitHub Actions 工作流**
- `.github/workflows/ci.yml`: 主 CI 流水线，支持 Python 3.10/3.11/3.12 矩阵测试
- `.github/workflows/test.yml`: 独立测试流程，固定 Python 3.11
- `.github/workflows/weekly.yml`: 每周内容自动生成，定时任务每周五 UTC 10:00 执行

**CI 流程步骤**
1. 检出代码 → 2. 设置 Python 环境 → 3. 安装依赖 → 4. Ruff lint → 5. Mypy 类型检查 → 6. Pytest 测试 → 7. Codecov 覆盖率上传

**自动化内容生成**
- 每周自动生成医学摘要，创建 PR 到 main 分支
- 支持手动触发和测试模式
- 环境变量通过 GitHub Secrets 管理 API Key

## 部署架构

**本地开发环境**
- 虚拟环境: `.venv/`（由 `python -m venv .venv` 创建）
- 配置文件: `configs/.env.example` → 复制为 `.env`
- 数据库: SQLite (`data/subskin.db`)，支持 Alembic 迁移

**生产部署**
- 脚本部署: `scripts/deploy.sh` 全自动部署到阿里云 ECS
- Systemd 服务: `subskin-scheduler.service` 管理定时任务进程
- Docker 容器化: `web/backend/Dockerfile` 基于 `python:3.11-slim`
- 定时任务: Cron 每日 9:00 执行数据更新

**Docker 镜像构建**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 关键约束与约定

1. **Python 版本**: 最低 3.9，CI 测试 3.10-3.12，推荐 3.11
2. **依赖隔离**: 必须使用 `.venv` 虚拟环境，禁止全局安装
3. **配置管理**: 所有敏感信息通过 `.env` 文件管理，模板在 `configs/.env.example`
4. **代码规范**: 强制使用 ruff + black + mypy 三件套
5. **测试要求**: 新增代码必须通过 pytest 测试，覆盖率上传至 Codecov
6. **部署流程**: 生产环境必须通过 `deploy.sh` 脚本部署，确保环境一致性
7. **日志管理**: 所有运行日志输出到 `logs/` 目录，支持 cron 日志轮转