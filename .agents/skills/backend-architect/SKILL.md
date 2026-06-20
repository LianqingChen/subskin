---
name: backend-architect
description: Use when writing, reviewing, or modifying SubSkin backend Python code — FastAPI routes, services, models, utils. Triggers on backend code generation, API endpoint creation, service refactoring, error handling, auth changes, or any Python file under web/backend/.
---

# Backend Architect Skill

> SubSkin 后端架构师 — Python/FastAPI 后端代码质量守门人
>
> **触发词**: 后端审查、后端架构、BE review、API设计、服务层、Python代码审查、后端审计、新增API、修改API、后端代码
>
> **关键原则**: 此 Skill 是 SubSkin 后端代码的最高质量标准。所有新增、修改的后端代码必须符合本 Skill 的规定。

---

## 一、异常与错误处理规范（零容忍）

### 1.1 禁止向客户端泄露内部异常信息

```python
# ❌ 绝对禁止 — 泄露内部异常详情
except Exception as e:
    raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")

# ✅ 正确 — 通用消息 + 服务端日志
except Exception as e:
    logger.error("操作失败: %s", str(e), exc_info=True)
    raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")
```

**规则**:
- `detail` 中**永远不要**包含 `str(e)`、`repr(e)`、`e.__class__.__name__` 或任何异常内部信息
- 异常详情只通过 `logger.error(..., exc_info=True)` 记录到服务端日志
- 客户端只看到通用错误消息

### 1.2 HTTPException detail 规范

| 场景 | detail 模板 |
|------|------------|
| 第三方服务失败 | `"服务暂时不可用，请稍后重试"` |
| 上传操作失败 | `"上传失败，请稍后重试"` |
| 数据库操作失败 | `"操作失败，请稍后重试"` |
| OAuth/登录失败 | `"登录服务暂时不可用，请稍后重试"` |
| 业务校验失败 | 可用具体提示，如 `"验证码错误或已过期"` |

### 1.3 业务异常 vs 意外异常

```python
# ✅ 业务异常：可以返回具体 detail（用户输入错误、资源不存在等）
except VASIAssessmentError as e:
    raise HTTPException(status_code=400, detail=str(e))

# ✅ 意外异常：只返回通用消息
except Exception as e:
    logger.error("VASI评估失败: %s", str(e), exc_info=True)
    raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")
```

---

## 二、分层架构规范（强制）

### 2.1 三层架构

```
API 层 (web/backend/api/)
  → 只做请求解析、响应构造、HTTP异常转换
  → 依赖 Service 层和 Model 层

Service 层 (web/backend/services/)
  → 业务逻辑、数据查询、外部调用
  → 依赖 Database 层和 Utils 层
  → 禁止依赖 FastAPI

Utils 层 (web/backend/utils/)
  → 纯函数、共享配置、工具
  → 零框架依赖
```

### 2.2 依赖方向规则

```
api/ → services/ → database/models, utils/
api/ → utils/ (可直接用)
services/ → utils/ (可直接用)
services/ ↛ api/ (禁止反向依赖)
services/ ↛ fastapi (禁止框架依赖)
utils/ ↛ 任何其他层 (零依赖)
```

### 2.3 跨模块导入规范

| 规则 | 说明 | 示例 |
|------|------|------|
| 禁止跨API模块导入私有函数 | `api/oauth.py` 不可导入 `api/user._get_user_response` | 提取到 `services/` |
| 禁止跨Service导入私有函数 | `services/vasi.py` 不可导入 `services/rag._get_llm_config` | 提取到 `utils/` |
| 下划线函数视为模块私有 | `_get_llm_config`、`_post_to_model` 等只在本模块内使用 | 需要共享就公开化 |

**正确的共享方式**:

```
私有函数跨模块需要 → 提取到合适的公共层

API间共享 → services/xxx.py
Service间共享 → utils/xxx.py
全局共享配置 → utils/llm_config.py
```

---

## 三、服务层纯净性规范

### 3.1 服务层禁止导入 FastAPI

