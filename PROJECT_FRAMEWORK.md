# SubSkin 项目框架与架构设计

> **版本**: 1.0 | **日期**: 2026-03-28 | **状态**: 草案

## 📋 项目概述

SubSkin 是一个综合性白癜风知识平台，整合三个核心任务：

1. **白癜风百科全书**：自动化收集、翻译、总结全球白癜风研究论文，构建结构化知识库
2. **每周AI/白癜风知识分享**：每周生成技术科普内容，支持视频创作者在抖音、小红书、Bilibili等平台分享
3. **SubSkin社区网站**：发布百科全书内容，建立患者与研究者社区，集成LLM问答功能

## 🎯 核心目标

### 1. 白癜风百科全书
- **数据源**：PubMed、Semantic Scholar、ClinicalTrials.gov
- **处理流程**：爬取 → 去重 → 翻译(英→中) → 总结(患者友好) → 存储
- **目标规模**：>1000篇论文，持续更新
- **交付形式**：结构化JSON + Markdown百科全书

### 2. 每周知识分享
- **频率**：每周五生成
- **内容**：
  - 本周白癜风研究亮点
  - 项目使用的AI工具与技术心得
  - 患者关心的实用信息
- **格式**：HTML页面（简洁科技风格），支持视频脚本提取
- **自动化**：基于每周数据收集自动生成

### 3. 社区网站
- **核心功能**：
  - 百科全书浏览与搜索
  - 用户账户与个人收藏
  - 社区讨论与问答
  - LLM智能问答（基于知识库）
- **技术栈**：静态站点生成器（VitePress/Docsify）+ 轻量级后端
- **扩展性**：支持未来添加更多交互功能

## 🏗️ 系统架构

### 整体架构图
```
数据层   →   处理层   →   应用层   →   展示层
─────────────────────────────────────────────
PubMed        爬虫引擎       知识库API       网站
Semantic      AI处理        每周生成器      (VitePress)
Scholar       (翻译/摘要)    社区后端       HTML分享
ClinicalTrials               调度系统
```

### 1. 数据收集与处理流水线（已有详细计划）
```python
# 基于现有 .sisyphus/plans/vitiligo-data-collection.md 扩展
1. 数据收集 → 2. 数据清洗 → 3. AI处理 → 4. 知识库构建 → 5. 内容发布
```

### 2. 每周内容生成系统
```
每周五自动触发：
1. 查询本周新增论文/临床试验
2. 提取关键发现
3. 生成中文科普摘要
4. 应用HTML模板生成分享页面
5. 可选：生成视频脚本大纲
```

### 3. 社区网站架构
```
前端: VitePress/Docsify (静态生成)
  ├── 百科全书浏览
  ├── 搜索功能
  ├── 用户系统 (基于GitHub OAuth/JWT)
  └── 评论区

后端: 轻量级Python服务 (FastAPI/Flask)
  ├── 用户认证
  ├── 内容API
  ├── LLM问答接口
  └── 社区功能API

数据库: SQLite (初期) → PostgreSQL (扩展)
```

## 📁 项目目录结构（扩展版）

