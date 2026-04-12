# 照片上传与AI知识库功能 - 流程设计

> **版本**: 1.0
> **日期**: 2026-04-07
> **状态**: 完整设计
> **关联文档**: [需求文档](./photo-upload-and-ai-kb-requirements.md) | [风险应对方案](./risk-mitigation-plan.md) | [架构设计](./photo-upload-and-ai-kb-architecture.md)

---

## 文档概述

本文档为照片上传和AI知识库功能提供详细的功能流程图，包括：
1. 照片上传流程 - 从选择文件到存储完成
2. AI分析流程 - 从触发分析到结果展示
3. 知识库检索流程 - 从语义搜索到结果排序
4. 异常处理流程 - 降级策略和错误恢复

---

## 功能一：照片上传流程

### 1.1 主流程（正常场景）

```
用户点击"上传照片"按钮
    ↓
显示文件选择对话框
    ↓
用户选择照片文件
    ↓
前端验证文件格式和大小
    ↓ 格式正确？尺寸≤10MB？
    ↓ 是
显示上传进度条
    ↓
生成预签名上传URL
    ↓
直接上传到对象存储（阿里云OSS/S3）
    ↓ 上传成功？
    ↓ 是
提取照片元数据（EXIF、尺寸、格式）
    ↓
生成缩略图（300×300px，WebP格式）
    ↓
上传缩略图到对象存储
    ↓
计算文件SHA-256哈希
    ↓
[后台] 保存照片记录到数据库
    ↓ photo_id=123
返回上传成功响应
    ↓
显示成功提示 + 照片预览
    ↓
[可选] 自动触发AI分析
```

### 1.2 上传失败降级流程

```
主存储（阿里云OSS）上传失败
    ↓ 记录错误日志
检查本地存储配置
    ↓ 本地存储可用？
    ↓ 是
使用本地文件系统存储
    ↓ 返回本地URL
标记降级状态
    ↓
前端显示警告："云存储暂时不可用，使用本地存储"
    ↓
    ↓ 否
返回错误给用户
    ↓
前端显示错误："上传失败，请稍后重试"
```

---

## 功能二：AI分析流程

### 2.1 完整分析流程（正常场景）

```
用户点击"AI分析"按钮
    ↓
检查是否已存在分析结果
    ↓ 已存在？
    ↓ 是 → 显示已有结果
    ↓ 否
显示分析中状态（加载动画）
    ↓
[后台] 调用AI分析服务
    ↓ USE_MOCK_AI == true？
    ↓ 是
使用Mock服务（返回模拟结果，延迟3秒）
    ↓
    ↓ 否
调用真实模型
    ↓ 加载照片到内存
    ↓ 预处理（归一化、调整尺寸）
    ↓ 推理白斑检测（UNet/SAM）
    ↓ 推理严重程度分类（ResNet/ViT）
    ↓ 推理病情阶段（进展期/稳定期）
    ↓ 汇总结果
    ↓
分析成功？
    ↓ 否
自动降级到Mock
    ↓ 标记degraded=true
    ↓ 前端显示警告："AI服务暂时不可用，使用模拟结果"
    ↓
    ↓ 是
保存分析结果到数据库
    ↓
触发知识库检索
    ↓ 提取关键关键词
    ↓ 构造查询语句
    ↓ 调用混合检索（全文+向量）
    ↓ 按相关性排序，取Top-5
    ↓ 保存推荐结果
    ↓
生成个性化建议
    ↓ 基于分析结果生成用药建议
    ↓ 生成生活方式建议
    ↓ 添加免责声明
    ↓
返回完整结果
    ↓
前端展示结果
    ↓ 显示诊断信息卡片
    ↓ 显示知识推荐列表
    ↓ 显示个性化建议
    ↓ 提供反馈入口
```

### 2.2 Mock服务流程（Day 1）

```
收到分析请求
    ↓
检查环境变量 USE_MOCK_AI
    ↓ == "true"？
    ↓ 是
返回Mock服务实例
    ↓
    ↓ 否
返回真实服务实例

[Mock服务处理流程]
    ↓
检查照片元数据（body_part, capture_date, file_size）
    ↓
基于元数据生成"合理"结果
    ↓ if body_part == "face":
    ↓     type = "非节段型面部"
    ↓     severity = "mild"
    ↓ if body_part == "hand":
    ↓     type = "节段型手部"
    ↓     severity = "moderate"
    ↓ confidence = random.uniform(0.65, 0.95)
    ↓
模拟延迟（3秒）
    ↓
构造返回结果（含is_mock标记）
    ↓
返回结果
```

### 2.3 轻量级模型集成流程（Day 2）

