---
kind: external_dependency
name: ChromaDB - RAG向量数据库
slug: chromadb
category: external_dependency
category_hints:
    - framework_behavior
    - client_constraint
scope:
    - '**'
---

### 身份与角色
- ChromaDB 作为本地向量数据库，存储白癜风知识库的向量嵌入，支撑 RAG 问答系统
- 支持增量更新和批量向量化操作

### 集成方式
- 通过 `compute_embedding=False` 参数控制是否自动计算向量
- 集合名称：`subskin_knowledge`
- 数据路径：`data/vector_db`
- 支持多种 embedding 模型配置

### 当前状态
- 已向量化任务从自动改为手动触发，避免无谓的 API 消耗
- 管理后台提供手动触发按钮进行批量向量化
- 新爬取的文献入库时不再自动调用向量化 API

### 注意事项
- 需要定期执行批量向量化以保持知识库新鲜度
- 向量数据存储在本地文件系统，需要注意备份