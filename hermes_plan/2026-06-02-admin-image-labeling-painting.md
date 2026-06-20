# Admin 图片打标模块优化规划

**日期**: 2026-06-02
**作者**: Hermes
**目标模块**: `/root/subskin/web/admin/src/views/ImageLabeling.vue`
**关联文件**: 测评页面填涂组件、模型/API、训练数据导出

---

## 1. 现状梳理

### 1.1 后端能力（已基本就绪）

| 组件 | 路径 | 关键点 |
|---|---|---|
| 数据模型 | `web/backend/models/image_label.py` | 已预留 `ImageLabelAnnotation` 表（`region_contour`/`mask_data`/`region_bbox`/`area_percentage` 等字段） |
| API 路由 | `web/backend/api/image_label.py` | 已支持 `POST /admin/image-labels/{id}/label` 接收 `annotations` 列表 |
| Pydantic Schema | `AnnotationItem` | 含 `region_contour`(JSON 字符串)、`mask_data`(PNG data URL)、`region_bbox` |
| 统计与导出 | 同文件 | `stats`、批量状态、训练数据导出接口已就位 |

**结论**: 后端**不需要新增模型/API**，只需要把 `annotations` 字段从前端传过去即可。但需要补一个 `GET /admin/image-labels/{id}/annotations` 用于编辑已标注时回显。

### 1.2 前端 Admin 页面（需要全面重构）

文件: `web/admin/src/views/ImageLabeling.vue` (554 行)

**当前问题**:
1. 列表视图: 每行只显示缩略图 + AI/人工标签对比，没有"点击放大"
2. 预览 Modal: 用 `n-modal` + `<img>` 静态展示，**没有标注画布**
3. 标注提交: 只有下拉选框（部位/分型/面积%），**无法画白斑轮廓**
4. 已标注编辑: 没有"打开已标注详情再次编辑"入口
5. 测评页面的 `MaskEditor`/`VitiligoContour` 组件**未在 admin 复用**

### 1.3 测评页面已有的画图组件（参考原型）

| 组件 | 路径 | 能力 | 适用场景 |
|---|---|---|---|
| `MaskEditor.vue` (497 行) | `web/app/src/components/tracker/` | 双画笔（皮肤+白斑+橡皮擦）、撤销/重做（30 步）、动画 marching-ants 轮廓、面积统计 | **像素级精确掩码** |
| `VitiligoContour.vue` (399 行) | 同上 | SVG 多边形圈选、点编辑、select/draw/move 模式、面积自动计算 | **几何级多边形轮廓** |

数据格式: `ContourRegion { label, polygon: number[][], area_percent? }`，多边形点为**归一化坐标 [0,1]**，与后端 `region_contour` JSON 字符串直接兼容。

### 1.4 千问 Skill 适用性分析

| Skill | 用途 | 在本项目中的角色 |
|---|---|---|
| `qianwen-vision` (Qwen3-VL-Plus) | 图像理解、目标定位 | **可选** — 已有 SubSkin 自家 VASI 推理链（7 级 fallback），不建议在 admin 内嵌第三方 VLM |
| `qianwen-image-generation` (Wan) | 文生图/图像编辑 | **不适用** — admin 不需要生成图片 |

**结论**: 千问 skill **不是核心依赖**。SubSkin 已有完整 VASI 7级 fallback 体系（SAM→VLM→合并→mock）。如果后续需要给管理员提供"AI 一键预标注"按钮，可以用现有 `/vasi/assessments` 接口跑一遍 VLM 拿到 contours，再渲染到画布上让管理员修正——这与 MaskEditor 的 `initialLesionLayerUrl` 模式天然兼容。

---

## 2. 目标功能

### 2.1 点击缩略图 → 大图查看 + 圈选 / 填涂

交互流程:
1. 列表行点击缩略图（或新增"标注"按钮）→ 打开**标注编辑器**
2. 编辑器是一个全屏 Modal：
   - **左侧**: 大图（可缩放）+ SVG 多边形圈选层（白斑）
   - **右侧**: 标注表单（部位、分型、面积% 等）+ 工具栏（draw / select / move / undo / redo / clear）
   - 底部: 历史标注摘要 + 确认/取消按钮
