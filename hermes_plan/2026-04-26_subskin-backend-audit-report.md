# SubSkin Backend API Architecture Compliance Audit

**审计日期**: 2026-04-26
**审计范围**: `/root/subskin/web/backend/` 全部源码
**审计维度**: RESTful 设计规范、分层依赖方向、错误处理与敏感信息泄露

---

## 一、RESTful API 设计审查

### 1.1 路由结构问题

| 严重度 | 文件 | 行号 | 问题描述 |
|--------|------|------|----------|
| **高** | `api/community.py` | 444-500 | 文件上传路由 `/upload`, `/upload/audio`, `/upload/file` 为扁平结构，未嵌套在资源下。RESTful 做法应为 `/posts/images`, `/posts/audio`, `/posts/files` |
| **高** | `api/user.py` | 244-251 | `GET /api/user/me` 和 `GET /api/users/me` 注册了两次 (router + profile_router)，存在重复路由，违反单一事实源原则 |
| **中** | `api/main.py` | 161 | `social.router` 和 `community.router` 共用 `/api/community` 前缀，导致路由语义混淆（focus/blocks/reports 混在 community 资源下） |
| **中** | `api/community.py` | 74-81 | `POST /check-claims` 是一个 RPC 风格的端点（动词），不符合 REST 资源命名规范 |
| **中** | `api/community.py` | 116-128 | `POST /posts/{post_id}/interact` 也是一个 RPC 端点。应为 `POST /posts/{post_id}/interactions` |
| **低** | `api/vasi.py` | 196-201 | `POST /assess/{id}/contour` 中的 `contour` 是单数名词，REST 约定应为复数 `/contours` |
| **低** | `api/social.py` | 242-275 | `GET /profile/{user_id}` 和 `GET /profile/{user_id}/posts` 路由扁平化为 `/api/community/profile/{id}`——实际完整路径应是 `/api/users/{id}/profile` |

### 1.2 内部数据模型暴露

| 严重度 | 文件 | 行号 | 问题描述 |
|--------|------|------|----------|
| **严重** | `api/user.py` | 80-106 | `_get_user_response` 在 `include_private=True` 时暴露 `email`, `phone`, `wechat_id`, `alipay_id` 到客户端。登录响应中包含全部敏感字段，违反最小暴露原则 |
| **严重** | `api/user.py` | 90-92 | `/me` 端点返回 `is_admin`, `user_status`, `muted_until`——这些内部管控字段不应暴露给普通用户（is_admin 可用于提权探测） |
| **高** | `api/social.py` | 264-274 | `GET /profile/{user_id}` 公开返回 `patient_relation`（患者关系）和 `is_doctor`，但缺少隐私模式检查 (`privacy_mode`) |
| **高** | `api/user.py` | 412-417 | 开发模式下短信发送端点 `/send-sms` 直接返回验证码明文 `{"code": code}`，若误部署到生产环境将造成严重安全漏洞 |
| **高** | `api/user.py` | 428-431 | 邮箱验证码同理，开发模式返回 `{"code": code}` |
| **中** | `api/oauth.py` | 75-93 | `/wechat/status` 在确认状态下直接返回 `access_token` 和 `refresh_token`，使得仅凭 state 参数即可获取 token（state 非一次性消耗） |
| **中** | `api/community.py` | 122-128 | Post model 返回 `moderation_status` 字段——用户能看到自己的帖子是否被审核标记 |

### 1.3 HTTP 方法使用

| 严重度 | 文件 | 行号 | 问题描述 |
|--------|------|------|----------|
| **中** | `api/social.py` | 218 | 举报端点 `POST /report` 使用 query string 参数 `target_user_id` 和 `reason` 而非 request body——违反了 POST 语义（数据应在 body 中） |
| **低** | `api/user.py` | 795-815 | `POST /pwa-status` 用于更新状态（幂等操作），语义上应使用 `PUT` |

### 1.4 状态码使用

| 严重度 | 文件 | 行号 | 问题描述 |
|--------|------|------|----------|
| **中** | `api/user.py` | 478-482 | 手机号未注册时返回 `404 Not Found` 而非 `401 Unauthorized`——404 暗示资源不存在而非认证失败，可能误导客户端重试逻辑 |
| **中** | `api/user.py` | 534-538 | 邮箱登录同样使用 404 而非 401 |
| **中** | `api/social.py` | 226-229 | 举报请求参数 `post_id: int = None` 缺少 Optional 类型，query string 缺失时 FastAPI 会返回不友好的 422 |

