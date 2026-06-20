---
name: llm-testing
description: "SubSkin AI/LLM 功能测试 — RAG 向量化、智能问答、VASI 评估"
---

# LLM Testing Skill

> SubSkin AI/LLM 功能测试 — RAG 向量化、智能问答、VASI 评估
>
> **触发词**: LLM测试、RAG测试、AI测试、向量化测试、embedding测试

---

## 测试项目

### 1. RAG Embedding API

```bash
# 验证 embedding API 可用
cd /root/subskin
source .venv/bin/activate
python -c "
from web.backend.utils.llm_config import get_llm_config
config = get_llm_config('rag')
print(f'Provider: {config[\"provider\"]}')
print(f'Embedding model: {config[\"embedding_model\"]}')
print(f'Dimensions: {config.get(\"embedding_dimensions\")}')
"
```

### 2. 批量向量化（手动触发）

```bash
# 手动触发增量向量化
curl -X POST http://127.0.0.1:8000/api/admin/embed-batch \
  -H "Authorization: Bearer <admin_token>"
```

### 3. 智能问答测试

```bash
# 测试 RAG 搜索是否返回结果
curl -s http://127.0.0.1:8000/api/chat/search \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"白癜风治疗方法"}'
```

### 4. 查看数据库中未向量化文档数

```bash
sqlite3 /root/subskin/web/backend/data/subskin.db \
  "SELECT COUNT(*) as unembedded FROM documents WHERE embedding IS NULL; SELECT COUNT(*) as total FROM documents;"
```

### 5. VASI 评估 API

```bash
# 测试 VASI 评估端点（需要图片文件）
curl -s http://127.0.0.1:8000/api/vasi/health 2>/dev/null || echo "No health endpoint"
```

---

## 关键配置

| 配置项 | 环境变量 | 默认值 |
|---|---|---|
| LLM Provider | `DASHSCOPE_API_KEY` / `VOLCENGINE_API_KEY` | — |
| Embedding 模型 | `DASHSCOPE_EMBEDDING_MODEL` | `text-embedding-v4` |
| Embedding 维度 | `DASHSCOPE_EMBEDDING_DIMENSIONS` | `1024` |
| 向量化开关 | `RAG_USE_VECTOR` | `true` |
| 批量限速 | `batch_embed_unembedded()` 内 1.5秒 | 1.5s |