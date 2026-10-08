# SubSkin C端上线前安全与隐私加固（2026-08-30）

> 目标：作为面向 C 端用户的正式平台，统一检查并加固「网站安全、数据安全、用户隐私保护」。
> 状态标记：[x] 已完成 [ ] 未完成 (>) 进行中

---

## 一、审计结论总览

### 服务器层
| # | 发现 | 严重度 |
|---|------|--------|
| S1 | SSH 7 天内 9.4 万次爆破尝试（单 IP 1.3 万次），无 fail2ban，root+密码登录开放 | P0 |
| S2 | iptables 全开（INPUT ACCEPT 无规则）；80/443/22/8787/19091/8999 对 0.0.0.0 监听（云防火墙似乎挡了非标端口，外部测试 8787/19091 不通） | P1 |
| S3 | `/root/deepseek-responses-proxy/proxy.py` 绑 0.0.0.0:8787，代码内**硬编码 DeepSeek API key**，无鉴权 | P1 |
| S4 | `web/backend/.env` 权限 644 + 两份 `.env.bak-*` 明文副本（含 SMS/SMTP/LLM/VAPID/管理员口令） | P1 |
| S5 | nginx 三站点无安全响应头（无 CSP/X-Frame-Options/nosniff/Referrer-Policy/Permissions-Policy；HSTS 仅 dsh 有）；server_tokens 未关 | P2 |
| S6 | `/usr/share/nginx/html/subskin.bak.202604150143` 旧前端备份留在 web 根（当前不可达，但属隐患）；`/etc/nginx/auth/dsh.htpasswd.bak.*` 三份旧哈希 | P3 |
| S7 | dsh.subskin.cn 有 Basic Auth + HTTPS（验证 401 未授权）✅；uvicorn 绑 127.0.0.1 ✅；后端上传目录不在 nginx 静态根下 ✅；web 根无 .git ✅ | 合格 |
| S8 | Git：`web/backend/.env` 从未提交 ✅；但 `data/llm_config_backup.json` 在 git 历史（私有仓库 GitHub LianqingChan/subskin）中含明文 DashScope key `sk-862aa...daa1`，该 key 至今仍可能有效 | P1 |
| S9 | 用户使用密码 SSH 登录（30 天 22 次），不能直接关闭 PasswordAuthentication（会锁死用户），改用 fail2ban + 加固参数 + 建议密钥化 | 约束 |

### 后端代码（两轮子代理审计，证据省略，详见审计报告结论）
| # | 发现 | 严重度 |
|---|------|--------|
| B1 | `api/oauth.py` status 端点：不过期校验、不消费 state、无限速 → 无限铸造 token | P0 |
| B2 | `api/files.py` im-image 上传零校验（无类型/魔数/大小）+ `serve_file` 按扩展名猜 Content-Type → 同源存储型 XSS（token 在 localStorage）→ 账号接管链 | P0 |
| B3 | `api/user.py` set-password 不要旧密码 → 会话被盗后持久接管 | P1 |
| B4 | 管理员 access token 365 天且无撤销机制 | P1 |
| B5 | 无账户删除/匿名化 API（被遗忘权缺失，PIPL 47条） | P1 |
| B6 | 健康数据（PatientProfile/日记/报告）发第三方 LLM 前不校验 consent；consent API 是死代码；系统提示硬编码"用户已授权" | P1 |
| B7 | 发帖无公开发表确认；正文无 PII 检测/脱敏；ImagePostEditor 把私密草稿静默转公开 | P0 |
| B8 | X-Forwarded-For 取首值可伪造 → 绕过登录/短信限速；读限速恒为 127.0.0.1 全局桶（未启用 proxy-headers） | P1 |
| B9 | 头像上传仅查可伪造的 Content-Type（XSS 面） | P2 |
| B10 | 帖子/评论作者 username 序列化未脱敏（历史上 username=手机号） | P2 |
| B11 | SMTP 日志打印完整邮箱；share-to-community 绕过审计；/shared/{token} 不校验 is_public 且无撤销 | P2 |
| B12 | 注册无密码强度校验/无限速；refresh token 明文入库；/docs 未按环境禁用；cleanup-temp 越权 | P2-P3 |
| B13 | SQL 注入：未发现（全参数化）；CORS 白名单正确；admin 路由全有鉴权；体检/测评/日记按属主过滤 | 合格 |