---

## 二、Import 依赖分层审查

### 架构分层模型（期望）

```
┌──────────────────────────┐
│    api/      (路由+请求解析) │  ← 依赖 services + models(pydantic)
├──────────────────────────┤
│    services/ (业务逻辑层)    │  ← 依赖 database + models(ORM)
├──────────────────────────┤
│    database/  (数据访问层)   │  ← 无外部依赖
└──────────────────────────┘
```

### 2.1 跨模块 API 层互引（严重违规）

| 严重度 | 文件 | 行号 | 导入语句 | 说明 |
|--------|------|------|----------|------|
| **严重** | `api/oauth.py` | 18 | `from web.backend.api.user import _get_user_response` | API 层 oauth 直接导入 API 层 user 的私有函数，违反模块边界，存在循环依赖风险 |
| **严重** | `api/social.py` | 287 | `from web.backend.api.community import _post_to_model` | API 层 social 直接导入 API 层 community 的私有函数 |

> **建议**: `_get_user_response` 和 `_post_to_model` 应下沉到 `services/user.py` 和 `services/community.py`（或独立的 `web.backend.serializers/` 模块）。

### 2.2 API 层直接使用数据库模型（反模式）

| 严重度 | 文件 | 行号 | 说明 |
|--------|------|------|------|
| **高** | `api/community.py` | 437-441 | `db.query(Tag)` 直接在路由中操作数据库，绕过 CommunityService |
| **高** | `api/community.py` | 251-258 | `db.query(PostORM)` 在 `get_my_diaries` 中直接查询 |
| **高** | `api/medical_report.py` | 34-49 | `db.query(MedicalReport)` 在路由中直接查询 |
| **高** | `api/vasi.py` | 12-15 | 直接导入 `User` ORM 模型和 `get_db`，并传入 VASIService |
| **高** | `api/moderation.py` | 9-16 | 直接导入 `ContentModeration`, `Post`, `User` 等 ORM 模型 |
| **高** | `api/patient_profile.py` | 7 | 直接导入 `PatientProfile` ORM 模型 |
| **高** | `api/rag.py` | 25-30 | 直接导入 `DBUser`, `GuestUsage`, `Conversation`, `Message` ORM 模型 |
| **高** | `api/rag.py` | 443 | `db = SessionLocal()` 直接创建 session，绕过 FastAPI 依赖注入 |
| **中** | `api/user.py` | 17 | 导入 `User as DBUser`，API 层直接使用 ORM 对象 |

> **影响**: API 层与数据库耦合过紧，无法独立测试路由逻辑，也无法替换持久化层。

### 2.3 服务层依赖 Web 框架（抽象渗漏）

| 严重度 | 文件 | 行号 | 导入语句 | 说明 |
|--------|------|------|----------|------|
| **高** | `services/credential.py` | 7-8 | `from fastapi import HTTPException, status` | 服务层直接使用 Web 框架异常类——应抛出领域异常，由 API 层转换为 HTTP 响应 |
| **高** | `services/credential.py` | 74-76 | `raise HTTPException(...)` | 同上 |
| **中** | `services/email_service.py` | 11 | `from fastapi import HTTPException, status` | 邮箱服务也引入 Web 框架依赖 |

### 2.4 服务层跨服务导入私有函数

| 严重度 | 文件 | 行号 | 导入语句 | 说明 |
|--------|------|------|----------|------|
| **高** | `services/vasi.py` | 420 | `from web.backend.services.rag import _get_llm_config` | VASI 服务导入 RAG 服务的私有函数 `_get_llm_config`——该函数应提取到 `utils/llm_config.py` |
| **高** | `services/content_safety.py` | 52-65 | `_get_llm_config()` 完整复制 | 与 `services/rag.py` 中的 `_get_llm_config` 功能完全相同，但实现略有差异——典型的代码重复 |

### 2.5 服务层直接导入 FastAPI 依赖注入工具

