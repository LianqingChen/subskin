---
name: vitiligo-pixel-labeling
description: "SubSkin 白癜风皮肤/白斑逐像素五类标注与自进化闭环：通用模型出初稿 → agent 用可复现 ops/多边形修订 → 人工金标 → review 归因 → 重训 + bench 验证。准确性优先；禁止抄金标/用户版。"
---

# Vitiligo Pixel Labeling

> 管理后台「图片打标」的逐像素五类标注。目标：**每多一张人工金标，下一张新图的 AI 初稿就更准。**
>
> 触发词：白斑打标、像素标注、涂层、labeling workspace、pixel labeling、载入 AI 初稿、重新生成初稿、金标复盘
>
> 动手前必读：本文 + 同目录 `LESSONS.md`（Index 按场景检索）。最新准确度见 `ml/pixel_labeling/bench/latest.md`。

---

## 0. 目标与度量（先读）

进步只用一个问题衡量：**一张从没见过的新图，AI 初稿离人工金标有多近？**

| 数字 | 怎么来 | 用途 |
|------|--------|------|
| **初稿 Dice** | 人工修订**之前**的 AI 稿 vs 该图金标（`review` 输出） | 真实 KPI，每张图都要报 |
| **bench auto** | `bench`：通用模型在每张金标上出稿，用**没见过该图/该人**的留一组模型评分 | 「下一张新图」的预估；任何方法/规则改动前后都要跑 |
| **复现 Dice** | 看着金标调参或重放决策文件得到的分数 | 只证明「能复现」，**不是进步**，不得当成准确度汇报 |

指标定义（`ml/pixel_labeling/metrics.py`；金标 255 一律忽略）：

- `lesion_dice`：白斑 Dice。
- `lesion_dice_tol2`：忽略金标白斑边界 ±2px 后的 Dice——两位认真的标注者在边界上本来就会差几像素，这是最接近「审核者会接受」的指标。
- `skin_dice`、`occl_dice`，以及类别错误 `bg_as_occl`（衣服/墙标成遮挡）、`occl_as_lesion`（指甲/唇标成白斑）。

**终极目标**：`lesion_dice_tol2 ≥ 0.99`（对应「99.99% 准确」的工程定义）且类别错误为 0。按字面的逐像素 99.99% 连人与人之间都达不到，不作为考核口径。

**当前基线（2026-10-25，13 张金标，bench `v2-f3 baseline`）**：通用模型 auto 均值 `lesion_dice` 0.51、`tol2` 0.51、`skin_dice` 0.92。离目标很远——现阶段初稿质量主要靠 §3 的 agent 审定，模型随金标增多而提升。

---

## 1. Hard rules（零容忍）

1. **隐私（2026-11-06 更新）**：`kind=job`（日记）仍为 L3；第三方模型分析按 [STD-03 §5.1](../../../docs/standards/03-privacy-security-compliance.md) 执行：先告知实际服务商、模型、照片用途及数据处理政策，用户点击「同意并开始 AI 分析」授权本次处理，并在请求前校验、审计。仅在有效授权覆盖范围内可外发；缺少授权的历史照片保持本地处理。分析授权不含训练授权，管理员批量指令不替代照片所有者授权。
2. **共享后端 = 生产**：`apply`/提交/审批立即生效；只在 `pending` 任务上写 AI 稿。
3. **禁止抄金标/用户版像素**当 AI 稿（L-180-3）。金标只用于：度量、训练（`train` 自动纳入）、复盘归因。
4. **禁止一次性脚本出稿**：所有改动都写进 `decisions/<id>.json`（base + ops + 多边形），能被 `compose` 重放；需要新方法就在 `ops.py` 加一个带 lesson 编号的 op（L-meta-1）。
5. **禁止看着金标调参后把分数当进步**；调参只能用 `bench`（留一组）来验收。
6. **不确定 → 255**，但只给真看不清的窄边；高对比清晰斑不要丢进 255（L-188-2、L-189-4）。
7. 验收必须看**填充 overlay**，禁止只看轮廓线或占比（L-180-2、L-181-2）。

---

## 2. 标注规范（来自金标的稳定约定）

这是比任何方法都重要的部分：模型学的就是这些约定。新金标若推翻某条，先改这里。

