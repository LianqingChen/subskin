# 白斑特征分析（非诊断性建议）功能规划方案

**日期:** 2026-05-23  
**作者:** Hermes Agent  
**状态:** 待审核

---

## 一、需求背景

### 1.1 现状
当前测评页面的核心流程：
```
用户选择身体部位 → 上传白斑照片 → VLM+SAM分割识别 → 返回VASI评分+面积占比
```

主要功能聚焦于**量化评估**（VASI评分、面积百分比），但缺少对白斑**视觉特征的定性分析**。

### 1.2 用户痛点
- 很多用户并不清楚自己的白斑是否符合白癜风的典型特征
- 用户更关心"这到底是不是白癜风"，但我们作为非医疗机构，**不能给出诊断结论**
- 现有的 VASI 评分对普通用户来说比较抽象，缺乏直观的特征解读

### 1.3 目标
在用户上传照片后、VASI测评之前，增加一个**白斑视觉特征分析**环节：
- 基于肉眼可见的图像特征，给出中肯的观察性描述
- 参考白癜风诊断的公开判断依据（如边缘、颜色、形态等），但**明确声明不是诊断**
- 帮助用户理解自己的白斑特征，引导其必要时就医

---

## 二、合规边界（核心红线）

### 2.1 绝对不能做的
| ❌ 禁止行为 | 说明 |
|---|---|
| 给出"白癜风"或"非白癜风"的诊断结论 | 属于医疗诊断，需执业医师资格 |
| 使用"确诊"、"诊断"、"判定"等医疗术语 | 容易误导用户认为是医学结论 |
| 建议具体治疗方案或用药 | 属于处方行为 |
| 给出概率性结论如"80%可能是白癜风" | 概率性诊断仍然是诊断 |
| 暗示用户可以不就医 | 可能延误治疗 |

### 2.2 可以做的
| ✅ 允许行为 | 说明 |
|---|---|
| 描述肉眼可见的图像特征 | 客观观察，非诊断 |
| 列出与某疾病特征"相似"或"不同"的视觉表现 | 对比参考，非结论 |
| 建议"建议就医进一步检查" | 合理引导 |
| 提供科普性质的特征说明 | 教育信息 |
| 使用"视觉特征分析"、"观察性描述"等措辞 | 明确非诊断性质 |

---

## 三、分析维度设计

参考白癜风临床诊断的公开判断标准（Wood灯检查、临床观察等），提炼出**可通过照片肉眼观察**的维度：

### 3.1 核心分析维度（6项）

| 维度 | 说明 | VLM可观察的特征 | 输出形式 |
|---|---|---|---|
| **1. 白斑可见性** | 白斑是否肉眼清晰可见 | 白斑区域是否存在、对比度 | 可见/隐约可见/不明显 + 描述 |
| **2. 颜色特征** | 白斑的颜色表现 | 白色程度（淡白/乳白/瓷白/纯白） | 颜色等级 + 描述 |
| **3. 边缘特征** | 白斑与正常皮肤的交界处 | 边界是否清晰、是否有色素加深带 | 清晰/模糊/部分清晰 + 描述 |
| **4. 形态特征** | 白斑的形状和分布 | 圆形/不规则/线条状，单发/多发 | 形态描述 |
| **5. 表面特征** | 白斑表面的纹理 | 是否光滑、有无鳞屑、有无萎缩 | 光滑/有鳞屑/其他 + 描述 |
| **6. 分布特征** | 白斑的位置和对称性 | 单侧/双侧、是否在暴露部位 | 分布描述 |

### 3.2 参考科普卡片

在分析结果旁边，展示一个可折叠的科普卡片：

> **白癜风常见视觉特征（科普参考）**
> - 颜色：乳白色或瓷白色，与正常皮肤色差明显
> - 边缘：边界通常清晰，边缘可能有色素加深
> - 表面：通常光滑无鳞屑
> - 形态：圆形、椭圆形或不规则形
> - 分布：可对称分布或沿神经节段分布
> 
> ⚠️ 以上为科普信息，仅供参考。很多皮肤状况都可能出现类似特征，
> 具体诊断需要专业医生结合 Wood 灯检查、病史等综合判断。

---

## 四、技术方案

### 4.1 整体流程变更

**当前流程:**
```
上传照片 → 照片质量检查 → VASI评估(VLM+SAM) → 显示结果
```

**新增后流程:**
```
上传照片 → 照片质量检查 → [新增] 白斑特征分析(VLM) → VASI评估(VLM+SAM) → 显示结果
```

