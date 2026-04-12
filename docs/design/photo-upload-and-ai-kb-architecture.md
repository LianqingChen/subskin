# 照片上传与AI知识库功能 - 技术架构设计

> **版本**: 1.0
> **日期**: 2026-04-07
> **状态**: 设计阶段
> **关联文档**: [需求文档](./photo-upload-and-ai-kb-requirements.md)

---

## 文档概述

本文档为照片上传和AI知识库功能提供完整的技术架构设计，包括：
1. **数据结构设计** - 数据库模型、数据流设计
2. **API接口设计** - RESTful API规范、请求/响应格式
3. **安全方案设计** - 认证授权、数据加密、隐私保护

---

## 1. 数据结构设计

### 1.1 数据库模型设计

#### 1.1.1 Photo 表（照片）

新增表：存储用户上传的照片元数据

主要字段：
- id (Integer, 主键)
- user_id (Integer, 外键→users.id)
- original_url (String) - 原图URL（对象存储）
- thumbnail_url (String) - 缩略图URL（300×300px，WebP）
- file_format (String) - jpeg/png/webp
- file_size (Integer) - 字节数，≤10MB
- file_hash (String) - SHA-256，去重用
- capture_date (DateTime) - 拍摄时间
- body_part (String) - 身体部位枚（脸、颈、手、躯干、腿等）
- treatment_stage (String) - 治疗阶段（未治疗、初期、治疗中、稳定期）
- description (Text) - 用户备注
- is_deleted (Boolean) - 软删除标记
- is_private (Boolean) - 是否私密（默认true）
- created_at, updated_at, deleted_at (DateTime)

关系：
- analysis → PhotoAnalysis (1:1)
- doctor_notes → DoctorNote (1:N)

索引：
- idx_photos_user_created (user_id, created_at DESC)
- idx_photos_body_part (body_part)

---

#### 1.1.2 PhotoAnalysis 表（AI分析结果）

新增表：存储AI诊断分析结果

主要字段：
- id (Integer, 主键)
- photo_id (Integer, 外键→photos.id, UNIQUE)
- vitiligo_type (String) - 白斑类型（节段型、泛发型、局灶型等）
- vitiligo_type_confidence (Float) - 类型置信度 0-1
- severity_level (String) - 严重程度（mild/moderate/severe）
- severity_score (Float) - 严重程度评分 0-1
- distribution (Text) - 分布描述
- area_coverage (Float) - 覆盖面积百分比 0-100
- disease_stage (String) - 病情阶段（stable/progressive）
- stage_confidence (Float) - 阶段置信度 0-1
- ai_model_version (String) - AI模型版本
- analysis_duration_ms (Integer) - 分析耗时
- overall_confidence (Float) - 总体置信度 0-1
- status (String) - completed/failed/pending
- error_message (Text) - 错误信息
- created_at, updated_at (DateTime)

关系：
- photo → Photo (N:1)
- recommendations → KnowledgeRecommendation (1:N)

---

#### 1.1.3 KnowledgeRecommendation 表（知识推荐）

新增表：AI分析推荐的知识条目，关联到Document表

主要字段：
- id (Integer, 主键)
- analysis_id (Integer, 外键→photo_analyses.id)
- document_id (Integer, 外键→documents.id)
- relevance_score (Float) - 相关性评分 0-1
- recommendation_type (String) - 推荐类型（treatment/research_paper/guideline等）
- highlight_snippet (Text) - 高亮摘要
- created_at (DateTime)

---

#### 1.1.4 DoctorNote 表（医生备注）

新增表：医生对照片的诊断备注（Phase 2功能）

主要字段：
- id (Integer, 主键)
- photo_id (Integer, 外键→photos.id)
- doctor_id (Integer, 外键→users.id，医生用户ID)
- diagnosis (Text) - 诊断结论
- severity_assessment (String) - 医生评估严重程度
- treatment_suggestion (Text) - 治疗建议
- notes (Text) - 其他备注
- is_confirmed (Boolean) - 是否确认
- created_at, updated_at (DateTime)

---

## 2. API接口设计

### 2.1 接口通用规范

域名：
- 开发环境: http://localhost:8000
- 生产环境: https://api.subskin.org

认证：所有照片相关接口均需要JWT认证

通用响应格式：
- 成功：{"success": true, "data": {...}, "message": "..."}
- 失败：{"success": false, "error": {"code": "...", "message": "..."}}

