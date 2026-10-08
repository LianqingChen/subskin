---
kind: configuration_system
name: SubSkin 配置系统：Pydantic Settings + 多源配置文件分层管理
category: configuration_system
scope:
    - '**'
source_files:
    - src/settings/settings.py
    - src/settings/base.py
    - src/settings/__init__.py
    - src/config.py
    - configs/.env.example
    - configs/crawler_config.yaml
    - configs/web_config.yaml
    - scheduler_config.json
---

## 1. 使用的系统与框架
- **核心框架**：基于 Pydantic v2 的 `BaseModel` 构建类型化配置类，通过 `model_config` 启用 `extra="forbid"`、`env_file`、`validate_default=True` 等严格校验。
- **环境变量加载**：优先读取进程环境变量（`os.getenv`），其次回退到 `.env` 文件；若未安装 `python-dotenv`，则使用内置的简单解析器（支持注释、引号包裹值）。
- **配置文件格式**：除 `.env`/环境变量外，还使用 YAML（`configs/crawler_config.yaml`、`configs/web_config.yaml`）和 JSON（`scheduler_config.json`）承载领域特定配置。
- **向后兼容包装**：`src/config.py` 仅做 re-export，强制新代码从 `src.settings` 导入。

## 2. 关键文件与包
- `src/settings/settings.py` — 定义 `Settings` Pydantic 模型，集中声明所有运行时配置项（API Key、数据库、邮件、调度、存储、监控等）。
- `src/settings/base.py` — `.env` 文件解析工具（`_resolve_env_file`、`_read_env_file`）。
- `src/settings/paths.py` — 项目根路径与数据目录常量。
- `src/settings/logging.py` — 日志初始化入口。
- `src/settings/__init__.py` — 统一导出 `PROJECT_ROOT`、`DATA_DIR`、`configure_logging`、`Settings`、`settings` 等。
- `src/config.py` — 向后兼容层，指向 `src.settings.settings`。
- `configs/.env.example` — 完整的环境变量模板（含生产环境段）。
- `configs/crawler_config.yaml` — 爬虫各数据源的搜索词、速率限制、缓存策略等。
- `configs/web_config.yaml` — Web 站点、认证、LLM/RAG、内容管理、搜索、邮件、监控、安全等配置。
- `scheduler_config.json` — 定时任务频率、通知开关等。

## 3. 架构与约定
- **单例全局实例**：模块末尾 `settings = Settings()` 提供全局可访问的配置对象，应用启动时即完成加载与校验。
- **分层加载顺序**：进程环境变量 > `.env` 文件 > Pydantic Field 默认值。字段名必须与 `.env` key 一一对应。
- **严格模式**：`extra="forbid"` 禁止未知字段，避免拼写错误静默失效。
- **类型与范围校验**：每个字段通过 `Field(..., ge=..., le=..., pattern=...)` 进行数值范围、正则格式等约束（如端口、时间格式、cron 表达式）。
- **缺失键检测**：`missing_keys()` / `validate()` 方法用于启动时检查必填项是否齐全。
- **YAML/JSON 配置独立于 Settings**：爬虫与 Web 配置以纯 YAML/JSON 形式存在，由各自模块自行解析，不混入 Pydantic Settings。
- **路径解析**：`.env` 路径可通过 `ENV_FILE` 环境变量或构造函数参数覆盖，否则默认在项目根目录下查找。

## 4. 约定与约束
- **新代码必须从 `src.settings` 导入**：`src/config.py` 明确声明“New code should import from `src.settings` instead”，旧接口仅保留兼容性。
- **敏感信息不得硬编码**：所有 API Key、密码、Secret 均通过环境变量注入，`.env.example` 中均为占位符。
- **字段命名规范**：配置项全部使用 UPPER_SNAKE_CASE，与 `.env` 键名一致。
- **默认值保守**：多数功能开关（如 `QQ_BOT_ENABLED`、`ALIYUN_OSS_ENABLED`、`ALERT_EMAIL_ENABLED`）默认关闭，需显式开启。
- **端口与超时校验**：端口字段限定 1–65535，超时/重试次数等数值字段带 `ge=0` 或 `ge=1` 下限约束。
- **日志级别规范化**：`__init__` 中对 `LOG_LEVEL` 执行 `.strip().upper()` 标准化处理。
- **YAML 中的环境变量引用**：`web_config.yaml` 与 `crawler_config.yaml` 使用 `${VAR}` 语法引用环境变量（由各自解析器处理）。
- **调度配置独立**：`scheduler_config.json` 单独管理定时任务行为，不与主 Settings 混用。