```python
# ❌ 绝对禁止 — 服务层依赖框架
from fastapi import HTTPException, status

def bind_credential(...):
    raise HTTPException(status_code=400, detail="已绑定")

# ✅ 正确 — 使用领域异常
from web.backend.exceptions import CredentialConflictError

def bind_credential(...):
    raise CredentialConflictError("已绑定")
```

### 3.2 领域异常体系

所有服务层异常使用 `web/backend/exceptions.py` 中定义的领域异常：

| 异常类 | 语义 | API层转换 |
|--------|------|-----------|
| `SubSkinException` | 业务异常基类 | — |
| `CredentialConflictError` | 凭证冲突 | `400 Bad Request` |
| `CredentialNotFoundError` | 凭证不存在 | `404 Not Found` |

**新增异常时**:
1. 在 `exceptions.py` 中定义，继承 `SubSkinException`
2. 服务层抛出领域异常
3. API 层 `try/except` 捕获并转换为 `HTTPException`

### 3.3 API 层异常转换模板

```python
from web.backend.exceptions import CredentialConflictError, CredentialNotFoundError

@router.post("/bind-phone")
def bind_phone(...):
    try:
        credential = bind_credential(db, user_id, "phone", data.phone, verified=True)
    except CredentialConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/credentials/{credential_id}")
def unbind(...):
    try:
        success = unbind_credential(db, credential_id, user_id)
    except CredentialNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

---

## 四、安全规范（零容忍）

### 4.1 敏感信息硬编码

```python
# ❌ 绝对禁止 — 硬编码手机号、邮箱、密码、密钥
is_admin=data.phone in {"15810004327", "17319030290"}
API_KEY = "sk-xxxxx"

# ✅ 正确 — 使用环境变量
is_admin=data.phone in set(os.getenv("ADMIN_PHONES", "").split(",")) if os.getenv("ADMIN_PHONES") else False
API_KEY = os.getenv("DASHSCOPE_API_KEY")
```

### 4.2 开发模式验证码守卫

```python
# ❌ 危险 — 任何 sms_provider=log 就返回验证码
if sms_provider == "log":
    return {"status": "ok", "code": code}

# ✅ 安全 — 双重守卫
if os.getenv("ENV") == "development" and sms_provider == "log":
    return {"status": "ok", "code": code}
```

**规则**: 验证码/密码等敏感数据只在 `ENV=development` **且** provider 为 mock 模式时才返回。

### 4.3 敏感数据脱敏

| 数据级别 | 示例 | 规则 |
|---------|------|------|
| 🔴 L4 | 密码、JWT token | 绝对不出现在API响应/日志/前端 |
| 🟠 L3 | 手机号、邮箱、病情图片 | API返回时脱敏 `138****1234` |
| 🟡 L2 | 昵称、发帖内容 | 用户自主选择公开/私密 |
| 🟢 L1 | 百科内容、公开帖子 | 可公开访问 |

### 4.4 日志安全

```python
# ❌ 禁止 — 日志中打印敏感信息
logger.info(f"User login: phone={phone}, password={password}")

# ✅ 正确
logger.info("User login: user_id=%s", user.id)
```

---

## 五、共享配置规范

### 5.1 LLM 配置统一入口

所有 LLM 配置通过 `web/backend/utils/llm_config.py` 的 `get_llm_config()` 获取：

```python
# ✅ 正确
from web.backend.utils.llm_config import get_llm_config
config = get_llm_config()

# ❌ 禁止 — 重复实现 LLM 配置逻辑
def _get_llm_config():  # 不要在各模块中重复
    if os.getenv("DASHSCOPE_API_KEY"): ...
```

### 5.2 用户序列化统一入口

用户信息序列化通过 `web/backend/services/user_serializer.py` 的 `get_user_response()` 获取：

```python
# ✅ 正确
from web.backend.services.user_serializer import get_user_response

# ❌ 禁止 — 跨API模块导入私有版本
from web.backend.api.user import _get_user_response
```

### 5.3 新增共享配置的模式

当发现多个模块需要同一个函数时：

1. **识别** — 函数被2个以上模块使用
2. **提取** — 移到合适的公共层（services/ 或 utils/）
3. **公开化** — 去掉下划线前缀，添加类型注解
4. **替换** — 所有调用方改为从公共层导入
5. **删除** — 原位置的私有版本删除

---

## 六、代码风格规范

### 6.1 Python 版本兼容

项目使用 Python 3.9，**禁止**使用以下语法：

```python
# ❌ Python 3.10+ 语法
def foo(x: str | None) -> list[int]: ...
match value:
    case "a": ...