| 严重度 | 文件 | 行号 | 导入语句 | 说明 |
|--------|------|------|----------|------|
| **中** | `services/auth.py` | 17 | `from web.backend.database.database import get_db` | `get_db` 是 FastAPI generator，不应被服务层直接导入 |
| **中** | `services/vasi.py` | 15 | `from web.backend.database.database import get_db` | 同上 |
| **中** | `services/content_safety.py` | 14 | `from web.backend.database.database import get_db` | 同上 |

### 2.6 函数体内延迟导入

| 严重度 | 文件 | 行号 | 说明 |
|--------|------|------|------|
| **中** | `api/user.py` | 269,348 | `import threading` 在函数体内部 |
| **中** | `api/community.py` | 186,392 | `import threading` 在函数体内部 |
| **中** | `api/vasi.py` | 56,235 | `import json` 在函数体内部 |
| **中** | `api/vasi.py` | 270 | `import math` 在函数体内部 |
| **中** | `services/content_safety.py` | 358 | `from web.backend.services.sms import send_sms` 在函数体内部 |
| **中** | `api/community.py` | 187 | `from web.backend.services.content_safety import moderate_post` 在函数体内部 |

### 2.7 代码重复

| 严重度 | 文件 | 行号 | 说明 |
|--------|------|------|------|
| **中** | `api/user.py:190` / `api/patient_profile.py:21` | — | `_normalize_optional_string` 函数在两个 API 文件中重复定义 |
| **中** | `services/rag.py:299` / `services/content_safety.py:52` | — | `_get_llm_config` 函数在两个服务文件中分别实现 |
| **低** | `database/models.py` | 21 | `from sqlalchemy.orm import relationship, relationship as orm_relationship` 冗余别名导入 |

---

## 三、错误处理与敏感信息泄露审查

### 3.1 异常详情泄露到客户端（严重）

| 严重度 | 文件 | 行号 | 问题代码 | 说明 |
|--------|------|------|----------|------|
| **严重** | `api/oauth.py` | 68-72 | `detail=f"微信登录失败: {str(e)}"` | `str(e)` 可能包含 API key、access token、第三方接口返回的完整响应体 |
| **严重** | `api/oauth.py` | 137-141 | `detail=f"支付宝登录失败: {str(e)}"` | 同上——支付宝 SDK 异常可能泄漏 app_id、签名密钥 |
| **严重** | `api/vasi.py` | 82-83 | `detail=f"评估失败: {str(e)}"` | 泛化 Exception 捕获 + 泄露内部错误信息 |
| **严重** | `api/vasi.py` | 133-134 | `detail=f"获取历史失败: {str(e)}"` | 同上 |
| **严重** | `api/vasi.py` | 188-189 | `detail=f"获取趋势失败: {str(e)}"` | 同上 |
| **严重** | `api/community.py` | 460 | `detail=f"上传失败: {str(e)}"` | 图片上传异常可能暴露文件系统路径 |
| **严重** | `api/community.py` | 484 | `detail=f"上传失败: {str(e)}"` | 音频上传同理 |

> **修复原则**: 对客户端返回通用错误消息（如 "服务暂时不可用，请稍后重试"），详细的异常信息仅记录在服务端日志中。

### 3.2 开发模式验证码泄露

| 严重度 | 文件 | 行号 | 问题代码 | 说明 |
|--------|------|------|----------|------|
| **严重** | `api/user.py` | 414-417 | `if sms_provider == "log": return {"code": code}` | 若 SMS_PROVIDER 环境变量误设置为 "log"，生产环境将直接返回验证码 |
| **严重** | `api/user.py` | 428-431 | `if email_provider == "log": return {"code": code}` | 同上 |

> **建议**: 开发模式验证码泄露应仅在 `ENV=development` 且绑定 localhost 时允许，增加多层防护。

### 3.3 日志敏感信息

