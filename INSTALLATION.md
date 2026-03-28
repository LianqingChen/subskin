# SubSkin 安装与配置指南

本文档详细说明如何设置和配置 SubSkin 项目的开发环境。

## 📋 系统要求

- **操作系统**: Linux, macOS, 或 Windows (WSL2 推荐)
- **Python**: 3.10 或更高版本
- **内存**: 最少 8GB RAM (推荐 16GB+)
- **磁盘空间**: 最少 10GB 可用空间
- **Git**: 版本控制

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/subskin.git
cd subskin
```

### 2. 使用 Makefile 一键安装 (推荐)

```bash
# 创建虚拟环境并安装所有依赖
make setup
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
make install
```

### 3. 手动安装步骤

如果您不使用 Makefile，请按照以下步骤操作：

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. 升级 pip
pip install --upgrade pip

# 4. 安装项目依赖
pip install -e ".[dev,web,ai]"
```

## 🔧 配置环境变量

### 1. 复制环境变量模板

```bash
cp configs/.env.example .env
```

### 2. 编辑 .env 文件

打开 `.env` 文件，配置以下必要的 API 密钥：

```ini
# PubMed/NCBI API (必需)
NCBI_API_KEY=your_ncbi_api_key_here

# OpenAI API (用于翻译和摘要，必需)
OPENAI_API_KEY=your_openai_api_key_here

# Semantic Scholar API (可选)
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_api_key_here

# 网站配置
SITE_URL=http://localhost:8000
```

### 3. 获取 API 密钥

#### PubMed API 密钥
1. 访问 [NCBI API 密钥申请页面](https://www.ncbi.nlm.nih.gov/account/)
2. 创建账户并登录
3. 在 "API Key Management" 部分生成密钥
4. 免费层级：3 请求/秒，有密钥：10 请求/秒

#### OpenAI API 密钥
1. 访问 [OpenAI 平台](https://platform.openai.com/)
2. 注册或登录账户
3. 在 "API Keys" 部分创建新密钥
4. 确保账户有足够的额度

#### Semantic Scholar API 密钥 (可选)
1. 访问 [Semantic Scholar API 页面](https://www.semanticscholar.org/product/api)
2. 注册获取 API 密钥
3. 免费层级：1000 请求/秒

## 🧪 验证安装

### 运行测试

```bash
make test
```

如果所有测试通过，说明安装成功。

### 验证虚拟环境

```bash
# 检查 Python 版本
python --version

# 检查已安装的包
pip list | grep subskin
```

## 📁 项目结构概览

安装完成后，您的项目目录应该包含以下结构：

```
subskin/
├── .venv/                   # Python 虚拟环境 (安装后生成)
├── src/                     # 源代码
│   ├── crawlers/           # 数据爬虫
│   ├── processors/         # AI 处理模块
│   ├── generators/         # 内容生成器
│   ├── web/                # 网站后端
│   ├── models/             # 数据模型
│   ├── utils/              # 工具函数
│   └── cli.py              # 命令行界面
├── data/                   # 数据存储
│   ├── raw/               # 原始数据
│   ├── processed/         # 处理后的数据
│   ├── exports/           # 导出文件
│   └── weekly/            # 每周生成内容
├── web/                    # 前端代码
│   ├── vitepress/         # VitePress 配置
│   ├── templates/         # HTML 模板
│   └── public/            # 静态资源
├── configs/                # 配置文件
├── tests/                  # 测试代码
├── docs/                   # 项目文档
├── scripts/               # 自动化脚本
└── requirements/          # 依赖管理
```

## 🔄 开发工作流

### 日常开发

1. **激活虚拟环境**
   ```bash
   source .venv/bin/activate
   ```

2. **运行开发服务器** (如果开发网站功能)
   ```bash
   make run-dev
   ```

3. **运行爬虫测试**
   ```bash
   make crawl-pubmed
   ```

### 代码质量检查

```bash
# 运行所有检查
make lint
make type-check

# 自动修复部分问题
make format
```

### 数据库操作 (如果需要)

```bash
# 初始化数据库
make db-init

# 运行迁移
make db-migrate
```

## 🐛 故障排除

### 常见问题

#### 1. 虚拟环境激活失败 (Windows)
```bash
# 使用 PowerShell
.venv\Scripts\Activate.ps1

# 如果遇到执行策略问题，以管理员身份运行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 2. 依赖安装失败
```bash
# 清理并重新安装
make clean
rm -rf .venv
make setup
```

#### 3. API 密钥无效
- 确认 API 密钥格式正确
- 检查账户是否有足够的额度
- 验证网络连接

#### 4. 测试失败
```bash
# 详细输出测试信息
pytest -v

# 运行特定测试文件
pytest tests/test_models.py -v
```

### 获取帮助

如果您遇到问题，请：

1. 检查错误信息是否提供了解决方案
2. 查看项目的 GitHub Issues
3. 在项目讨论区提问

## 🔗 相关资源

- [Python 虚拟环境文档](https://docs.python.org/3/tutorial/venv.html)
- [Pip 用户指南](https://pip.pypa.io/en/stable/user_guide/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)

## 📝 下一步

安装完成后，您可以：

1. **运行示例爬虫**: `make crawl-pubmed`
2. **启动开发服务器**: `make run-dev`
3. **生成每周内容**: `make generate-weekly`
4. **查看文档**: `make docs-serve`

祝您开发愉快！