3. 确认时把多边形列表以 `region_contour` 格式提交到后端 `annotations` 字段

### 2.2 双画布模式（按管理员偏好切换）

| 模式 | 工具 | 用途 | 保存字段 |
|---|---|---|---|
| **多边形圈选** (VitiligoContour 模式) | SVG polygon draw/move/select | 快速勾画白斑边界 | `region_contour` (JSON) + `region_bbox` |
| **像素填涂** (MaskEditor 模式) | brush/eraser | 精细白斑像素掩码 | `mask_data` (PNG data URL) + `area_percentage` |

默认 **多边形圈选模式**（更易操作）。填涂模式作为高级选项。

### 2.3 标注数据保存与训练数据回流

每次提交:
- 一张图片可保存**多处白斑**（多个 polygon）
- 每个白斑独立 `region_index`、`body_site`、`is_vitiligo`、`area_percentage`
- 整张图汇总: `admin_area_percentage` = 所有 `region.area_percent` 之和
- 训练数据标记: 提交时 `training_eligible=true` 的图片会自动加入训练集

### 2.4 已标注重新编辑

- 列表"已标注" Tab 行的"编辑"按钮 → 打开编辑器
- 编辑器自动加载已保存的 `region_contour` 多边形 / `mask_data` PNG
- 提交时**覆盖**或**追加**（默认追加，并显示已有的 N 处白斑）

---

## 3. 技术方案

### 3.1 组件复用策略

**核心原则**: **直接复用**测评页面的 `VitiligoContour` 和 `MaskEditor`，不改它们的源码。

**实施方式**:
1. 把 `VitiligoContour.vue` / `MaskEditor.vue` 从 `web/app/src/components/tracker/` 复制到 `web/admin/src/components/labeling/`
2. 删除 `import type { ContourRegion } from '@/api/vasi'` —— 在 admin 中**重新定义本地的** `ContourRegion` interface（避免 admin 依赖 app 的 API）
3. 删除组件中任何 NaiveUI/iOS 风格依赖 → 替换为 admin 现有的 Tailwind/NaiveUI 风格
4. 在 `vite.config.ts` 中确保 admin 能解析 `@/` 路径

**为什么不通过 monorepo 共享包？**
- Admin 和 App 用的是不同的样式系统（admin: NaiveUI 深色 + Tailwind；app: Tailwind + 主题色）
- 共享会增加 vite alias 配置复杂度
- 复制 2 个文件 + 简单改 import，是**最小风险方案**（100 行内的修改）

### 3.2 数据流

```
User 列表点开某图
  → GET /admin/image-labels/{id} 拿完整 AI/用户/管理员标注数据
  → 前端渲染: AI 预标注轮廓（半透明）+ 已有管理员标注轮廓（实色）
  → 管理员用画笔/多边形工具圈选新白斑
  → 点击"确认"
  → POST /admin/image-labels/{id}/label  payload = {
      body_site, is_vitiligo, vitiligo_type, ...,
      annotations: [
        { source: 'admin', region_index: 0,
          body_site, is_vitiligo, vitiligo_type,
          area_percentage,  // 自动从 polygon 计算
          region_contour: JSON.stringify([[x,y],...]),  // 归一化坐标
          region_bbox: JSON.stringify({x,y,w,h}),
          mask_data: <png dataurl>,  // 仅 fill 模式有
          notes: '管理员备注' }
      ]
    }
  → 后端写入 image_label_annotations 表
  → 训练数据导出时打包 (image_url, mask_data, region_contour) 三元组
```

### 3.3 面积自动计算

在编辑器内部用 Canvas API 计算多边形面积占图片总面积的比例：
```ts
function polygonAreaPercent(polygon: number[][], imgW: number, imgH: number): number {
  // 归一化坐标 [0,1] → 像素
  // Shoelace formula 计算多边形面积
  // 除以 (imgW * imgH) 得到百分比
}
```

填涂模式的面积 MaskEditor 已有 `areaPercent` 计算。

### 3.4 与 VLM 预标注的衔接

