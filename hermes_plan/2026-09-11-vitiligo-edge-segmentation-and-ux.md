# 2026-09-11 手帐白斑识别精度 + 操作体验优化

## 背景

用户反馈：手帐（`/assessment`）页面白斑面积识别**非常不准确**，要求：
1. 通过「逐像素颜色 + 相邻像素颜色差异」精准识别白斑范围与边缘。
2. 优化页面操作，让用户更方便地修正/标注。

## 诊断结论（实测 4 张真实上传照片，`tmp/diag/`）

| 问题 | 现象 | 根因 |
|---|---|---|
| 皮肤掩膜几乎覆盖全图 | 手部照片 skin=81.8%~100% | `build_skin_mask` 用 HSV ∪ YCrCb 并集，YCrCb(Cr 133-180) 把墙面/衣服/显示器全部纳入，无空间连贯性约束 |
| 分析区域=整图 | `region(hull)` = 100% | `expand_skin_mask_to_include_vitiligo` 对「膨胀后的最大轮廓」做**凸包**；皮肤贴边时凸包=整图 → 分母失真 |
| 白斑几乎全脸 | 面部照片粉色覆盖额头、眼周、衣领 | `detect_vitiligo_within_skin` 用**全图单一阈值** `max(median+12, p75+5)`；光照不均（一侧亮）时亮侧整体误判 |
| 边缘粗糙、块状 | 轮廓最多 40 点、epsilon=0.005 | `_mask_to_polygon` 无边缘吸附、无亚像素平滑 |
| 未利用相邻像素差异 | 完全未使用梯度/边缘信息 | 算法只做逐像素绝对/全局阈值 |

实测数据（768px 工作分辨率）：

```
1778982996  skin 51.5%  region 63.5%  vitiligo 12.9%  (threshold=171)
1778999494  skin 81.8%  region 100%   vitiligo 16.5%  (threshold=209)
1779529119  skin 100%   region 100%   vitiligo 20.9%  (threshold=170)
1780413603  skin 99.2%  region 100%   vitiligo 22.9%  (threshold=191)
```

## 方案

### A. 后端：新增 `web/backend/services/vasi_edge_segmentation.py`

边缘感知 + 局部自适应的分割模块（纯 cv2/numpy，无新依赖）：

1. **`compute_local_reference(L/chroma, valid, radius)`**
   迭代式「剥离亮区」局部参考：先算局部均值 → 低于均值的像素视为健康皮肤 →
   只对健康像素再算局部均值。得到**逐像素局部健康肤色参考**，消除光照梯度。
   （用 `cv2.boxFilter` 实现，O(n)，非循环 Python）

2. **`compute_gradient_magnitude(img)`**
   对 L、a\*、b\* 做 Sobel，合成梯度幅值 = 「相邻像素颜色差异」。

3. **`build_lesion_score(img, region)`**
   `score = wL·ΔL_local + wC·ΔChroma_local − wG·局部梯度均值`
   —— 比周围皮肤更亮 + 更少色素（低彩度）+ 内部平滑（无强边缘）。

4. **`hysteresis_threshold(score, hi, lo, valid)`**
   Canny 式双阈值：仅保留与高置信核心连通的区域 → 消除孤立噪点。

5. **`snap_mask_to_edges(img, mask, radius)`**
   在颜色梯度图上做 3 标记分水岭（FG 核心 / BG 核心 / 未知），
   让边界沿**颜色差异最大处**收敛 → 边缘精准吸附。

6. **`filter_lesion_components(...)`**
   剔除：过小、贴边背景、彩度高于周围（红疹/血管）、细长高光、无边界对比度。

7. **`segment_lesions_edge_aware(img, region)`**、**`refine_mask_by_edges(img, mask)`**、
   **`extract_precise_polygon(mask, max_points)`**（亚像素高斯平滑 + 保留更多顶点）

### B. 后端：改造现有模块

