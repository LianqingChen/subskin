# Vitiligo Pixel Labeling — Lessons

> 每条 lesson = 一次「agent 初稿 vs 人工金标」复盘的沉淀。  
> **新 agent**：先读同目录 `SKILL.md`（场景路由 + North Star），再按下方 **Index by scenario** 跳读相关条；动手前至少读与当前场景对应的全部 lesson。  
> ID 格式：`L-<task>-<n>`。权威流程以 `SKILL.md` 为准；本文件记「为什么」与反例。

**准确度目标**: 相对金标像素级 ≥ 99.99%（见 SKILL North Star）。每条 lesson 的 Rule 必须可执行，禁止空泛「下次注意」。

---

## Gold standards（approved，训练/回归用）

**权威清单不在这里手写**：`ml/pixel_labeling/gold.py::registry()` 从数据库读每个任务最新的 approved 提交；最新逐图分数见 `ml/pixel_labeling/bench/latest.md`。下表只是 2026-10-25 的快照，供阅读 lesson 时对照。

| 任务 | 提交 | 场景 | lesion_ratio | 对 AI 要点 |
|------|------|------|--------------|------------|
| 174 | s2 | 面颈（同人 user9） | ≈48.5% | 头发标背景 |
| 180 | s14（像素同 s13） | 面颈大斑 | ≈47.2% | face-gb 校准源 |
| 181 | s15 | 面颈同人 | ≈43.4% | 色偏 + 斑驳外扩/发际/眉洞 |
| 182 | s16 | 面颈同人 | ≈43.6% | 色偏小时欠召回；唇缘 |
| 185 | s19（像素同 s3） | 口周环状 | ≈16.1% | 唇/鼻孔/箭头=遮挡 |
| 186 | s21（**改过**，s4 为 39.1%） | 双手背大斑·木桌 | ≈34.7% | 木桌≠铺巾；指甲=遮挡 |
| 187 | s9 | 面颊小斑特写 | ≈0.34% | 遮眼黑条=遮挡 |
| 188 | s11 | 手 | ≈4.88% | 必审显式决策 |
| 189 | s20（像素同 s12） | 手 | ≈3.63% | 指节形态；全手扫描 |
| 191 | s5 | 背部单斑 | ≈4.47% | 头顶白发=遮挡（与 174 冲突，L-gold-1）；斑缘留 255 |
| 201 | s18（像素同 s17） | 颈特写 | ≈9.83% | 衣物=背景；次斑 |
| 207 | s24（像素同 s23） | 腹干多圆斑 | ≈1.65% | 禁无门控 close；卫星全收 |
| 263 | s7 | 深肤色双手 | ≈16.5% | 指甲=遮挡；斑缘留 255 |
| 192 | s26 | 双手背小斑·蓝铺巾 | ≈15.4% | 初稿只收最亮碎核（精确但漏大斑）；指甲/箭头对 |

---

## L-meta-1 · 2026-10-25 · 复盘方法本身的问题：复现分数≠进步、一次性脚本、金标清单过期

- **Task / submission**: 全局 review（180–207 全部任务）
- **Symptom**: 历次「复现 Dice」0.73–0.956 都是看着金标网格搜参得到的；同期**初稿 Dice**（人工改前）并无上升趋势（新场景 0.49–0.57）。181/185/186/199/207 的决策文件里有 `compose` 不认识的字段，无法重放。skill 里写的金标提交号 6 处已过期，且漏了 174/187/191/263 四张金标。通用模型首次留一组评估时，在训练图上调出的阈值 0.75 让所有新图系统性少标（均值 0.34，换成验证选出的阈值后约 0.45）。
- **Root cause**: 把「能否复现」当成「是否进步」；方法停在临时脚本里；清单靠人手维护；在训练集上调超参数。
- **Rule**:
  1. 进步只看初稿 Dice 和 `bench` 的留一组 auto 分数；复现分数一律标注「复现」。
  2. 出稿只能用 `draft`/`compose`；新方法进 `ops.py` 并注明 lesson。
  3. 金标清单用 `gold.registry()`；不在文档里手写提交号。
  4. 任何阈值/超参数只在留出数据上选。
  5. 186 的历史初稿 Dice（0.929）是对着试标 s4 调出来的，不能当作「当时的真实初稿水平」。
- **Status**: applied-to-code（`gold.py`/`bench.py`/`ops.py`/`pixel_model.py`）+ applied-to-skill

---

## L-gold-1 · 2026-10-25 · 金标之间对「头发」的标法不一致

- **Task / submission**: 174/s2、180–182 vs 191/s5
- **Symptom**: 同一人 4 张脸部金标把头发标为背景（每张约 3.6–5.3 万像素）；191 把头顶白发覆盖的头皮标为遮挡（约 2 万像素）。通用模型从 191 学到「头发=遮挡」，在 174/180/181/182 上产生约 3–4.5 万像素的背景→遮挡错误。
- **Root cause**: 标注规范没有覆盖头发；两种理解（头发不是皮肤→背景 / 头发挡住了头皮→遮挡）都说得通。
- **Rule**: 待用户定规范。在此之前：训练时跳过 mediapipe 判为头发且金标为背景/遮挡的像素；推理时头发按多数金标归背景。用户确认后改 SKILL §2 并重训。
- **Status**: pending（需用户确认）

---

## How to append

人工修订并 **approved**（或至少 submitted）后：

```bash
.venv/bin/python -m ml.pixel_labeling review <id>
# 读 data/labeling_work/<id>/review_overview.jpg + review_regions_*.jpg
```

1. 只记 `substantive`；`boundary`（≤3px）忽略。  
2. 判断人工是否更准；更准则归到一个落点：标注规范（SKILL §2）/ 方法（`ops.py`）/ 数据（`train` 自动纳入）。  
3. 追加到本文件（建议按任务号附近），并更新文末 Index。  
4. 跑 `train` + `bench --tag <id>`，在 lesson 里写清该图**初稿 Dice** 和 bench auto 均值的变化。  
5. `Status`: `applied-to-skill` | `applied-to-code` | `pending`。

```markdown
## L-<id>-<n> · YYYY-MM-DD · <一句话标题>

- **Task / submission**: <id> / s<submission_id>
- **Scene**: A 手足 | B 面颈大斑 | C 颈肢特写
- **Symptom**: 双方占比/Dice；实质 FP/FN 量级；关键 region 编号
- **Root cause**: 机制（非「再仔细点」）
- **Rule**: 可勾选的下次动作（改 SKILL / 代码 / 重训）
- **Status**: applied-to-skill | applied-to-code | pending
```

---

## L-192-1 · 2026-10-25 · 手背碎斑：初稿精确但只标最亮的核，漏掉连片的大斑

