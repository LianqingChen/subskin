---
kind: external_dependency
name: Meilisearch - 全文搜索引擎
slug: meilisearch
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
---

### 身份与角色
- Meilisearch 作为项目的全文搜索引擎，支持社区帖子、百科内容的快速检索
- 配置为可选依赖，可通过环境变量控制启用/禁用

### 集成方式
- 通过 `MEILISEARCH_API_KEY` 环境变量配置访问密钥
- 默认连接地址：`http://localhost:7700`
- 索引名称：`subskin_content`
- 支持可搜索字段、过滤字段、排序字段的灵活配置

### 当前状态
- 在配置文件中有完整定义，但实际部署中可能未启用
- 作为可选功能，不影响核心业务运行

### 注意事项
- 生产环境需要独立部署 Meilisearch 服务
- 需要合理配置索引策略和性能参数