如果图片已有 AI 标注 (`ai_details.contours` 来自 VASI 推理)，打开编辑器时：
- 解析 `ai_details.contours` 为 `ContourRegion[]`（半透明展示，标签前缀 `[AI] 白斑N`）
- 管理员可选择: **基于 AI 标注微调** / **完全重画**
- 提交时把最终结果写入 `annotations`，AI 预标注只作辅助，不污染 ground truth

### 3.5 训练数据格式

后端 `TrainingExportRequest` 已有 `split_ratio`/`include_ai`/`include_user` 字段。扩展：
- 在导出 JSON 中**额外**生成 `image_filename`、`mask_filename` 字段对
- 后续可调用 `vasi/finetune` 类服务消费这些 (image, mask) 对

---

## 4. 文件改动清单

### 新增文件
```
web/admin/src/components/labeling/
  VitiligoContourAdmin.vue      # 复用自 app 端，admin 风格适配 (复制 + 改 import)
  MaskEditorAdmin.vue           # 复用自 app 端，admin 风格适配 (复制 + 改 import)
  LabelingEditor.vue            # 编辑器主壳：左侧画布 + 右侧表单 + 顶部工具栏
```

### 修改文件
```
web/admin/src/views/ImageLabeling.vue   # 列表行：缩略图点击行为 → 打开 LabelingEditor
                                          # 列表行新增"编辑"按钮（已标注 Tab）
web/admin/src/api/imageLabel.ts         # （若不存在则新建）: API 调用封装
web/admin/src/router/                   # 无需改，Modal 形式不需独立路由
```

### 后端（最小改动）
```
web/backend/api/image_label.py
  + GET  /admin/image-labels/{id}/annotations  # 新增：回显已保存 annotations
  ~ POST /admin/image-labels/{id}/label       # 已支持 annotations 字段，无需改
```

### 数据库
- **无需迁移**。`image_label_annotations` 表已存在。

---

## 5. UI 设计

### 5.1 标注编辑器 Modal 结构

```
┌───────────────────────────────────────────────────────────────┐
│ 编辑标注 #123                                  [✕ 关闭]       │ ← header
├───────────────────────────────┬───────────────────────────────┤
│ [缩放 100% +/-]               │ 基本信息                       │
│                               │ 部位: [面部▼]                  │
│ ┌─────────────────────────┐  │ 是否白癜风: ⬤ 是 / ○ 否         │
│ │                         │  │ 分型: [非节段型▼]              │
│ │      大图 + 画布         │  │ 病情阶段: [稳定期▼]            │
│ │  [AI 预标注半透明]        │  │ 面积%: [3.2] (自动)            │
│ │  [管理员标注实色]        │  │ 备注: [____________]           │
│ │                         │  │                                │
│ │  ✏️ 画多边形              │  │ 白斑列表 (3 处)                 │
│ │  ↔ 移动                  │  │ ─ 白斑1 0.8%  [删除]          │
│ │  👆 选择                  │  │ ─ 白斑2 1.2%  [删除]          │
│ │  ↺ 撤销  ↻ 重做           │  │ ─ 白斑3 1.2%  [删除]          │
│ │  🗑️ 清空                 │  │                                │
│ │                         │  │ [训练数据标记 ✓ 适合训练]       │
│ └─────────────────────────┘  │                                │
│ [切换为填涂模式]                │ [取消]  [✅ 确认提交]          │
├───────────────────────────────┴───────────────────────────────┤
│ 上次操作: 添加了"白斑3" / 修改了"白斑2"  •  总面积 3.2%        │ ← footer
└───────────────────────────────────────────────────────────────┘
```

### 5.2 暗色主题适配

Admin 整体为暗色 (`#1e293b` / `#0f172a`)。编辑器需要:
- 画布背景: `#0f172a`
- AI 预标注轮廓: 半透明蓝色 (`rgba(99,102,241,0.3)`)
- 管理员标注轮廓: 实色 (按颜色轮换 `#6366f1 / #f59e0b / #10b981 / #ef4444 / #8b5cf6`)
- 表单: 用现有 `n-card` + `n-select`/`n-switch`/`n-input-number` 组件

---

## 6. 实施步骤（分 4 阶段）