- **Task / submission**: 192 / s26（approved，prefill=ai）
- **Scene**: A 双手背，蓝铺巾，指尖朝左，左上角黑箭头
- **Symptom**: 初稿 lesion Dice **0.564**（tol2 0.436，漏的是整块不是贴边）。白斑 6.1% vs 金标 **15.4%**。初稿的 9138 个白斑像素**全部**落在金标里（没有过标）。漏标实质约 1.1 万，59 个连通块，最大两块在腕/虎口（2700、2700）。指甲+箭头遮挡 Dice **0.993**。
- **Root cause**: 模型留下的是局部对比最高的碎核（sl 中位 10.9）。金标另外包括更大、更亮但局部对比被吸掉的斑（漏标 L 中位 78、sg 19.9、sl 7.2，大块核心 sl 甚至为负）。把 sg 阈值放宽能收到这些核，但同样亮的指节高光（sg 20–30）会被一起标成白斑，复现 Dice 停在 **0.68**。候选能盖住金标的 77%，可是大连通块里只有 30–50% 是金标，整块收下会过标。
- **Rule**:
  1. 手背图初稿要预期「碎核很准、连片大斑会漏」。验收时专看腕、虎口、前臂有没有只标了中心的斑。
  2. 不要用一个全局 sg 阈值去补这张图的漏标：指节高光和真斑的 sg 重叠。复现分 0.68 不是可部署的方法。
  3. 指甲用核对过的 `nail_ellipses`；箭头手画。`dark_marks_occlusion` 会把指缝阴影当箭头，手部图不要开。
  4. 这张金标先不进当前模型。2026-10-25 把 192/s26 和同日入库的 199/s25 一起训练后，其余图的留一组 Dice 平均掉 0.05（187 的小斑从 0.27 掉到 0.02），已回退。等有不拉低旧图的训练方式再纳入。
- **Status**: applied-to-skill（训练纳入已回退）

---

## L-189-1 · 2026-10-24 · 皮肤洞填充把手指间背景当成皮肤

- **Task / submission**: 189 / （标注阶段自发现，写入前已修）
- **Symptom**: 用 flood-fill 填「所有」皮肤封闭洞时，两只手与右图边界围住的浅蓝铺巾被标成皮肤。
- **Root cause**: 白斑造成的真洞（该填）和肢体围住的背景洞（不该填）在拓扑上无法区分；全填必然误伤。
- **Rule**: 默认 `skin.hole_max=2000`（只填小洞）。仅当皮肤是单一实心区域（如单手完全在画面内、无间无背景）才允许 `hole_max=null`。`prep` 后必须目视 `heat.jpg` / 皮肤遮罩。
- **Status**: applied-to-code（`core.skin_mask`）+ applied-to-skill

---

## L-188-1 · 2026-10-24 · 未列出的候选被默认成「正常」→ 漏标白斑

- **Task / submission**: 188 / s11（与 s10 像素相同；作者修订后提交）
- **Symptom**: 人工把白斑占比从 3.54% 提到 4.88%（lesion Dice 0.84）。实质漏标区 #4 对应候选 **#45**（area=311, score=8.2, rim=0）——拇指背上一块清楚的浅色斑，agent 初稿完全没标。
- **Root cause**: v1 决策文件只写了 `lesion`/`unknown`，其余候选**隐式**当正常。高分内部候选没有强制过目。
- **Rule**:
  1. 每个必审候选必须显式写入 `lesion` / `unknown` / `reject` 之一。
  2. 必审 = 内部且 area≥30 **或** `score ≥ t_hi`（含高分边缘）。
  3. `compose` 对未决策的必审候选直接报错（`legacy_implicit_reject` 仅用于复现旧稿）。
- **Status**: applied-to-code（`__main__.must_decide`）+ applied-to-skill

---

## L-188-2 · 2026-10-24 · 「看不准」标成 255，人工确认为白斑

- **Task / submission**: 188 / s11 · review region #2
- **Symptom**: 候选 #87 指蹼处 agent 只把 ROI 标成 unknown(255)；人工整块改为 lesion。该区 median score=14.1，对比很强。
- **Root cause**: 过度使用 255。255 的本意是「真假难辨」；高对比、边界清晰的浅色岛应优先判 lesion。
- **Rule**: score 明显高于 `t_hi`、边界清晰、形态是斑块而非条带 → 标 lesion，不要怕标错而丢进 255。255 留给「略浅 / 可能是光」的模糊区。
- **Status**: applied-to-skill（§2.4 接受启发）

---

## L-188-3 · 2026-10-24 · 生长阈值过严，白斑核偏小

- **Task / submission**: 188 / s11 · review regions #1,#3,#5,#6
- **Symptom**: 已接受的白斑（如 #33 附近）人工向外扩了一圈更淡的过渡带；agent 的 `grow_score=3` 两轮没吃到 score≈0.6–3 的边缘。
- **Root cause**: 生长阈值保守，故意避免吃到周围正常皮肤；对低对比晕圈会系统性偏小。把 `grow_score` 降到 2 会引入大量假阳性（实验 Dice 下降），不能靠降阈值一刀切。
- **Rule**: 保持 `grow_score=3`。对人工指出的淡晕圈，用 `lesion_roi` 或 `lesion_polygons` **手工补**，不要全局放宽生长。复盘时若多张图都出现同类晕圈，再考虑按图像调参。
- **Status**: applied-to-skill（保留默认；补标用 ROI/多边形）

---

## L-188-4 · 2026-10-24 · 高 rim 候选被跳过，边缘白斑漏标

- **Task / submission**: 188 / s11 · review regions #7,#8
- **Symptom**: 上手尺侧缘小白斑（候选 #41, rim=0.66, score=9.8）因「边缘」未进必审画廊，整块漏标；局部还被皮肤掩膜切掉一点（人工把皮肤边界外扩包住白斑）。
- **Root cause**: 旧必审规则只看 `rim<0.2`。白斑贴皮肤轮廓时 rim 必然高，但分数也高——这是真白斑贴边，不是反光条带。
- **Rule**: 必审集合加上 `score ≥ t_hi` 的边缘候选。判断时区分：**细长沿边条带** → reject（反光）；**局部斑块贴边** → lesion。皮肤掩膜若切掉贴边白斑，用 `skin.add_polygons` 补回。
- **Status**: applied-to-code + applied-to-skill

---

## L-189-2 · 2026-10-24 · 指尖漏标指甲；边缘高分条带需显式 reject

- **Task / submission**: 189 / （v1→v2 自复盘，用户尚未修订）
- **Symptom**: v1 标了 8 个指甲，漏了指尖两枚（约 603,182 与 700,387）；14 个高分边缘候选未写入 reject，依赖隐式默认。
- **Root cause**: 指尖检测脚本只找「每行最左皮肤点」的局部极小，对斜向/内收指尖不敏感；加上 L-188-1 的隐式 reject。
- **Rule**: 指甲一律用 `grid` 对着原图读坐标，不信任自动指尖。所有 `score≥t_hi` 的边缘候选写入 `reject`（或确认为 lesion）。189 已升为 `pixel-reviewed-v2`。
- **Status**: applied-to-skill；189 决策已更新并 re-apply

---

## L-189-3 · 2026-10-24 · 指节「褶皱提亮」误判，把真白斑 reject 掉

