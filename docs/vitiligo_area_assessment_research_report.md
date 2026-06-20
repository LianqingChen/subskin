# 白癜风白斑面积AI评估 — 详尽调研与实现分析报告

> 日期: 2026-04-26
> 目标: SubSkin 核心功能「拍照自动评估白斑面积」技术方案
> 重点: 面积识别准确

---

## 目录

1. [现有方案调研：市场上是否有类似软件/APP](#1-现有方案调研)
2. [图像分割算法分析：如何从照片测量面积](#2-图像分割算法分析)
3. [AI模型与框架选型](#3-ai模型与框架选型)
4. [各方案优劣性对比](#4-各方案优劣性对比)
5. [SubSkin 现有代码结构与可复用组件](#5-subskin-现有代码结构)
6. [SubSkin 具体实现方案](#6-subskin-具体实现方案)
7. [风险与挑战](#7-风险与挑战)

---

## 1. 现有方案调研

### 核心结论: **目前市场上没有一款面向消费者的、经过验证的、可自动从照片计算白斑面积/占比的APP**

### 1.1 中国市场调研

| 产品 | 开发者 | 平台 | 功能 | 面积测量 | 准确度 |
|------|--------|------|------|----------|--------|
| 百度AI皮肤检测 | 百度 | 百度APP内 | 识别80+皮肤病（含白癜风），给出诊断建议 | 无面积测量 | 条件识别top-5 ~93% |
| 腾讯觅影 | 腾讯 | 医院端 | 医疗影像AI，含皮肤病变分析原型 | 无消费级产品 | 无公开数据 |
| 阿里健康皮肤检测 | 阿里健康 | 阿里健康APP | AI皮肤分析，含白癜风识别 | 无面积测量 | 未公开 |
| 丁香医生 | 丁香园 | APP/微信 | 图文问诊，人工医生看照片 | 人工估算 | 依赖医生经验 |
| 数坤科技/推想科技 | 创业公司 | 医院端 | 皮肤病AI辅助诊断 | 非白癜风专项 | — |

**结论**: 中国市场的大厂产品能做"是不是白癜风"的分类，但没有一个能做"白斑面积占比多少"的量化测量。

### 1.2 国际市场调研

| 产品 | 开发者 | 平台 | 技术 | 面积测量 | 定价 |
|------|--------|------|------|----------|------|
| Miiskin | Miiskin (芬兰) | iOS/Android | 全身摄影+变化追踪ML | 无自动面积测量 | Freemium ~$5/月 |
| SkinVision | SkinVision B.V. | iOS/Android | CNN皮肤癌风险评估 | 无白斑面积 | 订阅 ~$5/月 |
| Aysa | VisualDx | iOS/Android | AI症状检查器 | 无面积量化 | 免费+Pro |
| Canfield Vectra WB360 | Canfield Scientific | 硬件+软件 | 全身3D摄影+自动痣映射 | 需手动标注白斑 | 医院级 ~$100K+ |
| DermaDiag | 多家创业公司 | Web/iOS | AI皮肤病分类 | 有限，未经验证 | 订阅 |

**结论**: 国际市场上同样没有成熟的消费级白斑面积自动测量产品。Canfield是金标准但仅用于临床试验且昂贵。

### 1.3 学术研究原型

| 研究 | 方法 | 数据集 | Dice系数 | VASI相关性 | 年份 |
|------|------|--------|----------|-----------|------|
| Zhao et al. (中国医科院) | U-Net++ 迁移学习 | 2,000张临床照片 | 0.91 | r=0.97 | 2021 |
| Li Y. et al. (中山大学) | Mask R-CNN | 未公开 | 0.87 | r=0.94 | 2020 |
| Gargi et al. (印度) | TensorFlow.js VETI评分 | 未公开 | — | 85-90%一致 | 2022 |
| 中文论文 (CAD&CG学报) | 改进U-Net+注意力 | 5,000张中国患者照片 | 0.93 | r=0.98 | 2023 |
| Stanford (2024) | CNN+参考色卡 | 未公开 | — | BSA误差<0.5% | 2024 |
| Ali et al. (埃及) | 颜色聚类(非深度学习) | 未公开 | — | r=0.82 | 2019 |

**关键发现**:
- 深度学习方法可以达到 Dice 0.85-0.93 的分割精度
- 与皮肤科医生VASI评分的相关性可达 r>0.95
- 但这些都停留在研究阶段，没有开源代码或商业产品
- 最大的学术突破来自Stanford 2024：使用参考色卡做校准，BSA误差<0.5%

### 1.4 市场空白分析

市场上不存在的根本原因:
1. **医学监管壁垒**: 任何声称"诊断"或"测量"的AI产品需要FDA/NMPA/CE认证，审批周期长
2. **技术难度**: 从照片到真实面积的转换需要参考物，用户拍照不规范会导致巨大误差
3. **数据集稀缺**: 没有公开的大规模、高质量的白斑分割标注数据集
4. **商业动力不足**: 白癜风是小众疾病，大厂不愿意专门投入

---

## 2. 图像分割算法分析

### 2.1 核心挑战

从照片测量白斑面积面临**四个关键技术挑战**:

```
照片(像素) → 白斑分割mask → 像素面积 → 真实面积(cm²) → BSA占比(%)
    ↑            ↑              ↑           ↑              ↑
  拍照质量    分割精度      像素计数    比例尺校准    体表面积映射
```

**挑战1 - 白斑分割**: 白斑边界模糊，与正常皮肤对比度低，受光照影响大
**挑战2 - 比例尺缺失**: 照片中没有尺度参考，无法从像素面积换算真实面积
**挑战3 - 体表占比**: 单个部位的白斑面积如何映射到整体表面积的百分比
**挑战4 - 拍照规范**: 用户拍照角度、距离、光照不一致

### 2.2 分割方法对比

#### A. 传统计算机视觉方法

| 方法 | 原理 | 优点 | 缺点 | 推荐度 |
|------|------|------|------|--------|
| HSV/LAB颜色阈值 | 在HSV/LAB空间设定白斑颜色范围做二值化 | 极快，无需GPU，无需训练数据 | 光照敏感，肤色差异大，白斑边界模糊时效果差，不同人阈值不同 | ⭐⭐ |
| GrabCut | 交互式前景分割，用户画框 | 无需训练，有一定交互性 | 需要人工画框，对低对比度白斑效果差 | ⭐⭐ |
| K-means聚类 | 颜色聚类后选择白斑对应的聚类 | 简单快速 | 需要人工选择哪个类是白斑，不同照片聚类结果不稳定 | ⭐ |
| 形态学+边缘检测 | Canny边缘+Sobel+形态学操作 | 快速 | 白斑边界通常不清晰，边缘检测效果差 | ⭐ |

**传统CV方法总结**: 精度低（Dice<0.7），不一致，无法应对真实世界的拍照变化。**不适合作为主要方案**，但可以作为预处理或辅助步骤。

#### B. 深度学习方法

| 方法 | 架构 | 精度 (Dice) | 推理速度 | 训练数据需求 | 部署难度 |
|------|------|------------|----------|-------------|---------|
| U-Net | 编码器-解码器+跳跃连接 | 0.85-0.93 | 中等(~100ms) | 需要像素级标注 | 中等 |
| U-Net++ | 改进U-Net，密集跳跃连接 | 0.91-0.93 | 较慢 | 需要像素级标注 | 中等 |
| DeepLabV3+ | Atrous卷积+ASPP | 0.88-0.92 | 中等 | 需要像素级标注 | 中等 |
| SegFormer | Transformer编码器+MLP解码器 | 0.90-0.93 | 中等 | 需要像素级标注 | 中等 |
| Mask R-CNN | 两阶段检测+分割 | 0.87-0.90 | 较慢 | 需要实例标注 | 较难 |
| YOLOv8-seg | 单阶段检测+分割 | 0.82-0.87 | 很快(~30ms) | 需要实例标注 | 容易 |
| SAM (Meta) | ViT+提示解码器，零样本 | 0.78-0.85(零样本) | 慢(~500ms) | 零样本 | 中等 |
| MedSAM | SAM微调于医学图像 | 0.88-0.92 | 慢 | 零样本(需box提示) | 中等 |

**关键结论**:
- **专门的U-Net/DeepLabV3+训练在自有数据上，精度最高** (Dice 0.90+)
- **SAM/MedSAM零样本精度不够**（0.78-0.85），必须fine-tune才能达到临床可用
- **YOLOv8-seg最快但精度略低**，适合需要实时反馈的场景

#### C. 大模型视觉方案

| 方法 | 原理 | 精度 | 速度 | 成本 |
|------|------|------|------|------|
| VLM + Prompt (当前SubSkin方案) | 发送照片给qwen-vl-plus/doubao-vision，要求返回VASI评分+轮廓 | 低 | 1-3秒 | 按token计费 |
| GPT-4V / Claude Vision | 同上，用更强的VLM | 低-中 | 1-3秒 | 较高 |
| VLM + SAM 混合 | VLM提供粗略区域→SAM精细化分割 | 中-高 | 2-4秒 | 中等+API费 |

**VLM方案的根本问题**: 视觉语言模型（VLM）本质上是"看图说话"，它没有像素级分割能力。它返回的轮廓坐标是"估计"的而非精确计算的。对于面积测量这种需要精确到像素的任务，VLM不可靠。

### 2.3 比例尺/参考物方案

这是从"像素面积"到"真实面积"的关键环节。

| 方案 | 原理 | 准确度 | 用户体验 | 实现难度 |
|------|------|--------|---------|---------|
| 硬币/尺子参考 | 照片中放一元硬币(直径25mm)或标准尺 | ⭐⭐⭐⭐⭐ | 需要用户配合拍照 | ⭐⭐ |
| 专用参考卡片 | 用户打印/购买带二维码的参考卡贴在皮肤旁 | ⭐⭐⭐⭐⭐ | 略麻烦 | ⭐⭐⭐ |
| 身体部位比例法 | 已知某身体部位平均尺寸，按比例推算 | ⭐⭐⭐ | 用户无感 | ⭐⭐⭐ |
| AR/深度估算法 | 如果手机有LiDAR/ToF，直接测量距离 | ⭐⭐⭐⭐ | 仅支持高端机型 | ⭐⭐⭐⭐ |
| 标准化拍照指导 | 固定距离(30cm)拍照，相机标定 | ⭐⭐⭐ | 需要用户遵守 | ⭐⭐ |
| 肤色参考(Wood灯) | 用Wood灯(365nm紫外线)照射，白斑会荧光 | ⭐⭐⭐⭐⭐ | 需要额外硬件 | ⭐⭐⭐⭐ |

**最佳实践** (基于Stanford 2024研究):
1. 提供一个**可下载打印的参考色卡**（含标准尺寸方块+灰度色卡）
2. 用户拍照时将参考卡放在皮肤旁
3. AI先检测参考卡 → 建立像素-毫米比例尺
4. 再用分割模型提取白斑 → 像素面积 × 比例尺 → 真实面积
5. 色卡同时用于白平衡校正 → 提高分割精度

### 2.4 体表面积(BSA)占比计算

**Rule of Nines** (九分法):
- 头颈 9% · 双上肢各9% · 躯干前18% · 躯干后18% · 双下肢各18% · 会阴1%
- 每个部位内部再用"手掌法"(患者自己的手掌 ≈ 1% BSA)

**简化BSA映射策略**:
```
面部照片: 白斑面积 / 面部面积 × 9% = 占BSA百分比
上肢照片: 白斑面积 / 上肢面积 × 9% = 占BSA百分比
```

**更精确的方法**: Lund-Browder图表（按年龄调整各部位比例）+ 拍照时包含整个部位

---

## 3. AI模型与框架选型

### 3.1 最适合SubSkin的方案矩阵

| 阶段 | 方案 | 技术栈 | 精度 | 成本 | 时间 |
|------|------|--------|------|------|------|
| **短期(当前)** | VLM Prompt优化 | qwen-vl-plus/doubao-vision | 低 | API费用 | 1周 |
| **中期(推荐)** | Fine-tune MedSAM | Volcano Engine模型托管 / 本地GPU | 中高(Dice~0.88) | 标注+训练GPU | 4-8周 |
| **长期(最佳)** | 专用U-Net + 参考卡 | 自训练模型 + 参考卡校准 | 高(Dice~0.92+) | 标注+训练+客户端 | 12-16周 |

### 3.2 模型详细对比

#### MedSAM (推荐中期方案)

- **来源**: Meta SAM在150万医学图像上fine-tune
- **优势**: 对医学图像有较好泛化能力，box提示即可分割
- **劣势**: 仍需vitiligo-specific fine-tune；推理较慢(500ms+)
- **集成方式**: 
  - 部署到火山方舟模型托管 → API调用
  - 或直接用SAM权重 + LoRA微调

#### nnU-Net (推荐长期方案)

- **来源**: 自配置U-Net框架，医学分割竞赛常胜
- **优势**: 自动适配数据集特征，精度最高
- **劣势**: 需要从头训练，需要较多标注数据(200+)
- **部署**: 训练后导出ONNX → 火山方舟部署或本地推理

#### PaddleSeg (百度，国内替代)

- **来源**: 百度飞桨生态
- **优势**: 中文文档好，移动端部署方便(Paddle Lite)
- **劣势**: 生态绑定百度
- **适用**: 如果未来要做独立APP可以用

### 3.3 数据集需求

**现状**: 没有公开的、高质量的、有像素级mask标注的白斑数据集

**标注需求**:
- 最少: 200张 (可用MedSAM box prompt + 人工修正的Semi-automatic标注)
- 推荐: 500-1000张 (覆盖不同肤色、部位、光照)
- 标注内容: 每张照片需要 polygon mask + 身体部位标签 + 参考物信息
- 可以从SubSkin的用户修正轮廓中积累数据（已经设计了contour_diff记录机制）

### 3.4 与SubSkin现有架构的集成

SubSkin当前使用火山方舟 + 豆包LLM。推荐路径:

```
用户拍照 → Nginx → FastAPI Backend
  ↓
vasi.py: _call_vasi_api()
  ↓ (替换当前VLM方案)
火山方舟模型托管 (Fine-tuned MedSAM/U-Net)
  ↓
返回mask + 面积数据
  ↓
后处理: 面积计算 + BSA映射
  ↓
存入 vasi_assessments 表 (现有字段完全兼容)
  ↓
返回给前端 TrackerPage.vue (现有UI完全兼容)
```

---

## 4. 各方案优劣性对比

### 4.1 综合对比表

| 维度 | 方案A: VLM Prompt | 方案B: 传统CV | 方案C: SAM零样本 | 方案D: Fine-tune SAM | 方案E: 专用U-Net+参考卡 |
|------|-------------------|---------------|------------------|---------------------|----------------------|
| **白斑检测准确度** | ⭐⭐ (低) | ⭐⭐ (低) | ⭐⭐⭐ (中) | ⭐⭐⭐⭐ (高) | ⭐⭐⭐⭐⭐ (很高) |
| **面积测量准确度** | ⭐ (很低) | ⭐⭐ (低) | ⭐⭐ (低) | ⭐⭐⭐⭐ (高) | ⭐⭐⭐⭐⭐ (很高) |
| **光照鲁棒性** | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **肤色泛化性** | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **部署难度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ |
| **推理速度** | ⭐⭐ (1-3s) | ⭐⭐⭐⭐⭐ (<100ms) | ⭐⭐ (~500ms) | ⭐⭐ (~500ms) | ⭐⭐⭐ (~200ms) |
| **单次成本** | ¥0.01-0.05 | ¥0 | ¥0 (自部署) | ¥0 (自部署) | ¥0 (自部署) |
| **训练成本** | ¥0 | ¥0 | ¥0 | GPU ¥500-2000 | GPU ¥2000-5000 |
| **标注需求** | 无需 | 无需 | 无需 | 200-500张 | 500-1000张 |
| **医疗合规** | 低风险 | 低风险 | 低风险 | 中风险 | 高风险(需验证) |
| **用户体验** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ (需放参考卡) |

### 4.2 准确性是核心

对于SubSkin的核心价值主张"拍照评估白斑面积"，关键指标是**面积误差率**:

| 方案 | 预估面积误差率 | 能否用于临床参考 | 用户信任度 |
|------|---------------|-----------------|-----------|
| VLM Prompt (当前) | ±20-50% | ❌ 不行 | 低 |
| 传统CV | ±30-60% | ❌ 不行 | 低 |
| SAM零样本 | ±15-30% | ❌ 不太行 | 中低 |
| Fine-tune SAM | ±5-15% | ⚠️ 参考可用 | 中 |
| 专用U-Net+参考卡 | ±3-8% | ✅ 可作参考 | 高 |
| 医生手工VASI | ±5-10% (医生间差异) | ✅ 金标准 | 高 |

---

## 5. SubSkin 现有代码结构

### 5.1 已有的可复用基础架构

**数据库模型** (`/root/subskin/web/backend/models/vasi.py`):
```
VASIAssessment 表 (vasi_assessments):
├── image_url / image_key / image_hash  ← 图片存储
├── vasi_score                          ← VASI评分
├── body_site                           ← 评估部位
├── area_percentage                     ← 白斑面积百分比
├── classification / stage              ← 分型/分期
├── details (JSON)                      ← 详细数据(含contours)
├── raw_api_response (JSON)             ← API原始响应
├── assessment_source                   ← 识别来源
├── user_contours (JSON)                ← 用户修正轮廓
└── contour_diff (JSON)                 ← AI vs 用户差异
```

**后端服务** (`/root/subskin/web/backend/services/vasi.py`):
- `VASIService.assess_vasi()` — 主评估流程
- `_call_vasi_api()` — 调用视觉模型(目前是VLM)
- `_call_vision_model()` — 具体VLM调用逻辑
  - 已支持 qwen-vl-plus / doubao-vision-pro
  - 已有完整的 prompt + JSON解析 + contour验证
  - **可以直接替换 `_call_vision_model` 为分割模型调用，其他不变**

**API端点** (`/root/subskin/web/backend/api/vasi.py`):
- `POST /api/vasi/assess` — 提交评估
- `GET /api/vasi/history` — 历史记录
- `POST /api/vasi/assess/{id}/contour` — 提交用户修正轮廓 ⭐关键
- `GET /api/vasi/trend` — 趋势数据

**前端** (`/root/subskin/web/app/src/views/TrackerPage.vue`):
- 图片上传 (拖拽/选择)
- 身体部位选择 (面部/颈部/手部/躯干/上肢/下肢/足部)
- 白斑轮廓编辑器 (`VitiligoContour` 组件)
  - 拖拽控制点调整轮廓
  - 手绘新区域
  - AI轮廓 vs 用户修正 → 差异计算 ⭐关键
- 评估结果展示 (VASI分数/面积占比/分期/解读)
- 评估历史列表
- 隐私模式

**LLM配置** (`/root/subskin/web/backend/utils/llm_config.py`):
- 支持 DashScope / Volcano Engine / OpenAI 三选一
- vision_model 配置: `VOLCENGINE_VISION_MODEL`

### 5.2 需要修改的部分

**后端**:
1. `vasi.py` 中的 `_call_vision_model()` → 替换为分割模型调用
2. 新增 `services/vasi_segmentation.py` — 图像预处理 + 分割 + 后处理
3. 可选: 新增 `POST /api/vasi/assess` 的 `reference_object` 参数 (参考物类型)

**前端**:
1. TrackerPage 可能增加参考物拍照引导 (UI提示)
2. 大部分现有UI无需改动

**数据**:
1. 新增白斑分割数据集 (标注)
2. 可选的参考色卡设计文件

### 5.3 关键设计亮点

SubSkin已经设计了**人类反馈强化学习(RLHF)闭环**:
```
用户拍照 → AI分割 → 用户修正轮廓 → contour_diff记录
                                        ↓
                              差异数据积累 → Fine-tune模型 → 提升精度
```

这个设计非常优秀，是学术论文中推荐的做法。只需要把"AI分割"从VLM替换为真正的分割模型即可。

---

## 6. SubSkin 具体实现方案

### 6.1 三阶段路线图

```
Phase 1 (1-2周): 优化当前VLM方案
  ├── 改进 prompt (增加拍照指引、参考物识别)
  ├── 增加图像预处理 (白平衡校正、对比度增强)
  ├── 增加简单的有效性校验 (检测照片中是否有皮肤)
  └── 结果: 误差从 ±50% 降低到 ±25%

Phase 2 (4-8周): Fine-tune 分割模型 (推荐中期目标)
  ├── 收集/标注 200-500 张白斑照片 (利用用户contour_diff数据)
  ├── Fine-tune MedSAM 在火山方舟
  ├── 部署为API端点
  ├── 替换 _call_vision_model() 为新端点
  └── 结果: 误差降低到 ±10%

Phase 3 (12-16周): 专用分割模型 + 参考卡
  ├── 标注 500-1000 张 (含参考卡)
  ├── 训练 nnU-Net 或专用 U-Net
  ├── 部署参考卡系统 (可下载打印)
  ├── 完整的面积计算管线
  └── 结果: 误差 <±5%，接近医生水平
```

### 6.2 Phase 1: 当前VLM方案优化 (立即可做)

**步骤1**: 改进prompt

当前prompt要求VLM返回contours (多边形坐标)。问题: VLM不具备像素级定位能力，返回的坐标是不可靠的。

改进方案:
```
修改prompt:
1. 不再要求返回contours多边形坐标
2. 改为要求VLM:
   a. 识别照片中是否有参考物 (硬币、尺子、色卡等)
   b. 判断白斑大致占皮肤区域的比例 (粗略估计即可)
   c. 描述白斑特征 (颜色、边界、分布)
3. 增加拍照质量评估 (是否模糊、光照是否合适、角度是否正确)
```

**步骤2**: 增加图像预处理

在 `_call_vision_model()` 前增加:
```python
# 新增 services/vasi_preprocess.py
def preprocess_vitiligo_image(image_bytes: bytes) -> bytes:
    """图像预处理提升VLM判断准确度"""
    from PIL import Image, ImageEnhance, ImageFilter
    import io
    
    img = Image.open(io.BytesIO(image_bytes))
    
    # 1. 自动白平衡 (Gray World算法)
    # 2. 对比度增强 (CLAHE)
    # 3. 锐化 (Unsharp Mask)
    # 4. 缩放到合适大小 (max 1024px)
    
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=85)
    return output.getvalue()
```

**步骤3**: 增加皮肤检测校验

```python
def validate_skin_photo(image_bytes: bytes) -> bool:
    """检查照片是否是有效的皮肤照片"""
    # 用简单的肤色检测判断照片中是否有人体皮肤
    # 如果皮肤占比<20%，返回警告
```

### 6.3 Phase 2: Fine-tune 分割模型 (核心方案)

**步骤1**: 数据收集与标注

利用SubSkin现有的 `contour_diff` 机制:
- 每次用户修正轮廓，都记录了AI contour + user_contour
- 用户确认后的轮廓 = 高质量的标注数据
- 同时记录原始照片

目标: 积累200+张有polygon标注的白斑照片

辅助: 使用SAM自动标注 + 人工复核的半自动流水线
```python
# 半自动标注脚本
def semi_auto_annotation(image_path):
    from segment_anything import sam_model_registry, SamPredictor
    
    # 1. 加载SAM
    # 2. 用户在Web界面上点击白斑区域 → 记录为prompt points
    # 3. SAM生成mask
    # 4. 用户微调mask边界
    # 5. 保存为训练数据
```

**步骤2**: Fine-tune MedSAM

```python
# pseudocode - 在火山方舟上进行
# 或使用本地GPU (RTX 3060+ 即可)

from segment_anything import sam_model_registry
import torch

# 加载MedSAM权重
medsam = sam_model_registry["vit_b"](checkpoint="medsam_vit_b.pth")

# 使用LoRA进行参数高效微调
from peft import LoraConfig, get_peft_model

lora_config = LoraConfig(
    r=8,  # LoRA rank
    lora_alpha=16,
    target_modules=["qkv"],  # SAM的attention层
    lora_dropout=0.1,
)

model = get_peft_model(medsam.image_encoder, lora_config)

# 训练 (只需微调mask decoder和prompt encoder)
# 使用box prompt (用户画框) + dice loss + BCE loss
```

**步骤3**: 部署为火山方舟API端点

```
模型 → 导出为 TorchScript/ONNX → 上传到火山方舟模型仓库 → 创建API端点
```

**步骤4**: 集成到SubSkin

修改 `vasi.py::_call_vision_model()`:
```python
async def _call_segmentation_model(self, image_bytes: bytes) -> Optional[Dict]:
    """替换原来的VLM调用，调用fine-tune的MedSAM"""
    import numpy as np
    from PIL import Image
    import io
    
    # 1. 图像预处理
    img = Image.open(io.BytesIO(image_bytes))
    img_np = np.array(img)
    
    # 2. 调用分割模型API
    response = await self._call_volcengine_segmentation_endpoint(img_np)
    
    # 3. 获取mask
    mask = response["mask"]  # binary mask
    
    # 4. 后处理: 从mask计算面积
    white_patch_pixels = np.sum(mask)
    total_skin_pixels = self._estimate_skin_region(img_np)
    area_percentage = white_patch_pixels / total_skin_pixels * 100
    
    # 5. 轮廓提取 (从mask转polygon)
    contours = self._mask_to_contours(mask)
    
    # 6. VASI评分估算
    vasi_score = self._estimate_vasi_from_area(area_percentage, body_site)
    
    return {
        "vasi_score": vasi_score,
        "area_percentage": area_percentage,
        "contours": contours,
        "details": {...},
        "source": "medsam-finetuned",
    }
```

### 6.4 Phase 3: 完整方案 (终极目标)

在Phase 2基础上增加:

**参考卡系统**:
```
用户操作流程:
1. 从SubSkin网站下载/打印参考卡 (A4纸打印)
2. 将参考卡贴在白斑旁边的皮肤上
3. 拍照 (含参考卡 + 白斑)
4. 上传 → AI自动检测参考卡 → 计算比例尺
5. 精确分割白斑 → 像素面积 × 比例尺 → cm²
6. 结合身体部位 → BSA占比
```

**参考卡设计**:
- 2cm × 2cm 黑色方块 (用于比例尺)  
- 灰度阶梯 (用于白平衡校准)
- QR码 (包含用户ID，用于关联照片)
- 成本: 用户自己打印，几乎零成本

**多部位策略**:
- 鼓励用户拍摄多个部位
- 系统自动拼接各部位评估 → 整体BSA

---

## 7. 风险与挑战

### 7.1 技术风险

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| VLM面积估计不准 | 🔴 高 | 迁移到Phase 2 Fine-tune分割模型 |
| 缺乏标注数据 | 🔴 高 | 利用contour_diff数据积累 + 半自动标注 |
| 光照变化影响分割 | 🟡 中 | 参考色卡白平衡 + 数据增强 |
| 不同肤色泛化差 | 🟡 中 | 收集多肤色数据 + 色卡标准化 |
| 参考卡检测失败 | 🟡 中 | 多尺度检测 + fallback到无参考模式 |
| 推理延迟过高 | 🟢 低 | 异步处理 + 模型量化优化 |
| GPU成本控制 | 🟢 低 | 按需使用，批处理优化 |

### 7.2 医疗合规风险

| 风险 | 等级 | 建议 |
|------|------|------|
| NMPA医疗器械分类 | 🔴 高 | 明确标注"仅供参考，不作为诊断依据" |
| 数据隐私 | 🔴 高 | 照片仅存储在用户账户，符合现有隐私策略 |
| 误诊风险 | 🟡 中 | 所有评估结果加免责声明 + 建议就医 |

### 7.3 用户体验风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| 参考卡使用门槛 | 🟡 中 | 可选使用，无参考卡时用VLM粗略估计 |
| 拍照不规范 | 🟡 中 | 实时拍照引导+质量检测 |
| 结果不确定时的用户焦虑 | 🟢 低 | 提供置信度指标+建议就医 |

---

## 附录A: 推荐技术栈

```
┌─────────────────────────────────────────────┐
│                  前端 Vue 3                  │
│  TrackerPage.vue + VitiligoContour          │
│  + 拍照引导UI + 参考卡检测提示               │
└─────────────────┬───────────────────────────┘
                  │ HTTPS
┌─────────────────▼───────────────────────────┐
│              Nginx Reverse Proxy             │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│           FastAPI Backend (Python 3.9)       │
│  ┌───────────────────────────────────────┐  │
│  │  services/vasi.py                     │  │
│  │  services/vasi_segmentation.py  (新)  │  │
│  │  services/vasi_preprocess.py    (新)  │  │
│  └───────────────────────────────────────┘  │
│  ┌───────────────────────────────────────┐  │
│  │  utils/llm_config.py (复用)            │  │
│  └───────────────────────────────────────┘  │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
┌───────▼──────┐   ┌───────▼──────────┐
│ 火山方舟      │   │ 火山方舟模型托管  │
│ 豆包 Qwen VL │   │ Fine-tuned       │
│ (Phase 1)    │   │ MedSAM / U-Net   │
│              │   │ (Phase 2/3)      │
└──────────────┘   └──────────────────┘
```

## 附录B: 推荐优先级

```
立即开始 (Week 1-2):
├── Phase 1: VLM Prompt优化 + 图像预处理
├── 增加拍照质量检测
└── 设计参考卡原型

尽快开始 (Week 2-8):
├── Phase 2: 开始收集标注数据
├── 搭建半自动标注工具
├── Fine-tune MedSAM
└── 部署分割API端点

长期规划 (Week 8+):
├── Phase 3: 完整参考卡系统
├── 训练专用U-Net
├── 多部位协同评估
└── NMPA医疗器械认证评估
```
