# SubSkin 小白手账 VASI 评估升级 — OpenCode 执行任务清单

> 基于调研报告 `/root/subskin/docs/vitiligo_area_assessment_research_report.md`
> 目标: Phase 1 可落地的 VASI 评估精度提升与用户体验优化
> 执行者: OpenCode CLI agent
> 工作目录: /root/subskin

---

## 完成后能实现的功能和效果

### 用户看到的变化

1. **拍照引导系统** — 上传照片前，显示拍照技巧提示卡片（光线、角度、距离建议 + 参考物提示）
2. **实时照片质量反馈** — 上传后即时检测：是否模糊、是否有皮肤、光照是否合适。不合适的照片给出具体改进建议
3. **更准确的白斑面积估算** — VLM prompt 优化 + 图像预处理（白平衡 + 对比度增强），面积误差从 ±50% 降低到 ±25%
4. **AI信心度显示** — 评估结果中显示AI对本次评估的信心度（高/中/低），帮助用户判断结果可靠性
5. **拍照技巧指南页** — 小白手账页面新增加"拍照技巧"入口，展示标准拍照示例
6. **多白斑区域可视化改进** — 轮廓编辑器支持多个白斑区域独立标注和面积汇总
7. **参考物提示** — 引导用户拍照时放置硬币/尺子等参考物，为Phase 2精确测量做准备

### 后端改进

1. **图像预处理管线** — 自动白平衡、CLAHE对比度增强、锐化，提升VLM识别准确度
2. **照片质量检测** — 模糊检测（拉普拉斯方差）、皮肤检测（肤色占比）、光照评估
3. **改进的VLM Prompt** — 更结构化的评估指令，不再依赖VLM返回精确多边形坐标
4. **面积估算校准** — 基于身体部位先验知识的面积修正

---

## 任务清单（共 14 个任务）

### 🟢 Phase A: 后端 — 图像预处理与质量检测 (Task 1-4)

---

#### Task 1: 新建图像预处理服务

**文件**: `web/backend/services/vasi_preprocess.py` (新建)

**内容**:
```
创建 VasiImagePreprocessor 类，提供:
1. auto_white_balance(img: Image) -> Image
   - Gray World 算法自动白平衡
2. enhance_contrast(img: Image) -> Image  
   - CLAHE (对比度受限自适应直方图均衡化)
3. sharpen(img: Image) -> Image
   - Unsharp Mask 锐化
4. preprocess(image_bytes: bytes) -> bytes
   - 完整管线: 白平衡 → CLAHE → 锐化 → 缩放到 max 1024px → JPEG输出
5. resize_for_api(image_bytes: bytes, max_size: int = 1024) -> bytes
   - 等比缩放，控制API调用成本
```

**依赖**: Pillow (已在项目中), numpy, scikit-image (如需CLAHE; 也可用PIL的ImageEnhance)
**验证**: 用一张测试照片运行预处理，确认输出图片文件大小减小、视觉上更清晰

---

#### Task 2: 新建照片质量检测服务

**文件**: `web/backend/services/vasi_quality.py` (新建)

**内容**:
```python
class VasiQualityChecker:
    """拍照质量检测器"""
    
    def check_all(image_bytes: bytes) -> QualityReport:
        """返回 QualityReport dataclass"""
    
    # 单项检测:
    def check_blur(image_bytes: bytes) -> BlurResult
        # 拉普拉斯方差法: cv2.Laplacian + variance
        # < 100: 模糊, 100-300: 一般, > 300: 清晰
    
    def check_skin_presence(image_bytes: bytes) -> SkinResult
        # HSV肤色检测: 肤色像素占比
        # 肤色范围: H 0-50, S 15-80, V 20-80
        # skin_ratio < 15%: 可能不是皮肤照片
    
    def check_lighting(image_bytes: bytes) -> LightingResult
        # 亮度直方图分析
        # 均值 < 60: 太暗, > 220: 过曝, 60-180: 正常
        # 暗部像素 > 40%: 光线不足
    
    def check_size(image_bytes: bytes) -> SizeResult
        # 分辨率检测: min 640x480, 推荐 1920x1080+
```

**QualityReport 结构**:
```python
@dataclass
class QualityReport:
    overall: str        # "good" | "acceptable" | "poor"
    blur_score: float   # 拉普拉斯方差值
    blur_ok: bool
    skin_ratio: float   # 0-1
    skin_ok: bool
    brightness_mean: float
    lighting_ok: bool
    resolution: tuple
    size_ok: bool
    suggestions: List[str]  # 中文改进建议
```

