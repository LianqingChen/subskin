---
kind: logging_system
name: SubSkin 日志系统：基于 Python logging 的统一结构化日志方案
category: logging_system
scope:
    - '**'
source_files:
    - src/utils/logger.py
    - src/settings/logging.py
    - src/scheduler/update_scheduler.py
    - tests/test_logger.py
    - tests/test_logging.py
---

## 1. 使用的系统与框架

SubSkin 项目使用 Python 标准库 `logging` 模块作为核心日志框架，并通过自定义工具函数提供统一的日志获取与配置入口。未引入第三方日志库（如 loguru、structlog），所有日志功能均基于标准库实现。

## 2. 核心文件与位置

- **主要日志工具**：`src/utils/logger.py` — 提供 `get_logger()` 工厂函数，统一创建带控制台输出和可选文件轮转的 Logger 实例
- **设置层日志配置**：`src/settings/logging.py` — 提供基于 settings 配置的 `configure_logging()` 和 `get_logger()` 快捷方式
- **调度器专用日志**：`src/scheduler/update_scheduler.py` — 使用独立日志文件 `logs/scheduler.log` 并启用 7 天轮转
- **日志测试**：`tests/test_logger.py`、`tests/test_logging.py` — 覆盖日志级别、文件输出、实例复用等场景
- **日志文件目录**：`logs/` — 存放按日期轮转的 scheduler 日志文件（scheduler.log.2026-08-05 等格式）

## 3. 架构与设计决策

### 3.1 双入口设计
项目存在两套日志获取方式：
- **工具层**（`src/utils/logger.py`）：提供 `get_logger(name, log_file=None, level=logging.INFO, rotate_days=7)` 工厂函数，支持控制台 + 可选文件输出 + 时间轮转
- **设置层**（`src/settings/logging.py`）：提供 `configure_logging(name, level=None)` 从 settings 读取 LOG_LEVEL 并配置基础 StreamHandler

### 3.2 日志格式规范
统一采用管道分隔格式：`%(asctime)s | %(levelname)s | %(name)s | %(message)s`，时间格式为 `%Y-%m-%d %H:%M:%S`

### 3.3 处理器策略
- **控制台输出**：始终添加 `StreamHandler(sys.stderr)`，避免重复添加
- **文件输出**：可选参数 `log_file` 指定路径，使用 `TimedRotatingFileHandler` 按午夜轮转，默认保留 7 天
- **传播控制**：`logger.propagate = False` 防止消息向上传播造成重复输出

### 3.4 使用模式
各模块通过 `from src.utils.logger import get_logger` 获取 logger，典型用法：
```python
logger = get_logger(__name__)  # 仅控制台输出
logger = get_logger(__name__, log_file="logs/app.log", rotate_days=7)  # 控制台 + 文件轮转
```

## 4. 约定与约束

### 4.1 命名约定
- 每个模块通过 `__name__` 作为 logger 名称，形成层级结构（如 `subskin.scheduler.update_scheduler`）
- 类内部实例 logger 使用 `f"{__name__}.ClassName"` 模式（见 `qq_notifier.py` 中的 `NotificationManager`）

### 4.2 级别使用约定
- 默认级别为 `INFO`，调试信息使用 `DEBUG`，警告使用 `WARNING`，错误使用 `ERROR`
- 测试验证了四个级别都能正确输出到 stderr 和文件

### 4.3 文件轮转规则
- 使用 `TimedRotatingFileHandler` 在午夜自动轮转
- 轮转文件格式：`scheduler.log.2026-08-05`（日期后缀）
- 默认保留 7 天历史文件，可通过 `rotate_days` 参数调整

### 4.4 异常处理集成
项目定义了自定义异常类型（`CrawlerError`、`APIError`、`RateLimitError`、`CacheError`），这些异常在测试中被验证能正常抛出和捕获，但未发现专门的异常日志记录机制。

### 4.5 配置管理
- 日志级别可通过 `settings.LOG_LEVEL` 环境变量或配置文件设置
- 文件路径和轮转天数通过函数参数直接传入，无集中配置文件

## 5. 当前状态评估

日志系统实现相对简单但完整，覆盖了基本的控制台输出、文件持久化和轮转需求。不过存在以下特点：
- 两套 `get_logger` 实现（utils 和 settings）可能造成混淆
- 缺少结构化日志字段（如请求 ID、用户 ID 等业务上下文）
- 未实现日志级别动态调整或异步写入
- 爬虫模块直接使用 `logging.getLogger(__name__)` 而非统一工具函数