错误码：UNAUTHORIZED, FORBIDDEN, PHOTO_NOT_FOUND, INVALID_FORMAT, FILE_TOO_LARGE, STORAGE_ERROR, AI_SERVICE_DOWN, AI_TIMEOUT

---

### 2.2 照片管理接口

#### 2.2.1 上传照片
- POST /api/photos
- 需要JWT认证
- multipart/form-data
- 参数：file (必填), capture_date (选填), body_part (必填), treatment_stage (选填), description (选填)
- 返回：photo_id, original_url, thumbnail_url, file_format, file_size, capture_date, body_part, treatment_stage, created_at

#### 2.2.2 获取照片列表
- GET /api/photos
- 需要JWT认证
- 查询参数：page, page_size, body_part, treatment_stage, date_from, date_to, sort_by, sort_order
- 返回：photos数组 + pagination信息

#### 2.2.3 获取照片详情
- GET /api/photos/{photo_id}
- 需要JWT认证
- 返回：照片完整信息

#### 2.2.4 删除照片
- DELETE /api/photos/{photo_id}
- 需要JWT认证
- 返回：success message

---

### 2.3 AI分析接口

#### 2.3.1 分析照片
- POST /api/photos/{photo_id}/analyze
- 需要JWT认证
- 返回：诊断结果 + 个性化建议 + 知识推荐

响应结构：
```json
{
  "success": true,
  "data": {
    "analysis_id": 123,
    "photo_id": 456,
    "diagnosis": {
      "vitiligo_type": "non_segmental_focal",
      "vitilic_type_confidence": 0.87,
      "severity_level": "moderate",
      "severity_score": 0.55,
      "distribution": "面部右侧颧骨区域",
      "area_coverage": 3.2,
      "disease_stage": "progressive",
      "stage_confidence": 0.72
    },
    "ai_info": {
      "model_version": "v1.2.3",
      "analysis_duration_ms": 4523,
      "overall_confidence": 0.79
    },
    "recommendations": [
      {
        "document_id": 789,
        "title": "局限性白癜风治疗指南",
        "relevance_score": 0.92,
        "recommendation_type": "clinical_guideline",
        "snippet": "对于局限性白癜风，外用激素..."
      }
    ],
    "suggestions": [
      "建议使用外用钙调神经磷酸酶抑制剂",
      "注意防晒，避免紫外线刺激",
      "定期随访，监测病情变化"
    ],
    "created_at": "2026-04-07T11:00:00Z"
  }
}
```

#### 2.3.2 获取分析结果
- GET /api/photos/{photo_id}/analysis
- 需要JWT认证
- 返回：已保存的分析结果

#### 2.3.3 提交反馈
- POST /api/photos/{photo_id}/analysis/feedback
- 需要JWT认证
- 参数：rating (1-5), comment (选填), helpful (Boolean)
- 返回：success message

---

## 3. 安全方案设计

### 3.1 认证与授权

3.1.1 用户认证
- 使用现有JWT认证系统
- 所有照片相关接口均需要有效JWT Token
- Token过期时间：30分钟（可配置）

3.1.2 数据所有权
- 照片数据归属检查：photo.user_id == current_user.id
- 删除操作严格验证所有权
- 医生备注仅限具有医生权限的用户

3.1.3 权限控制
- 普通用户：仅可访问自己的照片
- 管理员：可查看所有照片（审计用）
- 医生：可查看患者照片（需患者授权，未来功能）

---

### 3.2 数据加密

3.2.1 照片存储加密
- 对象存储启用服务器端加密（SSE-S3 / AES-256）
- 缩略图同样加密
- 密钥管理：使用云服务商KMS（AWS KMS / 阿里云KMS）

3.2.2 传输加密
- 所有API请求强制HTTPS（生产环境）
- TLS 1.2+，强加密套件
- HSTS启用

3.2.3 数据库加密
- 敏感字段加密（如照片描述中包含的PII）
- 使用AES-256加密敏感文本
- 加密密钥存储于环境变量或密钥管理服务

---

### 3.3 隐私保护

3.3.1 数据最小化
- 仅收集必要的照片元数据
- 不存储用户身份信息于照片文件名
- AI分析请求中不传递用户身份

3.3.2 数据保留策略
- 用户删除照片后7天从对象存储清除
- 分析结果保留，用于历史对比（可申请删除）
- 日志数据保留90天

