# 管理后台「图片打标」模块：审查与重构方案（2026-10-21）

> 目标：后台打标与「日记」页（`/assessment`，skin-seg-v2）的数据契约一致，产出可直接进入 `ml/rgb_segmentation` 五类训练、经得起复核的金标准。
> 依据：三路只读审查（后台前端 / 后端与训练链路 / 日记页契约）+ `docs/research/2026-10-06-strategy/{06,09}` + `hermes_plan/2026-10-17-assessment-auto-detection-plan.md`。

## 1. 现状一句话

后台一套界面同时驮着**两条流水线**：旧版 VLM/SAM + U-Net（分型/分期/面积/VASI、二值掩膜、逐图随机切分）与新版 RGB 五类（受试者切分、授权复核、门槛登记），靠 `item.rgb` / `is_rgb_label()` 在前后端至少 9 处分叉。真实数据：打标 31 条（RGB 3 条、金标准 0、仅 1 位授权用户），从未导出过 RGB 数据集、从未训练过。**瓶颈不在算力而在"能高效产出合格标注"的工作台和流程。**

## 2. 审查发现（按严重度）

### 2.1 阻断训练质量

| # | 问题 | 证据 |
|---|---|---|
| A1 | 训练要五类（0 背景/1 正常皮肤/2 脱色/3 遮挡/4 不可判读，255 未标），后台只能画皮肤+白斑两层；导出只写 0/1/2，**未标像素被写成 0=背景**（不是 255），模型会把没标的地方学成背景 | `dataset_pipeline.py:229-231`；`MaskEditorAdmin` 仅两层 |
| A2 | 无复核：同一管理员一次提交即成金标准；`label_source:"clinician"` 是自报字符串；无双标、无一致性 | `rgb_training_admin.py:28`；`/label` 内 approve_gold |
| A3 | 预填后直接提交（自动化偏差）；无盲标模式；不记录预填来源、耗时、标注者、指南版本 | `LabelingWorkspace.vue` 预填链；snapshot metadata |
| A4 | 部位词表四套互不相同：日记前端 16 码、后端 20 码、后台 13 个中文值、训练清单 7 桶。日记的胸/腹/背/左右肢在导出里全是 `unknown`；后台 `normalizeBodySite` 认不出日记标签 | `bodySites.ts`、`assessment_body_sites.py`、`LabelingWorkspace.vue:59`、`dataset_pipeline.py:53` |
| A5 | "皮肤"语义三种：日记=总皮肤（含白斑）；后台快照=正常皮肤（互斥）；后台面积%=白斑/(皮肤∪白斑)，表单却写"占整图" | `photo-mask.ts`、`label_sync.py:149`、`MaskEditorAdmin:458` |
| A6 | 分组字段只有部位是真的，肤色/光照/质量/设备恒为 unknown，无法分层评估 | `dataset_pipeline.py:255-268` |
| A7 | gold 在 skip/reject 后仍留在导出集；用户新修订把行打回 pending 但 gold 仍指旧修订且无提示 | `_gold_rows` 不看 label_status |

### 2.2 数据丢失 / 功能 Bug

| # | 问题 | 位置 |
|---|---|---|
| B1 | 切换白斑区域直接覆盖画布，未确认的涂抹丢失；新区域继承上一块画布 | `LabelingWorkspace.vue:486-494`、`MaskEditorAdmin:438` |
| B2 | 空格平移被 `@pointerdown.stop` 吞掉；Ctrl+L/B/E 被工具快捷键劫持；+/- 提示无实现 | `MaskEditorAdmin:584,611` |
| B3 | 旧「训练导出」访问不存在字段 `ai_depigmentation_level` → 500；`a or b` 把 0.0 当缺失 | `image_label.py:1667-1669` |
| B4 | 导出按钮 `window.open` 不带鉴权 → 401 | `ImageLabeling.vue:781` |
| B5 | 提交失败也退出工作区；无未保存提示；401 不跳登录；预填备注硬编码成真实备注 | `LabelingWorkspace.vue:187,405` `request.ts:22` |
| B6 | 日记数字人可选「头部」(`head`)，后端 `BODY_SITE_LABELS` 无此码 → 用户提交被拒（**用户端 Bug**） | `DigitalHuman.vue:107` |
| B7 | 后台上传 `original_user_id=管理员`，导致授权判定要求管理员本人授权；扩展名取自文件名、未解码校验、未去 EXIF | `image_label.py:1390-1399` |

### 2.3 安全与隐私

| # | 问题 |
|---|---|
| C1 | `training-manifest` 下载只做 `startswith`，`../` 可越出目录读任意文件（管理员权限内） |
| C2 | 图片接口接受 `?access_token=`，管理员 JWT 进访问日志/历史/Referer |
| C3 | 用户已删除（墓碑）的照片仍可经 `/image`、`/annotations` 访问 |
| C4 | `sync-assessments` 把**所有**用户的日记照片投进后台队列，与是否授权无关；授权只在导出时校验 |
| C5 | 旧 `ai-pretrain` 把用户照片发外部 VLM，不查 `ai_data` 授权 |
| C6 | 撤回训练授权只追加 `DataRightsJob`，无消费者；已导出数据集（照片全量副本）不会被清理 |

