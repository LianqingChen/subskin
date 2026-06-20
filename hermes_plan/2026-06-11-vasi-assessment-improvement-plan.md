# VASI 测评系统整体改进方案

> **调研日期**: 2026-06-11  
> **调研范围**: 前端页面、AI 管道、VASI 计算、移动端 UX  
> **核心问题**: AI 预填涂不准确、VASI 结果不准确、移动端体验差

---

## 一、现状分析

### 1.1 系统架构概览

```
┌─────────────────────────────────────────────────────────────┐
│  前端 (Vue 3 + TypeScript)                                   │
│  ├─ AssessmentWizard.vue (5 步向导编排)                       │
│  ├─ DigitalHuman.vue (SVG 人体图，22 个可点击区域)            │
│  ├─ BodyPartCamera.vue (拍照/上传，带身体部位遮罩)            │
│  ├─ MaskEditor.vue (双层画布：皮肤蓝 + 白斑粉，828 行)        │
│  └─ useVasiAssessment.ts (状态机，635 行)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓ API
┌─────────────────────────────────────────────────────────────┐
│  后端 (FastAPI + Python)                                     │
│  ├─ vasi.py (主编排器，VLM 调用，VASI 公式)                   │
│  ├─ vasi_quality.py (照片质量检查：模糊、皮肤、光照)          │
│  ├─ vasi_preprocess.py (预处理：白平衡、CLAHE、锐化)          │
│  ├─ vasi_segmentation.py (SAM vit_b 分割，自动 + VLM 引导)   │
│  ├─ vasi_skin_mask.py (颜色检测：HSV+YCrCb，相对 L* 阈值)    │
│  ├─ vasi_formula.py (VASI 计算：hand_units × depig × 10)     │
│  └─ vasi_promptable.py (点/框提示 SAM，用于用户修正)          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  AI 模型                                                     │
│  ├─ VLM: qwen-vl-max (通义千问视觉，用于分类 + 定位)          │
│  └─ SAM: vit_b (Segment Anything，用于像素级分割)             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 用户流程（当前 5 步）

```
[Step 1: 选部位] → [Step 2: 上传照片] → [Step 3: AI 分析] → [Step 4: 标注白斑] → [Step 5: 结果]
     ↓                    ↓                    ↓                    ↓                  ↓
DigitalHuman         BodyPartCamera       VLM + SAM          MaskEditor          分数 + 趋势
SVG 人体图           拍照/上传            10-70 秒           双层画布编辑         VASI 分数
22 个区域            质量检查              返回 contours      画笔 8-80px         严重程度
                                        + visual_features    缩放 0.05-8x        创建日记
```

### 1.3 核心问题诊断

#### 问题 1: AI 预填涂不准确

**根因分析：**

| 问题点 | 现状 | 影响 |
|--------|------|------|
| **VLM bbox 不稳定** | 同一图片多次运行得到不同 bbox | SAM 引导不一致，分割结果波动 |
| **置信度阈值过高 (0.85)** | 低置信度病灶被丢弃 | 漏检浅色/小面积白斑 |
| **VLM 引导失败时无 fallback** | 依赖 SAM 自动分割（网格点） | 小病灶、低对比度病灶漏检 |
| **颜色检测粗糙** | 相对 L* + 12，色度 ≤ 35 | 不同肤色、光照下阈值不适用 |
| **Post-SAM  bbox 填充检查激进** | SAM 填充 >60% VLM bbox → 面积 ×0.4 | 大面积白斑被低估 |
| **默认脱色级别 0.67** | VLM 失败时假设 level 2/3 | 系统性高估或低估 |

**代码证据：**
```python
# vasi.py line 592 - 置信度过滤
if lesion.get("confidence", 0) < 0.85:  # 过高阈值
    continue

# vasi.py lines 783-793 - Post-SAM 填充检查
if sam_fill_ratio > 0.6:
    area *= 0.4  # 激进降权
    confidence *= 0.3

# vasi.py line 96 - 默认脱色级别
depigmentation_level = 0.67  # 假设 level 2/3
```

#### 问题 2: VASI 计算结果不准确

**根因分析：**

| 问题点 | 现状 | 影响 |
|--------|------|------|
| **面积分母不一致** | `compute_two_layer_area()` 用 skin ∪ lesion，但其他路径用 total image | 同一图片不同计算路径结果不同 |
| **区域权重不匹配** | 前端 `left_hand=1.0` vs 后端 `hands=2.0` | 左右手未区分，权重错误 |
| **脱色级别加权粗糙** | `weighted_depig = Σ(area_i × level_i/3) / Σ(area_i)` | 未考虑病灶边界模糊性 |
| **无 VASI-24/VASI-50 支持** | 仅实现改良 VASI（hand-unit） | 无法与临床研究直接对比 |

**代码证据：**
```python
# vasi_formula.py lines 22-62 - 区域权重
BODY_SITE_BSA_PERCENT = {
    "face": 4.5, "neck": 1.0, "hands": 2.0,  # 未区分左右手
    "left_hand": 1.0, "right_hand": 1.0,  # 前端定义，后端未使用
}