- **Task / submission**: 189 / s12（approved → gold）
- **Symptom**: 白斑 Dice 仅 0.49。我 1.19% → 你 3.63%。我标的 2019 个白斑像素 **100% 被你保留**；你另补 ~4200。最大漏标区 #1 = 候选 **#7**（area=1089, score=6.7, rim=0，我写 reject「近节指间关节褶皱提亮」），你在其中标了 695px 白斑。同类还有 #13、#32、#29、#14。
- **Root cause**: 深色皮肤上白癜风常是「棕底上的浅棕/肉色岛」，不是粉笔白。贴指节时既有褶皱提亮、也有真白斑；我用「在关节上」一刀切 reject，把斑块状浅色岛当成了几何高光。
- **Rule**:
  1. **禁止**仅因「在指节/褶皱上」就 reject。
  2. 看形态：薄线沿褶皱 → reject；云状/斑块、边界不跟褶皱走 → lesion（或至少 unknown）。
  3. 内部 + score ≥ t_lo + 斑块形态 → 默认倾向 lesion，不要用 reject 逃。
- **Status**: applied-to-skill（§2.4）

---

## L-189-4 · 2026-10-24 · unknown 几乎全被人工清掉（再确认 L-188-2）

- **Task / submission**: 189 / s12
- **Symptom**: 我 unknown=1720 → 你只留 23。候选 #21/#23/#12/#5（当时 unknown）中共 544px 被你改成白斑；另有 396px 被改回正常（#23 的一部分）。
- **Root cause**: 同一病灶里深浅不均时，我整块丢进 255，等于把能判的核和不能判的边绑在一起。你拆开了：核→白斑，糊边→正常。
- **Rule**: 大块 unknown 先 `*_roi` / 拆核：对比清楚的核标 lesion，只把真正说不准的窄边留 255。整块 255 是最后手段。
- **Status**: applied-to-skill（强化 L-188-2）

---

## L-189-5 · 2026-10-24 · 候选召回不足：约 38% 人工白斑根本没进候选

- **Task / submission**: 189 / s12
- **Symptom**: 你标的白斑里有 **2379px（约 38%）完全不落在任何候选上**（如 review #5 score=-0.7、#8/#14/#16 中位数为负）。局部基线把淡斑吸进了参考，score 掉到阈值下。
- **Root cause**: 只靠 score 阈值召回，对「低对比、面积不小、肉眼可见」的淡斑会系统性漏检。
- **Rule**: `gallery` 判完候选后，**必须再做一次全手原图目视扫描**（不看热力图）：有浅色岛但无候选编号 → 用 `lesion_polygons` / `lesion_roi` 手动画上。禁止「候选审完 = 标注结束」。
- **Status**: applied-to-skill（§2.4.1 新步骤）

---

## L-180-2 · 2026-10-24 · 面颈大斑：局部基线把斑核吸进参考 → 候选根本长不出来

- **Task / submission**: 180 / （v1→v3 方法复盘；对照日记用户版，**不**以用户版为答案）
- **Symptom**: v1 白斑 22.5% vs 用户版 43.8%；召回仅 ~0.39。用户反馈「差太多」。尸检：用户版白斑像素里 **98.6% 从未落入任何候选**；FN 区 local score 中位数 ≈ **−0.4**（阈值下）。额/颊/颈大斑被拆成碎边缘岛。
- **Root cause**（机制，不是「阈值差一点」）:
  1. `baseline_mode=local`（σ≈25 高斯邻域）在**斑直径 ≫ σ** 时，斑核几乎填满窗口 → 局部均值被抬到接近斑本身 → `dL≈0` → 迟滞种子永远点不着核。这是 L-189-5 的极端放大版，不是 t_hi 调低能救的。
  2. MediaPipe 抠掉眉/眼：额带白斑被切出皮肤掩膜 → 即使有分也进不了候选（约 9–15% FN 在皮肤外）。
  3. 对比图若只用**轮廓线**叠在大斑上，会误以为「差不多」；必须用**填充 overlay** 才看得见核空洞。
- **Rule**:
  1. `prep` 后若 `large_plaque_risk.warn_large_plaque=true` → 切 **`baseline_mode=hybrid`**（不要纯 global，见 L-180-4），不要继续用碎候选硬扛。
  2. hybrid = 候选用 local；生长填「global 高且 local 负」的斑核。手部小斑仍用 local。
  3. MediaPipe 眉/眼洞：用 `lesion_polygons` 补；嘴唇 `no_draft` / `_lips_mask`。
  4. 边缘高光条带仍 `reject`；色素岛用 `normal_polygons`。
  5. job 预填优先用户版：改 AI 后必须让用户点「载入 AI 初稿」。
- **Status**: applied-to-code + applied-to-skill；纯 global 已被 L-180-4 否定；**有 face-gb 模型时优先 L-180-5，hybrid 仅作无模型回退**

---

## L-180-4 · 2026-10-24 · 纯 global 把「受光的半边正常脸」整片标成白斑

- **Task / submission**: 180 / （v3 global 被否：左半边脸几乎全是白斑）
- **Symptom**: v3 `baseline_mode=global` 后白斑 59%。**照片左半边**（viewer-LEFT）皮肤里 AI 标了 **88.8%** 为白斑；其中用户版标为正常的像素有 **85.6%** 被涂成白斑。逐像素抽样：这些 FP 的 RGB 仍是有色素的肤色（如 L*≈68，R≈210 G≈155 B≈130），**不是**粉笔白。
- **Root cause**（机制）:
  1. 本图左右半脸 **user-NORMAL 的 L\* 中位数差 23**：左≈66.3，右≈40.4（光照 + 色素分布不对称）。
  2. global 参考取全脸较暗 65% 分位 → ref L\*≈**47.5**，几乎全来自暗的右半边。
  3. 左半边正常皮肤相对这个暗参考 → global score≈**+19**，与真白斑分不开；迟滞后变成**一整块**候选，一接受就整颊涂满。
  4. 同一批 FP 的 **local score 中位数 ≈ 0.16**（对邻域并不更亮）——说明是「半脸亮度阶跃」，不是局部脱色斑。真白斑边缘 local 多为正、斑核 local 为负（被吸）。
  5. L-180-2 推的纯 global 在**半脸光照不对称**时会换成另一种系统性错误：从漏核 → 过召回整侧脸。
- **Rule**:
  1. `prep` 若 `L_half_asymmetry` ≳ 10（或目视一侧面明显更亮）→ **禁止**纯 `global`；用 **`baseline_mode=hybrid`**。
  2. hybrid：**候选只用 local**（亮颊平坦 → 不会长出整颊候选）；生长时额外填 `global高 ∧ local负` 的斑核（吸核区），**不**填 `global高 ∧ local≈0` 的受光正常皮。
  3. 逐像素核对过召回：看 FP 的 local score；≈0 且整片连在一起 → 光照阶跃，不是白斑。
  4. 对比必须用填充 overlay；不要用「和用户版 Dice」当唯一目标。