**优化方案（推荐）:**
考虑到 VLM 调用有延迟成本，将特征分析**合并到现有 VLM 调用中**，只需扩展 prompt：

```
上传照片 → 照片质量检查 → VLM综合分析(特征+定位) + SAM分割 → 显示结果
                              ↑
                   一次VLM调用同时返回：
                   1. 白斑视觉特征分析（新增）
                   2. 定位信息（skin_region, lesions，已有）
```

### 4.2 后端改动

#### 4.2.1 扩展 VLM Prompt（vasi.py `_call_vision_model`）

在现有 prompt 的 JSON 返回结构中，新增 `visual_features` 字段：

```json
{
  "skin_region": { ... },          // 已有
  "suspected_lesions": [ ... ],    // 已有
  "visual_features": {             // ★ 新增
    "visibility": {
      "level": "visible|faint|subtle",
      "description": "白斑肉眼清晰可见，与周围皮肤色差明显"
    },
    "color": {
      "level": "pale_white|milky_white|porcelain_white|pure_white",
      "description": "呈乳白色，色素脱失较明显"
    },
    "border": {
      "level": "clear|partial|unclear",
      "description": "白斑边界清晰，边缘可见轻度色素加深"
    },
    "shape": {
      "description": "呈不规则形，可见3处斑片，大小不等"
    },
    "surface": {
      "texture": "smooth|scaly|atrophic|other",
      "description": "表面光滑，未见明显鳞屑或萎缩"
    },
    "distribution": {
      "pattern": "localized|segmental|bilateral|generalized",
      "description": "局限于手背，呈散在分布"
    },
    "similarity_note": "上述特征中，颜色表现和边缘特征与白癜风常见表现有一定相似性，但很多皮肤状况（如白色糠疹、花斑癣、炎症后色素减退等）也可能出现类似表现。",
    "recommendation": "建议前往皮肤科进行 Wood 灯检查等专业检查以明确诊断。"
  },
  // ... 其他已有字段
}
```

#### 4.2.2 数据模型扩展（vasi.py Model）

在 `VASIAssessment` 表中新增一列存储特征分析结果：

```python
# models/vasi.py
visual_features_json = Column(Text, nullable=True)  # 白斑视觉特征分析JSON
```

#### 4.2.3 API 响应扩展

在 `VASIAssessmentResponse` 中新增 `visual_features` 字段：

```python
# api/models.py
class VASIAssessmentResponse(BaseModel):
    # ... 已有字段 ...
    visual_features: Optional[Dict[str, Any]] = None  # ★ 新增
```

#### 4.2.4 数据迁移

```python
# 在 ensure_vasi_columns() 中新增
"visual_features_json": ("TEXT", None),
```

### 4.3 前端改动

#### 4.3.1 API 类型扩展（api/vasi.ts）

```typescript
export interface VisualFeature {
  level?: string
  texture?: string
  pattern?: string
  description: string
}

export interface VisualFeatures {
  visibility: VisualFeature
  color: VisualFeature
  border: VisualFeature
  shape: VisualFeature
  surface: VisualFeature
  distribution: VisualFeature
  similarity_note: string
  recommendation: string
}

export interface VasiAssessmentResponse {
  // ... 已有字段 ...
  visual_features?: VisualFeatures | null  // ★ 新增
}
```

#### 4.3.2 新增组件：VisualFeaturesCard.vue

位置：`/root/subskin/web/app/src/components/tracker/VisualFeaturesCard.vue`

组件设计：

```
┌─────────────────────────────────────────────────┐
│ 🔍 白斑视觉特征分析                      [收起] │
├─────────────────────────────────────────────────┤
│                                                  │
│  👁 可见性     白斑肉眼清晰可见，与周围色差明显  │
│  🎨 颜色特征   乳白色，色素脱失较明显            │
│  📐 边缘特征   边界清晰，边缘可见轻度色素加深    │
│  🔷 形态特征   不规则形，可见3处斑片             │
│  ✋ 表面特征   表面光滑，未见鳞屑或萎缩          │
│  📍 分布特征   局限于手背，散在分布              │
│                                                  │
│ ┌──────────────────────────────────────────────┐ │
│ │ 📖 白癜风常见特征（科普参考）          [展开] │ │
│ │   · 颜色：乳白/瓷白，色差明显                │ │
│ │   · 边缘：通常清晰，可能有色素加深            │ │
│ │   · 表面：通常光滑无鳞屑                      │ │
│ │   · ...                                       │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ ┌─ 相似度参考 ─────────────────────────────────┐ │
│ │ [████████░░]  上述特征与白癜风常见表现有一    │ │
│ │               定相似性                        │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ 💡 建议前往皮肤科进行 Wood 灯检查等专业检查      │
│    以明确诊断。                                   │
│                                                  │
│ ⚠️ 以上分析基于照片的视觉观察，仅供参考，        │
│    不构成医疗诊断。很多皮肤状况都可能出现类似     │
│    特征，具体诊断需专业医生综合判断。             │
│                                                  │
│            [继续查看 VASI 测评结果 →]             │
└─────────────────────────────────────────────────┘
```