# vasi_formula.py lines 117-165 - 面积计算
def compute_two_layer_area(skin_mask, lesion_mask):
    region_pixels = np.sum((skin_mask > 0) | (lesion_mask > 0))  # skin ∪ lesion
    area_percent = (lesion_pixels / region_pixels) * 100
```

#### 问题 3: 移动端体验差

**根因分析：**

| 问题点 | 现状 | 影响 |
|--------|------|------|
| **无双指缩放** | 提示"双指缩放 · 单指绘画"但无实现 | 用户无法精细编辑 |
| **触控目标过小** | SVG 控制点 r=5 (10px 直径)，远低于 44px 标准 | 误触、操作困难 |
| **画笔滑块太窄** | 移动端 w-14 (56px)，桌面端 w-20 (80px) | 难以精确控制画笔大小 |
| **无两指平移** | 平移需要 metaKey/ctrlKey（移动端不存在） | 无法在放大状态下移动画布 |
| **步骤标签隐藏** | 移动端 `hidden sm:inline`，仅显示图标 | 用户不清楚当前步骤 |
| **工具栏拥挤** | 4+ 操作按钮挤在一行，无移动端优化 | 误触频繁 |
| **AssessmentWizard 过于复杂** | 单文件 670 行处理所有 5 步，无移动端变体 | 移动端信息过载 |

**代码证据：**
```vue
<!-- MaskEditor.vue line 733-738 - 虚假提示 -->
<span class="md:hidden">双指缩放 · 单指绘画</span>
<!-- 实际无双指缩放实现 -->

<!-- MaskEditor.vue line 783 - 滑块太窄 -->
<input type="range" class="w-14 md:w-20" />

<!-- VitiligoContour.vue line 323 - 控制点太小 -->
<r="selected ? 8 : 5" />  <!-- 10px 直径，远低于 44px -->
```

---

## 二、整体改进方案

### 2.1 设计原则

1. **移动端优先 (Mobile-First)**: 所有交互先为手机设计，再扩展到桌面
2. **AI 辅助而非替代**: 用户圈选区域，AI 基于真实色彩变化精修，而非纯依赖用户手指填涂
3. **渐进式复杂度**: 简单模式（快速评估）→ 高级模式（精细编辑），不强制用户学习复杂操作
4. **一致性**: 前后端区域权重、面积计算分母必须统一
5. **可解释性**: AI 结果附带置信度和解释，用户知道何时该信任、何时该修正

### 2.2 改进路线图（3 阶段）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  阶段 1: 快速修复 (1-2 周) - 解决最严重的准确性和 UX 问题                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✓ 降低 VLM 置信度阈值 (0.85 → 0.7)                                         │
│  ✓ 统一前后端区域权重 (left_hand/right_hand)                                 │
│  ✓ 实现真正的双指缩放 + 两指平移 (MaskEditor)                                │
│  ✓ 增大触控目标 (控制点 r=5 → r=22，44px 直径)                               │
│  ✓ 简化移动端工具栏 (隐藏次要操作，使用底部抽屉)                              │
│  ✓ 添加步骤指示文本 (移动端显示"步骤 2/5: 上传照片")                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  阶段 2: AI 准确性提升 (2-4 周) - 引入"圈选 + AI 精修"模式                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✓ 实现"圈选引导"模式: 用户画粗略圈 → AI 基于色彩变化精修边界                 │
│  ✓ 启用 VLM 集成模式 (ensemble)，减少 bbox 波动                              │
│  ✓ 改进颜色检测: 自适应阈值 (根据 Fitzpatrick 肤色类型)                       │
│  ✓ 添加"置信度可视化": 低置信度区域用半透明红色覆盖，提示用户检查              │
│  ✓ 优化 Post-SAM 填充检查: 根据病灶类型调整阈值 (60% → 80% for 大面积)        │
│  ✓ 添加 VASI-24/VASI-50 变体支持 (可选)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  阶段 3: 移动端体验重构 (4-6 周) - 全面简化移动端流程                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✓ 拆分 AssessmentWizard: 每步独立组件，移动端使用全屏沉浸式布局              │
│  ✓ 引入"快速评估"模式: 跳过手动标注，直接使用 AI 结果 (置信度 > 0.8 时)        │
│  ✓ 重新设计 MaskEditor: 单画布 + 颜色选择器，替代双层互斥系统                 │
│  ✓ 添加手势教程: 首次使用时 30 秒交互式教程 (双指缩放、两指平移、圈选)         │
│  ✓ 优化拍照引导: 实时检测光照、模糊、距离，给出具体调整建议                   │
│  ✓ 添加"历史记录对比": 滑动对比前后评估结果，直观看到变化                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、阶段 1 详细方案（快速修复）

### 3.1 AI 准确性快速修复

#### 修复 1: 降低 VLM 置信度阈值

**文件**: `web/backend/services/vasi.py` line 592

**当前代码**:
```python
if lesion.get("confidence", 0) < 0.85:
    continue  # 丢弃低置信度病灶