- **Status**: applied-to-code（`hybrid` / `score_pair` / `hybrid_global_fill`+`hybrid_core_max`）+ applied-to-skill；180 → `pixel-reviewed-v4-hybrid`（左半 AI 白斑占比约 47%，用户正常被误涂约 18–22%，整体约 34%）

---

## L-186-1 · 2026-10-25 · 木桌上手：默认 color_b 吞木纹、丢掉白斑

- **Task / submission**: 186 / s4（approved → gold）
- **Scene**: A 手足大斑（双手背+前臂，木桌背景，非蓝/白铺巾）
- **Symptom**: 初版 color_b 皮肤下，金标白斑约 95% 落在「背景」外；木纹大量进皮肤。复现用 pig∪depig−wood 后 lesion Dice≈0.93–0.94
- **Root cause**: `color_b`（B\*>b_min）适合铺巾；木桌高 L 高 b\* 与色皮同向，白斑 B\* 低被排除（吸核假象）
- **Rule**: 木桌/暖色背景手足图：皮肤 = 色皮（中低 L + 正 b\*）∪ 亮冷白斑（高 L + 低 b\*）− 高 b\* 木纹；再取大连通域。禁止裸用默认 color_b
- **Status**: applied-to-code（`skin.method=wood_aware`、op `global_score_fill`）+ applied-to-skill

## L-186-2 · 2026-10-25 · 指甲 sg 很高会被标成白斑；必须单独 occlusion

- **Task / submission**: 186 / s4
- **Scene**: A 手足大斑
- **Symptom**: review `occlusion` 实质≈6k；`Hocc→Ales`≈4.8k。金标指甲 L≈56–68 且 **sg≈22–38**（与白斑同向）
- **Root cause**: 全局 sg 阈值无法区分「白斑」与「亮指甲」；指尖带色阈也易漏
- **Rule**: 指甲用几何：皮肤顶缘局部 y 极小值（指尖）→ 椭圆盘 → class 3；箭头 CC → class 3。禁止指望 sg 阈值避开指甲。出稿后目视十指尖
- **Status**: applied-to-code（op `fingertip_nails`）+ applied-to-skill

## L-185-1 · 2026-10-25 · 口周环状金标：唇/鼻孔是遮挡，不是白斑

- **Task / submission**: 185 / s3（approved → gold）
- **Scene**: B 面部口周大斑特写（环状，非 180 同人）
- **Symptom**: 初稿 v1 Dice≈0.56；AI 21% vs 金标 16%。`Hocc→Ales`≈12.5k（MediaPipe 唇几乎全部被涂成白斑）；金标 occl≈27k（唇+鼻孔+箭头），AI 仅≈6.8k
- **Root cause**: 误把「口周脱色斑」理解成实心含唇；金标规则是**非皮肤器官（唇红、鼻孔）→ occlusion**，白斑只在唇周皮肤成环。箭头同为 occlusion
- **Rule**: 口周构图出稿：① MediaPipe `lips` → class 3；② 鼻孔暗区 → class 3；③ 黑箭头 CC → class 3；④ 白斑只留在皮肤环上。禁止「唇区保留白斑」作为默认
- **Status**: applied-to-code（op `lips_occlusion`、`dark_marks_occlusion`）+ applied-to-skill

## L-185-2 · 2026-10-25 · 颏部斑驳正常皮被并进白斑；鼻斑曾漏标

- **Task / submission**: 185 / s3
- **Scene**: B 口周环状
- **Symptom**: `overcalled_lesion` 实质≈28k（颏 #35/36/37、口周外扩）；`missed_lesion`≈22k（鼻背 #5 等曾被 reject）。复现用分区 face-gb 后 Dice≈0.73，仍 systematic 外扩（ratio 23% vs 16%）
- **Root cause**: hybrid 候选把颏中线斑驳/胡茬区高分当卫星；鼻部高分候选被当成 glare reject。face-gb 全局 thr 无法同时收环、抑颏、保鼻
- **Rule**: 颏：只收**中线两侧**高分岛（`sl` 门控 + 丢弃贴中线小连通域）。鼻：唇上方窄 ROI 内 face-gb/高分必审，勿当反光丢掉。口周：分区阈值（peri/nose/chin），勿一张 thr 通吃。残差 → 增量重训 face-gb（负样本：颏斑驳外扩、唇红）
- **Status**: applied-to-skill（重训 pending）

## L-207-1 · 2026-10-25 · 腹干多发圆形斑：无门控 morph-close 外扩低分 fringe

- **Task / submission**: 207 / s23（approved；s22 同像素 lesion 后被 superseded）
- **Scene**: C 腹干特写（蓝上衣入画；多枚光滑圆形白斑，金标 ratio≈1.65%）
- **Symptom**: v1 初稿 lesion Dice≈0.90；实质 FP 主要在最大斑 #11 外围低分 fringe 被 close 并入；衣物/手/ lit-flat#9 曾误收。seed（KEEP 核）Dice≈0.86。
- **Root cause**:
  1. **无门控闭运算**：`morph-close` 在 `sl` 接近 0 / 负的边缘也会把正常皮粘进白斑；腹干圆形斑临床边界光滑，但候选核偏小且边缘 local 分被吸核压低。
  2. **场景误用风险**：躯干多斑 ≠ 面颈大斑肖像；禁止 face-gb。衣物仍 = background（L-201-2）。
  3. **候选核 ≪ 临床盘**：如 #21 仅覆盖金标斑 ~27%；#23+#24 同属一斑却分成两核。
- **Rule**:
  1. 腹干/躯干多圆斑 → 场景 C：`color_b` + hybrid 候选；**禁 face-gb**；上衣/手 cy 靠上 → reject。
  2. **KEEP 全部**肉眼可见圆形/卵圆斑核（含小卫星）；禁「只留最大」。
  3. 合成后若要光滑：对每核 `fitEllipse`，按 **rim 中位 L 降至邻域正常皮 L** 自适应放大，再 `sl>≈2.5` 填盘；`dist≤3` 环带；**close 仅当新增像素满足 sg∧sl 门控**；fringe `sl` trim。
  4. 禁止无门控 morph-close / 盲目降 `sl` 补 rim（FN rim 常 sg 高但 sl≈0；放松 sl 会换来更多 FP，Dice 反而掉）。
- **Status**: applied-to-code（op `ellipse_fill`、`lesion_close_gated`、`fringe_trim`）+ applied-to-skill；复现 Dice≈0.956 属「复现」分数（L-meta-1）

---

## L-207-2 · 2026-10-25 · 圆形斑复现平台：候选核欠覆盖 + 吸核边缘 sg↑sl≈0

