# SubSkin 网站建设、架构与多 Agent 维护标准文档库 (`docs/standards/`)

> **定位**: 本目录是 SubSkin 全栈开发、用户体验、设计系统、隐私安全、部署运维及多 Agent 协同交接的**唯一模块化权威规范源**。
> **管理后台实时同步**: 本目录下的所有 Markdown 文档均通过 Vite `?raw` 直接编译进 SubSkin 管理后台（`https://admin.subskin.cn/#/dev-docs` — **「开发文档」** 栏目），确保仓库文件与后台展示 100% 零偏差同源。

## 📚 模块目录

| 编号 | 模块名称 | 文件路径 | 核心覆盖内容 |
|------|----------|----------|--------------|
| **STD-00** | **多 Agent 协同、无缝交接与项目治理总纲** | `docs/standards/00-agent-handover-governance.md` | 唯一事实来源矩阵、新 Agent 进场 5 步接手 SOP、`.agents/skills/` 技能挂载矩阵、CodeGraph 检索、接手 Prompt 模板 |
| **STD-01** | **产品架构、核心模块、用户动线与体验规范** | `docs/standards/01-product-ux-user-journey.md` | 站点模块唯一命名源、六大核心用户动线（免登录体验、AI问答导览、白斑日记与对比、体检解读、发现与就医经验、同行共建）、去焦虑化医疗 UX 准则 |
| **STD-02** | **全站 UI 设计系统、多端适配与分享海报规范** | `docs/standards/02-ui-design-cross-platform.md` | Cursor & GitHub × 医疗温度视觉哲学、色彩令牌、跨平台字体栈、三档容器宽度、微信 WebView/华为浏览器 7 大兼容铁律、RemixIcon 唯一图标、外部分享页与 Canvas 海报规范 |
| **STD-03** | **隐私保护、数据分级与安全合规生死线** | `docs/standards/03-privacy-security-compliance.md` | L1–L4 四级数据分类矩阵、10 条零容忍安全红线、颗粒度用途授权 (`UserConsent`)、不可篡改审计 (`AuditLog`)、被遗忘权、`is_discoverable` vs `privacy_mode` 反逻辑警示 |
| **STD-04** | **前端技术栈、工程架构与 PWA 开发规范** | `docs/standards/04-frontend-pwa-architecture.md` | `web/app/` 与 `web/admin/` 工程边界、Vue 3 + TS 单文件 <500 行规范、`vue-tsc` 零报错门禁、PWA 热更新与 4 项环境差异、`DigitalHuman` 与 `MaskEditor` 规范 |
| **STD-05** | **后端架构、数据库、AI/LLM 与算法服务规范** | `docs/standards/05-backend-ai-data-architecture.md` | 共享后端认知、`api -> services -> models/utils` 三层架构、领域异常转换、Python 3.9 兼容、SQLite 增量迁移、RAG 混合检索与 `rgb_seg_worker` 图像分割隔离 |
| **STD-06** | **三套环境隔离、部署流程、Nginx 与运维监控规范** | `docs/standards/06-environments-deployment-ops.md` | Staging / Production / Admin 三环境拓扑、零容忍部署四大铁律、Nginx 维护与 `nginx -t` 校验、P0–P3 故障分级与应急回滚预案 |
| **STD-07** | **质量门禁、测试规范与全栈交付验收清单** | `docs/standards/07-testing-quality-checklists.md` | 前后端与 AST 自动化检查命令、五大场景化交付验收 Checklist（新增页面、分享海报、后端 API、正式环境上线、Agent 会话交接清理） |

## 🔗 关联权威文件

- **Agent 根入口宪章**: `/root/subskin/AGENTS.md`
- **全站设计系统专项规格书**: `/root/subskin/docs/specs/2026-10-17-subskin-design-system.md`
- **统一 Skill 库**: `/root/subskin/.agents/skills/*/SKILL.md`
- **模块与页面命名源**: `/root/subskin/web/shared/site-modules.json`、`/root/subskin/web/shared/page-names.json`
- **部署与待发变更账本**: `/root/subskin/DEPLOY_LOG.md`
