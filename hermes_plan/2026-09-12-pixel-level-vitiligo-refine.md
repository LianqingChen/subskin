# 实施计划：白斑测评逐像素精修（VLM 粗定位 + SAM 逐像素定界）

- 日期：2026-09-12
- 设计文档：`docs/specs/2026-09-12-pixel-level-vitiligo-refine-design.md`（已批准）
- 目标：白斑/皮肤范围的**最终边界由像素级分割器决定**，结构性消灭矩形输出；大模型拒答时仍有逐像素结果

## 阶段

| # | 阶段 | 状态 |
|---|------|------|
| 1 | 新增 `services/vasi_pixel_refine.py` 精修服务 | ✅ 完成 |
| 2 | `annotation_provider` 拒答/空内容重试 + CV 降级 | ✅ 完成 |
| 3 | `assess_vasi` 接线 + `provenance` 落库 | ✅ 完成 |
| 4 | `.env` 开关 `VASI_PIXEL_REFINE` 与参数 | ✅ 完成 |
| 5 | 单测（纯函数，不触网不落库） | ✅ 完成（12 项全过） |
| 6 | 离线回归（审计合成图）+ 量化指标 | ✅ 完成 |
| 7 | 前端「算法版本变更」提示 | ✅ 完成（`AssessmentStep3Result.vue`，staging build 1789194138686） |
| 8 | 部署（前端 staging 先行；共享后端重启需用户确认） | ⏸ 前端已上 staging，**后端待重启** |

## 实测结果（离线，审计合成图，未用用户照片）

| 指标 | 结果 |
|---|---|
| 矩形候选（4 角点）→ 输出 | 外接框填充率 **0.79**（矩形=1.00）→ 矩形问题结构性消除 |
| 端到端 4 样本 | 4/4 出结果；`lesion ⊆ skin` 越界像素 0；面积占比 0.0–8.39% |
| 模型拒答样本 | `hard_shadow` 走「拒答 → CV 逐像素」降级仍交付结果 |
| 精修阶段耗时 | 0.3–6.9s（预算 25s）；整体含模型调用 40–70s |
| 单测 | 新增 12 项全过；既有分割测试 15 项无回归；`vue-tsc` 通过 |
| 既有失败 | `test_vasi.py` 5 项为**改动前既有**的 fixture 型失败（失败点在 `vasi.py:258`，先于本次插入代码） |

## 关键接口（已实测确认）

| 能力 | 入口 | 实测 |
|---|---|---|
| 严格皮肤候选 | `vasi_skin_mask.build_skin_mask(img_rgb)` | — |
| 皮肤收敛为主体型 | `vasi_edge_segmentation.refine_skin_region(img, skin, lesion, min_component_ratio)` | — |
| 白斑逐像素（CV） | `vasi_edge_segmentation.segment_lesions_edge_aware(img, region=, skin_candidate=)` → `lesion_mask` | 0.27s |
| 通用边缘吸附 | `vasi_edge_segmentation.refine_mask_by_edges(img, mask, region=, cfg=)` | — |
| SAM 编码/预测 | `vasi_promptable.prepare_image(key, bytes)` / `predict_by_points(key, [(x,y,label)])` | 2.0s / 4.1s，score 0.974 |
| SAM 掩膜解码 | `assessment_measurement.decode_mask(data_url)`（**读 alpha 通道**） | — |
| 色值校验 | `vasi_promptable._compute_color_confidence` | — |

## 决策与约束

- 精修失败 → 保留候选掩膜 + `provenance.status="candidate-only"`（用户已确认），不报错、不要求重拍
- `lesion ⊆ skin` 恒成立；`assessment_measurement.py` 测量口径**不改**
- 全局预算 25s、最多精修 4 个白斑连通域 + 1 个皮肤；超预算区域标 `candidate-only`
- 后端为共享后端：重启即对两环境生效 → **先离线验证，重启前需用户确认**
- 前端改动按 AGENTS.md 先上 staging

## 遇到的错误 / 修正

| 问题 | 处理 |
|---|---|
| `diary_image.py` 用 `os.getenv` 但未 `import os` | 已补 `import os`（本次相关改动） |
| `annotation_provider.py` 同上 | 已补 `import os` |
| SAM 掩膜用 `convert('L')` 读成空 | 必须走 `decode_mask`（alpha 通道） |
| `predict_by_points` 无 box 参数 | 用「质心前景 + 外接框四角背景」点提示；如需 box 走 `predict_by_circle` 的 box 管线 |

## 进度日志

- 2026-09-12：完成诊断（矩形来源、模型拒答率 2/3、逐像素能力勘察与 SAM 实测）、设计文档获批、三项确认决议回写。