```

**修改为**:
```python
# 分级处理：高置信度直接使用，低置信度标记为"需验证"
confidence = lesion.get("confidence", 0)
if confidence < 0.7:
    continue  # 仅丢弃极低置信度
elif confidence < 0.85:
    lesion["needs_verification"] = True  # 标记为需用户验证
```

**前端配合**: 在 MaskEditor 中，对 `needs_verification=True` 的病灶用虚线轮廓 + 半透明红色填充，提示用户"AI 不太确定，请检查此区域"。

#### 修复 2: 统一前后端区域权重

**文件**: 
- `web/backend/services/vasi_formula.py` lines 22-62
- `web/app/src/constants/bodySites.ts` lines 32-47

**当前问题**: 后端 `hands=2.0` 未区分左右手，前端定义了 `left_hand=1.0, right_hand=1.0` 但后端未使用。

**修改**:
```python
# vasi_formula.py - 统一使用前端定义
BODY_SITE_BSA_PERCENT = {
    "face": 4.5, "neck": 1.0,
    "left_arm": 4.5, "right_arm": 4.5,
    "left_hand": 1.0, "right_hand": 1.0,  # 区分左右手
    "left_leg": 9.0, "right_leg": 9.0,
    "left_foot": 1.75, "right_foot": 1.75,
    "chest": 4.5, "abdomen": 4.5,
    "upper_back": 4.5, "lower_back": 4.5,
}
```

**前端无需修改**（已正确定义）。

#### 修复 3: 优化 Post-SAM 填充检查

**文件**: `web/backend/services/vasi.py` lines 783-793

**当前代码**:
```python
if sam_fill_ratio > 0.6:
    area *= 0.4
    confidence *= 0.3
```

**修改为**:
```python
# 根据病灶大小调整阈值：大面积病灶允许更高填充率
if estimated_size_percent > 10:  # 大面积病灶
    threshold = 0.8
    penalty = 0.6
elif estimated_size_percent > 5:  # 中等病灶
    threshold = 0.7
    penalty = 0.5
else:  # 小病灶
    threshold = 0.6
    penalty = 0.4

if sam_fill_ratio > threshold:
    area *= penalty
    confidence *= 0.3
```

### 3.2 移动端 UX 快速修复

#### 修复 4: 实现真正的双指缩放 + 两指平移

**文件**: `web/app/src/components/tracker/MaskEditor.vue`

**当前问题**: 提示"双指缩放"但无实现，仅支持滚轮缩放。

**修改**: 添加 Pointer Events 多指手势处理

```typescript
// 新增手势状态
const pointers = ref<Map<number, { x: number; y: number }>>(new Map())
const initialPinchDistance = ref<number | null>(null)
const initialZoom = ref(1)

function onPointerDown(e: PointerEvent) {
  pointers.value.set(e.pointerId, { x: e.clientX, y: e.clientY })
  
  if (pointers.value.size === 2) {
    // 双指开始：记录初始距离和缩放
    const [p1, p2] = Array.from(pointers.value.values())
    initialPinchDistance.value = Math.hypot(p2.x - p1.x, p2.y - p1.y)
    initialZoom.value = zoom.value
    isPanning.value = false  // 双指模式下禁止绘画
  }
}

function onPointerMove(e: PointerEvent) {
  if (!pointers.value.has(e.pointerId)) return
  pointers.value.set(e.pointerId, { x: e.clientX, y: e.clientY })
  
  if (pointers.value.size === 2 && initialPinchDistance.value) {
    // 双指移动：缩放 + 平移
    const [p1, p2] = Array.from(pointers.value.values())
    const currentDistance = Math.hypot(p2.x - p1.x, p2.y - p1.y)
    const scale = currentDistance / initialPinchDistance.value
    zoom.value = Math.max(0.05, Math.min(8, initialZoom.value * scale))
    
    // 平移：双指中心点移动
    const centerX = (p1.x + p2.x) / 2
    const centerY = (p1.y + p2.y) / 2
    // ... 更新 panOffset
  } else if (pointers.value.size === 1) {
    // 单指：绘画（现有逻辑）
  }
}

function onPointerUp(e: PointerEvent) {
  pointers.value.delete(e.pointerId)
  if (pointers.value.size < 2) {
    initialPinchDistance.value = null
  }
}
```

**模板修改**:
```vue
<div
  @pointerdown="onPointerDown"
  @pointermove="onPointerMove"
  @pointerup="onPointerUp"
  @pointercancel="onPointerUp"
  style="touch-action: none"
>
  <!-- 画布内容 -->
