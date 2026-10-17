# 03 · 隐私保护、数据分级与安全合规生死线

> **文档编号**: `STD-03`  
> **适用范围**: 全栈（`web/backend/`、`web/app/`、`web/admin/`、`src/`、脚本、日志、Git 仓库）  
> **安全等级**: 最高红线（零容忍 — 任何一条违背均视为 P0 阻断性事故）  
> **更新日期**: 2026-10-17  
> **状态**: 强制执行（MANDATORY）

---

## 一、核心原则：用户隐私与数据安全是 SubSkin 的生死线

白癜风患者对个人身份、患处照片与就医记录具有极高的隐私敏感度。一次数据泄露足以彻底摧毁用户信任与整个项目。所有开发者与 AI Agent 必须将数据安全置于一切功能开发之上。

---

## 二、L1–L4 四级数据分类与管控矩阵（Data Classification Matrix）

| 安全级别 | 包含数据类型 | 存储规范 | 传输与 API 响应规范 | 访问与日志规范 |
|----------|--------------|----------|---------------------|----------------|
| **🔴 L4 极高机密**<br>(Critical) | 用户密码、JWT Secret、第三方 API Key (`DASHSCOPE_API_KEY` 等)、身份证号、银行卡号、私钥 | 密码必须 `bcrypt` 哈希存储；密钥仅存 `.env`（严禁入 Git）；Token 设有效期 | **绝对禁止**出现在任何 API 响应、前端代码、URL 参数或公开页面中 | **严禁写入任何日志**；规划档案读取器自动执行正则擦除 (`redact_document`) |
| **🟠 L3 高敏个人/医疗**<br>(High / PII & PHI) | 手机号、邮箱、患处白斑照片、个人照片、体检化验单、音频/视频、真实姓名、详细住址 | 影像文件存储在受控私有目录，数据库仅存相对路径与归属 `user_id` | API 返回给本人时手机号脱敏为 `138****1234`，邮箱脱敏为 `li***@domain.com`；**严禁向其他用户暴露** | 仅所有者本人或经本人显式签发未过期分享 Token 的请求可访问；日志中严禁打印明文手机号/邮箱 |
| **🟡 L2 中敏社区与档案**<br>(Medium) | 用户昵称、头像、发帖内容、评论、收藏、白斑评估历史摘要、部位统计 | 关联 `user_id` 存储，支持用户随时转为私密或删除 | 默认遵循用户隐私设置；从「日记」转发到「发现」或生成公开报告需用户主动操作 | 每一次「公开 / 分享 / 授权」操作**必须写入不可篡改的 `AuditLog` 审计表** |
| **🟢 L1 公开数据**<br>(Public) | 医学文献知识库、已公开社区帖子、医院基础公开信息、全站匿名聚合统计（「同行」大盘） | 标准关系型表与向量索引存储 | 公开 API 可读取，但必须剥离关联用户的 L3/L4 字段 | 采集自外部公开源的数据需保留来源引用（如 PubMed PMID） |

---

## 三、十条零容忍安全红线（Zero-Tolerance Hard Rules）

### 1. 严禁任何敏感信息与 PII 进入 Git 仓库
- 密码、API Key、JWT Token、管理员手机号、测试用户真实手机号/邮箱/姓名**永远不得提交到 Git**。
- `.env.example` 中只能放置占位符（如 `DASHSCOPE_API_KEY=your_key_here`、`ADMIN_PHONES=13800000000`）。
- 运维脚本、数据库迁移脚本、测试 Fixture 中严禁硬编码真实手机号或密钥，一律通过 `os.getenv()` 读取。

### 2. 严禁向客户端泄露服务端内部异常详情
```python
# ❌ 绝对禁止（P0 漏洞：暴露数据库表结构、文件路径或第三方 SDK 内部错误）
except Exception as e:
    raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")

# ✅ 唯一正确写法（服务端记录完整堆栈，客户端仅返回通用安全提示）
except Exception as e:
    logger.error("操作失败: %s", str(e), exc_info=True)
    raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")
```