### 隐私/训练合规
| # | 发现 | 严重度 |
|---|------|--------|
| P1 | 用户删除测评后图片保留且**继续参与模型训练**（collect_samples 不查 is_user_deleted） | P0 |
| P2 | 打标/训练界面 username+图片并排展示，可按用户名检索全部病情图 | P1 |
| P3 | 训练导出含 assessment_id（可回溯用户）、admin_notes；manifest 无 TTL | P1 |
| P4 | 私密帖正文/图片仍送第三方 LLM（AI 增强+内容安全） | P1 |
| P5 | 白斑报告一键分享社区无二次确认/预览 | P1 |
| P6 | GPS 全精度坐标送 nominatim.openstreetmap.org 且后台自动触发；用户 IP 明文 HTTP 送 ip-api.com；隐私政策第三方清单缺 LLM/地图 | P1 |
| P7 | localStorage 明文存手机号历史+完整 User 对象 | P2 |
| P8 | 用户修正蒙层自动进训练集无告知 | P2 |

---

## 二、实施方案（本次实施范围）

### Phase A — 服务器层（无需改业务代码）
- [x] A1 fail2ban：安装（dnf/epel 或手动），sshd jail：maxretry=3, findtime=10m, bantime=1h（含 aggressive 模式 ignoreip 127.0.0.1）
- [x] A2 sshd 加固（保留密码登录，因用户在用）：`/etc/ssh/sshd_config.d/00-subskin-hardening.conf`：MaxAuthTries 4 / LoginGraceTime 30 / PermitEmptyPasswords no / X11Forwarding no（注意 sshd 首次匹配优先，文件名 00- 排在 50-redhat 之前）；`sshd -t` 验证后 reload，**不重启现有连接**
- [x] A3 `web/backend/.env`、`.env.bak-*` chmod 600
- [x] A4 `data/llm_config_backup.json` 移除明文 api_key 字段（保留 Fernet 加密版）+ chmod 600；提醒用户轮换 sk-862aa…（git 历史+磁盘曾明文）
- [x] A5 `mv /usr/share/nginx/html/subskin.bak.202604150143 /root/backups/`；删除 htpasswd.bak 旧哈希副本
- [x] A6 nginx：server_tokens off；subskin/staging/admin 三站加安全头（nosniff/X-Frame-Options SAMEORIGIN/Referrer-Policy/Permissions-Policy/HSTS）；`nginx -t` 通过后 reload
- [x] A7 `/root/deepseek-responses-proxy/proxy.py`：默认绑定改 127.0.0.1，重启进程，chmod 600（key 留在 root-only 文件，建议后续改 env 注入）
- [x] A8 uvicorn 加 `--proxy-headers --forwarded-allow-ips=127.0.0.1`（systemd unit + start.sh）

### Phase B — 后端安全修复
- [x] B1 oauth status：加 expired_at 校验 + 签发后一次性消费（清 user_id）+ 简单限速；errmsg 不透传
- [x] B2 files：im-image 上传白名单(.jpg/.jpeg/.png/.webp)+魔数+10MB 上限；serve_file 按白名单 Content-Type inline，其余强制 attachment；cleanup-temp 加 admin 校验
- [x] B3 set-password：已有密码用户必须验旧密码（旧客户端未传 → 400，同批更新前端）
- [x] B4 管理员 token 365d→7d；新增 User.token_version（additive migration），access token 携带 tv claim，校验比对；改密/重置/登出全部设备时 tv+=1（实现即时撤销）
- [x] B5 client_ip：优先 X-Real-IP；读限速用真实 IP
- [x] B6 注册：密码 min_length=8 + 弱口令黑名单 + 注册 IP 限速（20/小时）
- [x] B7 community 序列化：post/comment 作者用 safe_public_username
- [x] B8 email_service SMTP 日志用 _mask_email
- [x] B9 view_file_as_html 改签发 5 分钟 file token（不再签完整 access token）
- [x] B10 头像上传：扩展名白名单+魔数
- [x] B11 APP_ENV=production 时关闭 /docs /redoc /openapi.json；.env 加 APP_ENV=production
- [x] B12 refresh token 改存 SHA-256（存量会话失效需重新登录一次；安全优先）

