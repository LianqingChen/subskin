# 05 · 后端架构、数据库、AI/LLM 与算法服务规范

> **文档编号**: `STD-05`  
> **适用范围**: 后端服务（`web/backend/`）、离线数据管线（`src/`）、SQLite 数据库  
> **关联 Skill**: `backend-architect`、`llm-testing`  
> **更新日期**: 2026-10-17  
> **状态**: 强制执行（MANDATORY）

---

## 一、核心认知：三环境共享唯一后端实例（Shared Backend Reality）

```text
https://subskin.cn (正式)  ──┐
https://staging.subskin.cn ──┼──► Nginx (/api/*) ──► FastAPI (127.0.0.1:8000) ──► SQLite (subskin.db)
https://admin.subskin.cn   ──┘
```

- **没有独立的测试环境后端或测试数据库**。
- 对 `web/backend/` 下任何 Python 代码、`.env` 配置或 SQLite 数据库表结构的修改，一旦重启 `subskin-backend`，**立即对所有线上正式用户生效**。
- 因此，后端开发必须遵循最高标准的**向后兼容性（Backward Compatibility）**与**防御性编程**。

---

## 二、严格三层架构与依赖方向（Three-Layer Architecture）

后端代码位于 `web/backend/`，强制实行三层职责分离，严禁跨层反向依赖：

```text
┌─────────────────────────────────────────────────────────────────┐
│ 1. API 路由层 (web/backend/api/*.py)                             │
│    - 职责：Pydantic 请求校验、鉴权依赖注入、调用 Service、         │
│            捕获领域异常并转换为 FastAPI HTTPException             │
│    - 禁止：直接编写复杂 SQL 事务或跨模块导入其他路由的 _私有函数   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ 单向调用
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Service 业务服务层 (web/backend/services/*.py)                │
│    - 职责：核心业务逻辑、数据库读写、LLM/CV 调用、审计日志写入     │
│    - 强制铁律：绝对禁止导入 fastapi (如 HTTPException, Request)！ │
│                遇到业务校验失败统一抛出 exceptions.py 中的领域异常 │
└───────────────────────────────┬─────────────────────────────────┘
                                │ 单向调用
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Data & Utils 基础层 (web/backend/models.py, utils/*.py)       │
│    - 职责：SQLAlchemy ORM 模型、纯工具函数、LLM 配置、PII 脱敏     │
│    - 强制铁律：零业务耦合、零 Web 框架依赖                         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 领域异常转换模式（Domain Exceptions）
所有业务异常统一在 `web/backend/exceptions.py` 中定义（继承自 `SubSkinException`）：
```python
# Service 层：只抛领域异常，不碰 FastAPI
from web.backend.exceptions import CredentialConflictError

def bind_credential(db: Session, user_id: int, ...):
    if existing:
        raise CredentialConflictError("该手机号已绑定其他账号")