#### 4.3.3 结果展示流程调整

在 `AssessmentSection.vue` 中，当评估完成后：

1. **先展示** `VisualFeaturesCard`（白斑特征分析卡片）
2. **再展示** 现有的 VASI 评分结果
3. 用户可以选择"跳过特征分析"直接看 VASI 结果

步骤引导也从 3 步变为 4 步：
```
1.选择部位 → 2.上传照片 → 3.特征分析（新增） → 4.测评结果
```

### 4.4 性能优化

#### 方案：合并 VLM 调用（推荐）

**核心思路**：不增加额外的 VLM 调用，而是扩展现有 `_call_vision_model` 的 prompt，让 VLM 在一次调用中同时返回：
- 原有的 skin_region + suspected_lesions（给 SAM 用）
- 新增的 visual_features（给用户看）

**优势**：
- 不增加 API 调用次数和延迟
- 不增加成本
- VLM 分析图片时本身就在"看"这些特征，只需在 prompt 中要求输出

**风险**：
- Prompt 变长可能导致 VLM 输出质量下降
- 需要测试 token 消耗是否在限制内

#### 备选方案：独立 VLM 调用

如果合并调用效果不佳，可以独立调用：
- 新增 API endpoint：`POST /vasi/analyze-features`
- 使用更轻量的模型（如 qwen-vl-turbo）降低成本
- 可与 VASI 评估并行调用，减少等待时间

---

## 五、交互设计

### 5.1 用户流程图

```
┌──────────────┐
│  选择部位    │ Step 1
└──────┬───────┘
       ▼
┌──────────────┐
│  上传照片    │ Step 2
└──────┬───────┘
       ▼
┌──────────────────────┐
│  照片质量检查 (本地)  │ 自动
└──────┬───────────────┘
       ▼
┌──────────────────────────────────────┐
│  AI 分析中（VLM特征分析 + SAM分割）   │ 约30-40s
│  ┌─ 进度提示 ──────────────────────┐ │
│  │ ① 正在分析白斑视觉特征...       │ │
│  │ ② 正在识别白斑区域...           │ │
│  │ ③ 正在计算面积...               │ │
│  └─────────────────────────────────┘ │
└──────┬───────────────────────────────┘
       ▼
┌──────────────────────────────────────┐
│  Step 3: 白斑特征分析卡片             │
│  (VisualFeaturesCard)                │
│                                      │
│  [6项特征分析结果]                    │
│  [科普卡片]                          │
│  [相似度参考]                        │
│  [就医建议]                          │
│  [免责声明]                          │
│                                      │
│  [继续查看 VASI 测评 →]              │
└──────┬───────────────────────────────┘
       ▼
┌──────────────────────────────────────┐
│  Step 4: VASI 测评结果 + 轮廓编辑    │
│  (现有功能不变)                      │
└──────────────────────────────────────┘
```

### 5.2 关键交互细节

1. **分析中状态**：在上传后的 loading 状态中，分阶段显示进度文案：
   - "正在分析白斑视觉特征..."
   - "正在识别白斑区域并计算面积..."

2. **特征卡片默认展开**：首次展示时展开所有6项特征，科普卡片默认折叠

3. **相似度参考**：不做数值化（避免被理解为诊断概率），而是用文字描述：
   - "多项特征与白癜风常见表现相似" 
   - "部分特征与白癜风常见表现相似"
   - "上述特征与白癜风常见表现差异较大"
   - "无法从照片中判断"

4. **免责声明必须显示**：每次展示特征分析结果时，底部免责声明不可隐藏

---

## 六、改动范围汇总

### 6.1 后端文件