```
收到分析请求
    ↓ USE_MOCK_AI == false
    ↓
加载预训练模型（首次）
    ↓ 从Hugging Face下载或本地缓存
    ↓ model = load_model("medical-segmentation/vitiligo-detection")
    ↓ classifier = load_model("microsoft/resnet-50")
    ↓
预处理照片
    ↓ 读取照片字节流
    ↓ 转换为RGB
    ↓ 调整尺寸到模型输入大小（224×224）
    ↓ 归一化
    ↓
白斑检测（分割任务）
    ↓ mask = model.segmentation(image)
    ↓ 计算白斑面积占比
    ↓ 提取白斑位置信息
    ↓
严重程度分类
    ↓ severity_logits = classifier(image)
    ↓ severity_class = argmax(softmax(logits))
    ↓ severity_score = max(softmax(logits))
    ↓
病情阶段判断
    ↓ 基于面积占比+边缘特征判断
    ↓ area > 10% AND 边缘不规则 → progressive
    ↓ area < 5% AND 边缘清晰 → stable
    ↓
汇总结果
    ↓
[异常处理]
    ↓ 模型加载失败或推理异常
    ↓ 记录错误日志
    ↓ 自动降级到Mock服务
    ↓ 返回Mock结果 + degraded标记
```

### 2.4 知识库检索流程

```
收到AI分析结果
    ↓ 提取关键词（白斑类型、严重程度、身体部位、白癜风、治疗）
    ↓
构造混合查询
    ↓
[全文检索]
    ↓ 调用Meilisearch
    ↓ text_results = meilisearch.search(query, limit=10)
    ↓
[向量检索]（Phase 2，可选）
    ↓ 调用ChromaDB/Pinecone
    ↓ query_vector = embedding_model.encode(query)
    ↓ vector_results = vector_db.search(query_vector, top_k=10)
    ↓
[混合排序]
    ↓ 合并全文和向量结果
    ↓ 计算综合评分：combined_score = 0.6 * text_score + 0.4 * vector_score
    ↓ 按combined_score排序
    ↓ 取Top-5
    ↓
[生成高亮摘要]
    ↓ 对每个推荐结果
    ↓ 提取包含关键词的句子
    ↓ 标高亮标记<mark>...</mark>
    ↓ 截取前200字符
    ↓
构造返回结果
    ↓
保存到数据库
    ↓
返回推荐结果
```

---

## 功能三：照片管理流程

### 3.1 照片删除流程

```
用户点击"删除照片"按钮
    ↓
显示确认对话框
    ↓
用户确认？
    ↓ 是
发送删除请求
    DELETE /api/photos/{photo_id}
    ↓
[后端] 验证JWT Token + 验证所有权
    ↓
执行软删除
    ↓ UPDATE photos SET is_deleted = true, deleted_at = NOW()
    ↓
延迟删除对象存储文件（7天）
    ↓ [后台任务] 调度任务 delete_from_storage.delay(delay=7_days)
    ↓
返回成功响应
    ↓
前端更新UI（从列表中移除照片）
    ↓ 显示Toast提示
```

### 3.2 照片恢复流程（撤销删除）

```
用户在7天内的地方照片中点击"恢复"
    ↓
发起恢复请求
    POST /api/photos/{photo_id}/restore
    ↓
[后端] 验证JWT Token + 验证所有权
    ↓
检查是否可恢复
    ↓ is_deleted == true AND deleted_at < 7 days ago？
    ↓ 是
恢复照片
    ↓ UPDATE photos SET is_deleted = false, deleted_at = NULL
    ↓
返回成功响应
    ↓
    ↓ 否
返回400 "照片已过期，无法恢复"
```

---

## 功能四：反馈与优化流程

### 4.1 AI分析反馈流程

```
用户对AI分析结果打分
    ↓ 5星
发起反馈请求
    POST /api/photos/{photo_id}/analysis/feedback
    Body: {rating: 5, comment: "分析很准确", helpful: true}
    ↓
[后端] 验证JWT Token
    ↓
保存反馈到数据库
    ↓ INSERT INTO analysis_feedback(...)
    ↓
更新AI服务监控指标
    ↓ 统计平均评分
    ↓
返回成功响应
    ↓
前端显示感谢提示
```

---

## 边界规则说明

### 照片上传边界规则

1. **文件格式限制**
   - 仅支持：JPEG、PNG、WebP
   - 不支持的格式返回错误提示

2. **文件大小限制**
   - 单张照片最大：10MB
   - 超过限制返回错误提示

3. **上传频率限制**
   - 速率限制：10次/小时
   - 超出限制返回429 Too Many Requests

4. **重复上传处理**
   - 可选功能：检测SHA-256哈希
   - 重复照片显示警告，允许继续上传

5. **元数据验证**
   - body_part为必填项
   - treatment_stage为选填项
   - description最长500字

### AI分析边界规则

1. **分析结果缓存**
   - 相同照片不重复分析
   - 缓存永久保存，除非用户删除

2. **分析频率限制**
   - 速率限制：5次/小时
   - 超出限制返回429

3. **降级策略**
   - 真实模型失败 → 自动降级到Mock
   - 前端显示降级警告

4. **超时保护**
   - 分析超时时间：30秒
   - 超时后返回错误

5. **置信度阈值**
   - Mock置信度：65%-95%随机
   - 真实模型置信度：< 0.5提示结果可能不准确

---

**文档状态**: 已完成

**下一步**: 补充边界规则到需求文档

**预计完成日期**: 2026-04-07