### 2.4 架构与可维护性

- `image_label.py` 2598 行、25 个路由，DB/PIL/文件 I/O 全写在 API 层，`/root/subskin/...` 硬编码 9 处。
- 前端 4 个文件超 500 行规则（1075/909/1026/685）；三图对比弹窗、`proxyImageUrl`、部位选项各复制 2–3 份；`api/labeling.ts` 整文件无人引用；洪水填充/套索/多边形工具写好但被白名单关掉。
- 后台文案仍用「记录页」「测评」，与用户端「日记」不一致。

## 3. 目标设计

### 3.1 单一流水线
- **只保留 RGB 五类流水线**。旧 VLM/U-Net 从后台 UI 下线（训练页旧区、分型/分期/VASI 表单、「添加至训练样本」、AI 预标注(VLM)）；旧后端端点保留只读以便历史查询，写入端点不再被调用。
- 旧行（无 `rgb_sync`）在列表中标「旧版」，只读查看。

### 3.2 标签契约（与日记、训练三方一致）
- 坐标系：日记规范图（长边 1024，EXIF 已校正），即 `artifacts` 里 `image.png`。
- 标签：单张 uint8 类别图 `labels.png`，值 ∈ {0,1,2,3,4,255}，与 `ml/rgb_segmentation` 完全相同；保留 `normal_skin.png`/`lesion.png` 兼容旧读取。
- 预填映射：日记 `skin`(总皮肤) & ~`lesion` → 1；`lesion` → 2；`excluded` → 0；其余 → 255（**不再默认背景**）。
- 指标：白斑占比 = 2 / (1 ∪ 2)，与日记「照片内浅色占比」同一公式；只显示、不让人手填。
- 部位：新增 `web/shared/body-sites.json` 为唯一事实来源（日记 16 码 + 后端兼容码 `hands/arms/legs/feet/other` + 补 `head`），每码含 label/group/side；后端 `BODY_SITE_LABELS`、后台、导出分组都从它派生。训练分组用 `group`（head/torso/arm/hand/leg/foot），不再用 7 个中文桶。

### 3.3 工作流（每张图一个任务）
```
待标注 → 已提交(标注员A) → 待复核 → 金标准
   ↘ 不可用(质量原因)          ↘ 退回(附意见) → 已提交…
```
- 每次提交生成**不可覆盖的版本**（快照文件 + 新表 `rgb_label_submissions` 一行：标注者、角色、预填来源 none/ai/user、是否盲标、耗时、指南版本、图像级属性、类别图哈希）。
- 复核：复核人不能是提交人（单人运营时见 §5 决策 2）；复核界面并排显示 A 版 / AI 初稿 / 用户日记确认版，给出与 AI、与用户的 Dice；通过 = 金标准，绑定到该版本。
- 用户再次修订日记 → 任务标「用户有新修订」，金标准保留但提示可重标；skip/reject → 自动撤销金标准。

### 3.4 工作台（替换 LabelingWorkspace）
- 工具：正常皮肤 / 白斑 / 遮挡 / 不可判读 / 背景 / 擦除为未标(255)；点除连通区；智能填充（启用已有 FloodFill）；AI 吸附（复用 SAM `/refine` 的服务端能力，后台专用端点）。
- 图层：AI 初稿、用户日记确认版、当前版本可切换叠加/对比；透明度。
- 导航：上一张 / 下一张 / 保存并下一张（队列按筛选条件），快捷键（数字键切类别、[ ] 画笔、Z/Shift+Z 撤销重做、空格平移、Enter 提交、→ 下一张），离开未保存提示。
- 图像级表单（按标注员指南 T-Q/T-S/T-V）：质量通过/不通过+原因、拍摄类型、Monk 肤色 1–10/不确定、可见体征（有/无/无法判断）、含可识别信息、升级给医生、备注。**不再让标注员填分型/分期/VASI**（指南规定 AI·禁/医生专属）。
- 盲标模式：任务标记为基准/测试集时不预填，从零画。
- 去掉"多白斑区域"实例列表（训练不用逐区属性；区域数由连通域自动算），从根上消除 B1。

### 3.5 训练页
- 只保留 RGB：金标准概况（受试者数、图片数、部位/肤色覆盖、阴性样本数、距门槛差多少）→ 导出数据集（预览 split 分布）→ 训练 → 门槛 → 登记/停用。
- 导出写 255、写真实分组（部位 group、MST、质量、光照）、写标注者/指南版本到 provenance；阴性图（无白斑）允许进入。
- 数据集保留期：撤回授权或删号时删除含该用户的数据集副本（消费 `DataRightsJob` 的最小实现）；数据集 30 天到期清理。