### Phase C — 隐私合规（后端）
- [x] C1 新增 `utils/pii_detect.py`：手机/邮箱/身份证/银行卡 检测+脱敏（138****1234 等）
- [x] C2 发帖：PostCreate 加 `confirm_pii`；命中 PII 且未确认 → 自动脱敏入库+响应 warning；确认保留 → 记审计 `community.pii_confirm`；加 `public_ack` 字段（公开帖确认标记，记审计，旧客户端不传不阻断）
- [x] C3 白斑报告：share-to-community 写审计 `skin_report.share`；新增 DELETE unshare 端点（is_public=False）；/shared/{token} 校验 is_public
- [x] C4 consent 接线：`build_user_context` 查 ai_data 同意，未同意 → 不注入个人上下文（返回提示语让用户在设置开启）；medical_report OCR 查 medical_photo 同意
- [x] C5 私密帖（is_private=True）不送第三方 LLM：post_ai 提取、图片视觉分析、content_safety 外部调用全部跳过（内容安全仅本地规则）
- [x] C6 训练数据：collect_samples / _add_label_to_training / _upsert_training_sample 过滤 is_user_deleted；导出 JSON/CSV 剥离 assessment_id；manifest 目录 7 天 TTL 清理（scheduler 挂钩）
- [x] C7 打标/训练 API 的 username 一律掩码（`U***abcd` 形式）；保留筛选能力但返回值脱敏
- [x] C8 ip-api 明文 HTTP → https://ipwho.is（HTTPS 免费无 key）
- [x] C9 账户删除 API：POST /api/user/delete-account（密码或 OTP 二次确认）→ 匿名化 User + 级联删除（帖子/图片/日记/VASI/报告/档案/事件/refresh token）+ 磁盘文件清理 + tv+=1；记审计

### Phase D — 前端（web/app）
- [x] D1 发布确认弹窗（所有编辑器统一）：公开帖发布前弹「内容将对所有人可见 + 请勿包含隐私信息」；前端 PII 检测命中 → 默认脱敏预览 +「保留原文」需显式勾选（confirm_pii）；**移除 ImagePostEditor 静默 is_private=false 翻转**
- [x] D2 SkinReportViewPage：分享到社区前弹确认（含预览）
- [x] D3 Profile 隐私中心：AI 数据授权（ai_data/medical_photo）开关 + 注销账户入口（OTP/密码确认）
- [x] D4 usePhoneHistory → sessionStorage；auth store 持久化前剔除 phone/email 字段
- [x] D5 useGeolocation：OSM 反编码坐标截断 2 位小数（≈1km）
- [x] D6 隐私政策页：第三方清单补 LLM/地图/IP 定位；AI 训练用途与撤回；注销权利
- [x] D7 set-password 传 old_password（已有密码时）

### Phase E — Admin（web/admin）
- [x] E1 ImageLabeling/TrainingDashboard 列头改「匿名编号」（后端已掩码）

### Phase F — 部署与验证
- [x] F1 后端语法检查 + systemctl restart subskin-backend + /api/health 验证
- [x] F2 web/app `npm run build`（staging）+ version.json 验证
- [x] F3 web/admin `npx vite build`
- [x] F4 DEPLOY_LOG.md 记录（Pending Changes）
- [x] F5 冒烟：登录/发帖(PII)/RAG/文件服务 端点验证

### 后续建议（本次不做，报告呈现）
1. **轮换密钥**：DashScope sk-862aa…（git 历史泄漏）+ proxy.py 内 DeepSeek key 改环境变量注入
2. SSH 改密钥登录（配好 authorized_keys 后 PasswordAuthentication no）
3. 云安全组/防火墙收敛入方向（仅 22/80/443）
4. python-jose → pyjwt（CVE-2024-33663/33664）
5. 生产建议加 CSP（需前端 nonce 改造，涉及面大）
6. 隐私政策法务复核；用户修正蒙层进训练集的单独告知勾选
