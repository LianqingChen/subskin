# SubSkin nnU-Net 火山引擎部署终极方案

> 日期: 2026-04-27
> 目标: 将白斑面积AI评估从 VLM "拍脑袋估算" 升级为 nnU-Net "像素级精确分割"
> 涉及: 后端 vasi.py 改造、火山引擎ML Platform模型部署、前端适度增强
> 当前基线: VLM方案误差 ±20-50%，目标: nnU-Net + 参考物 ≤±8%

---

## 目录

1. [当前项目现状与改造清单](#1-当前项目现状与改造清单)
2. [火山引擎 nnU-Net 部署实施方案](#2-火山引擎-nnu-net-部署实施方案)
3. [自动化 vs 人工操作边界](#3-自动化-vs-人工操作边界)
4. [最终效果预估与用户配合度分析](#4-最终效果预估与用户配合度分析)
5. [费用及预算预估](#5-费用及预算预估)
6. [Agent 可直接推进的任务清单](#6-agent-可直接推进的任务清单)

---

## 1. 当前项目现状与改造清单

### 1.1 当前架构剖析

```
用户拍照 → TrackerPage.vue → POST /api/vasi/assess
                                  ↓
                            vasi.py::assess_vasi()
                                  ↓
                         _call_vasi_api() → _call_vision_model()
                                  ↓
                     DashScope qwen-vl-plus / 火山方舟 doubao-vision-pro
                                  ↓
                        VLM 返回 JSON (含估算contours)
                                  ↓
                         存储到 vasi_assessments 表
```

**现有优势（可直接复用）**:
- ✅ `vasi.py::_call_vision_model()` — 单一替换点，整体流程不变
- ✅ `VASIAssessment` 模型 — 字段完备（contour_diff、user_contours）
- ✅ `POST /assess/{id}/contour` — RLHF闭环已在运行
- ✅ `VitiligoContour.vue` — 完整的轮廓编辑UI
- ✅ `TrackerPage.vue` — 拍照上传、部位选择、结果展示
- ✅ `llm_config.py` — 多Provider配置体系，可扩展

**核心缺陷**:
- ❌ VLM 返回的 contour 坐标是"猜"的，不是像素级计算
- ❌ 没有图像预处理（白平衡、对比度增强）
- ❌ 没有照片质量检测（模糊、光照、皮肤占比）
- ❌ 没有参考物检测和比例尺校准
- ❌ 面积估算完全依赖VLM的"感觉"，无数学依据

### 1.2 改造清单

#### A. 后端改造（关键路径）

| 改造项 | 文件 | 改造内容 | 优先级 |
|--------|------|----------|--------|
| **A1. 新增分割服务** | `services/vasi_segmentation.py` (新建) | nnU-Net API调用封装、mask→轮廓转换、面积计算 | 🔴 P0 |
| **A2. 替换VLM调用** | `services/vasi.py::_call_vision_model()` | 改为调用火山引擎nnU-Net在线服务 | 🔴 P0 |
| **A3. 新增预处理服务** | `services/vasi_preprocess.py` (新建) | 白平衡、CLAHE对比度增强、缩放到1024px | 🟡 P1 |
| **A4. 新增质量检测** | `services/vasi_quality.py` (新建) | 模糊检测、皮肤占比检测、光照评估 | 🟡 P1 |
| **A5. 新增参考物检测** | `services/vasi_reference.py` (新建) | 硬币/参考卡检测、比例尺计算 | 🟢 P2 |
| **A6. 扩展配置** | `utils/llm_config.py` | 新增 `VOLC_ML_ENDPOINT`、`VOLC_ML_TOKEN` 环境变量 | 🔴 P0 |
| **A7. 数据库迁移** | `models/vasi.py` | 新增字段: confidence、preprocessed、has_reference、scale_factor | 🟡 P1 |
| **A8. API扩展** | `api/vasi.py` | 新增 `POST /check-photo-quality` 端点 | 🟡 P1 |
| **A9. API模型扩展** | `api/models.py` | 新增 quality_report、confidence 字段 | 🟡 P1 |

#### B. 前端改造

| 改造项 | 文件 | 改造内容 | 优先级 |
|--------|------|----------|--------|
| **B1. 拍照引导** | `components/tracker/PhotoGuideCard.vue` (新建) | 拍照技巧提示卡片（光线/距离/参考物） | 🟡 P1 |
| **B2. 质量反馈** | `TrackerPage.vue` | 上传后即时质量检测+改进建议 | 🟡 P1 |
| **B3. 信心度显示** | `TrackerPage.vue` | 评估结果显示AI信心度（高/中/低） | 🟢 P2 |
| **B4. 拍照指南页** | `views/PhotoGuidePage.vue` (新建) | 标准拍照示例+好/坏对比 | 🟢 P2 |
| **B5. 面积汇总** | `VitiligoContour.vue` | 多白斑区域面积汇总面板 | 🟢 P2 |

#### C. 部署与运维

| 改造项 | 内容 | 优先级 |
|--------|------|--------|
| **C1. nnU-Net训练** | 收集标注数据 → 训练 → 导出 | 🔴 P0 (人工) |
| **C2. 模型上传** | TOS 上传 → ML Platform 导入 | 🔴 P0 (人工) |
| **C3. 在线服务** | 创建GPU推理服务 → 获得API端点 | 🔴 P0 (人工) |
| **C4. 灰度切换** | 新旧方案A/B对比，逐步切换 | 🟡 P1 |
| **C5. 监控告警** | 推理延迟、错误率、GPU利用率 | 🟢 P2 |

---

## 2. 火山引擎 nnU-Net 部署实施方案

### 2.1 整体架构

```
┌─────────────────────────────────────────────────┐
│              用户手机 (PWA)                       │
│  拍照 → 选择部位 → 上传 → 查看结果 + 修正轮廓      │
└──────────────────┬──────────────────────────────┘
                   │ HTTPS
┌──────────────────▼──────────────────────────────┐
│           Nginx (subskin.cn)                     │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│       FastAPI Backend (Python 3.9)               │
│                                                  │
│  POST /api/vasi/assess                           │
│    → VASIService.assess_vasi()                   │
│      → vasi_preprocess.py (白平衡+CLAHE)          │
│      → vasi_quality.py (质量检测)                 │
│      → vasi_segmentation.py (调用nnU-Net API)     │
│      → 面积后处理 + 存入DB                        │
│                                                  │
│  POST /api/vasi/assess/{id}/contour              │
│    → 记录用户修正 → contour_diff → 训练数据积累    │
└──────────────────┬──────────────────────────────┘
                   │ HTTP POST (image bytes → mask+area)
┌──────────────────▼──────────────────────────────┐
│     火山引擎 ML Platform 在线服务                 │
│                                                  │
│  GPU T4 推理容器                                 │
│    ├── nnU-Net TorchScript模型                    │
│    ├── predict.py (预处理+推理+后处理)             │
│    └── REST API: /v1/predict                     │
│                                                  │
│  输入: JPEG image bytes                          │
│  输出: { mask, area_pixels, area_percentage,      │
│           confidence, scale_factor }             │
└─────────────────────────────────────────────────┘
```

### 2.2 nnU-Net 训练阶段

**步骤1: 数据准备**（人工主导，Agent辅助数据整理）

```bash
# 数据集组织结构
nnUNet_raw/
└── Dataset001_Vitiligo/
    ├── imagesTr/
    │   ├── vitiligo_001_0000.png   # 白斑照片
    │   ├── vitiligo_002_0000.png
    │   └── ...
    ├── labelsTr/
    │   ├── vitiligo_001.png         # 分割标注mask (0=背景, 1=白斑)
    │   ├── vitiligo_002.png
    │   └── ...
    └── dataset.json
```

**数据来源优先级**:
1. 从SubSkin现有 `vasi_assessments` 表中提取 `user_contours` 不为空的记录 → 生成mask
2. 利用SAM做半自动标注（人在Web UI上点几个点 → SAM生成mask → 人工修正）
3. 公开数据集（若有）

**步骤2: nnU-Net训练**（可在火山引擎GPU云服务器或本地GPU执行）

```bash
# 环境准备
pip install nnunetv2

export nnUNet_raw="/path/to/nnUNet_raw"
export nnUNet_preprocessed="/path/to/nnUNet_preprocessed"
export nnUNet_results="/path/to/nnUNet_results"

# 数据预处理
nnUNetv2_plan_and_preprocess -d 1 --verify_dataset_integrity

# 训练 2D U-Net (白斑分割适合2D)
nnUNetv2_train 1 2d 0
nnUNetv2_train 1 2d 1   # 多fold交叉验证
# ... fold 2,3,4

# 验证
nnUNetv2_find_best_configuration 1 -c 2d

# 导出为zip (含TorchScript模型)
nnUNetv2_export_model_to_zip -d 1 -c 2d -o nnunet_vitiligo.zip
```

**步骤3: 编写推理代码**（Agent可完成）

`predict.py` — 部署在ML Platform容器中的推理入口:

```python
import io
import json
import numpy as np
from PIL import Image
import torch
from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

# 全局初始化（容器启动时执行一次）
predictor = None

def init():
    """容器启动时调用"""
    global predictor
    predictor = nnUNetPredictor(
        tile_step_size=0.5,
        use_gaussian=True,
        use_mirroring=True,  # TTA提升精度
        perform_everything_on_gpu=True,
        device=torch.device('cuda'),
        verbose=False,
    )
    predictor.initialize_from_trained_model_folder(
        '/opt/ml/model/',  # ML Platform模型挂载路径
        use_folds=(0, 1, 2, 3, 4),  # 5-fold ensemble
    )

def preprocess(image_bytes: bytes) -> np.ndarray:
    """预处理：白平衡 + CLAHE + 缩放"""
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    # 等比缩放到适合推理的大小
    max_size = 1024
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
    return np.array(img)

def postprocess(masks: np.ndarray, original_shape: tuple) -> dict:
    """后处理：计算面积 + 提取轮廓"""
    mask = masks[0]  # 白斑通道
    white_pixels = int(np.sum(mask > 0.5))
    total_pixels = mask.size
    
    area_percentage = white_pixels / total_pixels * 100
    
    # 轮廓提取 (cv2.findContours)
    import cv2
    mask_uint8 = (mask > 0.5).astype(np.uint8) * 255
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 归一化坐标 + 简化
    normalized_contours = []
    h, w = mask.shape
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 100:  # 过滤噪点
            continue
        # 归一化
        cnt_norm = cnt.reshape(-1, 2).astype(float)
        cnt_norm[:, 0] /= w
        cnt_norm[:, 1] /= h
        # 简化到≤20个点
        epsilon = 0.005 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True).reshape(-1, 2).astype(float)
        approx[:, 0] /= w
        approx[:, 1] /= h
        normalized_contours.append({
            "polygon": approx.round(3).tolist(),
            "area_percent": round(cv2.contourArea(cnt) / total_pixels * 100, 2)
        })
    
    return {
        "mask": mask.tolist() if mask.size < 10000 else None,  # 大mask不传mask数据
        "area_pixels": white_pixels,
        "area_percentage": round(area_percentage, 2),
        "contours": normalized_contours,
        "confidence": round(min(area_percentage / 50, 1.0), 2),  # 简单信心度
        "patch_count": len(normalized_contours),
    }

def predict(image_bytes: bytes) -> dict:
    """推理函数 — ML Platform在线服务调用入口"""
    img_np = preprocess(image_bytes)
    
    # nnU-Net推理
    masks = predictor.predict_single_npy_array(
        img_np,
        None,  # properties
        None,  # previous mask
        None,  # image file
    )
    
    return postprocess(masks, img_np.shape[:2])

# ML Platform 会自动调用 predict() 函数
```

### 2.3 火山引擎部署步骤（人工操作）

```
步骤1: 开通服务
  ├── 登录 volcanoengine.com 控制台
  ├── 开通「机器学习平台」服务
  ├── 开通「对象存储 TOS」服务
  └── 申请 GPU T4 配额（华北region推荐）

步骤2: 上传模型
  ├── TOS 创建 bucket: subskin-models
  ├── 上传 nnunet_vitiligo.zip 到 TOS
  └── 上传 predict.py + requirements.txt 到 TOS

步骤3: 创建在线服务
  ├── ML Platform 控制台 → 在线服务 → 创建
  ├── 服务名称: nnunet-vitiligo-api
  ├── 模型文件: TOS路径
  ├── 推理代码: predict.py
  ├── 实例规格: ecs.gn6i-c4g1.xlarge (T4, 8C16G) × 1副本
  ├── 环境变量: CUDA_VISIBLE_DEVICES=0
  └── 启动服务

步骤4: 获取API信息
  ├── 端点URL: https://ml-xxxx.ml-platform.volces.com/v1/models/nnunet-vitiligo:predict
  ├── Access Token: ml-xxxxxxxxxxxx
  └── 测试连通性: curl -X POST -H "Authorization: Bearer $TOKEN" --data-binary @test.jpg $URL
```

### 2.4 SubSkin 后端打通方式

**新增环境变量** (`.env` 或 systemd 环境文件):

```bash
# 火山引擎 ML Platform 配置
VOLC_ML_ENDPOINT=https://ml-xxxx.ml-platform.volces.com/v1/models/nnunet-vitiligo:predict
VOLC_ML_TOKEN=ml-xxxxxxxxxxxx

# 现有配置不变 (VLM作为fallback)
VOLCENGINE_API_KEY=xxx
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

**后端代码打通** (关键改动):

```python
# services/vasi_segmentation.py (新建)
class nnUNetSegmentationService:
    """nnU-Net分割服务 — 调用火山引擎ML Platform在线推理"""
    
    def __init__(self):
        self.endpoint = os.getenv("VOLC_ML_ENDPOINT", "")
        self.token = os.getenv("VOLC_ML_TOKEN", "")
        self._available = bool(self.endpoint and self.token)
    
    async def segment(self, image_bytes: bytes) -> Optional[Dict]:
        """调用nnU-Net分割API"""
        if not self._available:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/octet-stream",
                    },
                    content=image_bytes,
                )
                resp.raise_for_status()
                result = resp.json()
                
                # 转换为现有格式
                return {
                    "vasi_score": self._estimate_vasi(result["area_percentage"], None),
                    "area_percentage": result["area_percentage"],
                    "contours": result.get("contours", []),
                    "confidence": result.get("confidence", 0.5),
                    "details": {
                        "patch_count": result.get("patch_count", 1),
                        "source": "nnunet-segmentation",
                    },
                    "raw_response": result,
                    "source": "nnunet-segmentation",
                }
        except Exception as e:
            logger.warning("nnU-Net segmentation failed: %s", e)
            return None

# vasi.py 中的修改
class VASIService:
    def __init__(self, db: Session):
        self.db = db
        self.segmentation_service = nnUNetSegmentationService()  # 新增
        self.quality_checker = VasiQualityChecker()              # 新增
        self.preprocessor = VasiImagePreprocessor()              # 新增
    
    async def _call_vasi_api(self, image_file: bytes) -> Dict[str, Any]:
        """调用推理服务（nnU-Net优先，VLM fallback）"""
        
        # Step 1: 质量检测
        quality = self.quality_checker.check_all(image_file)
        if quality.overall == "poor":
            return self._quality_reject_response(quality)
        
        # Step 2: 预处理
        try:
            processed = self.preprocessor.preprocess(image_file)
        except Exception:
            processed = image_file
        
        # Step 3: nnU-Net分割 (优先)
        result = await self.segmentation_service.segment(processed)
        if result:
            return result
        
        # Step 4: Fallback到VLM
        result = await self._call_vision_model(processed)
        if result:
            return result
        
        # Step 5: 最后fallback到mock
        return self._mock_result()
```

---

## 3. 自动化 vs 人工操作边界

### 3.1 Agent 可以自动完成的 ✅

| 任务 | 说明 |
|------|------|
| 编写 `vasi_segmentation.py` | nnU-Net API调用封装 |
| 编写 `vasi_preprocess.py` | 图像预处理（白平衡、CLAHE、缩放） |
| 编写 `vasi_quality.py` | 质量检测（模糊、皮肤占比、光照） |
| 修改 `vasi.py` | 集成新服务、修改调用流程 |
| 修改 `llm_config.py` | 新增ML Platform配置 |
| 修改 `models/vasi.py` | 数据库字段扩展 + migration |
| 修改 `api/vasi.py` | 新增 `/check-photo-quality` 端点 |
| 修改 `api/models.py` | 扩展 Response model |
| 编写 `predict.py` | nnU-Net推理容器代码 |
| 编写 Dockerfile | 推理容器镜像 |
| 编写 requirements.txt | 推理依赖 |
| 编写前端组件 | PhotoGuideCard、信心度显示、质量反馈 |
| 编写前端页面 | PhotoGuidePage (拍照指南) |
| 更新前端API层 | `api/vasi.ts` 新增方法 |
| 编写训练脚本 | nnU-Net数据预处理+训练+导出全流程脚本 |
| 编写半自动标注工具 | SAM辅助标注 Web 工具 |
| 编写A/B测试切换逻辑 | nnU-Net vs VLM 灰度切换 |

### 3.2 必须人工操作的 🔴

| 任务 | 为什么必须人工 |
|------|---------------|
| **火山引擎账号注册+实名认证** | 需要企业/个人信息 |
| **开通ML Platform + TOS服务** | 控制台操作，需要支付方式 |
| **GPU配额申请** | 需要提工单申请 |
| **标注数据集** (最关键!) | 需要皮肤科知识判断白斑边界 |
| **审核标注质量** | 需要医学背景 |
| **上传模型到TOS** | 需要Access Key |
| **创建在线推理服务** | 控制台操作，选择实例规格 |
| **配置API Token/密钥** | 安全凭证管理 |
| **生产环境部署** | systemd服务重启、nginx reload |
| **医疗合规审查** | 免责声明、用户协议 |
| **用户参考卡设计** (Phase 3) | 需要印刷规范 + 物理测试 |
| **NMPA认证评估** (如需要) | 法规事务 |

### 3.3 半自动（Agent辅助+人工确认）

| 任务 | Agent能做的 | 人工需要做的 |
|------|-----------|-------------|
| 数据收集 | 从DB提取已有标注、批量导出 | 审核数据质量、剔除不合格样本 |
| 半自动标注 | 搭建SAM标注Web工具、生成初始mask | 手动修正mask边界 |
| nnU-Net训练 | 编写训练脚本、配置参数 | 在GPU机器上执行、监控训练曲线 |
| 模型验证 | 计算Dice/IoU、生成报告 | 审核分割效果、判断是否达标 |
| 灰度切换 | 编写A/B路由逻辑 | 监控指标、决定切换时机 |

---

## 4. 最终效果预估与用户配合度分析

### 4.1 精度预估（基于学术论文数据）

| 方案 | 白斑识别 | 面积误差 | BSA占比误差 | 临床可用性 |
|------|---------|---------|------------|-----------|
| **当前VLM** | 70-80% | ±20-50% | 无法计算 | ❌ 仅参考 |
| **Phase 1 (VLM优化)** | 75-85% | ±15-25% | 无法计算 | ⚠️ 粗略参考 |
| **Phase 2 (nnU-Net, 无参考物)** | 90-95% (Dice~0.88) | ±10-15% | ±15% | ⚠️ 可参考 |
| **Phase 3 (nnU-Net + 参考卡)** | 93-97% (Dice~0.92) | ±5-8% | ±5-10% | ✅ 临床参考可用 |
| **金标准(医生VASI)** | — | ±5-10% | ±5-10% | ✅ 当前金标准 |

**精度瓶颈分析**:

```
照片 → [nnU-Net分割] → 像素mask → [比例尺] → 真实面积(cm²) → [部位映射] → BSA%
  ✅ 高精度        ❌ 缺少信息      ❌ 需要参考物      ❌ 需要全身体表映射
```

三个瓶颈中，**nnU-Net分割本身精度可以很高（Dice 0.92+）**，但：
- **瓶颈1**: 没有参考物 → 不知道1个像素等于多少毫米
- **瓶颈2**: 照片只拍了局部 → 不知道该部位占BSA的精确比例
- **瓶颈3**: 患者自拍角度、距离不一致

### 4.2 用户配合度分析 — 如何最大限度降低用户负担

#### 方案A: 无参考物模式（Phase 2，用户无需配合）

**原理**: 利用身体部位平均尺寸 + 图像中可见解剖标志估算比例尺

```
算法流程:
1. 检测身体部位 (面部/手部/上肢等)
2. 查找该部位统计学平均尺寸 (如成人面部高度约22cm)
3. 在图像中检测解剖学可见边界 (眼距、耳距等)
4. 计算: 像素/毫米比 = 图像中特征像素距离 / 统计学平均毫米距离
5. 白斑面积 = 白斑像素数 × (毫米/像素)²
```

**精度**: 误差 ±15-25%（比VLM好，但不够精确）
**用户负担**: 零（完全无感）
**实现难度**: 中（需要收集各部位尺寸统计数据 + 解剖特征点检测）

#### 方案B: 硬币/常见物品参考（Phase 2.5，用户轻微配合）

**原理**: 拍照时随手放一枚一元硬币(直径25mm)在皮肤旁

```
算法流程:
1. 用YOLO/颜色分割检测硬币
2. 已知硬币直径=25mm → 比例尺 pixels/mm
3. 白斑面积(cm²) = 白斑像素 / (硬币像素/25mm)²
```

**精度**: 误差 ±8-12%
**用户负担**: ⭐（拍照时放个硬币，99%的人做得到）
**实现难度**: 低（硬币是标准圆形+颜色特征明显）

#### 方案C: 专用参考卡（Phase 3，最佳精度）

**原理**: 用户打印专用参考卡（含2cm方块+灰度阶梯+QR码）

```
参考卡设计:
┌──────────────────┐
│ [QR Code]  □ 2cm │  ← 标准方块用于比例尺
│ [灰度阶梯 ░▒▓█]  │  ← 用于白平衡校正
│ [患者ID水印]     │  ← 关联照片
└──────────────────┘
```

**精度**: 误差 <±5%
**用户负担**: ⭐⭐（需要打印一次参考卡，之后反复使用）
**实现难度**: 中（参考卡设计 + 检测算法）

#### 推荐策略: 渐进式，无需用户选择

```
用户体验流程:
1. 拍照 → 系统自动检测是否有参考物
   ├── 检测到硬币 → 硬币校准模式 (误差±10%)
   ├── 检测到参考卡 → 参考卡校准模式 (误差±5%)
   └── 无参考物 → 部位比例估算模式 (误差±15%) + 提示"放个硬币更准哦~"

2. 无论哪种模式，用户操作完全相同：拍照 → 上传 → 看结果
```

### 4.3 最终效果总结

| 指标 | Phase 2 (nnU-Net上线) | Phase 3 (完整方案) |
|------|----------------------|-------------------|
| **白斑分割精度 (Dice)** | 0.88-0.92 | 0.92-0.95 |
| **面积误差** | ±10-15% (无参考物) | ±3-8% (有参考物) |
| **用户体验** | 无需配合 | 需打印参考卡(一次性) |
| **单次评估时间** | 2-4秒 | 2-4秒 |
| **支持多白斑区域** | ✅ | ✅ |
| **趋势追踪(同一用户)** | ⭐⭐⭐ (相对变化可追踪) | ⭐⭐⭐⭐⭐ (绝对精确) |
| **跨用户对比** | ⭐⭐ (缺少绝对尺度) | ⭐⭐⭐⭐ |

**核心结论**: nnU-Net上线后，即使不用参考物，**同一用户的趋势追踪（相对变化）已经相当可靠**——这对白友来说是最核心的需求（"我的白斑在变好还是变坏？"）

---

## 5. 费用及预算预估

### 5.1 一次性投入

| 项目 | 规格 | 费用 |
|------|------|------|
| nnU-Net训练GPU | A100 × 1, ~20小时 | ¥300-600 |
| 数据标注（如有外包） | 200-500张，外包标注 | ¥5,000-15,000 |
| 参考卡设计+测试 (Phase 3) | 设计稿+印刷测试 | ¥500-1,000 |
| **一次性合计** | | **¥800-16,600** |

### 5.2 月度运营费用

| 项目 | 规格 | 月费 |
|------|------|------|
| GPU T4 在线服务 × 1副本 | gn6i-c4g1.xlarge | ¥1,500-2,500 |
| TOS 对象存储 | 模型文件 ~2GB | ¥5-10 |
| 火山方舟 VLM (fallback) | doubao-vision-pro (低调用量) | ¥50-200 |
| 现有ECS服务器 | 已有 | ¥0 |
| **月度合计** | | **¥1,555-2,710** |

### 5.3 成本优化方案

| 策略 | 节省 | 说明 |
|------|------|------|
| **按量付费替代包月** | -30% | 低调用量时更便宜 |
| **使用竞价实例** | -60% | GPU随时可能被回收，适合非实时 |
| **模型量化(INT8)** | -40% | 可用T4替代A10 |
| **本地推理替代云端** | -80% | 如果服务器有GPU，省去在线服务费 |
| **冷启动+自动缩容** | -50% | 无请求时0副本，有请求时自动启动 |

### 5.4 推荐成本方案

```
Phase 2 (初期): 
  GPU T4 按量付费 ×1 (每天活跃6h) ≈ ¥400-600/月
  + 模型存储 ¥10/月
  ≈ ¥500/月

Phase 3 (成熟期):
  GPU T4 包月 ×1 ≈ ¥2,000/月
  + 或本地GPU推理 ≈ ¥0/月
```

---

## 6. Agent 可直接推进的任务清单

以下任务**无需用户参与**，Agent可以立即开始实现：

### Phase A: 后端基础设施（可立即开始）

| # | 任务 | 文件 | 工作量 | 状态 |
|---|------|------|--------|------|
| A1 | 新建 `vasi_preprocess.py` | 新建文件 | 2h | ⬜ |
| A2 | 新建 `vasi_quality.py` | 新建文件 | 2h | ⬜ |
| A3 | 新建 `vasi_segmentation.py` (框架) | 新建文件 | 1h | ⬜ |
| A4 | 修改 `vasi.py::_call_vasi_api()` 集成三个新服务 | 修改 | 2h | ⬜ |
| A5 | 修改 `llm_config.py` 新增 ML Platform 配置 | 修改 | 0.5h | ⬜ |
| A6 | 修改 `models/vasi.py` + 数据库 migration | 修改 | 1h | ⬜ |
| A7 | 修改 `api/vasi.py` 新增 `/check-photo-quality` | 修改 | 1h | ⬜ |
| A8 | 修改 `api/models.py` 扩展 Response | 修改 | 0.5h | ⬜ |
| A9 | 编写 nnU-Net `predict.py` (推理容器代码) | 新建 | 2h | ⬜ |
| A10 | 编写 Dockerfile + requirements.txt | 新建 | 1h | ⬜ |

### Phase B: 前端增强（可立即开始）

| # | 任务 | 文件 | 工作量 | 状态 |
|---|------|------|--------|------|
| B1 | 新建 `PhotoGuideCard.vue` 拍照技巧卡片 | 新建文件 | 2h | ⬜ |
| B2 | 修改 `TrackerPage.vue` 集成质量检测结果 | 修改 | 2h | ⬜ |
| B3 | 修改 `TrackerPage.vue` 信心度显示 | 修改 | 1h | ⬜ |
| B4 | 修改 `api/vasi.ts` 新增 `checkPhotoQuality()` | 修改 | 0.5h | ⬜ |
| B5 | 新建 `PhotoGuidePage.vue` 拍照指南页 | 新建文件 | 2h | ⬜ |
| B6 | 修改 `VitiligoContour.vue` 面积汇总面板 | 修改 | 2h | ⬜ |

### Phase C: ML辅助工具（可立即开始）

| # | 任务 | 文件 | 工作量 | 状态 |
|---|------|------|--------|------|
| C1 | 编写 nnU-Net 训练全流程脚本 | 新建 `scripts/train_nnunet.sh` | 2h | ⬜ |
| C2 | 编写数据导出脚本 (从DB提取标注) | 新建 `scripts/export_training_data.py` | 2h | ⬜ |
| C3 | 编写 nnU-Net 数据集转换脚本 | 新建 `scripts/convert_to_nnunet_format.py` | 1.5h | ⬜ |
| C4 | 编写半自动标注SAM工具 | 新建 `scripts/sam_semi_auto_label.py` | 3h | ⬜ |
| C5 | 编写模型验证报告脚本 | 新建 `scripts/evaluate_segmentation.py` | 1.5h | ⬜ |

---

### 建议推进顺序

```
第一优先级 (本周, Agent可独立完成):
  ├── A1-A3: 三个新服务文件 (vasi_preprocess/vasi_quality/vasi_segmentation)
  ├── A4: 集成到 vasi.py
  ├── A5-A8: 配置、模型、API扩展
  └── B4: API前端层

第二优先级 (下周, Agent可独立完成):
  ├── A9-A10: nnU-Net推理容器代码
  ├── B1-B5: 前端拍照引导+质量反馈
  ├── C1-C3: 训练脚本
  └── C5: 评估脚本

第三优先级 (需要人工配合, 并行推进):
  ├── 数据标注 (人工主导)
  ├── 火山引擎部署 (人工主导, Agent提供脚本)
  └── C4: 半自动标注工具
```

---

## 附录: 关键风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 标注数据不足(<200张) | 🔴 高 | 利用contour_diff积累 + SAM半自动 + 数据增强 |
| nnU-Net Dice <0.85 | 🟡 中 | 增加数据量; 回退到MedSAM方案 |
| 火山引擎GPU资源紧张 | 🟡 中 | 提前申请配额; 备选本地GPU推理 |
| 推理延迟>3s | 🟢 低 | INT8量化; 输入缩放到512px |
| 用户拍照不规范 | 🟡 中 | 实时引导+质量检测; 不接受低质量照片 |
| 医疗合规风险 | 🟡 中 | 显著免责声明; 标注"仅供参考" |
