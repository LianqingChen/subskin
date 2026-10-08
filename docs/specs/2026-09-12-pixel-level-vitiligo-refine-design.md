# 白斑测评逐像素精修设计（VLM 粗定位 + SAM 逐像素定界）

- 日期：2026-09-12
- 状态：**待用户复核**（批准后进入实现规划）
- 关联：`docs/specs/2026-09-12-provider-neutral-skin-annotation.md`（现行 `skin-outline-v1` 协议）
- 触发：用户反馈「当前方案结果很差，输出的白斑范围和皮肤范围都是矩形，没有按照白斑实际的边缘生成范围」

---

## 1. 问题诊断（实测证据，非推测）

### 1.1 矩形来自模型输出，不是代码兜底
`render_annotation()` 与 `_call_vasi_api()` 中**不存在**「用 bbox 填矩形」的逻辑；矩形只能来自大模型自己输出的 4 个角点。
线上记录 `vasi_assessments.id=162`（当时模型 `dashscope/qwen3.7-plus`）即含 4 个轴对齐矩形（`excluded_regions` 3 个、`uncertain_regions` 2 个为 4 点退化多边形）。

### 1.2 更根本的原因：大模型无法「逐像素」
大模型只输出文本 token（坐标数字），其空间精度上限就是它给出的多边形顶点数（实测 16–26 点，点与点之间为直线段）。
**边界只有像素级分割器（SAM / 边缘感知算法）才能贴合真实色差过渡**，大模型的正确职责是「指出哪里（粗定位）」。

### 1.3 当前视觉模型在空间标注上不稳定
同一张图、同一提示词，各跑 3 次：

| 模型 | 结果 | 推理 token |
|---|---|---|
| `deepseek-flash`（当前配置） | #1 `not_assessable`（区域全空）；#2 `candidate`（24/24 点）；#3 `not_assessable` | 700 / 5577 / 1164 |
| `qwen3.7-plus`（切换前） | 3/3 `candidate`，皮肤 20/16/26 点、白斑 14/12/14 点 | ~4.1–5.5k |

→ `deepseek-flash` **2/3 拒答**，属不可用级别的不稳定；这一条不解决，逐像素无从谈起。

### 1.4 逐像素能力已存在，但在新协议路径被绕过
`vasi.py:298` 的 `if not annotation_protocol:` 使 `skin-outline-v1` 路径**跳过**整段 SAM/共识管线。
实测可用性（本机 CPU）：

| 能力 | 实测 |
|---|---|
| SAM ViT-B 权重 `models/sam_vit_b_01ec64.pth`（375MB）+ torch 2.8.0+cpu + `segment_anything` | ✅ |
| `vasi_promptable.prepare_image`（编码） | 2.0s |
| `vasi_promptable.predict_by_points`（预测） | 4.1s，score 0.974 |
| 输出掩膜形态 | 外接框填充率 **0.80**（贴合圆形病灶）；对照：轴对齐矩形 = 1.00 |
| `vasi_edge_segmentation.segment_lesions_edge_aware` | 0.27s（纯算法，确定性） |
| `refine_mask_by_edges()`（任意来源掩膜 → 边缘吸附） | ✅ 现成通用后处理 |
| `refine_skin_region()` / `build_skin_mask()` / `_refine_by_color()` | ✅ 现成 |
| SAM box 提示管线 | ✅ `predict_by_circle` 内部即 box 提示 |

---

## 2. 目标与非目标

### 目标
1. 白斑范围与皮肤范围的**最终边界由像素级分割器决定**，贴合实际色差过渡。
2. **结构性消灭**「输出是矩形」——退化候选只能影响提示，不能成为最终边界。
3. 大模型拒答/不稳定时**仍有逐像素结果**，而不是报错或退化。
4. 保持「模型只提候选、程序做测量」的安全原则与 `skin-outline-v1` 协议兼容。
5. 历史趋势/结果对比处提示「算法版本变更」，避免用户把测量口径变化误读为病情突变（已确认纳入范围，见 §8）。

