# 医评（/hospitals）· 公开评价与分享改造

> 用户需求（2026-09-10）：
> 1. 第四个页面导航名改成 2 个字，一眼看出主要功能是「医院、医生、治疗方案」的分享和评价 → **医评**
> 2. 地图放到页面顶端
> 3. 用户先创建或选择医院（按省份、城市、具体地址）
> 4. 在下方进行医院、医生、治疗方案、治疗经历的评价和分享（**要真正公开可看**，用户已确认授权后端变更）

## 现状
- 页面 `web/app/src/views/HospitalMapPage.vue`，路由 `/hospitals`，导航名「就医地图」（`web/shared/site-modules.json`）
- 纯前端体验版：7 家官方来源医院为静态数据 `web/app/src/data/hospitals.ts`，标记/经历草稿只存 localStorage，**无任何公开评价**
- 无后端：`web/backend` 中不存在医院相关表/服务/API

## 目标架构

### 后端（共享后端，additive only — 新表新接口，不改动既有表结构）
| 文件 | 内容 |
|------|------|
| `web/backend/models/hospital.py` | Pydantic 请求/响应模型 |
| `web/backend/services/hospital.py` | 业务层：目录查询、聚合统计、创建医院、创建/查询/删除评价、官方目录种子 |
| `web/backend/api/hospital.py` | `/api/hospitals` 路由 |
| `web/backend/database/models.py` | 新增 ORM 表 `hospitals`、`hospital_reviews`（append-only 新增） |

**表设计**
- `hospitals`：id / slug / name / province / city / district / address / department / kind / features(JSON) / summary / source / lat / lng / origin(official|community) / status(visible|hidden) / checked_at / submitted_by / created_at / updated_at
- `hospital_reviews`：id / hospital_id / user_id / target(hospital|doctor|treatment|experience) / doctor_name / doctor_title / doctor_department / treatment_name / visit_month / duration / cost / outcome / ratings(JSON) / tags(JSON) / content / moderation_status(approved|flagged|blocked) / status(visible|deleted) / created_at / updated_at

**接口**
- `GET /api/hospitals` 目录（province/city/q/origin 过滤 + 评价数与均分聚合）
- `GET /api/hospitals/{id}` 详情
- `POST /api/hospitals` 创建医院（登录；省/市/区/详细地址；标记 origin=community 并展示「病友补充·待核实」）
- `GET /api/hospitals/{id}/reviews` 公开评价列表（只返回 approved+visible，按 target 过滤 + 评分聚合）
- `POST /api/hospitals/{id}/reviews` 发布评价（登录；PII 自动脱敏 + 夸大疗效用语提示 + LLM 内容安全异步审核）
- `DELETE /api/hospitals/reviews/{id}` 删除自己的评价（软删 + 审计）
- `GET /api/hospitals/reviews/mine` 我的评价
- 管理端：`POST /api/hospitals/{id}/hide`、`POST /api/hospitals/reviews/{id}/hide`

**合规**
- 公开发布 → `AuditLogService` 留不可篡改审计（`target_type=hospital_review`）
- PII（手机号/邮箱/身份证/银行卡）自动脱敏（复用 `utils/pii_detect.py`）
- 医生只记录「姓氏/称呼 + 职称 + 科室」，禁止联系方式；前端明确提示
- 疗效自述与主观体验分开；全程「本文不构成医疗建议」

### 前端（staging first）
页面自上而下改为：
1. **地图（顶端，全宽）** + 省/市快速选择
2. **第一步：选择或创建医院**（省 → 市 → 关键词/具体地址；选中或新建）
3. **第二步：评价与分享**（Tab：综合 / 医院评价 / 医生评价 / 治疗方案 / 治疗经历 + 公开评价列表 + 写评价）
4. 页脚免责声明

新增/改造文件：
- `web/app/src/api/hospital.ts`（新）
- `web/app/src/types/hospital.ts`（扩展）
- `web/app/src/composables/useHospitalRegistry.ts`（新：目录 API + 静态兜底 + 创建医院）
- `web/app/src/composables/useHospitalReviews.ts`（新：评价列表/发布/删除/统计）
- `web/app/src/composables/useHospitalDirectory.ts`（改造：接入 registry + 地址过滤）
- `web/app/src/components/hospitals/HospitalPicker.vue`、`HospitalCreateForm.vue`、`HospitalReviewBoard.vue`、`HospitalReviewList.vue`、`HospitalReviewCard.vue`、`HospitalReviewComposer.vue`（新）
- `web/app/src/views/HospitalReviewPage.vue`（重构，替换 HospitalMapPage.vue）
- 导航命名：`web/shared/site-modules.json`（label=医评 + desc + keywords）、`web/shared/page-names.json`、`web/app/src/constants/page-names.ts`、`router/index.ts` meta

### 验收
- [ ] `python -m pytest tests/backend -k hospital` 通过
- [ ] `npm run type-check` 通过
- [ ] `npm run build` 部署 staging，version.json buildTime 更新
- [ ] curl 新接口（目录/评价）返回正常，`/api/health` 正常
- [ ] DEPLOY_LOG.md 记录（含「后端已重启，共享后端即时生效」）