</div>
```

#### 修复 5: 增大触控目标

**文件**: `web/app/src/components/tracker/VitiligoContour.vue` line 323

**当前代码**:
```vue
<r="selected ? 8 : 5" />
```

**修改为**:
```vue
<r="selected ? 22 : 18" />  <!-- 44px / 36px 直径，符合触控标准 -->
```

**文件**: `web/app/src/components/tracker/MaskEditor.vue` line 783

**当前代码**:
```vue
<input type="range" class="w-14 md:w-20" />
```

**修改为**:
```vue
<input type="range" class="w-20 md:w-24" />  <!-- 移动端加宽 -->
```

#### 修复 6: 简化移动端工具栏

**文件**: `web/app/src/components/tracker/MaskEditor.vue` lines 759-800

**当前问题**: 4+ 按钮挤在一行，移动端误触。

**修改**: 使用底部抽屉，仅显示主要操作

```vue
<!-- 移动端：底部抽屉，仅 3 个主要按钮 -->
<div class="md:hidden fixed bottom-0 left-0 right-0 bg-white/95 border-t pb-[env(safe-area-inset-bottom)]">
  <div class="flex justify-around py-3">
    <button @click="toggleBrush">
      <i class="ri-brush-line text-2xl"></i>
      <span class="text-xs">画笔</span>
    </button>
    <button @click="toggleEraser">
      <i class="ri-eraser-line text-2xl"></i>
      <span class="text-xs">橡皮</span>
    </button>
    <button @click="showMoreTools = true">
      <i class="ri-more-2-line text-2xl"></i>
      <span class="text-xs">更多</span>
    </button>
  </div>
</div>

<!-- 更多工具抽屉 -->
<van-popup v-model:show="showMoreTools" position="bottom" round>
  <div class="p-4 grid grid-cols-4 gap-4">
    <button @click="undo">撤销</button>
    <button @click="redo">重做</button>
    <button @click="clearAll">清空</button>
    <button @click="zoomToFit">适应窗口</button>
    <!-- 画笔大小、透明度滑块 -->
  </div>
</van-popup>

<!-- 桌面端：保持现有工具栏 -->
<div class="hidden md:block absolute bottom-0 ...">
  <!-- 现有工具栏 -->
</div>
```

#### 修复 7: 添加步骤指示文本

**文件**: `web/app/src/components/tracker/AssessmentWizard.vue` lines 252-263

**当前代码**:
```vue
<span class="hidden sm:inline">{{ step.label }}</span>
```

**修改为**:
```vue
<!-- 移动端：显示简化步骤文本 -->
<div class="text-center text-sm text-gray-600 mb-2">
  步骤 {{ currentStep + 1 }}/5: {{ step.label }}
</div>
<!-- 桌面端：保持现有进度条 -->
<div class="hidden sm:flex ...">
  <!-- 现有步骤条 -->
</div>
```

---

## 四、阶段 2 详细方案（AI 准确性提升）

### 4.1 "圈选 + AI 精修"模式

**核心理念**: 用户画粗略圈（不需要精确），AI 基于图片真实色彩变化精修边界。

#### 前端实现

**新增组件**: `CircleSelectTool.vue`

```vue
<template>
  <div class="circle-select-tool">
    <canvas
      @pointerdown="startCircle"
      @pointermove="updateCircle"
      @pointerup="finishCircle"
    />
    
    <!-- 用户画的粗略圈（红色虚线） -->
    <svg v-if="userCircle">
      <ellipse
        :cx="userCircle.cx"
        :cy="userCircle.cy"
        :rx="userCircle.rx"
        :ry="userCircle.ry"
        fill="none"
        stroke="red"
        stroke-dasharray="5,5"
        stroke-width="2"
      />
    </svg>
    
    <!-- AI 精修后的边界（粉色实线） -->
    <svg v-if="aiRefinedPolygon">
      <polygon
        :points="aiRefinedPolygon"
        fill="rgba(244, 114, 182, 0.3)"
        stroke="#F472B6"
        stroke-width="2"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
const userCircle = ref<{ cx: number; cy: number; rx: number; ry: number } | null>(null)
const aiRefinedPolygon = ref<number[][] | null>(null)

async function startCircle(e: PointerEvent) {
  // 记录起点
}

async function updateCircle(e: PointerEvent) {
  // 实时更新椭圆
}

async function finishCircle(e: PointerEvent) {
  // 1. 将用户圈选区域发送到后端
  const response = await api.post('/vasi/promptable/refine-circle', {
    image_id: assessmentId,
    circle: {
      center: [userCircle.value.cx, userCircle.value.cy],
      radius_x: userCircle.value.rx,
      radius_y: userCircle.value.ry,
    },
  })
  
  // 2. 接收 AI 精修后的多边形边界
  aiRefinedPolygon.value = response.data.polygon
  
  // 3. 显示置信度热力图（可选）
  if (response.data.confidence_map) {
    showConfidenceHeatmap(response.data.confidence_map)
  }
}
</script>
```

#### 后端实现

**新增 API**: `POST /api/vasi/promptable/refine-circle`

**文件**: `web/backend/services/vasi_promptable.py`

```python
@router.post("/refine-circle")
async def refine_circle(
    image_id: int,
    circle: CirclePrompt,
    db: Session = Depends(get_db),
):
    """
    用户画粗略圈，AI 基于色彩变化精修边界。
    
    算法:
    1. 将用户圆圈转换为 SAM box prompt
    2. SAM 生成初始 mask
    3. 在 mask 范围内，分析色彩分布：
       - 计算正常皮肤的颜色中心（HSV 空间）
       - 检测与皮肤颜色差异 > 阈值的像素（白斑候选）
       - 使用边缘检测（Canny）精修边界
    4. 返回精修后的多边形 + 置信度
    """
    assessment = db.query(VASIAssessment).filter_by(id=image_id).first()
    image = load_image(assessment.image_path)
    
    # 1. SAM 初始分割（使用 box prompt）
    box = circle_to_box(circle)
    sam_mask = sam_predict(image, box=box)
    
    # 2. 色彩分析精修
    skin_color_center = compute_skin_color(image, sam_mask)
    vitiligo_candidates = detect_color_deviation(image, sam_mask, skin_color_center)
    
    # 3. 边缘检测
    edges = cv2.Canny(image, 50, 150)
    refined_polygon = snap_to_edges(vitiligo_candidates, edges)
    
    # 4. 计算置信度（基于色彩对比度）
    confidence = compute_confidence(image, refined_polygon, skin_color_center)
    
    return {
        "polygon": refined_polygon,  # [[x1,y1], [x2,y2], ...]
        "confidence": confidence,
        "area_percent": compute_area_percent(refined_polygon),
    }
