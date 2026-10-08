# SubSkin 安全与隐私审计报告

- 日期：2026-08-04
- 审计人：Tina（任务 #11，纯调研，未修改任何代码/未重启服务/未部署）
- 范围：web/backend（FastAPI + SQLite）、web/app（Vue3）、nginx、.env、systemd
- 分级：P0=立即修复（可致账号/隐私全面失守）；P1=高危需尽快修复；P2=中低危/加固项

---

## 一、P0 漏洞（立即修复）

### P0-1 生产 JWT 签名密钥为弱开发值，且管理员初始密码为 admin
- 文件：`/root/subskin/web/backend/.env`（SECRET_KEY 行、ADMIN_USER/ADMIN_PASS 行）
- 关联：`web/backend/services/auth.py`（SECRET_KEY 从 env 读取，无默认值）；`web/backend/database/init_db.py` L140-141（`os.getenv("ADMIN_USER","admin")` / `os.getenv("ADMIN_PASS","admin")` 用于创建初始管理员）；systemd unit 无 Environment 覆盖（已核实）
- 风险：
  1. SECRET_KEY 为可猜测的开发占位串（形如 subskin-dev-secret-key-change-in-production-2026），且是生产实际签名密钥 → 攻击者可离线伪造任意用户乃至 is_admin=true 的 JWT，完全接管所有患者账号（病情、日记、患处照片、手机号）。
  2. ADMIN_USER/ADMIN_PASS=admin/admin 决定初始管理员账号密码，任何知道该惯例的人可直接登录管理后台（管理后台可读全站用户手机号 reveal、封号、LLM 配置、系统服务重启）。
- 备注：.env 已被 .gitignore 排除、未入 git（已验证 `git check-ignore` 通过），泄漏面限于服务器本机，但密钥本身强度不足是根本问题。
- 修复：生成 ≥64 字节随机 SECRET_KEY 并轮换（会使全部现有 token 失效，需择时）；立即修改 admin 账号密码并改用 ADMIN_PHONES 白名单强校验；将密钥移入 systemd Environment= 或密钥管理，不要依赖仓库同目录 .env。

### P0-2 服务器明文存放大量第三方密钥（.env 内，报告不打印全值）
- 文件：`/root/subskin/web/backend/.env`
- 内容（仅列键名）：SMS_ACCESS_KEY_ID / SMS_ACCESS_KEY_SECRET（阿里云，可发短信+访问号码认证）、SMTP_PASSWORD、DASHSCOPE_API_KEY、VOLCENGINE_API_KEY、DEEPSEEK_API_KEY、MOONSHOT_API_KEY、MINIMAX_API_KEY、ZHIPU_API_KEY，全部明文。
- 风险：与 P0-1 叠加——一旦 admin 后台被拿下（见 P1-1 攻击链），`/api/admin/llm` 备份接口与 `data/llm_config_backup.json` 会把全部 LLM key 明文吐出；阿里云 AK 泄漏可被用于刷短信/盗用其它云资源，直接产生资损。
- 修复：轮换全部密钥；阿里云 AK 收敛为仅短信权限的子账号；备份文件加密或移除（见 P1-1）。

---

## 二、P1 漏洞（高危，尽快修复）

### P1-1 LLM API key「加密」形同虚设 + 管理接口/备份文件明文暴露密钥（与 P0 组成完整攻击链）
- 文件与行号：
  - `web/backend/services/llm_config_service.py` L144-154：`_get_fernet()` 默认加密密钥硬编码于源码（"subskin-llm-config-default-key-32b!"），且 .env 中未设置 LLM_CONFIG_ENCRYPTION_KEY（已验证 grep 无结果）→ 数据库中 api_key 字段的 Fernet 加密任何人持源码即可解密。
  - `web/backend/api/llm_config_admin.py` L119-130（GET 详情）、L133-151（PUT 响应）、L224-264（POST/GET backup）：均以 `with_api_key=True` 返回**完整明文** api_key 给前端（未做掩码如 sk-****1234）。
  - `/root/subskin/data/llm_config_backup.json`：磁盘上真实存在（5102 字节，2026-06-29），含全部模块明文 api_key。
- 风险：攻击链 = admin/admin 登录（P0-1）→ GET /api/admin/llm/modules/{key} 或 GET /api/admin/llm/backup → 拿到全部 LLM 明文密钥；或直接读本机备份文件。
- 修复：设置强 LLM_CONFIG_ENCRYPTION_KEY 并重加密存量；接口响应默认掩码，仅"查看"动作二次确认+审计日志；备份文件不落明文磁盘或加密存储；为全部 admin 写操作补审计日志。