**依赖**: opencv-python-headless (或 numpy 手动实现模糊检测)
**验证**: 用清晰/模糊/非皮肤/过暗照片各一张测试

---

#### Task 3: 集成预处理到 VASI 评估流程

**文件**: `web/backend/services/vasi.py` (修改)

**修改点**:
1. 在 `_call_vision_model()` 方法开头，调用预处理:
   ```python
   from web.backend.services.vasi_preprocess import preprocessor
   image_bytes = preprocessor.preprocess(image_bytes)
   ```

2. 在 `assess_vasi()` 方法中，调用VLM前先质量检测:
   ```python
   from web.backend.services.vasi_quality import quality_checker
   quality = quality_checker.check_all(image_bytes)
   # quality report 存入 details
   ```

3. 当质量太差时（overall == "poor"），**不调用VLM**，直接返回质量报告给前端，提示用户重新拍照

**关键**: 
- 遵循 Python 3.9 约束: Optional[T] 而非 T | None
- 新服务可能依赖 opencv，用 try/except 包裹 import，提供 graceful fallback
- 不改变现有的 API 返回格式

---

#### Task 4: 改进 VLM Prompt

**文件**: `web/backend/services/vasi.py` (修改 `_call_vision_model()` 方法中的 prompt)

**改进内容**:

原 prompt 问题: 要求 VLM 返回精确的多边形坐标 (VLM 做不到 → 返回随机坐标)
新版 prompt 策略:

```python
prompt = """你是一位专业的皮肤科AI助手，正在分析白癜风患者的皮肤照片。

请仔细观察照片，然后按以下JSON格式返回评估结果:

{
  "vasi_score": 0-100,        // VASI评分 (0=无白斑, 100=全身100%受累)
  "area_percentage": 0-100,   // 该部位白斑占照片中可见皮肤面积的百分比
  "classification": "节段型|非节段型|未确定",
  "stage": "进展期|稳定期|好转期",
  "body_site_confirmed": "面部|颈部|手部|躯干|上肢|下肢|足部|其他",
  "confidence": 0.0-1.0,      // 评估信心度 (0=完全不确定, 1=非常确定)
  "quality_notes": "",         // 照片质量备注(光照/角度/模糊等)
  "details": {
    "patch_count": 1,           // 白斑区域数量
    "patch_distribution": "散在|聚集|融合",  
    "color_type": "纯白|乳白|灰白|淡白",
    "border_clarity": "清晰|模糊|部分清晰",
    "description": "50字以内的白斑特征描述",
    "has_reference_object": false,  // 照片中是否检测到参考物(硬币/尺子等)
    "lighting_quality": "良好|一般|较差"
  }
}

注意:
1. 如果照片不是皮肤照片或无法识别，返回 {"error": "无法识别皮肤图像"}
2. VASI评分要保守估计，宁低勿高
3. area_percentage 是可见皮肤中白斑占比，不是全身占比
4. confidence 低于0.5时应谨慎使用评估结果
5. 只返回JSON，不要其他文字
"""
```

**关键变化**:
- ❌ 删除了 `contours` 要求（VLM无法准确输出多边形坐标）
- ✅ 增加了 `confidence` 信心度
- ✅ 增加了 `quality_notes` 质量备注
- ✅ 增加了 `has_reference_object` 检测
- ✅ `details` 结构更丰富

**后续处理**: 在 `_call_vision_model()` 中，如果VLM没有返回contours（新版prompt不会），使用改进的默认轮廓生成逻辑（已有代码在line 570-587，保留并改进）

---

### 🟡 Phase B: 后端 — API 与数据模型扩展 (Task 5-7)

---

#### Task 5: 扩展 API 返回质量报告

**文件**: `web/backend/api/vasi.py` 和 `web/backend/api/models.py` (修改)

**修改**:
1. 在 `VASIAssessmentResponse` 中新增字段:
   ```python
   quality_report: Optional[Dict[str, Any]] = None  # 照片质量报告
   confidence: Optional[float] = None  # AI信心度 0-1
   ```

2. 在 `POST /assess` 返回中包含这些字段