- **Task / submission**: 207 / s23
- **Scene**: C 腹干多圆斑
- **Symptom**: 方法复现（椭圆 L 自适应 + 门控 close）Dice≈0.956；miss≈590、over≈292。FN 距当前边界 p50≈2px、p90≈5px；miss 区 **sg≈14 且 sl≈0.3**。最大斑 (#11 核) 仍欠约 7%；弱对比斑 (#13 等) 边缘类似。
- **Root cause**: hybrid **local** 分在斑缘被吸进基线 → 临床仍属白斑的一圈 rim 过不了 `sl` 门；纯靠提高 sg / 放松 sl 会把 lit-flat 正常皮一并吸入。GrabCut/固定椭圆/无差别 ring-grow 平台约 0.90–0.94；L 自适应椭圆是当前最佳经典 CV，但到不了 0.99。
- **Rule**:
  1. 复盘时先算 seed Dice 与「miss 的 sg/sl」——若 miss=高 sg + 近零 sl，记为**吸核边缘**，不要只怪「没 close 够」。
  2. 同斑双候选（中心距≲数 px，如 #23+#24）→ dilate-merge 后再 fitEllipse。
  3. 验收用填充 overlay + 逐斑 cov；平台停滞在 ~0.95 时：**写清残差机制**，下一步靠斑盘学习模型 / 更多金标，**禁止抄 PNG 凑 100%**。
  4. 金标若含少量 unknown(255)，AI 稿可对齐保留，勿强行涂成 lesion/normal。
- **Status**: applied-to-code + applied-to-skill

---

## L-199-1 · 2026-10-25 · 深肤色额面：face-gb 漏掉眉上较淡白斑带

- **Task / submission**: 199 / 用户对 AI 初稿的反馈（尚无金标）
- **Scene**: B 面额大斑肖像（深肤色，异于 180 同人）
- **Symptom**: face-gb thr0.69 初稿 ratio≈40%；用户指出「眉毛上方白斑缺失很多」。眉上带 L(0–100)≈52–58，色素皮≈44；上额 chalk 斑≈70。漏标区 GB prob≈0.15，sg≈17 但 sl≈1.6。
- **Root cause**: ① hybrid local 分在大斑附近被吸核 → GB 概率低；② 眉上斑比上额 chalk 淡，全局 L/sg 阈值只收得到上额；③ 只接纳「连着已有斑」的补点会漏掉眉上独立岛。另：`core.lab_channels` 的 L 是 **0–100**，与 OpenCV LAB 的 0–255 混用会把阈值算错。
- **Rule**:
  1. 面额肖像出稿后必查**眉上带**（发际→眉→眼上）是否被逐行覆盖，不能只看总占比。
  2. 补标分两步：上额用 `L ≥ L_ref+12 ∧ sg>7`；眉上带用 `L − open(L, r=15) > 5 ∧ sg>1`，**独立岛**面积 ≥20 也要收，再做轻度 close。
  3. `L_ref` 只取非病灶、低 sg、中间亮度的色素皮（排除眉毛和帽子）；统一使用 `lab_channels` 的 0–100 尺度。
  4. 自检：病灶像素 L 低于正常皮中位数的比例应很低（199 约 2%）。
- **Status**: applied-to-code（op `chalk_fill`、`local_contrast_fill`）+ applied-to-skill（待金标复盘）。**注意**：本条当时的补标位置判断错误，见 L-199-2。

---

## L-199-2 · 2026-10-25 · 199 旧初稿严重过标：没看图就按行号补标；mediapipe 眉区挖洞

- **Task / submission**: 199 / 用户复看（尚无金标）
- **Symptom**: face-gb + chalk/local_contrast 旧稿白斑 63%：上额整片（含棕色色素皮、发际灰发）被涂成白斑；用户指出的眉上两大白斑反而是**背景色的洞**。改用 `pixel-gb-v2` 起稿 + 仅眉上带 `chalk_fill` 后为 21.9%，眉上两大斑与眉间小岛完整。
- **Root cause**:
  1. 补标 roi 是按「行能量最低处=眼睛」等启发式推出来的，没在图上核对，补到了上额而不是眉上。
  2. `face-gb` 底稿用 mediapipe 皮肤，**把眉区整块剔出皮肤**——眉上白斑正好落在里面，永远标不上。
  3. 上额受顶光整体偏亮，按「比色素皮亮 dL」阈值时正常棕色皮也过线；同一个 `chalk_fill` 在整额 roi 下多出 3.5 万像素误标。
  4. 打码眼部条被模型部分判成白斑；低头构图 mediapipe 检不出唇。
- **Rule**:
  1. 任何 roi/多边形都要在 overlay 或 `grid` 上核对坐标（SKILL §3）。
  2. 面部图先看 `pixel-gb-v2` 稿；`face-gb` 稿出现眉区背景洞时不要用它当底稿。
  3. 亮度阈值类 op（`chalk_fill`）只放在光照均匀的小范围 roi；加完必须看「新增像素」高亮图。
  4. 打码区 → `unreadable_polygons`（类 4，提议规范）；mediapipe 检不出唇时手画 `occlusion_polygons`；模型把帽沿当遮挡 → `occlusion_to_background`。
- **Status**: applied-to-code（`occlusion_to_background`、`unreadable_polygons`）+ applied-to-skill（待金标复盘）

---

## L-201-2 · 2026-10-25 · 人工 s17 vs 初稿：衣物不该标遮挡；漏了下颈次斑；主斑边缘略外扩

- **Task / submission**: 201 / s17（approved，prefill=previous）
- **Symptom（对比）**:
  | | AI 初稿 | 人工 s17 |
  |---|---|---|
  | 白斑占比 | 6.64% | **9.83%** |
  | lesion Dice | — | **0.573** |
  | 实质「遮挡」差异 | AI occl **50.7k** | 人工 occl **1.3k** |
  | 实质漏标 | — | **≈20k**（下颈为主） |
  | 实质过标 | — | **≈2.5k**（主斑边缘） |
- **差异本质**（人工更准；三类机制）:
  1. **衣物类别用错（最大像素债）**: AI 把黄衣大片标成 **occlusion(3)**；人工标 **background(0)**。遮挡应用于指甲/绑带/压在皮肤上的非皮肤结构；**画幅内大块衣服/背景布 = 背景**，不是 occlusion。color_b 把黄衣吃进「皮肤」后，用 occlusion 硬盖会污染训练语义（occl dice≈0）。
  2. **漏标下颈次级白斑**: 人工在锁骨/下颈有一片较淡、不连续的脱色（#3/#6/#7 等）；AI 只收了上颈心形主斑，把下颈候选全 reject。混淆矩阵 **AI背景→人工白斑 ≈15k**，且 FN 距主斑中位 **≫100px**——是远处第二灶，不是主斑贴边欠填。出稿后必须再扫**主斑以外**的皮肤：淡斑/卫星用 lesion 或 unknown，禁止「只留最大候选」。
  3. **主斑本身**: 与人工重叠约 **18k**（主体对上）；AI 在颌缘/斑周略外扩（#10/#14），部分高分核人工标 **unknown**（#9 lesion_too_confident ≈3k）——边界不确定用 255，勿硬涂满。
- **与 L-201-1 的关系**: 禁 face-gb、主斑孔洞填充仍对；但「衣物→occlusion」和「只收主斑」两条过激，被 s17 否定。
- **Rule**:
  1. 衣服/墙/床单 → **background**；仅指甲、压在皮肤上的绳/饰品/箭头等 → occlusion。
  2. 单斑图也要二次扫描：主斑之外是否有更淡的次斑/卫星；有则标 lesion 或 unknown，不要默认全 reject。
  3. 主斑高分但边界糊 → unknown 窄边，不要 lesion_too_confident 硬填。
  4. 复盘时 occl 像素差一个数量级 = 类别用错警报，优先查衣服是否被标成 3。
- **Status**: applied-to-skill；201 以 s17 为金标

---

## L-201-1 · 2026-10-25 · 颈侧单斑特写：禁止套 face-gb；颜色法收主斑后要孔洞填充

- **Task**: 201（PMC OA 上传，颈侧心形斑；非 180 同人面照）
- **Symptom**: 旧 AI（ita/grabcut）白斑 18%；试跑 face-gb / Lab对齐180 → **25–55%** 严重过召回。颜色法候选 #2=真白斑，#4 等=黄衣误检。
- **Root cause**:
  1. `face-plaque-gb-v1` 校准域是面颈大斑同人照，不能用于异人颈特写。
  2. `color_b` 易把黄衣当皮肤 → 衣物候选 **reject**，像素归 **background**（不要大面积 occlusion，见 L-201-2）。
  3. 局部基线吸核 → compose 后白斑呈**空心环**（同 L-180-2）；需对白斑连通域做**孔洞填充**再微调边界。
- **Rule**: 颈/肢单斑特写 → color_b/mediapipe + 候选审定；**禁止 face-gb**；出稿后查空心孔洞 + **二次扫描次斑**（L-201-2）。
- **Status**: applied-to-201 + applied-to-skill；细节以 L-201-2 / s17 为准

---

## L-182-1 · 2026-10-24 · 同人第三张：Lab 已对齐时 face-gb 占比准，残差是「欠召回 + 眉洞 + 嘴唇禁标」

- **Task / submission**: 182 / s16（approved，prefill=ai，`face-plaque-gb-v1+lab-match-180`）
- **Symptom（对比）**:
  | | AI 初稿 | 人工 s16 |
  |---|---|---|
  | 白斑占比 | 43.15% | **43.63%** |
  | lesion Dice | — | **0.945** |
  | 实质过标 | — | **0.9k**（次要） |
  | 实质漏标 | — | **5.2k** |
  | 实质漏皮肤 | — | **7.5k**（眉/眼周，AI=背景） |
- **与 181 对照**: 182 皮肤 Lab 已接近 180（dB≈0），无需大色偏校正；Dice/占比明显好于 181/s15（0.895 / 过标主导）。说明 **L-181-1 色偏是主祸首**；色偏不大时 face-gb 可直接用。
- **差异本质**（人工更准；残差三类）:
  1. **漏皮肤（最大块 #1/#2）**: MediaPipe 剔眉/上睑 → AI 背景；人工标回 **normal_skin**（91% miss_skin 落在眼鼻带）。与 L-181-2 相同，仍未自动化。
  2. **漏白斑（主残差）**:
     - **额发际连续斑欠一圈**（#3，≈1.9k）— 同 L-181-2；
     - **口周/下颌/颈侧卫星斑**（#4/#6/#7/#9/#10/#12 等）— FN 的 local≈0、global 常为负，GB 阈值下不够亮；人工按临床连续/小卫星补上；
     - **嘴唇**: AI `lips no_draft` 强制正常；人工在唇红缘标了 ≈**953px** 白斑。禁止自动把嘴唇当白斑种子仍成立，但出稿后须**目视唇缘**：确有粉笔白则 `lesion_polygons` 补，勿假装「嘴唇永远无白斑」。
  3. **过标很少**（#5/#13，实质 <1k）: 相对 181 的颊部斑驳外扩已不是主矛盾；边界微调即可。
- **Rule**:
  1. 同人新图：先比皮肤 Lab 中位与校准图；**|dB|≲1 且 |dA|≲2** → 可直接 face-gb，不必强行 Lab 对齐（对齐可能微伤）。|dB|≳3 仍走 L-181-1。
  2. 占比/Dice 已高时，复盘优先查：**眉区皮肤洞、额发际欠填、口周/颈卫星、唇缘**——不要再主攻「拧阈值降过标」。
  3. 出稿检查清单加一项：唇缘有无明显白斑？有 → 多边形补白斑；无 → 保持 normal。
  4. 180+181+182 金标可作 face-gb v2：正样本加重发际/卫星斑，负样本保持 181 斑驳外扩。
- **Status**: applied-to-skill；182 以 s16 为金标

---

## L-181-2 · 2026-10-24 · Lab 对齐后 vs 人工 s15：占比已接近，差在「斑驳外扩 / 额发际欠填 / 眉区皮肤洞」

- **Task / submission**: 181 / s15（approved，prefill=ai，`face-plaque-gb-v1+lab-match-180`）
- **Symptom（对比）**:
  | | AI（Lab对齐+face-gb） | 人工 s15 |
  |---|---|---|
  | 白斑占比 | 46.6% | **43.44%** |
  | lesion Dice | — | **0.895** |
  | 实质过标 | — | **8.6k**（最大一块左颊 7.1k） |
  | 实质漏标 | — | **3.6k**（额发际为主） |
  | 实质漏皮肤 | — | **8.6k**（眉/鬓，AI=背景） |
- **差异本质**（人工更准；三种机制，不是又一次全局色偏）:
  1. **过标 = 临床边界外的斑驳/过渡带外扩**（#1/#5/#10）: FP 的 local≈**−0.8**、global≈**14**（lit-flat 带）；61% FP 面积在 ≥1000px 大块里；到人工白斑边界中位距离 ≈**12px**。AI 把颊上「有点花、有点亮」的正常皮并进连续斑；人工收成光滑临床边界。
  2. **漏标 = 额发际连续斑欠填**（#4 等；FN 的 57% 在额带）: FN 到 AI 白斑中位距离仅 ≈**2.8px**——贴边欠一圈，不是远处漏岛。发际/眉上缘高对比处 GB+皮肤洞把连续额斑咬碎。
  3. **漏皮肤 ≠ 白斑问题**（#2/#3/#7）: MediaPipe 把**眉毛/鬓角**剔出皮肤 → AI=背景；人工标回 **normal_skin**。混淆矩阵 AI背景→人工正常 ≈9.8k。这是皮肤掩膜洞，不要当成漏白斑去用 face-gb 硬填。
- **与 L-181-1 的关系**: 色偏校正已把占比从 59% 拉回 ~47% 量级；s15 说明**校正后仍需边界后处理**，不能宣布 face-gb「同人可直接用」。
- **与 180 金标**: 同人 180≈47.2%、181 人工≈43.4%——照片/构图不同允许数个点差距；不要用「必须与 180 占比逐点相同」当 KPI。
- **Rule**:
  1. Lab 对齐 + face-gb 出稿后，用填充 overlay 专查：**(a)** 颊/鼻侧是否斑驳外扩（local≈0 且在白斑外 5–20px）→ 收回为正常；**(b)** 额发际连续斑是否欠一圈 → 沿亮带补白斑（非抄 PNG）；**(c)** 眉/鬓是否仍是背景 → 标 **normal_skin**（或扩皮肤掩膜），禁止当白斑种子。
  2. 人工偏好**光滑连续临床边界**；禁止把盐椒碎斑/毛孔级亮点当白斑留下。
  3. 复盘指标：Dice/占比接近后仍要按三类机制写 lesson；「只看占比」会漏掉 181 这种边界债。
  4. 后续模型：180+181 金标重训时加入「斑驳外扩负样本 + 额发际正样本」；推理侧可对 face-gb 结果做「距高置信核过远且 local≈0 → 降为正常」的保守修剪（须回归 180 不回退）。
- **Status**: applied-to-skill；181 以 s15 为金标；待 180+181 重训 v2

---

## L-181-1 · 2026-10-24 · 同人另一张照：单张校准的 face-gb 因色偏把正常皮当成白斑

- **Task**: 181（与 180 同一人；180/s13 金标白斑≈47.2%，181 日记用户版≈47.2%）
- **Symptom**: 默认 `face-gb` thr0.69 在 181 上白斑 **59.4%**（Dice vs 用户≈0.76–0.78）。FP≈35–42k，近半在眼鼻区，viewer-LEFT 为主；**70%+ FP 的 P(lesion)≥0.85**（高置信误标）。
- **Root cause**（机制）:
  1. `face-plaque-gb-v1` **只在 180/s13 一张图上校准**，决策面绑死了该照片的绝对 Lab / 白度分分布。
  2. 181 整体更冷、更少黄：皮肤中位 **B\* 低 ≈4、A\* 低 ≈3**（相对 180）。
  3. 181 上被误标的「正常皮」B\*≈18 —— 几乎等于 **180 白斑** 的 B\*≈19；而 180 正常皮 B\*≈22。模型没有「相对本图」的色度锚，只能按 180 的绝对颜色切。
  4. 眉缘 fringe / 闭运算不是主因（去掉各只动 ≈0.7pp）。
  5. 对照实验：把 181 的 Lab 皮肤中位数对齐到 180 再跑 face-gb → 占比 **≈46.5%**（回到同人应有量级）——证实是 **跨照片色偏/白平衡域偏移**，不是「181 白斑真的更大」。
- **Rule**:
  1. **同人多图**：不可假定「180 上 Dice0.95 的模型」直接可迁移；出稿后必须和同人已核占比（或 180 金标量级）交叉核对。
  2. 发现占比相对同人金标漂移 ≳5–8pp → 先查皮肤 Lab 中位差（尤其 **B\***）；差 ≳2–3 时对当前图做 **Lab 中位数对齐到校准图** 再跑 face-gb，或把新图金标并入重训 GB。
  3. 仍禁止贴用户版/他图 PNG（L-180-3）；色偏校正是改输入颜色分布，不是抄 mask。
  4. 单图校准模型的 `P|nor` 若在新图上 p90≳0.5，视为域偏移警报，不要只拧 threshold 凑占比。
- **Status**: applied-to-181（`face-plaque-gb-v1+lab-match-180`）+ applied-to-skill；待 181 人工确认后考虑 180+181 重训 v2

---

## L-180-5 · 2026-10-24 · 人工修订 vs hybrid 初稿：差在「斑核连续填充」；复现靠 B*/Lab 校准模型

- **Task / submission**: 180 / s13（approved，prefill=ai v4-hybrid）
- **Symptom（对比）**:
  | | AI v4 hybrid | 人工 s13 |
  |---|---|---|
  | 白斑占比 | 34.1% | **47.2%** |
  | lesion Dice | — | **0.71** |
  | 实质漏标 | — | **47k px**（最大一块 35k @颊中，median local≈−0.8） |
  | 实质过标 | — | **9.7k px** |
- **差异本质**: 人工从 AI 边缘**向外扩进斑核/斑驳过渡带**（94% 漏标落在 AI 白斑 40px 邻域内）。这些核 local≈−1、global 仅中等——颜色上像「有点色素的正常皮」，但临床是连续白斑内部。hybrid 为防 L-180-4 吞亮颊，core fill 偏保守 → 系统性欠召回。
- **尝试过的复现路径**:
  1. 加强 hybrid grow / g_cap → Dice≈0.79–0.81
  2. 按连通域形态学闭运算（临床连续边界）+ 挖 lit-flat → Dice≈0.84，ratio 易飙到 58%
  3. GrabCut / watershed / 测地线 → 不如 2
  4. **HistGB on Lab+sl/sg（无 x,y）**：半脸交叉验证 Dice **0.73–0.86**；全图校准后 vs s13 Dice **0.945**、ratio **46.7%≈47.2%**
- **特征启示**: 人工决策面里 **B\***（黄度）与 **A\***、local score 权重大；单纯抬高 `dL−0.8·db` 的 db 权重到 1.5，确定性 hybrid 约到 0.82，仍不如 GB。
- **Rule**:
  1. 面颈大斑：用 `python -m ml.pixel_labeling face-gb <id>`（模型 `ml/pixel_labeling/models/face_plaque_gb_v1.joblib`，默认 thr≈**0.69**）作可复现先验；**禁止**把 s13/用户版 PNG 当答案粘贴（仍守 L-180-3）。
  2. 特征面（勿擅自改成带 x,y 或纯 dL 阈值）：`L,A,B, sl, sl40, sg, L5, L15−L, L−med(L), B−med(B)`；嘴唇剔除；闭运算 r=2；眉缘亮带并入。
  3. hybrid 仅无 GB 模型时回退；**有模型必须优先 face-gb**，不要再手拧 hybrid grow / 闭运算凑占比。
  4. 新面颈金标入库后应增量重训 GB，不要假设单张 180 通吃所有肤色/光照。
  5. 复盘：先看漏标是否「贴着 AI 边缘的大核」（要连续填充），再看过标是否 lit-flat（local≈0 且 global 很高）。
  6. Admin「重新生成初稿」已走同一路径（`draft_for_labeling_workspace` → `face_plaque_gb`）；agent 本地出稿应对齐，禁止另写一套。
- **下次禁止的偏差路径**（180 实走弯路，勿重复）:
  `local 碎候选` → `纯 global 吞亮颊` → `贴用户版` → `拧 hybrid 凑 Dice` → **正确终点只有 face-gb（或无模型时的 hybrid）**。
- **Status**: applied-to-code（`face_gb.py` / CLI / admin redraft）+ applied-to-skill（§0.1 / §2.1.1）；180 vs s13 Dice **0.945**、ratio **46.7%≈47.2%**

---

## L-180-3 · 2026-10-24 · 禁止把日记用户版当 AI 初稿「抄作业」

- **Task / submission**: 180 / （v2 曾以用户版连续边界为底，被明确否决）
- **Symptom**: 发现与用户版差太多后，一度用日记用户版 mask 作 clinical prior 直接出稿。用户要求：必须**对比分析差因**，不得只抄用户版。
- **Root cause**: 把「对齐用户版」当成标注目标，绕过了方法失效的根因；用户版本身是另一标注者的判断（可错、可偏），抄了既学不到规则，也污染「AI 初稿」语义，复盘时无法区分方法进步与复制。
- **Rule**:
  1. **永远不要**把 `ref_user` / 日记用户版像素复制或形态学贴进 `ai.png`。用户版只作**对照度量**（Dice/FP/FN 尸检）与视觉参考。
  2. 差距大时的标准动作：填充 overlay 尸检 → 写清机制（本例 = local 吸核）→ 改方法/决策 → 再 compose。禁止「先贴用户版再微修」冒充 AI。
  3. 与用户版 Dice 不是 KPI；临床连续边界 + 可复现 `decisions/*.json` 才是。允许方法稿在边界/过渡带与用户版不同，但必须能在 notes 里用 score/形态解释。
  4. 每次对比发现的新机制必须追加 LESSONS（本条 + L-180-2），并改 SKILL/默认参数，避免下一张面颈大斑重蹈。
- **Status**: applied-to-skill；180 v2 用户版底已废弃，v3 为 global 方法稿

---

## L-180-1 · 2026-10-24 · job 初稿写入后被 cleanup 删掉 →「标注版本暂不可用」

- **Task / submission**: 180 / （打开工作区时报错，尚未人工提交）
- **Symptom**: 管理后台显示「标注版本暂不可用」。`rgb_sync.ai_revision` 指向的目录在磁盘上不存在；`read_manifest` 抛 `ARTIFACT_INVALID`。
- **Root cause**: `rgb_segmentation/cleanup.py` 只保留 VASI `assessment.details` / `job.result_json` 里的 revision。打标写入的新 `ai_revision` 不在保留集，worker 约 1 小时后 `rmtree` 掉。DB 指针还在，文件没了。
- **Rule**:
  1. cleanup 必须并入 `ImageLabel.rgb_sync`（`ai_revision` / `previous_ai_revision`）及打标日志里的 revision。
  2. `apply` job 草稿后做落盘校验，并在 `data/labeling_work/<id>/job_revision_backup/` 留副本。
  3. 若再遇此错：先确认 revision 目录是否存在；用 `previous_ai_revision` 恢复可读后再 `apply`。
- **Status**: applied-to-code（cleanup + system_io）

---

## Index by scenario

### 场景 A — 手足小斑

| ID | 一句话 | 触发时先想 |
|----|--------|------------|
| L-189-1 | 洞填充误吞背景 | 皮肤掩膜是否多了指缝/图边背景？ |
| L-188-1 | 隐式 reject 漏标 | 每个高分/内部候选都写进了决策文件吗？ |
| L-188-2 | 255 用过头 | 高对比清晰斑还在标 unknown 吗？ |
| L-188-3 | 生长偏紧 | 淡晕圈用 ROI 补，不降全局阈值 |
| L-188-4 | 贴边白斑 | 高分+高 rim？斑块还是反光条带？ |
| L-189-2 | 指甲/边缘 | grid 读指甲；边缘高分显式 reject |
| L-189-3 | 指节误 reject | 斑块还是褶皱细线？深色皮肤淡斑也是白斑 |
| L-189-4 | unknown 整块丢 | 核/边拆开了吗？ |
| L-189-5 | 候选召回不足 | 原图全皮肤扫过无编号浅色岛了吗？ |
| L-192-1 | 碎核很准、连片大斑漏 | 腕/虎口是不是只标了中心？别用全局 sg 补 |
| L-186-1 | 木桌 color_b 失效 | 背景是木桌？白斑是否落在皮肤外？ |
| L-186-2 | 指甲高 sg→假白斑 | 十指尖是否单独标了 occl？ |

### 场景 B — 面颈大斑肖像（含同人多图）

| ID | 一句话 | 触发时先想 |
|----|--------|------------|
| L-180-2 | 局部基线吸大斑核 | large_plaque_risk？→ face-gb 或 hybrid（禁纯 global） |
| L-180-3 | 禁止抄用户版当 AI | 在做尸检改方法，还是在贴 PNG？ |
| L-180-4 | 纯 global 吞受光半脸 | L_half_asymmetry？FP local≈0？ |
| L-180-5 | HistGB 复现临床核 | 面颈肖像 → face-gb thr0.69；禁拧规则凑数 |
| L-181-1 | 同人跨图色偏 | 占比高一截？查 B\*；Lab 对齐或重训 |
| L-181-2 | 对齐后边界债 | 斑驳外扩 / 发际欠填 / 眉洞？别只看占比 |
| L-182-1 | 色偏小时欠召回 | 眉洞/发际/卫星/唇缘？勿再死磕过标 |
| L-185-1 | 口周环：唇/鼻孔=occl | 是否把唇红涂成白斑了？箭头/鼻孔呢？ |
| L-185-2 | 颏斑驳外扩；鼻易漏 | 颏是否双侧岛？鼻背候选是否误 reject？ |
| L-199-1 | 深肤色眉上淡斑漏标 | 眉上带逐行覆盖了吗？独立岛收了吗？L 尺度 0–100？ |
| L-199-2 | 没看图按行号补标→过标 63% | roi 在图上核对了吗？face-gb 有没有眉区背景洞？打码区标 4 了吗？ |
| L-180-1 | cleanup 删 job 修订 | revision 目录还在吗？ |

### 场景 C — 颈/肢/腹干特写

| ID | 一句话 | 触发时先想 |
|----|--------|------------|
| L-201-1 | 禁 face-gb；吸核空心 | 特写单斑？候选+孔洞填充，勿套面模型 |
| L-201-2 | 衣物≠遮挡；漏次斑 | 衣服是 bg？主斑外扫过淡斑？occl 是否过大？ |
| L-207-1 | 腹干圆斑禁无门控 close | 多枚圆斑？卫星全 KEEP？close 有 sg∧sl 门吗？ |
| L-207-2 | 吸核边缘 sg↑sl≈0 | miss 的 sg/sl？平台~0.95 勿抄 PNG 凑 100% |

### 全局 / 流程

| ID | 一句话 | 触发时先想 |
|----|--------|------------|
| L-meta-1 | 复现分数≠进步；禁止一次性脚本 | 我报的是初稿 Dice / bench，还是看着金标调出来的分？ |
| L-gold-1 | 头发标法冲突（待定） | 这张图的头发按哪条规范？ |

### 全场景速问（出稿前 30 秒）

1. 场景是 A / B / C 哪一个？  
2. 有没有触发 §0.2 已踩坑表里的禁止项？  
3. 验收是否用了**填充** overlay？  
4. 人工修订后是否已 `review` + 写 lesson？