### 3. 开发模式验证码双重守卫（Dual-Guard for Mock Codes）
```python
# ❌ 严重漏洞：生产环境若临时切换 sms_provider=log 会直接在接口返回验证码导致任意账号接管
if sms_provider == "log":
    return {"status": "ok", "code": code}

# ✅ 强制双重守卫：必须同时满足 ENV == "development" 且 provider == "log"
if os.getenv("ENV") == "development" and sms_provider == "log":
    return {"status": "ok", "code": code}
```

### 4. API 响应强制脱敏与统一序列化
- 用户信息返回必须统一调用 `web/backend/services/user_serializer.py` 中的 `get_user_response()`，严禁各路由自行拼接 User 字段导致误把 `hashed_password` 或未脱敏手机号返回前端。
- 文本内容对外展示或归档检索时，统一通过 `web/backend/utils/pii_detect.py` 的 `redact_pii()` 进行手机号、邮箱、身份证号、银行卡号脱敏。

### 5. 颗粒度用途授权（Granular Purpose-Based Consent）
SubSkin 对用户健康与影像数据的使用实行严格的**分用途独立授权（Opt-in）**，绝不搞“一揽子霸王授权”：
1. `vasi_eval`：允许使用上传照片进行个人白斑面积与 VASI 评估（基础功能授权）。
2. `model_training`：允许将脱敏后的患处局部影像用于训练提升白斑识别 AI 模型（同行共建授权，可随时撤回）。
3. `community_display`：允许在「发现」社区帖子中展示本人选定的日记或报告（单次/内容级授权）。
4. `research_dataset`：允许纳入匿名化医学统计研究数据集（独立授权，默认关闭）。

### 6. 不可篡改的分享与授权审计日志（Immutable `AuditLog`）
- 用户每执行一次「公开帖子」、「生成报告分享链接 (`/share/report/:token`)」、「撤销分享」、「修改数据授权范围 (`UserConsent`)」操作，后端必须在 `AuditLog` 表中追加一条不可修改、不可删除的审计记录：
  - 记录字段：`user_id`、`action`、`resource_type`、`resource_id`、`scope`、`ip_address`、`created_at`、`revocable`。
- 外部分享链接必须使用高熵随机 Token，支持设置过期时间，且所有者可随时一键撤销（撤销后外部访问立即返回 404/已失效提示）。

### 7. 医疗影像与私有文件访问鉴权
- 用户上传的白斑原图、分割掩码图、体检报告图片严禁作为无鉴权公开目录枚举。
- 访问他人非公开照片或未授权报告的接口请求必须校验 `current_user.id == resource.user_id`，越权访问一律返回 `403 Forbidden` 或 `404 Not Found`。
- 用户上传患处图片时，应在服务端或客户端剥离 EXIF 中的 GPS 精确经纬度元数据，防止拍摄地点泄露。

### 8. 被遗忘权与账号彻底注销（Right to be Forgotten）
- 用户在「个人中心」（`/profile`）发起账号注销或数据删除请求时，系统必须提供清晰的确认流程，并在规定周期内彻底清理该用户的 L2–L4 级个人数据（个人资料、登录凭证、私有照片、体检单、聊天记录），仅保留完全不可逆的匿名聚合计数。

### 9. 警惕 `privacy_mode` 历史字段反逻辑陷阱（Naming Warning）
- **重要历史包袱提醒**：数据库 `users` 表中的布尔列 `privacy_mode`，其历史定义为 **`True` = 允许被白友发现（公开），`False` = 隐藏自己（私密）**——与英文直译相反！
- **开发强制规范**：API 序列化层已提供语义清晰的别名字段 **`is_discoverable`**（`True` = 可被发现，`False` = 隐藏）。所有新编写的前端与后端逻辑**必须优先使用 `is_discoverable`**，修改涉及 `privacy_mode` 的旧代码时必须反复核对真值表，严禁写反导致用户设为私密反而被公开！

### 10. 内容安全与就医经验风控底线
- 社区发帖、评论与就医经验提交必须经过敏感词与合规风控检测：
  - 严禁发布买卖处方药、虚假“包治百癜”偏方、微商引流微信号/二维码。
  - 严禁对具体医生进行人身攻击或未经证实的诽谤，同时保留病友客观陈述就诊流程、费用与服务体验的权利，并提供透明的申诉与纠错机制。
