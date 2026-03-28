# Draft: 白癜风资料收集系统规划

## 用户需求（已确认）
- **目标**：高效收集白癜风相关的医学资料，构建知识库
- **数据源优先级**：PubMed、中文医学数据库、Google Scholar
- **数据规模**：大规模（>1000篇）
- **更新策略**：定期更新（推荐）

## 研究发现

### 1. 现有代码库状态
**项目完全空白**，只有文档文件：
- ✅ AGENTS.md（技术指南）
- ✅ README.md（项目说明）
- ❌ 无爬虫实现
- ❌ 无数据模型
- ❌ 无配置文件
- ❌ 无数据存储

**结论**：需要从零开始构建整个系统

### 2. 医学文献API研究

#### PubMed E-utilities（主要数据源）
- **官方API**：https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
- **速率限制**：
  - 无API key：3 req/s
  - 有API key：10 req/s（推荐）
- **核心工具**：
  - ESearch：搜索PMID
  - ESummary：获取摘要
  - EFetch：获取完整记录
- **查询语法**：
  - `vitiligo[MeSH Terms]` - MeSH主题词搜索
  - `(vitiligo) AND (JAK inhibitors[Title/Abstract])` - 组合查询
  - `mindate=2020&maxdate=2026` - 日期范围过滤

#### Semantic Scholar（Google Scholar替代）
- **API**：https://api.semanticscholar.org/
- **速率限制**：1000 req/s（免费）
- **优势**：
  - 214M+论文，2.49B+引用
  - 有Python客户端库
  - 提供AI生成的TLDR摘要
  - 无法律风险

#### ClinicalTrials.gov（临床试验数据）
- **v2 API**：https://clinicaltrials.gov/api/v2/studies
- **无需认证**，JSON格式
- **关键字段**：
  - NCT ID、试验阶段、招募状态
  - 干预措施（JAK抑制剂等）
  - 入组人数、地点、日期

#### Google Scholar
- **不推荐爬虫**：违反ToS，有IP封禁和法律风险
- **替代方案**：使用Semantic Scholar或OpenAlex

### 3. 生产级爬虫实现参考

#### metapub（148 stars）- 最成熟
- **GitHub**：https://github.com/metapub/metapub
- **优势**：
  - 内置速率限制处理
  - SQLite缓存机制
  - 完整的PubMedArticle数据模型
  - 自定义异常处理
- **数据模型字段**：
  - pmid, title, authors, journal, year
  - doi, abstract, mesh_terms

#### paperscraper（~700 stars）- 多源支持
- **GitHub**：https://github.com/jannisborn/paperscraper
- **优势**：
  - 支持PubMed、arXiv、bioRxiv等
  - 自动重试机制
  - JSONL流式输出
  - 全文获取回退机制

#### async-pubmed-scraper（44 stars）- 异步模式
- **GitHub**：https://github.com/IliaZenkov/async-pubmed-scraper
- **优势**：
  - aiohttp异步请求
  - 信号量控制并发
  - 13 articles/s性能

## 技术决策（初步）

### 推荐架构
```
数据源层：
├── PubMed E-utilities（主要）
├── Semantic Scholar（补充）
├── ClinicalTrials.gov（临床试验）
└── 中文数据库（待研究）

处理层：
├── Scrapy爬虫框架
├── metapub库（PubMed）
├── 自定义速率限制器
└── SQLite缓存

存储层：
├── data/raw/（原始JSON）
├── data/processed/（处理后）
└── PostgreSQL（Phase 2）
```

### 推荐数据模型
```json
{
  "pmid": "string",
  "doi": "string",
  "title": "string",
  "abstract": "string",
  "authors": ["string"],
  "journal": "string",
  "pub_date": "date",
  "mesh_terms": ["string"],
  "keywords": ["string"],
  "source": "pubmed|semantic_scholar|clinical_trials",
  "crawled_at": "timestamp"
}
```

## 技术决策（已确认）

### 数据源策略
1. **PubMed E-utilities**（主要）
   - 使用免费额度（3 req/s）
   - 后续可申请API key提升到10 req/s

2. **Semantic Scholar**（补充）
   - 免费API（1000 req/s）
   - 替代Google Scholar

3. **ClinicalTrials.gov**（临床试验）
   - 免费v2 API
   - 关注JAK抑制剂等新药试验

4. **中文数据库**（探索免费方案）
   - 寻找免费替代方案
   - 可能选项：
     - 中国生物医学文献服务系统（CBM）
     - 国家科技图书文献中心（NSTL）
     - 或先跳过，专注国际文献

### LLM处理
- **选择**：OpenAI（GPT-4/GPT-3.5）
- **用途**：
  - 论文摘要翻译（英→中）
  - 患者友好的科普总结
  - 关键信息提取

### 存储方案
- **Phase 1**：JSON/Markdown
  - 简单快速，无需数据库配置
  - 适合初期开发和测试
  - 易于版本控制和备份
- **Phase 2**（未来）：PostgreSQL
  - 大规模数据存储
  - 复杂查询需求
  - 多用户访问

### 测试策略
- **方法**：TDD（测试驱动开发）
- **框架**：pytest（Python标准测试框架）
- **流程**：RED（写失败测试）→ GREEN（最小实现）→ REFACTOR（优化代码）
- **覆盖**：
  - 单元测试：数据模型、工具函数
  - 集成测试：API调用、爬虫逻辑
  - Mock策略：模拟外部API响应，避免真实调用

### 更新策略
- **频率**：定期更新（每周/每月，待定）
- **方式**：增量更新（只获取新论文）
- **实现**：记录最后爬取时间，查询时过滤

## 范围边界（已确认）

### INCLUDE
- ✅ PubMed文献收集（主要数据源）
- ✅ Semantic Scholar补充数据
- ✅ ClinicalTrials.gov临床试验数据
- ✅ 元数据提取（PMID, DOI, MeSH, 摘要等）
- ✅ 定期更新机制
- ✅ OpenAI翻译和总结
- ✅ JSON/Markdown存储（Phase 1）

### EXCLUDE
- ❌ 全文下载（版权限制）
- ❌ 实时监控（资源消耗大）
- ❌ Google Scholar爬虫（法律风险）
- ❌ 付费中文数据库（万方/知网）
- ❌ 患者社区数据（论坛、社交媒体）
- ❌ PostgreSQL（Phase 2再考虑）

## 实现优先级

### Phase 1 - MVP（最小可行产品）
1. 项目结构搭建
2. PubMed爬虫实现
3. 数据模型定义
4. JSON存储
5. 基础配置管理

### Phase 2 - 增强
1. Semantic Scholar集成
2. ClinicalTrials.gov集成
3. OpenAI翻译和总结
4. 定期更新机制
5. Markdown文档生成

### Phase 3 - 优化
1. 性能优化（异步、缓存）
2. 错误处理增强
3. 监控和日志
4. PostgreSQL迁移（可选）

## 所有需求已明确 ✅