| 类别 | 标什么 | 依据 |
|------|--------|------|
| **2 白斑** | 临床连续、边界光滑的脱色区；**卫星小斑全收**；深肤色上的浅棕/肉色岛也算；斑内小色素点不挖 | L-189-3、L-201-2、L-207-1、L-181-2 |
| **1 正常皮** | **唇红（2026-11-09 用户拍板；注意唇缘与白斑的边界）**、色素岛、褶皱/指节提亮、受光但不脱色的皮（lit-flat）、**眉区皮肤**（不是背景） | L-180-4、L-181-2、L-189-3 |
| **3 遮挡** | 指甲、鼻孔、画在图上的箭头/标注、遮眼黑条、压在皮肤上的饰物 | L-185-1、L-186-2、187/s9 |
| **0 背景** | 衣服、墙、桌面、铺巾、床单 | L-201-2 |
| **255 未知** | 斑缘 1–3px 的真模糊带（金标 185/191/201/263 都这样留）；不要整块 | L-189-4 |
| **4 不可读** | 隐私打码/模糊条覆盖的皮肤（看不出有没有斑）——**提议**，199 首次使用，待金标确认 | L-199-2 |

**待你确认的不一致**：头发——174/s2 标为背景，191/s5（头顶白发覆盖头皮）标为遮挡。确认前保持各图原样，不据此改模型。

---

## 3. 工作流（新任务）

```
draft <id>  →  填充 overlay 目视 + §4 清单  →  改 decisions（ops / 多边形）→ compose 复查
            →  apply（pending）→ 告知用户「载入 AI 初稿」
            →  人工修订并提交金标 → review → LESSON → train → bench（auto 不降才接受）
```

1. `draft <id>`：通用模型 `pixel-gb-v2` 出初稿，并在没有决策文件时生成骨架（`base: pixel-gb-v2`）。
   注意：管理后台「重新生成初稿」按钮仍走后端旧路径（face-gb-v1 / infer_rgb），**不是** v2；「载入 AI 初稿」只读已写入的稿。把 v2 接进后端属于共享后端改动，需用户确认。
2. 用 `result.jpg`（填充 overlay）对照原图，按 §4 找该场景的已知失败模式。**必须真正看图**：任何 `roi`/多边形坐标都要在 overlay 或 `grid` 上核对过，禁止按行号/能量曲线等启发式推断位置（L-199-2）。
3. 修订**只**通过决策文件：加 `ops`（§5.3）或多边形覆盖（`lesion_/normal_/unknown_/occlusion_/background_polygons`）。每处改动在 `notes` 写原因和 lesson 编号。
4. 按 bench 证据选底稿（选完在 `notes` 写理由；目视明显更准时可以改选）：

   | 场景 | bench 证据（留一组 auto vs 历史初稿） | 建议底稿 |
   |------|------------------------------------|----------|
   | 面颈大斑肖像 | v2 0.65–0.82；face-gb 只在 180 一人上校准 | `pixel-gb-v2` 起稿，再用 `face-gb-v1` 对照；占比明显偏低时查 §4 面部条目 |
   | 口周 / 颈特写 | v2 0.73 vs 历史 0.56–0.57 | `pixel-gb-v2` |
   | 手、躯干的小斑/卫星斑 | v2 0.01–0.46 vs 历史 0.84–0.90 | **`candidates` 逐块审定**（模型对小斑基本无效） |
   | 深肤色大片白斑 | v2 0.29–0.49 | `pixel-gb-v2` 起稿 + 大量 ops/多边形修订，或 `candidates` |

   每次 `train` 后以新的 `bench/latest.md` 更新此表。
5. `apply <id> --actor 9`，告诉用户白斑占比与需要重点检查的区域。

---

## 4. 已知失败模式清单（出稿后逐条查）

**面颈肖像**
- 额发际连续斑欠一圈；**眉上带较淡白斑漏标**（深肤色尤甚）→ `chalk_fill` / `local_contrast_fill`（L-181-2、L-199-1）
- 颊/鼻侧斑驳外扩、受光半脸整片涂白 → `litflat_trim` 或 `normal_polygons`（L-180-4、L-181-2）
- 眉区被当背景 → 应为正常皮（`normal_polygons`）（L-181-2、L-182-1）
- 口周：唇红 = 正常皮（2026-11-09 用户拍板）、鼻孔 = 遮挡，白斑只在唇周皮肤成环；颏中线斑驳不要并入（L-185-1/2）
- 同一人多张照：颜色整体偏移会让占比漂 5–8pp → face-gb 用 `lab_shift`，或直接依赖通用模型（L-181-1）