### 非目标（YAGNI，本次不做）
- 前端新增「逐像素」开关或协议版本升级（前端继续发 `annotation_protocol=skin-outline-v1`）。
- nnU-Net 远程推理（`VOLC_ML_ENDPOINT` 未配置）。
- 重新启用患者画布共识 / LLM 裁判队列（保持现状）。
- 改动测量口径代码 `assessment_measurement.py`（仍 `photo-mask-v1`，只是输入掩膜更准）。

---

## 3. 设计

### 3.1 架构与插入点

```
assess_vasi()
  ├─ normalize_capture() / quality_checker            （不变）
  ├─ propose_annotation()          ← 大模型：只给「哪儿有白斑」（粗候选）
  ├─ 【新增】refine_annotation_layers()  ← SAM / 边缘感知：逐像素定界
  ├─ measure_layers()              ← 程序：从逐像素掩膜测量（不变）
  └─ 落库 / 人工核对                （不变）
```

新增服务层模块 `web/backend/services/vasi_pixel_refine.py`：

- 纯服务层，**不依赖 FastAPI**（backend-architect 规范 §3.1）。
- 不跨模块导入私有函数：所需能力通过既有公开入口调用（`build_skin_mask`、`refine_skin_region`、`segment_lesions_edge_aware`、`refine_mask_by_edges`）或在本模块内实现；如需复用 `vasi_promptable` 的内部能力，先将其公开化（§5.3 提取-公开化-替换）。
- 公开 API（草案）：

```python
def refine_annotation_layers(
    image_bytes: bytes,
    geometry: Dict[str, Any],          # propose_annotation 返回的原始 geometry
    *,
    time_budget_s: float = 25.0,
    max_lesion_regions: int = 4,
) -> Dict[str, Any]:
    """把大模型候选几何精修为逐像素掩膜。

    Returns:
        {
          "skin_mask", "lesion_mask", "uncertain_mask", "excluded_mask",  # np.ndarray(bool)
          "provenance": {
             "engine": {"skin": "cv", "lesion": ["sam", "cv", ...]},
             "sam_score": [...], "iou_vs_candidate": [...],
             "fallback_reason": [...], "timings": {...},
             "status": "refined" | "partial" | "candidate-only"
          }
        }
    """
```

### 3.2 逐像素算法（按区域）

| 区域 | 算法 |
|---|---|
| **皮肤** | `build_skin_mask()` 严格色彩模型 → 与大模型皮肤候选做一致性校验（重叠率）→ `refine_skin_region()` 收敛为主体皮肤（中心主体先验 + 断桥开运算 + 填洞 + 有界膨胀，**禁止凸包**）。CV 候选不可用或与候选严重冲突时，保留大模型多边形。 |
| **白斑** | 每个候选连通域 → 构造 SAM 提示（质心为前景点 + 外接框四角为背景点，或直接 box 提示）→ 得逐像素掩膜 → `refine_mask_by_edges()` 把边界吸附到颜色梯度脊线 → `_refine_by_color()` 剔除掩膜内明显非皮肤色像素。 |
| **排除区** | 直接采用候选（减法层）。 |
| **不确定区** | 直接采用候选（减法层），沿用现行规则从确定候选面积中扣除。 |

### 3.3 校验与兜底（不允许静默降级）

SAM 掩膜必须**同时**满足才采纳：

| 校验 | 阈值 | 理由 |
|---|---|---|
| SAM score | ≥ 0.80 | 低置信度掩膜不可用 |
| 与候选 IoU | ≥ 0.20 | 防止 SAM 跳到别的区域 |
| 面积比（SAM / 候选） | 0.2 – 3.0 | 防止一口吞掉整块皮肤 |
| 与皮肤求交后 | `lesion ⊆ skin`（沿用现有 2% 泄漏容忍） | 分母不可被污染 |

降级链（**逐级记录原因**）：

