---
kind: external_dependency
name: Sentry - 错误追踪与监控
slug: sentry
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
---

### 身份与角色
- Sentry 作为项目的错误追踪和性能监控服务
- 用于收集后端异常、前端错误和性能指标

### 集成方式
- 通过 `SENTRY_DSN` 环境变量配置 DSN 地址
- 支持 Python SDK 和 JavaScript SDK 集成
- 可配置采样率、忽略特定错误类型

### 当前状态
- 在依赖列表中存在，但生产环境可能未启用
- 配置项包含在 web_config.yaml 中

### 注意事项
- 生产环境需要配置有效的 DSN 地址
- 建议在生产环境启用以提升故障排查效率