| 文件 | 改动内容 |
|---|---|
| `web/backend/services/vasi.py` | 扩展 `_call_vision_model` 的 prompt，新增 visual_features 解析 |
| `web/backend/models/vasi.py` | 新增 `visual_features_json` 列 |
| `web/backend/api/vasi.py` | 响应中返回 visual_features |
| `web/backend/api/models.py` | VASIAssessmentResponse 新增 visual_features 字段 |

### 6.2 前端文件

| 文件 | 改动内容 |
|---|---|
| `web/app/src/api/vasi.ts` | 新增 VisualFeatures 类型，响应中增加字段 |
| `web/app/src/components/tracker/VisualFeaturesCard.vue` | **新建**，特征分析展示组件 |
| `web/app/src/components/tracker/AssessmentSection.vue` | 集成 VisualFeaturesCard，调整步骤引导 |
| `web/app/src/composables/useVasiAssessment.ts` | 解析和存储 visual_features 数据 |

### 6.3 数据库

| 操作 | 说明 |
|---|---|
| ALTER TABLE | vasi_assessments 新增 visual_features_json 列 |

---

## 七、实施计划

### Phase 1：后端扩展（预计 2-3 小时）
1. 扩展 VLM prompt，增加 visual_features 输出
2. 数据模型新增列 + 迁移
3. API 响应扩展
4. 测试 VLM 输出质量（用几张真实白斑照片测试 prompt 效果）

### Phase 2：前端组件开发（预计 3-4 小时）
1. 新建 VisualFeaturesCard.vue 组件
2. API 类型扩展
3. AssessmentSection.vue 集成
4. useVasiAssessment.ts 数据流适配

### Phase 3：联调与优化（预计 1-2 小时）
1. Staging 部署测试
2. VLM prompt 调优（根据实际输出调整措辞）
3. UI 细节打磨
4. 移动端适配验证

### 总计预估：6-9 小时

---

## 八、风险与注意事项

| 风险 | 应对策略 |
|---|---|
| VLM prompt 扩展后输出质量下降 | 拆分调用，独立分析 |
| 特征分析结果与 VASI 不一致造成困惑 | 明确说明两者是不同维度的分析 |
| 用户过度依赖特征分析结果 | 强化免责声明，引导就医 |
| 法律合规风险 | 全文不出现"诊断""确诊"等词，措辞严格审核 |
| VLM 返回非预期的 visual_features 格式 | 后端做 schema 校验，缺失时降级显示 |

---

## 九、Prompt 设计细节

以下是扩展后的 VLM prompt 核心部分（新增 `visual_features` 指令）：

```
你是一位皮肤科AI助手。请仔细分析这张皮肤照片。

重要声明：你不是医生，不能进行医疗诊断。你的分析仅基于照片中肉眼可见的
视觉特征，供用户参考。请在所有描述中使用"观察到"、"可见"等客观措辞，
避免使用"诊断为"、"确诊"等医疗术语。

返回 JSON（只返回 JSON，不要其他文字）：
{
  "visual_features": {
    "visibility": {
      "level": "visible|faint|subtle",
      "description": "用一句话描述白斑的肉眼可见程度"
    },
    "color": {
      "level": "pale_white|milky_white|porcelain_white|pure_white",
      "description": "描述白斑的颜色表现和色素脱失程度"
    },
    "border": {
      "level": "clear|partial|unclear",
      "description": "描述白斑与正常皮肤交界处的特征"
    },
    "shape": {
      "description": "描述白斑的形状、数量和大体分布"
    },
    "surface": {
      "texture": "smooth|scaly|atrophic|other",
      "description": "描述白斑表面的纹理特征"
    },
    "distribution": {
      "pattern": "localized|segmental|bilateral|generalized",
      "description": "描述白斑的分布模式"
    },
    "similarity_note": "基于上述特征，说明与白癜风常见表现的相似程度，
      同时列举其他可能出现类似特征的皮肤状况（至少2种）",
    "recommendation": "基于观察到的特征，给出是否建议就医的建议"
  },
  // ... 其他已有字段（skin_region, suspected_lesions 等）保持不变
}
```

---

## 十、验收标准

- [ ] 用户上传照片后，能看到白斑视觉特征分析卡片
- [ ] 6项特征维度均有描述，且措辞客观中立
- [ ] 科普卡片可折叠展开
- [ ] 相似度参考使用文字描述而非概率数值
- [ ] 免责声明始终可见
- [ ] 不出现任何"诊断""确诊"等医疗术语
- [ ] 特征分析不影响 VASI 评估流程和结果
- [ ] VLM 调用未增加额外请求次数（合并到现有调用中）
- [ ] 移动端展示正常