| 严重度 | 文件 | 行号 | 问题代码 | 说明 |
|--------|------|------|----------|------|
| **高** | `api/rag.py` | 70-74 | `_get_client_fingerprint` 中将客户端完整 IP + User-Agent 做 SHA256 哈希——指纹本身是安全的，但原始 IP 在其他地方被直接记录 | 审计日志中 IP 地址有 `mask_ip()` 处理，但部分 `logger.info/warning` 中直接记录了 IP |
| **中** | `api/community.py` | 150-153 | `logger.warning("User %s used exaggerated claims: %s in post '%s'", ...)` | 记录了用户发布的完整夸张词汇和标题片段——审查目的合理，但应截断标题长度以防日志膨胀 |
| **中** | `api/community.py` | 332 | `logger.error("删除帖子失败 post_id=%s: %s", post_id, e, exc_info=True)` | 日志中输出了完整异常栈，这是良好的做法（日志应详细，但客户端响应不应详细） |
| **低** | `services/auth.py` | 20 | `SECRET_KEY=os.environ["SECRET_KEY"]` | 没有默认值，在缺少环境变量时会直接崩溃，但 Python traceback 不会输出 key 值——这是正确的 |

### 3.4 错误处理模式不一致

| 严重度 | 文件 | 行号 | 问题描述 |
|--------|------|------|----------|
| **中** | `api/community.py` | 97-101 | `create_post` → `update_post_tags` 中将业务异常 `ValueError` 映射为 `404`——逻辑错误应映射为 4xx，但使用 404 掩盖了真实错误类型 |
| **中** | `api/community.py` | 329-331 | `delete_post` 中吞掉了 service 层异常，返回通用消息——但内部仍然记录了详细日志。半正确：对外隐藏细节（好），但使用了裸 `except Exception`（不好） |
| **低** | `api/user.py` | 73 | `GENERIC_REGISTRATION_ERROR` 常量—良好的防枚举实践。但 `register_by_phone`（444行）使用了具体错误消息，不一致 |

### 3.5 安全配置问题

| 严重度 | 文件 | 行号 | 问题描述 |
|--------|------|------|----------|
| **严重** | `api/user.py` | 454 | 管理员手机号硬编码: `{"15810004327", "17319030290", "15978713663", "18790010679"}`——应通过环境变量 `ADMIN_PHONES` 配置 |
| **中** | `app/main.py` | 92-97 | CORS `allow_origins` 使用了环境变量但 fallback 到 `DEFAULT_ALLOWED_ORIGINS` 包含 `localhost:3000` 和 `localhost:5173`——生产中应仅允许生产域名 |
| **中** | `app/main.py` | 144 | `allow_headers=["*"]` ——允许任意请求头，虽方便但降低了安全性 |
| **中** | `services/auth.py` | 27 | `OAuth2PasswordBearer(auto_error=False)` ——自动错误设为 False，意味着未认证用户不会收到 401 而是得到 None 用户，可能导致权限检查遗漏 |
| **低** | `api/rag.py` | 47-48 | 文件上传允许 `text/plain` 和 `text/markdown` 类型——虽然无直接安全风险，但缺少文件内容扫描（恶意脚本嵌入） |

---

## 四、总结与优先级建议

### 4.1 应立即修复（P0）

1. **OAuth 异常泄露** (`api/oauth.py:68-72, 137-141`) — 将 `str(e)` 替换为通用错误消息
2. **VASI 异常泄露** (`api/vasi.py:82-83, 133-134, 188-189`) — 同上
3. **上传异常泄露** (`api/community.py:460, 484`) — 同上
4. **开发模式验证码泄露** (`api/user.py:414-431`) — 增加环境检查守卫
5. **管理员手机号硬编码** (`api/user.py:454`) — 迁移到环境变量

### 4.2 应在下一迭代修复（P1）

6. **跨 API 模块导入** (`api/oauth.py:18`, `api/social.py:287`) — 提取共享函数到 service/serializer 层
7. **服务层 Web 框架依赖** (`services/credential.py:7-8`) — 替换为领域异常
8. **服务层跨服务导入** (`services/vasi.py:420`) — 提取 `_get_llm_config` 到 `utils/`
9. **API 层直接操作数据库** — 9 处违规应统一走 service 层

### 4.3 应纳入技术债务（P2）

10. **路由重复** (`/api/user/me` 双注册)
11. **RPC 风格端点** (`/check-claims`, `/interact`)
12. **私有字段暴露** (登录响应中的 email/phone/wechat_id/alipay_id)
13. **延迟 import** (6 处函数体内 import)
14. **_get_llm_config 重复** (services/rag.py + services/content_safety.py)
15. **CORS 宽松配置**