3. 新增 API 端点:
   ```python
   @router.post("/check-photo-quality")
   async def check_photo_quality(image: UploadFile = File(...)):
       """预检照片质量（无需登录），返回质量报告"""
       image_bytes = await image.read()
       quality = quality_checker.check_all(image_bytes)
       return {
           "overall": quality.overall,
           "blur_score": quality.blur_score,
           "blur_ok": quality.blur_ok,
           "skin_ratio": quality.skin_ratio,
           "skin_ok": quality.skin_ok,
           "brightness_mean": quality.brightness_mean,
           "lighting_ok": quality.lighting_ok,
           "suggestions": quality.suggestions,
       }
   ```
   > 注意: 这个端点无需登录，方便用户拍照后先检测质量

---

#### Task 6: 数据库模型扩展

**文件**: `web/backend/models/vasi.py` (修改)

**新增字段**:
```python
# 在 VASIAssessment 类中新增:
quality_report_json = Column(Text, nullable=True)  # JSON格式的照片质量报告
confidence = Column(Float, nullable=True)  # AI信心度 0-1
preprocessed = Column(Boolean, default=False)  # 是否经过预处理
```

**自动迁移**: 在 `web/backend/app/main.py` 中添加:
```python
def ensure_vasi_quality_columns() -> None:
    inspector = inspect(engine)
    try:
        columns = {c["name"] for c in inspector.get_columns("vasi_assessments")}
    except Exception:
        return
    if "quality_report_json" not in columns:
        with engine.begin() as connection:
            _ = connection.execute(
                text("ALTER TABLE vasi_assessments ADD COLUMN quality_report_json TEXT")
            )
    if "confidence" not in columns:
        with engine.begin() as connection:
            _ = connection.execute(
                text("ALTER TABLE vasi_assessments ADD COLUMN confidence FLOAT")
            )
    if "preprocessed" not in columns:
        with engine.begin() as connection:
            _ = connection.execute(
                text("ALTER TABLE vasi_assessments ADD COLUMN preprocessed BOOLEAN DEFAULT 0")
            )

ensure_vasi_quality_columns()
```

---

#### Task 7: 更新 VASI 服务集成质量数据

**文件**: `web/backend/services/vasi.py` (修改)

在 `assess_vasi()` 方法中:
1. 调用质量检测 → 质量差的返回质量报告给前端（不让VLM浪费token）
2. 调用预处理
3. 调用VLM
4. 将质量报告、信心度存入数据库

```python
# assess_vasi() 修改后流程:
async def assess_vasi(self, ...):
    self._validate_input(...)
    
    # Step 0: 质量检测
    quality = quality_checker.check_all(image_file)
    
    # Step 0.5: 如果质量极差，直接拒绝并返回建议
    if quality.overall == "poor":
        return quick_quality_reject_response(quality)
    
    # Step 1: 预处理
    try:
        preprocessed_bytes = preprocessor.preprocess(image_file)
        preprocessed = True
    except Exception:
        preprocessed_bytes = image_file
        preprocessed = False
    
    # Step 2: 上传
    image_url, image_key = await self._upload_image(...)
    
    # Step 3: VLM评估 (使用预处理后的图片)
    vasi_result = await self._call_vasi_api(preprocessed_bytes)
    
    # Step 4: 创建记录
    assessment = VASIAssessment(
        ...
        quality_report_json=json.dumps(quality_report_to_dict(quality)),
        confidence=vasi_result.get("confidence"),
        preprocessed=preprocessed,
    )
    ...
```

---

### 🟢 Phase C: 前端 — 拍照引导与质量反馈 (Task 8-12)

---

#### Task 8: 新增拍照技巧提示卡片组件

**文件**: `web/app/src/components/tracker/PhotoGuideCard.vue` (新建)

**内容**: 在 TrackerPage 上传区域上方显示的可折叠拍照技巧卡片

功能:
- 默认折叠，首次使用时展开
- 展示拍照要点（图标+文字）:
  1. 📏 保持30cm距离，正对皮肤拍摄
  2. 💡 在自然光或白色灯光下拍摄
  3. 🪙 拍照时可放一枚硬币作参考
  4. 🔍 确保白斑区域清晰可见
  5. ❌ 避免阴影遮挡和闪光灯直射
- "不再显示"按钮（存 localStorage）
- "查看示例"链接（跳转到拍照技巧页 Task 11）

---

#### Task 9: 增加实时照片质量检测反馈

**文件**: `web/app/src/views/TrackerPage.vue` (修改)
**API**: `web/app/src/api/vasi.ts` (修改)