**手足**
- 指甲亮且白度分高，会被当白斑 → `fingertip_nails` 或 `occlusion_polygons`（L-186-2、L-189-2）
- 木桌/暖色背景：`color_b` 吞桌面、丢白斑 → 皮肤用 `wood_aware`（L-186-1）
- 指节上的斑块状浅色岛是白斑，细线状褶皱提亮才是正常（L-189-3）
- 淡斑召回不足：全手原图再扫一遍（L-189-5）
- 碎核可以很准，但腕/虎口的连片斑常只剩中心：不要用全局白度阈值去补，指节高光会一起进来（L-192-1）
- 浅色掌心整片偏粉是正常掌色，棕色斑是色素，不是白斑。模型会把整只掌涂成白斑（195）

**颈/躯干/背部特写**
- 衣服是背景不是遮挡（L-201-2）
- 主斑之外的次斑/卫星斑（L-201-2、L-207-1）
- 圆形斑候选核偏小、边缘被低估 → `ellipse_fill` + `lesion_close_gated` + `fringe_trim`；**禁止**无门控闭运算（L-207-1/2）
- 大斑中心空心 → `fill_lesion_holes`（L-201-1）

---

## 5. 方法库（全部有代码，可重放）

### 5.1 底稿 `base`

| base | 内容 | 何时用 |
|------|------|--------|
| `pixel-gb-v2`（默认） | 通用四类像素模型（背景/正常/白斑/遮挡），特征含 Lab、白度分、局部对比、mediapipe 人体解析置信度；在全部金标上训练 | 所有新图的第一稿 |
| `face-gb-v1` | 只在 180 一张图上校准的面颈白斑模型 + mediapipe 皮肤；`base_params.threshold`、`lab_shift` | 面颈大斑肖像对照 |
| `candidates` | 皮肤规则 + 白度分候选，逐块写 `lesion/unknown/reject` | 手足小斑需要逐块审定；历史决策 |

`candidates` 必审规则不变：内部且面积 ≥30 或 `score ≥ t_hi` 的候选必须显式决策（L-188-1、L-188-4）。

### 5.2 皮肤 `params.skin.method`（`candidates` 底稿用）

`mediapipe`（人像/身体）、`color_b`（蓝白铺巾近景，`hole_max` 只填小洞 L-189-1）、`wood_aware`（木桌/暖色背景，L-186-1）。

### 5.3 ops（`ops.py`，按列表顺序执行，再应用多边形覆盖）

| op | 作用 | lesson |
|----|------|--------|
| `chalk_fill(roi, dL, sg)` | 收比色素皮亮 `dL` 且白度高的粉笔白斑（模型低估的吸核区） | L-199-1 |
| `local_contrast_fill(roi, open_r, dL, sg, min_area)` | 收比局部暗底亮的较淡斑，独立小岛也收 | L-199-1 |
| `litflat_trim(band, sl_abs, sg_max)` | 白斑外缘只是「受光」的一圈退回正常 | L-180-4 |
| `ellipse_fill(...)` | 圆形斑按椭圆自适应扩到边界亮度回落为止 | L-207-1/2 |
| `lesion_close_gated(r, sg, sl)` | 平滑边界，只接纳本身发白的像素 | L-207-1 |
| `fringe_trim(sl_max, band)` | 去掉局部不发白的外圈 | L-207-1 |
| `global_score_fill(sg, close_r, pigment_L_off)` | 大面积手部斑：全局白度阈值 + 色素岛还原 | L-186-1 |
| `fill_lesion_holes(max_area)` | 填大斑空心 | L-201-1 |
| `lips_occlusion` / `dark_marks_occlusion` / `fingertip_nails` | 唇（**已废弃**：2026-11-09 起唇红=正常皮）、箭头/标注、指甲 → 遮挡 | L-185-1、L-186-2 |
| `occlusion_to_background` | 模型把帽沿/衣领当遮挡时，全部遮挡退回背景；真遮挡再用 `occlusion_polygons` 画回 | L-201-2、L-199-2 |
| `nail_ellipses(items)` | 图上核对过的指甲椭圆（cx,cy,rx,ry）→ 遮挡。`dark_marks_occlusion` 会把指缝阴影当箭头，手部图的箭头优先手画 | L-186-2 |
| `relabel_lesion_as_normal` | 审定后整幅白斑改回正常皮（如浅色掌心被整片误标） | 195 |

