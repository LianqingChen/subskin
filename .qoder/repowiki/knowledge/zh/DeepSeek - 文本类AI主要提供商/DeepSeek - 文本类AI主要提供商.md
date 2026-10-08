---
kind: external_dependency
name: DeepSeek - 文本类AI主要提供商
slug: deepseek
category: external_dependency
category_hints:
    - vendor_identity
    - sdk_real_api
scope:
    - '**'
---

### 身份与角色
- DeepSeek 是当前项目文本类 AI 功能的主要提供商，替代了原有的百炼文本模型
- 承担 RAG 问答、简报生成、百科内容生成、文本总结、翻译等核心文本处理能力

### 集成方式
- 使用 DeepSeek 官方 API：`https://api.deepseek.com/v1`
- 主模型：`deepseek-v4-flash`（原 `deepseek-chat` 已映射到此模型）
- 通过 `DEEPSEEK_API_KEY` 环境变量注入密钥
- 支持流式响应，用于实时对话体验

### 当前状态
- 已成功切换并运行稳定，问答、周报摘要、百科生成等功能正常
- 修复了双重加密导致的认证失败问题
- 支持个性化 RAG，可注入用户档案、日记、用药上下文

### 注意事项
- 仅支持文本处理，不具备视觉能力，不能替代百炼的视觉模型
- 模型名称使用官方最新命名规范