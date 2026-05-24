# SubSkin 安装与配置指南

## 系统要求

- **操作系统**: Linux, macOS, 或 Windows (WSL2)
- **Python**: 3.10+
- **Node.js**: 18+
- **内存**: 最少 8GB

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/LianqingChen/subskin.git
cd subskin
```

### 2. 后端 (Python)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt

# 配置环境变量
cp configs/.env.example .env
# 编辑 .env，填入 API Key

# 启动后端
make run-dev       # http://localhost:8000
```

### 3. 前端

```bash
cd web/app
cp .env.example .env   # 根据需要配置
npm install
npm run dev            # http://localhost:5174，自动代理 /api → :8000
```

### 4. 配置 Web 后端

```bash
cp web/backend/.env.example web/backend/.env
# 编辑 web/backend/.env，填入数据库 URL、JWT Secret、LLM 配置等
```

## 验证安装

```bash
# 后端测试
source .venv/bin/activate
pytest

# 前端类型检查
cd web/app
npm run type-check
```

## 项目结构

```
subskin/
├── src/                          # Python 数据 pipeline
│   ├── crawlers/                 # PubMed, Semantic Scholar, ClinicalTrials.gov
│   ├── processors/               # 翻译、摘要、去重
│   ├── exporters/                # JSON / Markdown 导出
│   ├── scheduler/                # 定时调度
│   └── notifications/            # QQ / 微信通知
├── web/
│   ├── app/                      # Vue 3 PWA 前端
│   ├── backend/                  # FastAPI 后端
│   └── deploy/                   # Nginx 配置
├── configs/                      # 配置文件
├── tests/                        # pytest
└── requirements/                 # Python 依赖
```

## 开发工作流

```bash
# 后端
make lint          # ruff 检查
make format        # ruff 格式化
make type-check    # mypy
make run-dev       # 启动后端

# 前端
cd web/app
npm run lint       # ESLint
npm run type-check # vue-tsc
npm run build      # 生产构建

# 数据 Pipeline
python -m src.cli pubmed --query "vitiligo" --limit 10
python -m src.cli run-scheduler
```

## 获取 API 密钥

- **PubMed**: [NCBI API Key](https://www.ncbi.nlm.nih.gov/account/)
- **OpenAI**: [OpenAI Platform](https://platform.openai.com/)
- **Semantic Scholar**: [S2 API](https://www.semanticscholar.org/product/api)

## 故障排除

- 虚拟环境问题：删除 `.venv` 重建
- 前端依赖问题：删除 `node_modules` 和 `package-lock.json` 重装
- API 密钥无效：检查账户额度和密钥格式