# ✅ Python 3.9 兼容
from typing import Optional, List
def foo(x: Optional[str]) -> List[int]: ...
```

### 6.2 日志规范

```python
# ✅ 正确 — 使用 % 格式化（延迟求值，性能更好）
logger.error("操作失败: %s", str(e), exc_info=True)

# ❌ 不推荐 — f-string（即使不打印也会求值）
logger.error(f"操作失败: {str(e)}")
```

### 6.3 类型注解

所有公开函数必须有类型注解：

```python
# ✅
def get_user_response(db_user: DBUser, include_private: bool = False) -> dict[str, object]:

# ❌
def get_user_response(db_user, include_private=False):
```

---

## 七、审查工作流

### 7.1 新增/修改后端代码时

1. **异常处理审查** — 是否泄露内部异常信息？（参见 1.1）
2. **分层审查** — 导入方向是否合法？（参见 2.2）
3. **跨模块审查** — 是否导入其他模块的私有函数？（参见 2.3）
4. **服务层审查** — 是否依赖 FastAPI？（参见 3.1）
5. **安全审查** — 是否硬编码敏感信息？（参见 4.1）
6. **配置审查** — 共享配置是否使用统一入口？（参见 5.1-5.3）
7. **兼容性审查** — 是否使用 Python 3.10+ 语法？（参见 6.1）

### 7.2 审查输出格式

```markdown
## 后端审查结果

### ✅ 通过项
### 🔴 必须修复（阻塞合并）
### 🟡 建议优化（非阻塞）
### 🔒 安全检查
### 🏗️ 架构检查
```

### 7.3 审查标准

| 检查项 | 严重级别 | 阻塞合并 |
|--------|----------|----------|
| 向客户端泄露异常详情 | 🔴 P0 | 是 |
| 服务层依赖 FastAPI | 🔴 P0 | 是 |
| 硬编码敏感信息（手机号/密钥） | 🔴 P0 | 是 |
| 验证码缺少 ENV 守卫 | 🔴 P0 | 是 |
| 跨模块导入私有函数 | 🔴 P1 | 是 |
| 服务层跨服务导入私有函数 | 🔴 P1 | 是 |
| 重复实现共享配置 | 🟡 | 否 |
| 缺少类型注解 | 🟡 | 否 |
| 使用 Python 3.10+ 语法 | 🟡 | 否 |

---

## 八、禁止事项

### 绝对禁止

1. ❌ `detail=f"...: {str(e)}"` — 向客户端泄露异常内部信息
2. ❌ 服务层 `from fastapi import HTTPException` — 框架依赖
3. ❌ 硬编码手机号、邮箱、密码、API Key
4. ❌ 验证码在非 development 环境返回给客户端
5. ❌ `from web.backend.api.xxx import _private_func` — 跨API导入私有函数
6. ❌ `from web.backend.services.xxx import _private_func` — 跨Service导入私有函数
7. ❌ 重复实现 `get_llm_config()` 等共享配置
8. ❌ `as any`、类型忽略注解
9. ❌ 空 `catch` 块 `except Exception: pass`
10. ❌ 日志中打印 L3/L4 级别敏感数据

### 强烈不建议

- 在 API 层编写业务逻辑（应提取到 Service 层）
- 在 Service 层直接返回 HTTP 响应（应抛出领域异常）
- 新建模块时忘记添加 `__init__.py`

---

## 九、参考文件

- 项目总规范: `/root/subskin/AGENTS.md`
- 领域异常定义: `/root/subskin/web/backend/exceptions.py`
- LLM 配置入口: `/root/subskin/web/backend/utils/llm_config.py`
- 用户序列化入口: `/root/subskin/web/backend/services/user_serializer.py`
- 服务层 CommunityService: `/root/subskin/web/backend/services/community.py`
- 前端架构规范: `/root/subskin/.agents/skills/frontend-architect/SKILL.md`