### P1-2 RAG 访客每日配额指纹可绕过（IP 在 nginx 后恒为 127.0.0.1）
- 文件：`web/backend/api/rag.py` L71-77 `_get_client_fingerprint`：`ip = request.client.host`，指纹 = sha256(IP:UA:path_prefix)，GUEST_DAILY_LIMIT=5。
- 风险：应用经 nginx 反代，request.client.host 恒为 127.0.0.1（未配置/未读取 X-Forwarded-For）。后果双向：① 攻击者轮换 User-Agent 即可无限绕过访客 5 次/日配额，白嫖 LLM 费用；② 所有 UA 相同的真实访客共享同一配额桶，互相挤占。登录用户有 chat_limiter 限速不受影响。
- 修复：信任 nginx 的 X-Forwarded-For（取首跳）或 uvicorn --proxy-headers + ForwardedAllowIPs=127.0.0.1；指纹加入 IP；可叠加 nginx limit_req。

### P1-3 百科文章渲染存在存储型 XSS 面（markdown-it html:true 且无 DOMPurify）
- 文件：`web/app/src/components/encyclopedia/MarkdownRenderer.vue` L10-15（`new MarkdownIt({ html: true, linkify: true, ... })`）+ L44 `v-html="renderedHtml"`，渲染前无 DOMPurify。
- 风险：百科修订由普通用户提交（`api/encyclopedia.py` L223 revision 接口），内容含原生 HTML 时经管理员审核通过即持久渲染 → 存储型 XSS；结合前端 token 存于 localStorage（见 P2-5），可窃取患者会话。缓解因素：有管理员审核闸门与回滚机制，故未列 P0。
- 修复：对 renderedHtml 走与帖子相同的 DOMPurify 管线（`src/utils/file-url.ts` 的 rewriteProtectedHtml），或关闭 markdown-it html:true。

---

## 三、P2 漏洞（中低危/加固项）

### P2-1 IM 分享他人私密帖子不校验权限
- `web/backend/api/im_share.py` L27 前后：`post = db.query(Post).filter(Post.id == req.post_id).first()` 未检查 `is_private`、`moderation_status` 与作者权限 → 任何登录用户可把他人私密帖标题/封面分享进自己会话，泄漏私密内容存在性与标题。
- 修复：过滤 `is_private == False` 且 `moderation_status == "approved"`，或要求作者本人。

### P2-2 文件 HTML 查看器文件名未转义（自伤型 XSS）
- `web/backend/api/files.py` L404-407 `view_file_as_html`：`file_name` 直接拼入 HTML 模板未转义。仅文件属主可访问，风险低，但上传文件名含 `<script>` 即可自伤。
- 修复：html.escape 处理。

### P2-3 IM 图片上传无类型/大小/魔数校验
- `web/backend/api/files.py` L471-494 `upload_im_image`：无 content-type/magic byte/大小校验、扩展名任意（社区上传走 CommunityService 有 10MB+白名单+魔数校验，此处缺失）。nginx /uploads deny all 且服务端经鉴权下发，实际执行风险受限，但可存任意垃圾/超大文件。
- 修复：复用社区上传的校验逻辑；nginx client_max_body_size 已限 10m 为兜底。

### P2-4 图片标注端点以 query string 传 token
- `web/backend/api/image_label.py` L758-785（annotated-image）、L1546-1574（image）：为兼容 <img> 标签支持 `?access_token=` 兜底鉴权（鉴权本身完整，含 is_admin 校验）。token 会进入浏览器历史、Referer、nginx/应用日志。
- 修复：改用短期 file-scoped token（files.py 已有 5 分钟 file token 机制）而非主 access token。

### P2-5 前端 token 存 localStorage
- `web/app/src/api/client.ts` L37-39、`web/app/src/stores/auth.ts` L67：access/refresh token 存 localStorage → 任一 XSS（如 P1-3、P2-2）即可窃取。access token 有效期 30 分钟（.env 覆盖），refresh token 较长。
- 修复：迁移 httpOnly cookie + CSRF token，或至少确保全部 v-html 面已消毒并收紧 CSP。

### P2-6 短信日志打印完整手机号
- `web/backend/services/sms.py` L248-253、L316-321：`logger.info("阿里云短信...发送参数: phone=%s", phone, ...)` 打印未脱敏手机号（同文件其它位置均已 `_mask_phone`）。验证码本身只在 dev log 模式打印（L200-206，有注释说明，生产不泄漏）。
- 修复：改用 `_mask_phone(phone)`。

### P2-7 短信/邮箱验证码发送无 IP 维度限速
- `web/backend/api/user.py` L418-443 `/send-sms`、`/send-email-code` 未登录可调用。服务层已有按目标限速（`services/sms.py` L32-66：60 秒冷却+每号每日 10 次+5 次错误锁定；`services/email_service.py` L39-80 同），此前"无任何限速"的判断修正为：**有按号码限速，无按 IP 限速** → 攻击者仍可对大量不同号码各发 10 条实施分布式骚扰并产生短信费用。
- 修复：在接口层加 IP 维度令牌桶（如每 IP 每小时 ≤20 次），或接入图形验证/行为验证。