**前端改动**:
1. 用户选择照片后，立即调用 `POST /api/vasi/check-photo-quality`（无需登录）
2. 显示质量检测结果卡片:
   ```
   ┌─────────────────────────────────┐
   │ 📸 照片质量检测                  │
   │ ✅ 清晰度良好                    │
   │ ✅ 皮肤区域充足 (78%)            │
   │ ⚠️ 光线偏暗，建议在更亮处拍摄    │
   │ [仍然使用] [重新选择]            │
   └─────────────────────────────────┘
   ```
3. 质量好 → 绿色边框 + "照片质量良好，可以进行评估"
4. 质量一般 → 黄色边框 + 具体建议
5. 质量差 → 红色边框 + "建议重新拍摄"

**API 扩展** (vasi.ts):
```typescript
async checkPhotoQuality(image: File): Promise<{
  overall: string
  blur_score: number
  blur_ok: boolean
  skin_ratio: number
  skin_ok: boolean
  brightness_mean: number
  lighting_ok: boolean
  suggestions: string[]
}> {
  const formData = new FormData()
  formData.append('image', image)
  const { data } = await apiClient.post('/vasi/check-photo-quality', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
```

---

#### Task 10: 评估结果增加信心度显示

**文件**: `web/app/src/views/TrackerPage.vue` (修改)

在评估结果卡片中新增信心度指示器:

```vue
<!-- 在评估结果 areaPercentage 旁边 -->
<div class="flex items-center gap-2">
  <span class="text-sm text-gray-500">AI信心度:</span>
  <span v-if="assessmentResult.confidence >= 0.8" class="text-green-500">● 高</span>
  <span v-else-if="assessmentResult.confidence >= 0.5" class="text-amber-500">● 中</span>
  <span v-else class="text-red-500">● 低</span>
  <span class="text-xs text-gray-400">({{ Math.round(assessmentResult.confidence * 100) }}%)</span>
</div>
```

当信心度 < 0.5 时显示提示:
```
⚠️ 本次评估信心度较低，建议在更好的光照条件下重新拍照，
或手动调整白斑轮廓后再确认。
```

**VASIAssessmentResponse 接口扩展**:
```typescript
export interface VasiAssessmentResponse {
  // ... existing fields
  confidence?: number
  quality_report?: {
    overall: string
    blur_score: number
    skin_ratio: number
    brightness_mean: number
    suggestions: string[]
  }
}
```

---

#### Task 11: 新增拍照技巧指南页

**文件**: `web/app/src/views/PhotoGuidePage.vue` (新建)
**路由**: 添加到 router，路径 `/photo-guide`

**内容**: 
- 独立页面，从 TrackerPage 拍照引导卡片链接过来
- 示例图片展示（用好/坏对比）:
  ```
  好的拍照示例:
  - 光线均匀、白斑清晰、有参考物
  - 对焦清晰、30cm距离
  
  不好的拍照示例:  
  - 闪光灯直射、阴影遮挡
  - 距离太远、模糊
  - 角度倾斜
  ```
- VASI评估原理简介（通俗版）
- "现在去拍照"按钮 → 跳转回 `/tracker?tab=tracker`

**路由配置**: 在 `router/index.ts` 中添加:
```typescript
{
  path: '/photo-guide',
  name: 'photo-guide',
  component: () => import('@/views/PhotoGuidePage.vue'),
  meta: { title: '拍照技巧 - SubSkin' }
}
```

---

#### Task 12: 优化轮廓编辑器增加面积汇总

**文件**: `web/app/src/components/tracker/VitiligoContour.vue` (修改)

**改进内容**:
1. 在工具栏下方显示当前各区域的面积:
   ```vue
   <div class="absolute top-14 right-3 bg-white/90 rounded-lg px-3 py-2 text-xs shadow">
     <div v-for="(c, i) in localContours" :key="i" :style="{color: contourColors[i % contourColors.length]}">
       {{ c.label }}: {{ (c.area_percent ?? computeArea(c.polygon) * 100).toFixed(1) }}%
     </div>
     <div class="font-bold mt-1 border-t pt-1">
       合计: {{ totalAreaPercent.toFixed(1) }}%
     </div>
   </div>
   ```

2. 计算多边形面积的辅助函数:
   ```typescript
   function computePolygonArea(polygon: number[][]): number {
     // Shoelace formula (鞋带公式) 计算归一化多边形面积
     let area = 0
     for (let i = 0; i < polygon.length; i++) {
       const j = (i + 1) % polygon.length
       area += polygon[i][0] * polygon[j][1]
       area -= polygon[j][0] * polygon[i][1]
     }
     return Math.abs(area) / 2
   }
   ```