3.3.3 用户控制
- 提供数据导出功能（GDPR合规）
- 提供数据删除功能（完全清除）
- 隐私设置页（照片可见性控制）

3.3.4 匿名化
- AI模型训练数据匿名化处理
- 统计分析使用聚合数据
- 不向第三方分享原始照片数据

---

### 3.4 访问控制

3.4.1 速率限制
- 照片上传：10次/小时
- AI分析：5次/小时
- API请求：100次/分钟
- 超出返回429 Too Many Requests

3.4.2 IP白名单
- 管理员接口启用IP白名单
- 内部服务间通信使用专用网络

3.4.3 审计日志
- 所有照片操作记录审计日志
- 记录内容：user_id, action, resource_id, timestamp, ip_address
- 日志存储：安全日志系统（如CloudWatch / 阿里云日志）

---

### 3.5 依赖服务安全

3.5.1 对象存储安全
- Bucket私有访问，仅限应用服务器
- 预签名URL短期有效（5分钟）
- CORS严格限制域名

3.5.2 AI服务安全
- 使用临时凭证访问AI服务
- AI请求不包含用户PII
- 照片数据临时传输，不持久化

3.5.3 知识库安全
- 全文搜索结果过滤（仅返回公开知识）
- RAG检索不暴露敏感文档
- 向量数据库访问控制

---

## 4. 技术选型

### 4.1 对象存储
- 首选：阿里云OSS / AWS S3
- 备选：MinIO（自托管）
- 特性：服务器端加密、预签名URL、生命周期管理

### 4.2 AI图像分析服务
- 选项1：自研模型（PyTorch + FastAPI）
- 选项2：第三方API（AWS Rekognition, Google Vision）
- 推荐：自研模型，数据不外传，可控性强

### 4.3 知识库检索
- 全文搜索：Meilisearch / Elasticsearch
- 向量检索：ChromaDB / Pinecone（Phase 2）
- 混合检索：全文+向量结合（提升相关性）

---

## 5. 数据迁移计划

### 5.1 数据库迁移
1. 创建迁移脚本：alembic revision -m "Add photo upload tables"
2. 升级数据库：alembic upgrade head
3. 验证表结构：alembic check
4. 回滚测试：alembic downgrade -1

### 5.2 索引优化
1. 创建复合索引：(user_id, created_at DESC)
2. 创建单列索引：body_part, treatment_stage, file_hash
3. 分析查询计划：EXPLAIN ANALYZE
4. 优化慢查询

---

## 6. 性能优化策略

### 6.1 上传优化
- 前端：分片上传，支持断点续传
- 后端：异步生成缩略图（Celery / 后台任务）
- CDN：照片分发使用CDN加速
- 压缩：WebP格式，质量85%

### 6.2 查询优化
- 分页：避免全量查询，使用游标分页
- 缓存：热门照片分析结果缓存（Redis）
- 只读：照片详情查询使用只读副本
- 索引：充分利用复合索引

### 6.3 AI分析优化
- 缓存：分析结果永久缓存
- 异步：长时间分析异步化，返回任务ID
- 超时：30秒超时保护，避免阻塞
- 限流：控制并发分析数量

---

## 7. 监控与告警

### 7.1 关键指标
- 照片上传成功率、平均延迟
- AI分析完成率、响应时间
- 对象存储可用性、延迟
- 数据库查询性能
- 错误率（4xx, 5xx）

### 7.2 告警规则
- 上传失败率 > 1% 立即告警
- AI分析失败率 > 5% 告警
- 存储服务不可用 告警
- 数据库连接池耗尽 告警
- 请求响应时间 > 5s（P99）告警

### 7.3 日志规范
- 结构化日志（JSON格式）
- 日志级别：ERROR, WARN, INFO, DEBUG
- 包含上下文：request_id, user_id, action
- 敏感信息脱敏

---

## 8. 合规检查清单

- [ ] GDPR：数据导出、删除功能
- [ ] 医疗合规：AI诊断免责声明
- [ ] 隐私政策：照片数据使用说明
- [ ] 安全审计：定期渗透测试
- [ ] 数据备份：每日增量备份
- [ ] 灾难恢复：RPO < 1小时, RTO < 4小时

---

**文档状态**: 待评审

**下一步**: 创建开发排期文档

**预计完成日期**: 2026-04-08