### 阶段 1: 组件迁移与最小可用版
- [ ] 复制 `VitiligoContour.vue` → `web/admin/src/components/labeling/VitiligoContourAdmin.vue`
- [ ] 删除 app 端 API import，定义本地 `ContourRegion` interface
- [ ] 暗色主题适配（CSS 变量、阴影色）
- [ ] 在 `ImageLabeling.vue` 中点击缩略图直接打开 `VitiligoContourAdmin` 全屏 Modal
- [ ] 简单提交: 只传 `region_contour` JSON 字符串到 `annotations`
- [ ] **后端**: 新增 `GET /admin/image-labels/{id}/annotations` 路由

### 阶段 2: 编辑器主壳 + 完整表单
- [ ] 新建 `LabelingEditor.vue` 整合: 左侧画布 + 右侧表单 + 顶部工具栏
- [ ] 完整表单: 部位、分型、阶段、面积% (自动算)、备注、训练标记
- [ ] 多白斑管理列表
- [ ] 撤销/重做 30 步历史
- [ ] AI 预标注回显

### 阶段 3: 填涂模式
- [ ] 复制 `MaskEditor.vue` → `MaskEditorAdmin.vue`
- [ ] 暗色主题适配
- [ ] 在编辑器内加"切换为填涂模式"开关
- [ ] 填涂 → `mask_data` PNG 提交，面积自动算

### 阶段 4: 训练数据导出增强
- [ ] 扩展 `TrainingExportRequest` 增加导出 PNG mask 字段
- [ ] 在 admin 导出界面增加"导出 (image, mask) 对到 OSS"按钮
- [ ] 配套文档: `docs/admin-image-labeling-training.md`

### 部署策略
- 每个阶段完成后**立即部署到 staging**（遵循 AGENTS.md 强制规范）
- 阶段 1+2 完成 → 用户验收 → 推正式
- 阶段 3+4 完成 → 用户验收 → 推正式
- 所有部署记录写入 `DEPLOY_LOG.md`

---

## 7. 风险与备选方案

| 风险 | 应对 |
|---|---|
| 复制组件后 admin 主题不一致 | 阶段 1 先做最简圈选+提交，主题留到阶段 2 统一调 |
| `mask_data` PNG data URL 太大（>1MB） | 提交前在浏览器用 `canvas.toBlob(quality=0.8)` 压缩 |
| 后端 `mask_data` 字段是 TEXT，存大图不够 | 若发现超过 5MB 警告，升级到独立 OSS + 字段改存 URL；目前 admin 标注场景以小图（手机拍摄~500KB）为主，预计不会触发 |
| 多个管理员同时标注同一张图 | 后端乐观锁：`updated_at` 校验，冲突时返回 409 |
| VLM 预标注 JSON 解析失败 | 静默降级: 跳过 AI 轮廓，仅展示空画布 + 提示"AI 标注不可用" |
| 撤销/重做 30 步会内存溢出 | 已存在的 MaskEditor 用了 `ImageData` 浅拷贝，问题不大；多边形用深拷贝更省内存 |

---

## 8. 验收标准

- [ ] admin 用户在"待标注" Tab 点击缩略图，能看到大图并用鼠标圈选 1+ 处白斑
- [ ] 圈选后多边形自动求面积并填入表单"面积%"
- [ ] 提交后状态从 `pending` 变为 `labeled`，且数据库 `image_label_annotations` 表有对应记录
- [ ] "已标注" Tab 行的"编辑"按钮能打开已有标注并继续编辑
- [ ] 训练数据导出 JSON 含 `region_contour`/`mask_data` 字段
- [ ] 移动端不要求完整功能，但 Modal 能正常打开不报错
- [ ] 部署到 staging 后 `https://staging-admin`（或 admin 入口）可访问

---

## 9. 相关文档引用

- 后端数据模型: `web/backend/models/image_label.py:160-205` (`ImageLabelAnnotation`)
- 后端 API: `web/backend/api/image_label.py:362-428` (`admin_label_image`)
- 测评页参考组件: `web/app/src/components/tracker/VitiligoContour.vue`
- 测评页填涂组件: `web/app/src/components/tracker/MaskEditor.vue`
- 部署规范: `AGENTS.md` 强制 staging → production 流程
- `DEPLOY_LOG.md` 必须记录每次变更