```
SAM 通过 → 采纳 SAM 逐像素掩膜
  ↓ 不通过
边缘感知 CV：segment_lesions_edge_aware(region = 皮肤 ∩ 候选外扩框) → 与候选重叠的连通域
  ↓ 不通过
保留候选多边形掩膜，`provenance.status = "candidate-only"`（并在 provenance 中标注降级原因）
```

### 3.4 大模型拒答/不稳定的处理

1. `propose_annotation()` 增加**重试**：遇 `not_assessable` 或空内容最多重试 2 次。
2. 仍失败 → **降级到纯 CV 逐像素路径**（皮肤 `build_skin_mask`+`refine_skin_region`；白斑 `segment_lesions_edge_aware`），用户仍得到逐像素结果，而不是 `AnnotationContractError`。
   - 例外：照片质量门禁已判不合格的，仍按原有流程拒绝（不掩盖真实的质量问题）。
3. 每次拒答/降级写入日志与 `provenance`，作为「是否把视觉模型换回 `qwen3.7-plus`」的决策依据。

### 3.5 性能预算

| 阶段 | 实测 | 约束 |
|---|---|---|
| SAM 图像编码 | 2.0s | **每张图只做一次**（复用 `_embedding_cache`） |
| SAM 单次预测 | 4.1s | 最多 4 个白斑连通域（按面积取大）+ 1 个皮肤 |
| 边缘感知 CV | 0.27s | 兜底路径，代价可忽略 |
| **全局预算** | — | **25s**，超预算的区域直接 `candidate-only` |

现有超时余量：客户端 `annotation_provider` 150s、前端 300s、nginx 300s。
现有并发模型：SAM 为全局单例 + 线程锁（`vasi_promptable`），测评请求会**串行化**，高峰期排队时间上升 —— 见 §6 风险。

### 3.6 数据与兼容

- **不改表结构**（backend-architect §4 / AGENTS.md：schema 只增不改）。
- `ai_skin_layer` / `ai_lesion_layer` 现在存**精修后的逐像素掩膜**（仍是 PNG data URL，格式不变）。
- 精修来源写入 `details.measurement.refine`（additive JSON）：引擎、score、IoU、耗时、降级原因、`status`。
- 原始候选几何继续保留在 `raw_api_response.geometry`（可审计、可回溯）。
- **测量语义变化**：面积分母/分子将由逐像素掩膜决定，数值会变化 → 跨版本趋势对比可能出现台阶。缓解：写入测量版本与精修来源；不跨版本强行比较（沿用既有「版本 + 掩膜缓存失效」机制）。

### 3.7 开关与可回滚

新增环境变量 `VASI_PIXEL_REFINE`（默认 `1`）。
- `=0`：完全回到当前行为（仅用候选多边形掩膜），无需改代码。
- 其余精修参数（预算秒数、最大区域数、各项阈值）同样以环境变量暴露，便于线上调参。

---

## 4. 测试与验收标准

### 4.1 单元测试（纯函数，不触网不落库）
1. 合成掩膜：矩形候选 + 圆形目标 → 精修后**不再是轴对齐矩形**（外接框填充率显著 < 1.0）。
2. `lesion ⊆ skin` 恒成立（构造越界样例）。
3. 校验阈值行为：低 score / 低 IoU / 面积比越界 → 正确走降级链并记录原因。
4. CV 路径确定性：同输入两次运行结果逐像素一致。
5. 超预算：模拟慢预测 → 剩余区域标记 `candidate-only` 且不抛异常。

### 4.2 回归（仓库内 2026-09-11 审计合成图）
`docs/audits/2026-09-11-assessment/evidence/*.png`（**非用户照片**）：
- 断言失败样本不再出现轴对齐矩形；
- 面积占比数值合理（对照 `-reference` 图）；
- 记录耗时分布（SAM 编码/预测/精修）。