- `vasi_skin_mask.build_skin_mask`：收紧色彩阈值 + 连通域连贯性（保留主体大域、填洞、剔除贴边背景色域）。
- `vasi_skin_mask.expand_skin_mask_to_include_vitiligo`：**取消全局凸包**，改为 主体皮肤 ∪ 邻近脱色素候选（有界膨胀）。
- `vasi_skin_mask.detect_vitiligo_within_skin`：改为调用边缘感知算法，保留原签名与 stats 字段。
- `vasi_segmentation._is_white_patch_mask_within_skin`：全局中位数 → 局部参考。
- `vasi_segmentation.consolidate_segmentation` / `_segmentation_result_from_mask`：
  对任意来源（U-Net / SAM / CV）的 mask 统一做 `refine_mask_by_edges`，多边形改用 `extract_precise_polygon`。

### C. 前端：`web/app/src/utils/lesionMaskTools.ts`

浏览器端逐像素 + 邻域差异工具（与后端同源思路，交互即时）：
- `buildEdgeMap(imageData)`：Sobel(L, a, b) 梯度缓存。
- `magicWandGrow(...)`：点击白斑 → 边缘感知区域生长（颜色相似 + 强边缘停止）。
- `snapLesionMaskToEdges(...)`：沿法线搜索最大梯度，吸附边缘 + 平滑。

### D. 前端：MaskEditor 操作优化

- 工具栏新增「智能选斑（魔法棒）」「边缘吸附」「清空白斑」「重做」。
- 选区容差滑杆；操作引导文案更新；移动端 44px 触控目标。
- 面积实时反馈（白斑占比）。

## 验收

- 5 张真实照片：分析区域不再=整图；白斑掩膜不覆盖背景/衣物/衣领；边缘贴合真实色差边界。
- `pytest tests/...` 新增单元测试通过；`npm run type-check` 通过。
- 后端重启后 `/api/health` 正常；前端构建部署 staging（**不推正式环境**）。

## 实际结果（2026-09-11 完成）

实测数据（768px 工作分辨率，占比均为「占整图」/「占皮肤区域」）：

| 照片 | 旧 skin% | 旧 region% | 旧 vitiligo% | 新 region% | 新 vitiligo%（占皮肤） |
|---|---|---|---|---|---|
| 1778982996 面部 | 51.5 | 63.5 | 12.9 | 51.7 | 32.2 |
| 1778999494 手部 | 81.8 | 100 | 16.5 | 90.9 | 20.4 |
| 1779529119 面部 | 100 | 100 | 20.9 | 87.6 | 10.2 |
| 1780413603 面部 | 99.2 | 100 | 22.9 | 70.5 | 15.1 |

- 旧算法把墙面/窗帘/衣领/显示器判为白斑；新算法掩膜集中在额头、眼周、腕部等真实病灶。
- 边界放大对比：旧边界为噪声锯齿，新边界贴合真实色调过渡。
- 全分辨率 CV 回退路径耗时 3.61s → 1.28s；SAM 路径端到端（512px）18.6s 正常出结果。
- 后端 15 项新单测通过；`node --test tests/frontend/*.cjs` 35 项通过；vue-tsc 对改动文件无报错。
- staging buildTime 1789053244469；共享后端已 restart，`/api/health` OK。

额外修复（实施中发现）：**白斑画笔会擦掉皮肤层** → 用户手绘的白斑落在皮肤范围外，
提交时被后端以「请确认白斑范围在皮肤范围以内」拒绝且无法自救。现改为白斑笔补画皮肤层。

## 剩余风险

- 分析区域（分母）仍可能包含部分背景；单张特写无法可靠推得真实身体部位面积。
- 占画面比例极大的融合性白斑可能中心漏检（局部参考被自身主导）。
- `tests/backend/services/test_vasi.py` 有 5 项失败，经 git stash 对照确认由工作区中
  他人未提交的 `vasi.py` + `test_vasi.py` + 未跟踪的 `assessment_measurement.py`
  （体检测量 WIP）引起，与本次改动无关。