## 4. 实施阶段

| 阶段 | 内容 | 影响面 |
|---|---|---|
| **P0 修缺陷与对齐基础** | B3/B6/B7/C1/C3/C5、A7；`body-sites.json` 与后端派生（补 `head`）；导出写 255 + 真实分组；后台文案「日记」；删死代码（`api/labeling.ts`、未用 composable 导出） | 共享后端 + 后台 |
| **P1 新工作台** | 五类编辑器、队列导航与快捷键、图层对比、图像级表单、盲标、版本化提交（新表，增量建表） | 后端（新增端点/新表）+ 后台 |
| **P2 复核与金标准** | 复核视图与 Dice、通过/退回、gold 绑定版本与自动撤销、进度仪表盘（待标/待复核/人均产量/一致性）、训练页重做、数据集保留期与撤回清理 | 后端 + 后台 |
| **P3 数据供给** | 后台上传走规范化+初稿管线（来源/许可字段）、主动学习排序（AI 与用户分歧大的优先）、旧流水线 UI 彻底移除 | 后端 + 后台 |

各阶段：后端测试补齐（`tests/assessment`、`tests/backend`），全量回归对照 15 个既有失败基线；后台构建即上线；后端重启影响全部环境，每次重启前确认。

## 5. 决策（用户 2026-10-21 拍板）

1. 旧 VLM/U-Net 流水线：**后台 UI 下线，后端只读保留**。
2. 复核：**单人可自复核，版本记 `single_review`**；标为测试集（基准）的样本必须由非提交人复核才算金标准。
3. 队列可见性：**只显示已授权「改进识别」(`model_training`) 的日记照片**；后台上传的图不受此限。
4. 范围：**P0~P3 全部**。

## 6. 实施结果（2026-10-22，代码完成、本地验证通过，待部署）

**后端（共享，需重启 backend + rgb worker）**
- 新增 `services/labeling/{class_map,sources,attributes,submissions,workflow,tasks,uploads,progress}.py`、`api/labeling_admin.py`（`/api/vasi/admin/labeling/*`）、`models/label_submission.py`（新表 `label_submissions`）、`image_labels.benchmark` 列（增量 ALTER）。
- `web/shared/body-sites.json` + `utils/body_sites.py`；`BODY_SITE_LABELS` 改为派生（原 20 码标签不变，补 `head`=头部，修复日记选「头部」提交被拒）。
- `dataset_pipeline`：金标准绑定提交版本；导出读 `labels.png`、未标写 255、分组取真实属性（部位 group/MST/光照/质量/拍摄类型）、provenance（复核方式/盲标/预填/指南版本/匿名标注员）、基准集受试者锁进 test、`prune_datasets`（30 天到期 + 消费 `model_training` 撤回工单；worker cleanup 也会调用）。
- 旧接口修补：训练导出 500、manifest 路径越界、墓碑照片仍可访问（10 处）、VLM 预标注改 410 并删除 SSRF 下载函数、RGB 标注禁止经旧 `/label`/`training-sample`/`POST gold` 写入。
- `label_sync`：用户再次修订不再把复核中/金标准任务打回 pending。

**后台前端（构建即上线）**
- 新工作台：五类画笔/填充/魔棒/点除、撤销重做、缩放平移/双指、对照查看（AI/用户/任意版本）、图像属性表单（指南 T-Q/T-S/T-V）、复核面板、版本历史、不可用原因、基准集切换、本地草稿自动保存、队列上一张/下一张、快捷键。
- 列表页、训练页重写（旧 U-Net 区下线）；删除 MaskEditorAdmin/LesionCard/LesionPanel/tools/3 个旧 composable（git rm）。所有文件 ≤ 500/400/200 行规则，vue-tsc 通过。

**验证**
- 新增 `tests/assessment/test_labeling_workflow.py` 10 项；更新 2 项旧断言。后端全量 671 过 / 15 既有失败（与基线一致）。
- 隔离 E2E（DB/产物副本 + 临时密钥 + 关闭后台循环，端口 8010/5175）：真实库副本上迁移成功；合成图上传→填充/魔棒/画笔/撤销→Ctrl+Enter 提交并下一张→单人复核→金标准→不可用→导出数据集，掩膜像素与画布一致；旧版 26 条转入成功；1024 宽布局可用。
- 修掉的前端问题：Tailwind `img{max-width:100%}` 致照片不显示、状态筛选白名单缺项、占比 ×100、优先级刻度、返回列表丢筛选。

**未做 / 遗留**
- 后台 SAM 点选吸附（避免在 API 进程加载 SAM）；医生角色与资质权限（仍是 `is_admin`）；旧版管理员标注作为「上一版本」预填。
- 当前只有 1 位授权用户：门槛要求测试集 ≥5 位受试者，按 15% 比例约需 ≥34 位授权受试者，瓶颈仍是授权与标注量。