3. 增加"添加区域"按钮（已有 hand-draw 模式，但可以加一个快速添加矩形框的选项）

---

### 🔵 Phase D: 集成验证与部署 (Task 13-14)

---

#### Task 13: 后端服务启动与验证

**执行步骤**:
```bash
# 1. 重启后端服务
sudo systemctl restart subskin-backend

# 2. 检查服务状态
sudo systemctl status subskin-backend

# 3. 等待5秒后检查日志
sleep 5 && sudo journalctl -u subskin-backend --no-pager -n 30

# 4. 测试API端点
curl http://localhost:8000/api/vasi/trend
curl http://localhost:8000/docs  # 检查 OpenAPI 文档是否包含新端点

# 5. 测试照片质量检测端点 (需要一张测试照片)
curl -X POST http://localhost:8000/api/vasi/check-photo-quality \
  -F "image=@test_photo.jpg"
```

**验证清单**:
- [ ] `subskin-backend` 状态为 active
- [ ] 日志中无导入错误（特别是 opencv 回退）
- [ ] `/api/vasi/check-photo-quality` 返回 200
- [ ] 数据库 `vasi_assessments` 表新增列存在
- [ ] OpenAPI 文档中看到新端点

---

#### Task 14: 前端构建与验证

**执行步骤**:
```bash
cd /root/subskin/web/app

# 1. 安装依赖（如果需要新的）
npm install

# 2. TypeScript 类型检查
npx vue-tsc --noEmit

# 3. 生产构建
npm run build

# 4. 检查构建产物
ls -la dist/
```

**验证清单**:
- [ ] `vue-tsc` 无类型错误
- [ ] `npm run build` 成功（exit code 0）
- [ ] `dist/` 目录存在且有 index.html
- [ ] 无 console 中的 import 错误

**部署**:
```bash
# 复制构建产物到 nginx 服务目录
sudo cp -r dist/* /var/www/subskin/
sudo systemctl reload nginx
```

---

## 文件变更总览

| 类型 | 文件 | 操作 |
|------|------|------|
| 新建 | `web/backend/services/vasi_preprocess.py` | 图像预处理 |
| 新建 | `web/backend/services/vasi_quality.py` | 照片质量检测 |
| 新建 | `web/app/src/components/tracker/PhotoGuideCard.vue` | 拍照引导卡片 |
| 新建 | `web/app/src/views/PhotoGuidePage.vue` | 拍照技巧指南页 |
| 修改 | `web/backend/services/vasi.py` | 集成预处理 + 改进prompt + 质量检测 |
| 修改 | `web/backend/api/vasi.py` | 新增 check-photo-quality 端点 + 返回扩展 |
| 修改 | `web/backend/api/models.py` | VASIAssessmentResponse 扩展 |
| 修改 | `web/backend/models/vasi.py` | 新增 quality_report_json / confidence / preprocessed 字段 |
| 修改 | `web/backend/app/main.py` | 添加数据库自动迁移 |
| 修改 | `web/app/src/api/vasi.ts` | 新增 checkPhotoQuality + 类型扩展 |
| 修改 | `web/app/src/views/TrackerPage.vue` | 集成质量反馈 + 信心度 + 引导卡片 |
| 修改 | `web/app/src/components/tracker/VitiligoContour.vue` | 面积汇总显示 |
| 修改 | `web/app/src/router/index.ts` | 新增 /photo-guide 路由 |

---

## 注意事项

1. **Python 3.9 约束**: 后端所有代码使用 `Optional[T]`/`List[T]`/`Dict[K,V]`，不使用 `T | None`/`list[T]`/`dict[K,V]`
2. **opencv 依赖**: 用 try/except 包裹 import，安装失败时跳过模糊检测（仅返回基本报告）
3. **Pillow 已安装**: 不要重复安装
4. **numpy**: 如果未安装，可用纯 Python 实现简单替代
5. **不修改数据库表结构**: 只新增列（ADD COLUMN），不改现有列
6. **不改变现有 API 契约**: 所有新增字段都是 Optional，不影响现有前端
7. **前端已有所有依赖**: Vue 3 + TypeScript + TailwindCSS，无需新增框架依赖

## 回滚方案

如果出现问题:
1. `git checkout` 恢复 `vasi.py`, `vasi.py(api)`, `models.py`, `TrackerPage.vue`
2. 删除新建文件
3. 重启服务: `sudo systemctl restart subskin-backend`
4. 新增的数据库列不影响现有功能（都是 nullable）