带 `roi` 的 op 用于单图修订（坐标写进决策文件），**不能**写成通用规则；能泛化的规律应进入训练数据或模型特征。

### 5.4 决策文件

```json
{
  "task_id": 199,
  "base": "pixel-gb-v2",
  "base_params": {},
  "ops": [{"op": "local_contrast_fill", "roi": [0, 275, 602, 355], "dL": 5, "sg": 1}],
  "lesion_polygons": [], "normal_polygons": [], "unknown_polygons": [],
  "unreadable_polygons": [], "occlusion_polygons": [], "background_polygons": [],
  "notes": {"_method": "为什么这样改 + lesson 编号"}
}
```

旧决策已迁移，原参数保存在 `legacy_params`，迁移说明在 `notes._migrated`。185/201/207 的旧稿来自一次性脚本，迁移后重放分数与当年不同（bench `replay` 列），以重放结果为准。

---

## 6. 复盘与进化协议（每张金标都走）

1. `review <id>`：读 `review_overview.jpg` / `review_regions_*.jpg`，只对 substantive 区域归因。
2. 判断谁更准。人工更准 → 归到三个落点之一，写进 LESSONS：
   - **标注规范**（§2 改一行）——例如「衣服是背景」；
   - **方法**（`ops.py` 新增/修改 op，带 lesson 编号）——只在规律可复用时；
   - **数据**——什么都不用做：`train` 会自动把新金标纳入训练。
3. `train`：重训通用模型（留一组评估写入 `models/pixel_gb_v2.json`）。
4. `bench --tag <说明>`：对比 `bench/history.jsonl` 上一次的 `auto_mean`。`lesion_dice_tol2` 下降或出现新的类别错误 → 回滚该改动。
5. 汇报时同时给出：该图**初稿 Dice**、bench auto 均值变化；复现分数必须标注「复现」。

---

## 7. Toolkit

```bash
cd /root/subskin
.venv/bin/python -m ml.pixel_labeling draft <id>            # 通用模型初稿 + 决策骨架
.venv/bin/python -m ml.pixel_labeling compose <id>          # 按决策重放（base + ops + 多边形）
.venv/bin/python -m ml.pixel_labeling view <id> x0 y0 x1 y1 # 局部放大
.venv/bin/python -m ml.pixel_labeling grid <id> x0 y0 x1 y1 # 坐标网格（画多边形/指甲）
.venv/bin/python -m ml.pixel_labeling prep|gallery <id> ... # candidates 底稿用
.venv/bin/python -m ml.pixel_labeling apply <id> --actor 9  # 写入 AI 初稿（pending）
.venv/bin/python -m ml.pixel_labeling review <id>           # 金标提交后
.venv/bin/python -m ml.pixel_labeling train                 # 全部金标重训 + 留一组评估
.venv/bin/python -m ml.pixel_labeling bench --tag <说明>     # 回归基准
```

| 文件 | 内容 |
|------|------|
| `ml/pixel_labeling/gold.py` | 金标清单（从数据库读最新 approved 提交，不手写） |
| `ml/pixel_labeling/models/pixel_gb_v2.json` | 模型卡：训练集、阈值、每张金标的留一组分数 |
| `ml/pixel_labeling/bench/latest.md`、`history.jsonl` | 最新基准与历史 |
| `ml/pixel_labeling/decisions/`、`reviews/` | 每图决策、复盘 |
| `data/labeling_work/<id>/` | 工作区（缓存特征、overlay） |

五类标签值：0 背景、1 正常皮、2 白斑、3 遮挡、4 不可读、255 未知（训练时忽略）。

---

## 8. 完成检查清单

- [ ] 读过 LESSONS Index；按 §4 查过对应场景
- [ ] 初稿来自 `draft`/`compose`，没有一次性脚本；决策文件能重放出已写入的稿
- [ ] 填充 overlay 验收；类别符合 §2（衣服=背景、指甲=遮挡、唇红=正常皮、眉区=正常皮）
- [ ] `apply` 成功，已告知用户占比和重点检查区域
- [ ] 金标提交后：`review` → LESSON → `train` → `bench`，汇报初稿 Dice 与 bench 变化