```
subskin/
├── src/                          # Python源代码
│   ├── crawlers/                 # 数据爬虫 (现有计划)
│   │   ├── pubmed_crawler.py
│   │   ├── semantic_scholar_crawler.py
│   │   └── clinical_trials_crawler.py
│   ├── processors/               # AI处理模块 (现有计划)
│   │   ├── translator.py
│   │   ├── summarizer.py
│   │   └── deduplicator.py
│   ├── generators/               # 【新增】内容生成器
│   │   ├── weekly_digest.py      # 每周摘要生成
│   │   ├── html_template.py      # HTML模板引擎
│   │   └── video_script.py       # 视频脚本生成
│   ├── web/                      # 【新增】网站后端
│   │   ├── api/                  # API端点
│   │   ├── auth/                 # 用户认证
│   │   └── llm_qa/               # LLM问答集成
│   ├── scheduler/                # 调度系统 (现有计划扩展)
│   │   ├── update_scheduler.py
│   │   └── weekly_scheduler.py   # 【新增】每周内容调度
│   ├── models/                   # 数据模型 (现有计划)
│   │   ├── paper.py
│   │   ├── trial.py
│   │   └── user.py               # 【新增】用户模型
│   ├── utils/                    # 工具库 (现有计划)
│   └── cli.py                    # 命令行界面 (现有计划)
├── web/                          # 前端代码
│   ├── vitepress/                # VitePress配置
│   │   ├── docs/
│   │   │   ├── encyclopedia/     # 自动生成的百科内容
│   │   │   ├── weekly/          # 每周分享内容
│   │   │   └── community/       # 社区页面
│   │   └── .vitepress/
│   ├── templates/                # HTML模板
│   │   ├── weekly-digest.html   # 每周分享模板
│   │   └── base-style.css       # 科技风格CSS
│   └── public/                   # 静态资源
├── data/                         # 数据存储
│   ├── raw/                      # 原始数据 (现有计划)
│   ├── processed/                # 处理后的数据 (现有计划)
│   ├── exports/                  # 导出文件 (现有计划)
│   └── weekly/                   # 【新增】每周生成内容
├── scripts/                      # 自动化脚本
│   ├── run_crawlers.py          # 运行所有爬虫
│   ├── generate_weekly.py       # 生成每周内容
│   └── deploy_website.py        # 部署网站
├── configs/                      # 配置文件
│   ├── .env.example              # 环境变量模板
│   ├── crawler_config.yaml      # 爬虫配置
│   └── web_config.yaml          # 网站配置
├── tests/                        # 测试代码
├── docs/                         # 项目文档
├── requirements/                 # Python依赖
│   ├── base.txt                  # 基础依赖
│   ├── dev.txt                   # 开发依赖
│   ├── web.txt                   # 【新增】Web相关依赖
│   └── ai.txt                    # 【新增】AI处理依赖
└── .github/workflows/           # CI/CD
    ├── test.yml                 # 测试流水线
    ├── weekly.yml               # 【新增】每周内容生成流水线
    └── deploy.yml               # 【新增】部署流水线
```

## 🔧 技术栈选择

### 后端与数据处理
- **Python 3.10+**：主要开发语言
- **FastAPI/Flask**：Web API框架（轻量级选择）
- **SQLAlchemy**：ORM（数据库操作）
- **SQLite** → **PostgreSQL**：数据库演进路径
- **Redis**（可选）：缓存与会话管理

### 数据收集与AI
- **metapub**：PubMed API封装
- **requests** + **BeautifulSoup**：网页爬取
- **OpenAI API** / **Anthropic API**：翻译与摘要
- **pydantic**：数据验证

### 前端与网站
- **VitePress** / **Docsify**：静态站点生成器（推荐VitePress）
- **Vue 3**（如果选VitePress）：组件开发
- **Tailwind CSS**：样式框架（科技风格）
- **Algolia**（可选）：搜索功能

### 部署与运维
- **Docker**：容器化部署
- **GitHub Actions**：自动化工作流
- **Vercel** / **Netlify**：静态站点托管
- **PythonAnywhere** / **Railway**：后端托管

### 开发工具
- **pytest**：测试框架
- **ruff** + **black**：代码格式化
- **mypy**：类型检查
- **pre-commit**：代码质量钩子

## 📊 数据流设计

### 1. 核心数据流（百科全书）
```
外部API → 爬虫 → 原始数据(JSON) → 去重清洗 → AI处理 → 知识库条目 → 网站展示
  ↑           ↓           ↓           ↓           ↓           ↓
PubMed   Semantic    data/raw/   processors/   data/      web/docs/
          Scholar                 translator    processed/   encyclopedia/
ClinicalTrials                   summarizer
```

### 2. 每周内容生成流
```
每周五触发 → 查询本周新数据 → 提取亮点 → 生成中文摘要 → 应用模板 → 输出HTML
   ↓              ↓              ↓           ↓           ↓          ↓
scheduler/    data/processed/  generators/   AI处理     templates/ web/weekly/
```

### 3. 社区互动流
```
用户请求 → 网站前端 → API后端 → 数据库查询 → LLM处理 → 返回结果
   ↓          ↓          ↓          ↓          ↓         ↓
浏览器    VitePress    FastAPI    SQLite    OpenAI      JSON
                                   用户数据  知识库上下文
```

## 🚀 实施阶段

### 阶段一：基础数据管道（4-6周）
**目标**：建立可靠的数据收集与处理流水线
1. 搭建项目基础结构（目录、虚拟环境、依赖）
2. 实现PubMed爬虫（参考现有计划任务8）
3. 实现Semantic Scholar爬虫（任务9）
4. 实现ClinicalTrials.gov爬虫（任务10）
5. 开发AI翻译与摘要模块（任务12-13）
6. 创建基础数据导出（任务14）