# API 层：捕获领域异常并映射为 HTTP 状态码；未知异常统一打日志并返回通用提示
@router.post("/bind")
def bind_route(...):
    try:
        return bind_credential(db, current_user.id, ...)
    except CredentialConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("绑定失败: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
```

### 2.2 公共函数共享入口（严禁跨模块导入 `_private` 函数）
- **LLM 配置统一入口**：必须使用 `from web.backend.utils.llm_config import get_llm_config`，严禁在各模块内重复读取环境变量或导入 `rag._get_llm_config`。
- **用户序列化统一入口**：必须使用 `from web.backend.services.user_serializer import get_user_response`，严禁从 `api/user.py` 导入私有函数。
- **PII 脱敏统一入口**：必须使用 `from web.backend.utils.pii_detect import redact_pii`。

---

## 三、Python 3.9 语法兼容与代码风格铁律

生产服务器运行环境包含 Python 3.9 约束，编写后端代码时必须遵守：

1. **禁止使用 Python 3.10+ 专属语法**：
   - ❌ 禁止使用 `str | None`、`int | float` 联合类型语法（会导致运行时 `TypeError: unsupported operand type(s) for |`）。
   - ❌ 禁止使用 `match ... case ...` 结构化模式匹配。
   - ✅ 必须使用 `from typing import Optional, List, Dict, Union, Tuple, Any`。
2. **日志记录规范**：
   - 统一使用 `%` 占位符延迟求值：`logger.error("VASI 评估异常 user_id=%s: %s", user_id, str(e), exc_info=True)`。
   - 避免在高频日志中使用 f-string，且严禁在日志中输出明文密码、Token、手机号。

---

## 四、数据库与增量迁移规范（SQLite & Additive-Only Migrations）

1. **仅限增量变更（Additive-Only Schema Changes）**：
   - ✅ 允许：新增表（`CREATE TABLE IF NOT EXISTS`）、新增带默认值或允许 `NULL` 的列（`ALTER TABLE ... ADD COLUMN`）、新增索引。
   - ❌ **绝对禁止**：删除列（`DROP COLUMN`）、重命名现有表或列、修改现有列的数据类型或非空约束（会导致正在运行的正式环境立刻报错或历史数据丢失）。
2. **迁移脚本管理**：
   - 结构变更除了更新 ORM 模型外，必须提供幂等的迁移逻辑（检查列是否存在后再执行 `ALTER TABLE`），确保多次重启或重复执行均安全无副作用。
3. **API 契约向后兼容**：
   - 对已有 API 响应结构体，只允许**新增字段**，不得随意删除或重命名前端正在消费的字段。

---

## 五、AI / LLM / RAG 与计算机视觉（CV）服务架构

### 5.1 智能问答与 RAG 检索服务 (`web/backend/services/rag.py`)
- **混合检索架构**：结合 DashScope `text-embedding-v4`（1024 维向量余弦相似度）与关键词检索，从医学论文与科普知识库中召回高置信度上下文。
- **站内功能智能路由（`SITE_FEATURE_KEYWORDS`）**：
  - 当用户提问命中站内功能关键词（源自 `web/shared/site-modules.json`）时，RAG 服务会自动在回复中注入对应的站内模块导航指引，引导用户前往「日记 (`/assessment`)」、「体检解读 (`/assessment/exam`)」、「发现 (`/community`)」、「就医经验 (`/hospitals`)」或「同行 (`/contribution`)」。

### 5.2 白斑图像分割与 VASI 评估服务 (`services/vasi.py` & `rgb_seg_worker.py`)
- **独立 Worker 进程隔离**：
  - 图像分割（OpenCV / PyTorch / RGB 肤色与白斑聚类分割）属于 CPU/内存密集型计算。
  - 为防止阻塞 FastAPI 异步主事件循环，重度图像计算通过 `services/rgb_seg_worker.py` 独立进程或受控线程池执行，并设有超时保护与优雅降级策略。
- **双照片/双记录对比引擎**：
  - 支持对同一部位不同时期的两张照片或两次日记记录进行面积变化百分比计算、复色趋势判定与 AI 综合解读。

### 5.3 图片打标与训练数据链路 (`services/labeling/` · `api/labeling_admin.py`)
- **唯一流水线**：后台「图片打标」只走五类标注（0 背景 / 1 正常皮肤 / 2 白斑 / 3 遮挡 / 4 不可判读，255 未标），像素值与 `ml/rgb_segmentation` 训练格式一致；坐标系是日记规范图（EXIF 已校正，长边 ≤1024）。旧 VLM/U-Net 接口（`api/image_label.py`）只读保留，RGB 标注不能经它写入或定金标准。
- **部位词表**：唯一来源 `web/shared/body-sites.json`（`utils/body_sites.py` 派生后端 `BODY_SITE_LABELS`、后台选项与训练分组）；已入库的中文标签不可改。
- **版本与复核**：每次提交生成不可覆盖的快照（`data/rgb_segmentation/admin_labels/{id}/{revision}/labels.png`）与 `label_submissions` 行；金标准只来自复核通过的提交，提交人自复核记 `single_review`；基准集（锁定测试集）必须盲标 + 他人复核，受试者整体进 test。
- **授权**：日记照片仅在用户授权「帮助改进白斑识别」（`model_training`）后对管理员可见；后台上传/旧版转入须确认来源授权并记录确认人。导出数据集 30 天到期删除，撤回授权或注销时删除含该受试者的数据集（消费 `DataRightsJob`）。

### 5.4 离线医学数据采集管线 (`src/`)
- `src/crawlers/`：定时或按需从 PubMed、Semantic Scholar、ClinicalTrials.gov 抓取白癜风最新研究论文与临床试验进展（遵守 `robots.txt` 与 API 速率限制）。
- `src/processors/`：调用大模型将英文医学摘要翻译并提炼为患者友好的中文结构化卡片（自动附带 PMID 来源与免责声明）。