### 4.3 量化指标（实现后回填实测值）
| 指标 | 目标 |
|---|---|
| 白斑掩膜为轴对齐矩形的比例 | **0%**（SAM/CV 成功时） |
| 端到端耗时（单张） | ≤ 45s（当前 ~20–40s + 精修预算 25s 内） |
| 精修成功（非 candidate-only）比例 | ≥ 90%（合成图集） |
| 重复运行面积波动 | CV 路径 0；SAM 路径记录实测 |

### 4.4 验收前置
实现完成后**先离线跑完 4.1–4.3**，再考虑重启共享后端。

---

## 5. 上线方式（⚠️ 共享后端约束）

后端为**单一实例、测试与正式共用**，本次为后端行为变更：

1. 实现 + 离线验证（不触碰线上）；
2. **必须提醒用户**：`systemctl restart subskin-backend` 后该能力对**测试环境与正式环境同时生效**，无法只上 staging；
3. 重启后灰度手段仅剩环境变量开关（`VASI_PIXEL_REFINE=0` 一键回退，仍需重启才能生效）；
4. 部署后验证：真实照片抽测（由用户在 staging 用自己账号执行，我不读取用户照片）、`/api/health`、耗时与降级率日志。

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| SAM ViT-B 为通用模型，可能选中反光/衣物/背景 | 面积虚高 | 皮肤约束 + 色值校验 + 面积比守卫；不通过即降级 CV |
| 面积数值变化导致历史趋势出现台阶 | 用户困惑 | 记录测量版本；跨版本不强行比较；必要时在 UI 标注「算法版本变更」 |
| SAM 串行化导致高峰期排队 | 测评变慢 | 25s 预算 + 最多 4 区域；必要时降低最大区域数或临时关闭精修 |
| CV 在毛发/反光/弱对比下欠分割（实测填充率 0.28 vs SAM 0.80） | 兜底质量差于 SAM | 兜底仅在前两级失败时使用；provenance 标注来源，便于后续审查 |
| `deepseek-flash` 持续 2/3 拒答 | 每次都走 CV 兜底，SAM 精修形同虚设 | 记录拒答率；若持续偏高，建议视觉模型换回 `qwen3.7-plus`（本设计已含重试与降级，换模型不影响精修链路） |

---

## 7. 影响文件清单（预估）

| 文件 | 变更 |
|---|---|
| `web/backend/services/vasi_pixel_refine.py` | **新增**（精修服务） |
| `web/backend/services/vasi.py` | `assess_vasi` 插入精修调用（约 10 行） |
| `web/backend/services/annotation_provider.py` | 拒答/空内容重试 |
| `web/backend/services/vasi_promptable.py` | 如有需要，公开化 box 提示入口（§5.3 规范） |
| `web/backend/.env` | 新增 `VASI_PIXEL_REFINE` 及精修参数 |
| `web/backend/tests/` | 新增精修单测 |
| `web/app/src/components/tracker/AssessmentStep3Result.vue` | 「VASI 趋势」处加算法版本提示 |
| `web/app/src/components/tracker/AssessmentRecentStrip.vue`、`AssessmentHistoryPanel.vue` | 历史迷你卡趋势箭头 / 历史面板处同源提示（实现时按实际渲染位置定位） |
| `DEPLOY_LOG.md` | 部署记录 |

**不改**：`assessment_measurement.py`（测量口径）、数据库结构。

**部署差异**：后端为共享后端（重启即对两环境生效）；前端改动按 AGENTS.md 规则**先部署 staging**，用户确认后再推正式环境。

---

## 8. 已确认决议（2026-09-12，用户确认）

1. **精修失败 → 保留候选多边形并标注 `provenance.status="candidate-only"`**，不报错、不要求重拍；用户可在核对界面手动修正。
2. **前端加「算法版本变更」提示**（已纳入本次范围，见 §2 目标 5 与 §7 文件清单）。
3. **视觉模型由数据决定**：记录 `deepseek-flash` 拒答率与降级率；若持续偏高，授权换回 `qwen3.7-plus`。精修链路与模型解耦，换模型不影响逐像素能力。