**交付物**：可运行的Python项目，能从三个来源收集并处理白癜风数据

### 阶段二：知识库构建与每周内容（3-4周）
**目标**：构建结构化知识库并实现每周自动化
1. 设计百科全书数据结构
2. 实现Markdown导出与组织
3. 开发每周摘要生成器
4. 创建HTML模板系统
5. 实现自动化调度（扩展任务15）

**交付物**：
- 白癜风知识库（Markdown格式）
- 每周内容生成系统
- 自动化调度脚本

### 阶段三：社区网站开发（4-6周）
**目标**：搭建功能完整的社区网站
1. 设置VitePress/Docsify静态站点
2. 集成知识库内容自动发布
3. 实现用户认证系统
4. 开发基础社区功能（评论、收藏）
5. 集成LLM问答功能

**交付物**：可部署的SubSkin社区网站

### 阶段四：优化与扩展（持续）
**目标**：增强用户体验和功能
1. 搜索功能优化
2. 移动端适配
3. 性能优化
4. 社区功能扩展（论坛、私信等）
5. 数据分析与可视化

## 🔐 关键决策点

### 1. 网站技术栈选择
**选项A**：VitePress（Vue 3 + Vite）
- 优点：现代、快速、SEO友好、主题丰富
- 缺点：需要学习Vue基础

**选项B**：Docsify
- 优点：简单、零配置、纯Markdown
- 缺点：功能相对简单、定制性有限

**建议**：VitePress，因其更好的扩展性和现代技术栈

### 2. 用户认证方案
**选项A**：GitHub OAuth
- 优点：开发简单、用户信任度高
- 缺点：依赖GitHub账户

**选项B**：邮箱密码 + JWT
- 优点：完全控制、无需第三方
- 缺点：需要实现完整的安全机制

**建议**：初期使用GitHub OAuth，后期增加邮箱注册

### 3. LLM集成策略
**选项A**：直接调用OpenAI API
- 优点：简单快速、效果好
- 缺点：API成本、数据隐私

**选项B**：本地模型（Llama、Qwen等）
- 优点：数据隐私、无API成本
- 缺点：需要本地GPU、效果可能稍差

**建议**：初期使用OpenAI API，后期评估本地部署

## ⚠️ 风险与缓解

### 技术风险
1. **API限制与变化**
   - 风险：PubMed/Google Scholar API限制或变更
   - 缓解：多数据源、优雅降级、实现缓存

2. **AI成本控制**
   - 风险：OpenAI API使用成本超预期
   - 缓解：实现缓存、分批处理、监控使用量

3. **网站性能**
   - 风险：知识库内容增多后网站加载慢
   - 缓解：静态生成、CDN分发、图片优化

### 项目风险
1. **范围蔓延**
   - 风险：功能不断增加导致项目延期
   - 缓解：明确阶段目标、优先级排序

2. **依赖更新**
   - 风险：依赖库版本冲突或停止维护
   - 缓解：锁定版本、定期更新、选择成熟库

## 📈 成功指标

### 第一阶段（数据管道）
- [ ] 成功收集>100篇白癜风相关论文
- [ ] AI翻译准确率>90%（人工抽样评估）
- [ ] 处理流水线完全自动化

### 第二阶段（知识库）
- [ ] 知识库包含>500个结构化条目
- [ ] 每周内容生成完全自动化
- [ ] HTML模板支持多种分享平台

### 第三阶段（网站）
- [ ] 网站部署并可通过域名访问
- [ ] 用户注册与登录功能正常
- [ ] LLM问答准确回答基础问题

## 🤝 下一步行动

### 立即行动（本周）
1. [x] 完成项目框架设计（本文档）
2. [ ] 创建完整的项目目录结构
3. [ ] 设置Python开发环境与依赖
4. [ ] 开始实施现有计划中的Wave 1任务

### 短期计划（1-2个月）
1. 完成数据收集流水线（现有计划Wave 1-2）
2. 开发每周内容生成系统
3. 设计并实现基础网站结构

### 长期愿景
1. 建立国内领先的白癜风知识库
2. 形成活跃的患者-研究者社区
3. 探索AI在皮肤病辅助诊断中的应用

---

**文档维护**：本框架将随项目进展持续更新。重大架构变更需更新版本号并记录变更原因。