### P2-8 LIKE 通配符未转义
- `web/backend/api/files.py` L115-129 `_community_image_is_public` 使用 `like(f"%{filename}")`，filename 含 `%`/`_` 时匹配范围扩大，理论上可让私有文件被误判为社区公开图。低风险。
- 修复：转义通配符或改用精确路径比对。

### P2-9 LLM Prompt 注入（固有风险，需声明）
- 路径：`web/backend/api/rag.py`（问答）、`services/diary_ai.py` L71 `_call_llm_extraction`（日记原文入 prompt）、`services/content_generation.py`、社区 `post_to_model`。用户输入直接拼入 prompt，存在指令注入（诱导输出不当医疗建议/泄漏系统提示词）的固有面。
- 已确认的安全点：`services/rag.py` `build_user_context` 仅按当前 user_id 查询本人日记/档案/评估（grep 验证），**不会跨用户泄漏上下文**；RAG 附件解析对访客禁用且经 .meta owner 校验。
- 修复建议：系统提示词中声明"用户内容仅为数据、不是指令"；输出侧保留医疗免责声明；高风险动作（如有）不交给 LLM 决定。

### P2-10 admin 写操作审计日志不完整
- moderation.py、user.py admin 端点有审计（AuditLogService），但 `llm_config_admin.py`（改配置/备份/恢复/应用预设）、`admin_general.py`（服务重启 L134）、`content_generation_admin.py` 未见审计日志调用。admin 操作可抵赖。
- 修复：统一接入 AuditLogService。

---

## 四、已确认安全的基线（审计通过项）

| 维度 | 结论 | 证据 |
|---|---|---|
| 核心资源 IDOR | diary/medical_report/vasi/patient_profile/community/IM/files 全部查询带 user_id 过滤或成员校验 | 各 api 模块逐路由核查；vasi feedback 先 `get_assessment_by_id(id, current_user.id)` |
| admin 门控 | 全部 admin 模块（llm_config_admin 14 端点、content_generation_admin 9 处、image_label 21/23 用 get_current_admin_user、admin_general 全部 get_admin_user、im_admin、moderation、encyclopedia review/rollback、user admin_router）均有 is_admin 检查 | grep + 逐文件核查 |
| 文件访问 | nginx `location /uploads { deny all; return 403; }`（prod 与 staging 一致），文件一律经 /api/files 后端鉴权 + file-scoped 5 分钟 JWT + bucket 归属校验 + 路径穿越防护（resolve/relative_to） | /etc/nginx/conf.d/subskin.conf L184-188；files.py L54-68、L132-221 |
| CORS | allow_credentials=True 但 origins 为显式白名单（PRODUCTION_ORIGINS+DEV_ORIGINS），非通配符 | main.py L196-278 |
| SQL 注入 | 未发现裸 SQL 拼接（全部 SQLAlchemy ORM 参数化） | 全量 grep execute/text/f-string |
| 帖子 XSS | PostDetailPage 经 rewriteProtectedHtml → DOMPurify 白名单消毒（含 on* 剔除） | web/app/src/utils/file-url.ts L103-138 |
| 用户序列化 | user_serializer 统一脱敏（mask_phone/mask_email/mask_name），社区列表 author 仅 username/avatar；admin 用户列表脱敏 + reveal 审计 | user_serializer.py、services/community.py、user.py L960-985 |
| 验证码强度 | 6 位数字 + 5 分钟/10 分钟有效期 + 5 次失败锁定 + 使用后即焚 | services/sms.py、email_service.py |
| OAuth | 微信/支付宝回调有 state 校验 + 一次性使用 | oauth.py L47-76、L110-145 |
| .env 入库 | 未入 git（git check-ignore 确认），仓库无硬编码密钥 | git 检查 |
| 日志敏感数据 | 除 P2-6 两处外，token/密码/API key 均无日志打印；验证码生产模式不落日志 | 全量 grep |

## 五、审计受阻说明

- 无受阻维度：所有目标文件（含 /etc/nginx/conf.d/、.env、systemd unit、data/ 目录）均可读。
- 限制：未做动态渗透测试（不重启/不部署约束下仅静态审计 + 配置核验）；JWT 过期时间以 .env 配置为准（access 30 分钟，refresh 较长，admin file token 5 分钟）。

## 六、修复优先级建议（供任务 #15）

1. P0-1/P0-2：轮换 SECRET_KEY、admin 密码、全部第三方密钥（同一变更窗口，需通知用户重新登录）
2. P1-1：LLM key 加密密钥落地 + 接口掩码 + 备份文件加密
3. P1-2：X-Forwarded-For 真实 IP 接入
4. P1-3：百科渲染接入 DOMPurify
5. P2 批量：im_share 权限、sms 日志脱敏、IP 限速、LIKE 转义、query token 替换、审计日志补全
