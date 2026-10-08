---
kind: external_dependency
name: 阿里云百炼平台 - 视觉AI与内容安全服务
slug: aliyun-dashscope
category: external_dependency
category_hints:
    - vendor_identity
    - auth_protocol
scope:
    - '**'
---

### 身份与角色
- 阿里云百炼（DashScope）是本项目视觉AI能力的主要供应商，提供 VASI 白斑测评、体检报告解析、内容安全审核、IM 内容审核等视觉模型调用
- 文本类 AI（问答、周报摘要、百科生成、翻译、总结）已切换至 DeepSeek 官方 API，不再依赖百炼

### 集成方式
- 通过 DashScope 兼容模式端点调用，使用 `DASHSCOPE_API_KEY` 环境变量注入密钥
- 视觉模型：`qwen-vl-max`（VASI 测评、医疗报告解析）
- 文本模型：`qwen-turbo`（内容安全审核、IM 审核）
- 密钥格式要求：标准 `sk-` 开头的 35 位字符串，不支持 `sk-sp-` 前缀的 Token Plan key

### 当前状态
- 文本类模块已全部迁移到 DeepSeek，运行正常
- 视觉模块仍依赖百炼，但当前 API Key 失效，需要重新获取标准格式的 API Key
- Embedding 向量化任务已从自动改为手动触发，避免无谓消耗
- 每日 6:00 的内容生成 cron 已移除，改为管理后台手动触发

### 注意事项
- 百炼账户欠费会导致所有视觉功能不可用
- 新申请的 API Key 必须是标准格式（`sk-` + 32位hex），不是 Token Plan 的 JWT 格式
- 更换 Key 后需要同步更新数据库中加密存储的旧 Key 记录