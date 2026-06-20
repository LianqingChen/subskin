# 🎯 Goal: VASI 白斑识别精度持续优化

> 创建日期: 2026-05-29
> 目标类型: 持续优化（不设终点，不断迭代）
> 优先级: 🔴 P0 — 核心功能，直接影响产品价值

## 终极目标

将 VASI 测评模块的白斑识别精度优化到**逼近皮肤科医生手动评估水平**，实现：
- 白斑检出率（Recall）> 90%
- 面积误差 < ±10%
- 用户手动修正比例 < 20%
- 误检率 < 5%

## 当前状态

### 已有管线
```
用户上传 → 质量检测(vasi_quality.py) → 预处理(vasi_preprocess.py)
  → VLM分类(千问 qwen3-vl-plus, via DashScope) → SAM VLM-guided 分割
  → nnU-Net 远程回退 → Mock 回退
```

### 模型资源
- **SAM ViT-B**: `/root/subskin/models/sam_vit_b_01ec64.pth` (358MB, CPU only)
- **千问云视觉模型**: qwen3-vl-plus (via DashScope, API key 已配置)
- **火山引擎**: VOLC_ML_ENDPOINT (nnU-Net 远程推理，如可用)
- **GPU**: 无本地 GPU

### 现有代码文件
- `web/backend/services/vasi.py` — 主编排服务
- `web/backend/services/vasi_segmentation.py` — SAM 分割核心
- `web/backend/services/vasi_skin_mask.py` — 皮肤前景检测
- `web/backend/services/vasi_preprocess.py` — 图像预处理
- `web/backend/services/vasi_quality.py` — 照片质量检测
- `web/backend/services/vasi_formula.py` — VASI 评分公式
- `web/backend/services/vasi_promptable.py` — 交互式 SAM
- `web/backend/api/vasi.py` — API 端点
- `web/backend/utils/llm_config.py` — LLM 配置（支持 DashScope/Volcengine）

### 数据飞轮已就绪
- `contour_diff` 字段已记录 AI 轮廓 vs 用户修正的差异
- 用户修正的轮廓会自动保存
- RLHF 数据管道已设计但未激活

## 优化路线图

### Phase B: MedSAM 替换（立即开始）
- [ ] 下载 MedSAM ViT-B 权重到 `/root/subskin/models/medsam_vit_b.pth`
- [ ] 对比测试 SAM vs MedSAM 在白斑分割上的表现
- [ ] 如效果更好，替换生产模型
- [ ] 预期精度提升: 30-50%

### Phase C-1: 千问云 VLM Prompt 持续优化
- [ ] 迭代优化 `_call_vision_model()` 中的 prompt
- [ ] 实验不同的千问视觉模型（qwen3-vl-plus → qwen-vl-max 等）
- [ ] 增加皮肤区域定位准确性
- [ ] 增加白斑边缘特征描述精度
- [ ] 实验多轮对话式分析（先总体分析，再逐个白斑精细分析）

### Phase C-2: 分割算法迭代
- [ ] 优化皮肤检测的色彩空间参数（HSV/YCrCb 阈值自适应）
- [ ] 实验局部自适应亮度阈值替代全局阈值
- [ ] 优化 SAM 采样参数（points_per_side, pred_iou_thresh 等）
- [ ] 增加多尺度推理（不同分辨率的图片各跑一次，融合结果）
- [ ] 实验 tile 策略的参数调优

### Phase D: 数据驱动持续改进
- [ ] 从 contour_diff 导出用户修正样本
- [ ] 建立白斑分割评估测试集
- [ ] 实现自动化回归测试（每次改代码后跑评估）
- [ ] 建立精度看板（检出率、面积误差趋势图）
- [ ] 如果收集到足够标注数据（200+），启动 nnU-Net 训练

### Phase E: 千问云 Code Interpreter / 多模态能力利用
- [ ] 实验千问 qwen3-max 的代码解释器能力进行图像分析
- [ ] 实验多模态链式推理（先分析皮肤类型 → 调整检测策略 → 精细分割）
- [ ] 利用千问云的 structured output 能力确保输出格式一致

## 工作原则

1. **每次修改必须可测量**：改任何参数或算法，必须有 before/after 对比
2. **优先利用千问云 API**：作为主要的智能决策层（分类、定位、特征分析）
3. **SAM 负责精度**：作为像素级分割的执行层
4. **用户修正数据是金矿**：每次用户手动修正都是免费的标注数据
5. **渐进式改进**：每次只改一个变量，验证后再改下一个
6. **保留回退链**：任何改动不能破坏现有的多级 fallback 机制

## 关键指标追踪

每次优化迭代后，应记录以下指标的变化：

| 指标 | 基线值 | 目标值 | 最新值 |
|------|--------|--------|--------|
| 白斑检出率 (Recall) | ~30% | >90% | ? |
| 面积误差 (MAPE) | ±50% | <±10% | ? |
| 误检率 (FPR) | ~40% | <5% | ? |
| 用户手动修正率 | ~80% | <20% | ? |
| 推理时间 (quick) | ~15s | <20s | ? |
| 皮肤检测 IoU | ~50% | >85% | ? |

## 可用的千问云模型

| 模型 | 用途 | 
|------|------|
| qwen3-vl-plus | 视觉分析（当前使用）|
| qwen-vl-max | 最强视觉能力 |
| qwen3-max | 代码解释器 + 推理 |
| qwen3-coder-plus | 代码生成优化 |

## 执行指令

作为 Codex agent，你的任务是：
1. 读取并理解当前 VASI 管线的所有代码
2. 按照上述路线图，从 Phase B 开始执行优化
3. 每次修改后对比效果
4. 将改进结果记录到 `hermes_plan/` 目录
5. 不断迭代，直到白斑识别精度达到目标
6. 如果遇到需要决策的问题（如选择模型、需要标注数据等），暂停并向用户请示