```

**色彩分析核心算法**:

```python
def detect_color_deviation(image, mask, skin_color_center, threshold=30):
    """
    在 mask 范围内，检测与皮肤颜色差异 > 阈值的像素。
    
    Args:
        image: BGR 图像
        mask: SAM 生成的初始 mask
        skin_color_center: 正常皮肤的 HSV 中心值
        threshold: 颜色差异阈值（HSV 空间欧氏距离）
    
    Returns:
        vitiligo_mask: 白斑候选区域
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 在 mask 范围内采样皮肤颜色
    skin_pixels = hsv[mask > 0]
    
    # 计算每个像素与皮肤中心的距离
    distances = np.sqrt(np.sum((skin_pixels - skin_color_center) ** 2, axis=1))
    
    # 距离 > 阈值的像素为白斑候选
    vitiligo_mask = np.zeros_like(mask)
    vitiligo_mask[mask > 0] = distances > threshold
    
    # 形态学操作：去除噪点、填充空洞
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    vitiligo_mask = cv2.morphologyEx(vitiligo_mask, cv2.MORPH_OPEN, kernel)
    vitiligo_mask = cv2.morphologyEx(vitiligo_mask, cv2.MORPH_CLOSE, kernel)
    
    return vitiligo_mask
```

#### 用户流程（新）

```
[Step 1: 选部位] → [Step 2: 上传照片] → [Step 3: AI 分析] → [Step 4: 圈选 + AI 精修] → [Step 5: 结果]
     ↓                    ↓                    ↓                         ↓                      ↓
DigitalHuman         BodyPartCamera       VLM + SAM              用户画粗略圈              分数 + 趋势
                     质量检查               返回 contours         AI 精修边界               置信度可视化
                                                                (椭圆 → 多边形)           创建日记
```

**关键改进**:
- 用户不需要精确填涂，只需画一个大致的圈
- AI 基于图片真实色彩变化精修边界
- 低置信度区域用红色半透明覆盖，提示用户检查
- 用户可以多点几个圈，AI 合并处理

### 4.2 启用 VLM 集成模式

**文件**: `web/backend/services/vasi.py`

**当前代码**:
```python
ENABLE_VLM_ENSEMBLE = False  # line 45
```

**修改为**:
```python
ENABLE_VLM_ENSEMBLE = True  # 启用集成模式，减少 bbox 波动
```

**效果**: VLM 运行两次，取交集，减少随机性。代价：API 调用时间 ×2（约 20 秒 → 40 秒）。

**优化**: 仅在 `precision='precise'` 模式下启用，`quick` 模式保持单次调用。

### 4.3 自适应颜色检测阈值

**文件**: `web/backend/services/vasi_skin_mask.py`

**当前问题**: 固定阈值 `L* ≥ skin_median_L + 12 AND chroma ≤ 35` 不适用于所有肤色。

**修改**: 根据 Fitzpatrick 肤色类型调整阈值

```python
# 根据 VLM 返回的 Fitzpatrick 类型调整阈值
FITZPATRICK_THRESHOLDS = {
    "I": {"L_delta": 10, "chroma_max": 30},  # 浅肤色，白斑对比度高
    "II": {"L_delta": 11, "chroma_max": 32},
    "III": {"L_delta": 12, "chroma_max": 35},  # 中等肤色
    "IV": {"L_delta": 14, "chroma_max": 38},  # 深肤色，白斑对比度低
    "V": {"L_delta": 16, "chroma_max": 40},
    "VI": {"L_delta": 18, "chroma_max": 42},  # 极深肤色
}

def detect_vitiligo(image, skin_mask, fitzpatrick_type="III"):
    thresholds = FITZPATRICK_THRESHOLDS.get(fitzpatrick_type, FITZPATRICK_THRESHOLDS["III"])
    
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0]
    
    skin_L_median = np.median(L[skin_mask > 0])
    L_threshold = skin_L_median + thresholds["L_delta"]
    
    # 色度检测
    a = lab[:, :, 1]
    b = lab[:, :, 2]
    chroma = np.sqrt(a**2 + b**2)
    
    vitiligo_mask = (L >= L_threshold) & (chroma <= thresholds["chroma_max"])
    
    return vitiligo_mask
```

### 4.4 置信度可视化

**前端**: 在 MaskEditor 中，对低置信度区域用半透明红色覆盖

```vue
<!-- 置信度热力图覆盖层 -->
<canvas
  v-if="confidenceMap"
  ref="confidenceCanvas"
  class="absolute inset-0 pointer-events-none"
/>

<script setup lang="ts">
function drawConfidenceHeatmap(confidenceMap: number[][]) {
  const ctx = confidenceCanvas.value.getContext('2d')
  
  for (let y = 0; y < confidenceMap.length; y++) {
    for (let x = 0; x < confidenceMap[y].length; x++) {
      const confidence = confidenceMap[y][x]
      
      if (confidence < 0.5) {
        // 低置信度：红色半透明
        ctx.fillStyle = `rgba(239, 68, 68, ${0.5 - confidence})`
        ctx.fillRect(x, y, 1, 1)
      }
    }
  }
}
</script>
```

---

## 五、阶段 3 详细方案（移动端体验重构）

### 5.1 拆分 AssessmentWizard

**当前问题**: 单文件 670 行处理所有 5 步，移动端信息过载。

**重构方案**: 每步独立组件，移动端使用全屏沉浸式布局

```
components/tracker/
├─ AssessmentWizard.vue (编排器，仅负责步骤切换)
├─ steps/
│  ├─ Step1SelectPart.vue (选部位)
│  ├─ Step2UploadPhoto.vue (上传照片)
│  ├─ Step3AIAnalysis.vue (AI 分析)
│  ├─ Step4MarkLesions.vue (标注白斑)
│  └─ Step5Results.vue (结果)
└─ mobile/
   ├─ MobileStepIndicator.vue (移动端步骤指示器)
   └─ MobileToolbar.vue (移动端工具栏)
```

**移动端布局**: 每步占满全屏，无多余信息

```vue
<!-- MobileStepIndicator.vue -->
<template>
  <div class="fixed top-0 left-0 right-0 bg-white/90 backdrop-blur z-50">
    <div class="flex items-center justify-between px-4 py-3">
      <button @click="goBack">
        <i class="ri-arrow-left-line text-2xl"></i>
      </button>
      <div class="text-center">
        <div class="text-sm font-medium">步骤 {{ currentStep + 1 }}/5</div>
        <div class="text-xs text-gray-500">{{ stepLabels[currentStep] }}</div>
      </div>
      <button @click="skipStep" v-if="canSkip">
        跳过
      </button>
    </div>
    
    <!-- 进度条 -->
    <div class="h-1 bg-gray-200">
      <div
        class="h-full bg-primary-500 transition-all"
        :style="{ width: `${((currentStep + 1) / 5) * 100}%` }"
      />
    </div>
  </div>
</template>
```

### 5.2 "快速评估"模式

**理念**: 当 AI 置信度 > 0.8 时，跳过手动标注，直接使用 AI 结果。

**前端实现**:

```typescript
// useVasiAssessment.ts
async function submitAssessment() {
  const result = await api.post('/vasi/assess', formData)
  
  if (result.confidence > 0.8) {
    // 高置信度：直接显示结果，提供"精细编辑"选项
    showQuickResult(result)
  } else {
    // 低置信度：进入手动标注步骤
    goToStep(3) // Step 4: 标注白斑
  }
}
```

**UI**:

```vue
<!-- 快速结果页 -->
<div v-if="quickResult" class="fullscreen">
  <div class="text-center py-8">
    <div class="text-6xl font-bold text-primary-500">
      {{ quickResult.vasi_score.toFixed(1) }}
    </div>
    <div class="text-gray-500 mt-2">{{ severityLevel }}</div>
  </div>
  
  <!-- AI 结果预览 -->
  <div class="relative mx-4 rounded-xl overflow-hidden">
    <img :src="quickResult.image_url" />
    <svg class="absolute inset-0">
      <polygon
        v-for="contour in quickResult.contours"
        :points="contour.polygon"
        fill="rgba(244, 114, 182, 0.3)"
        stroke="#F472B6"
      />
    </svg>
  </div>
  
  <!-- 操作按钮 -->
  <div class="flex gap-4 px-4 py-6">
    <button @click="editManually" class="flex-1 btn-ghost">
      <i class="ri-edit-line"></i>
      精细编辑
    </button>
    <button @click="acceptResult" class="flex-1 btn-primary">
      <i class="ri-check-line"></i>
      接受结果
    </button>
  </div>
  
  <div class="text-center text-xs text-gray-400">
    AI 置信度: {{ (quickResult.confidence * 100).toFixed(0) }}%
  </div>
</div>
```

### 5.3 重新设计 MaskEditor

**当前问题**: 双层画布（皮肤蓝 + 白斑粉）互斥系统复杂，用户困惑。

**新设计**: 单画布 + 颜色选择器

```vue
<template>
  <div class="mask-editor-v2">
    <!-- 单画布 -->
    <canvas
      ref="canvas"
      @pointerdown="startPaint"
      @pointermove="paint"
      @pointerup="endPaint"
    />
    
    <!-- 颜色选择器（底部） -->
    <div class="fixed bottom-20 left-0 right-0 flex justify-center gap-4">
      <button
        @click="setColor('skin')"
        :class="{ active: currentColor === 'skin' }"
        class="w-12 h-12 rounded-full"
        style="background: #60A5FA"
      >
        <i class="ri-hand-heart-line text-white text-2xl"></i>
      </button>
      <button
        @click="setColor('lesion')"
        :class="{ active: currentColor === 'lesion' }"
        class="w-12 h-12 rounded-full"
        style="background: #F472B6"
      >
        <i class="ri-virus-line text-white text-2xl"></i>
      </button>
      <button
        @click="setColor('eraser')"
        :class="{ active: currentColor === 'eraser' }"
        class="w-12 h-12 rounded-full bg-gray-200"
      >
        <i class="ri-eraser-line text-2xl"></i>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
const currentColor = ref<'skin' | 'lesion' | 'eraser'>('lesion')

function paint(e: PointerEvent) {
  const ctx = canvas.value.getContext('2d')
  
  if (currentColor.value === 'eraser') {
    ctx.globalCompositeOperation = 'destination-out'
  } else {
    ctx.globalCompositeOperation = 'source-over'
    ctx.fillStyle = currentColor.value === 'skin' ? '#60A5FA' : '#F472B6'
  }
  
  ctx.beginPath()
  ctx.arc(e.offsetX, e.offsetY, brushSize.value, 0, Math.PI * 2)
  ctx.fill()
}
</script>
```

**优势**:
- 单一画布，概念简单
- 颜色选择器直观（皮肤蓝、白斑粉、橡皮擦）
- 无需理解"互斥"逻辑

### 5.4 手势教程

**首次使用时显示 30 秒交互式教程**

```vue
<template>
  <div v-if="showTutorial" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
    <div class="bg-white rounded-2xl p-6 max-w-sm mx-4">
      <h3 class="text-lg font-bold mb-4">如何编辑白斑区域</h3>
      
      <!-- 步骤 1: 双指缩放 -->
      <div v-if="tutorialStep === 0" class="text-center">
        <div class="text-6xl mb-4">🤏</div>
        <p class="text-gray-600">双指捏合缩放画布</p>
        <button @click="nextTutorialStep" class="btn-primary mt-4">
          我知道了
        </button>
      </div>
      
      <!-- 步骤 2: 两指平移 -->
      <div v-if="tutorialStep === 1" class="text-center">
        <div class="text-6xl mb-4">🖐️</div>
        <p class="text-gray-600">两指按住拖动平移画布</p>
        <button @click="nextTutorialStep" class="btn-primary mt-4">
          我知道了
        </button>
      </div>
      
      <!-- 步骤 3: 圈选白斑 -->
      <div v-if="tutorialStep === 2" class="text-center">
        <div class="text-6xl mb-4">⭕</div>
        <p class="text-gray-600">单指画圈选择白斑区域，AI 会自动精修边界</p>
        <button @click="finishTutorial" class="btn-primary mt-4">
          开始使用
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const showTutorial = ref(!localStorage.getItem('vasi_tutorial_completed'))
const tutorialStep = ref(0)

function nextTutorialStep() {
  tutorialStep.value++
}

function finishTutorial() {
  showTutorial.value = false
  localStorage.setItem('vasi_tutorial_completed', 'true')
}
</script>
```

---

## 六、实施优先级与时间估算

### 阶段 1: 快速修复 (1-2 周)

| 任务 | 优先级 | 估时 | 影响 |
|------|--------|------|------|
| 降低 VLM 置信度阈值 | P0 | 2h | 减少漏检 |
| 统一前后端区域权重 | P0 | 4h | 修复计算错误 |
| 实现双指缩放 + 两指平移 | P0 | 8h | 移动端基础交互 |
| 增大触控目标 | P1 | 2h | 减少误触 |
| 简化移动端工具栏 | P1 | 6h | 提升操作效率 |
| 添加步骤指示文本 | P2 | 2h | 提升可理解性 |

**总计**: ~24h (3 人天)

### 阶段 2: AI 准确性提升 (2-4 周)

| 任务 | 优先级 | 估时 | 影响 |
|------|--------|------|------|
| "圈选 + AI 精修"模式 | P0 | 40h | 核心体验改进 |
| 启用 VLM 集成模式 | P1 | 4h | 减少 bbox 波动 |
| 自适应颜色检测阈值 | P1 | 16h | 提升多肤色准确性 |
| 置信度可视化 | P2 | 12h | 提升可解释性 |
| 优化 Post-SAM 填充检查 | P1 | 8h | 减少大面积病灶低估 |
| VASI-24/VASI-50 支持 | P3 | 20h | 临床研究对接 |

**总计**: ~100h (12.5 人天)

### 阶段 3: 移动端体验重构 (4-6 周)

| 任务 | 优先级 | 估时 | 影响 |
|------|--------|------|------|
| 拆分 AssessmentWizard | P1 | 24h | 代码可维护性 |
| "快速评估"模式 | P0 | 20h | 提升效率 |
| 重新设计 MaskEditor | P0 | 32h | 核心体验改进 |
| 手势教程 | P2 | 8h | 降低学习成本 |
| 优化拍照引导 | P2 | 16h | 提升照片质量 |
| 历史记录对比 | P3 | 12h | 直观看到变化 |

**总计**: ~112h (14 人天)

---

## 七、风险与缓解

### 风险 1: "圈选 + AI 精修"模式可能引入新 bug

**缓解**: 
- 保留现有 MaskEditor 作为 fallback
- 新功能通过 feature flag 控制，可随时关闭
- 先在 staging 环境测试 2 周

### 风险 2: VLM 集成模式增加 API 成本

**缓解**:
- 仅在 `precision='precise'` 模式下启用
- 监控 API 调用量，设置预算上限
- 考虑缓存：相同图片不重复调用

### 风险 3: 移动端重构可能破坏桌面端体验

**缓解**:
- 使用 `md:` 断点严格区分移动端/桌面端
- 桌面端保持现有布局，仅移动端使用新布局
- 在 375px、768px、1024px、1440px 四个断点测试

### 风险 4: 用户可能不信任 AI 精修结果

**缓解**:
- 显示置信度，让用户知道 AI 的确定性
- 提供"接受 AI 结果"和"手动编辑"两个选项
- 收集用户反馈，持续改进算法

---

## 八、成功指标

### 准确性指标

| 指标 | 当前 | 目标 | 测量方法 |
|------|------|------|----------|
| AI 预填涂 Dice 系数 | ~0.6 | ≥0.75 | 与用户修正结果对比 |
| VASI 分数误差 | ±30% | ±15% | 与医生评估对比 |
| 漏检率 | ~25% | ≤10% | 用户修正时新增的病灶数 |

### UX 指标

| 指标 | 当前 | 目标 | 测量方法 |
|------|------|------|----------|
| 移动端评估完成率 | ~60% | ≥80% | 开始评估 → 完成评估的比例 |
| 平均评估时间 | 8 分钟 | ≤5 分钟 | 从上传到查看结果的时间 |
| 手动编辑率 | ~90% | ≤50% | 使用"快速评估"直接接受结果的比例 |
| 移动端误触率 | 高 | 低 | 撤销/重做操作频率 |

---

## 九、下一步行动

### 立即执行（本周）

1. **创建实施计划文档**: 将本方案拆分为具体的 GitHub Issues
2. **阶段 1 任务分配**: 
   - 后端：降低置信度阈值、统一区域权重（4h）
   - 前端：实现双指缩放、增大触控目标（10h）
3. **设置监控**: 添加 AI 准确性指标追踪（Dice 系数、漏检率）

### 短期（2 周内）

1. **完成阶段 1 所有任务**
2. **在 staging 环境测试 1 周**
3. **收集用户反馈**

### 中期（1-2 个月）

1. **实施阶段 2: "圈选 + AI 精修"模式**
2. **A/B 测试**: 新旧模式对比
3. **根据数据调整算法**

### 长期（3-6 个月）

1. **实施阶段 3: 移动端体验重构**
2. **持续优化 AI 模型**（基于用户反馈数据）
3. **探索新技术**: 如移动端 on-device SAM（减少 API 调用）

---

## 十、附录

### 10.1 相关代码文件清单

**前端**:
- `web/app/src/components/tracker/AssessmentWizard.vue` (670 行)
- `web/app/src/components/tracker/MaskEditor.vue` (828 行)
- `web/app/src/components/tracker/DigitalHuman.vue`
- `web/app/src/components/tracker/BodyPartCamera.vue` (382 行)
- `web/app/src/composables/useVasiAssessment.ts` (635 行)
- `web/app/src/constants/bodySites.ts`

**后端**:
- `web/backend/api/vasi.py`
- `web/backend/services/vasi.py` (主编排器)
- `web/backend/services/vasi_segmentation.py` (SAM 分割)
- `web/backend/services/vasi_skin_mask.py` (颜色检测)
- `web/backend/services/vasi_formula.py` (VASI 计算)
- `web/backend/services/vasi_promptable.py` (点/框提示 SAM)
- `web/backend/services/vasi_preprocess.py` (预处理)
- `web/backend/services/vasi_quality.py` (质量检查)

### 10.2 参考资料

- **VASI 原始论文**: Hamzavi et al. (2004) - Vitiligo Area Scoring Index
- **SAM 论文**: Kirillov et al. (2023) - Segment Anything
- **Fitzpatrick 肤色分类**: https://en.wikipedia.org/wiki/Fitzpatrick_scale
- **移动端触控目标**: Apple HIG (44pt), Material Design (48dp)

---

**文档版本**: v1.0  
**最后更新**: 2026-06-11  
**维护者**: SubSkin 团队
