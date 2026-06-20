# Admin 图片打标模块优化 — 实施完成

**日期**: 2026-06-02
**状态**: 全部 4 阶段完成 + 统一部署待执行
**工作目录**: `/root/subskin/web/`

---

## 实施概览

| 阶段 | 目标 | 状态 |
|---|---|---|
| 1 | 迁移 VitiligoContour → admin (多边形圈选版) | ✅ |
| 2 | LabelingEditor.vue 完整编辑器 (表单+撤销+多白斑+AI回显) | ✅ |
| 3 | 迁移 MaskEditor → admin (像素填涂版) | ✅ |
| 4 | AI 一键预标注 + 训练数据导出增强 | ✅ |
| 5 | 统一部署 staging 验收 | ⏳ |

---

## 新增/修改文件清单

### 前端 (admin)
- **新增** `web/admin/src/components/labeling/VitiligoContourAdmin.vue` (419 行)
  - 多边形圈选编辑器 (SVG)
  - 支持 select / draw / move 三种模式
  - 拖拽缩略图变多边形
  - 与 VitiligoContour.vue 行为一致
- **新增** `web/admin/src/components/labeling/MaskEditorAdmin.vue` (≈480 行)
  - 双层画布 (皮肤层 + 白斑层)
  - 皮肤画笔 / 白斑画笔 / 橡皮擦 / 撤销重做 (30 步)
  - 像素级动画轮廓 (粉色虚线)
  - 面积实时统计
- **新增** `web/admin/src/components/labeling/LabelingEditor.vue` (≈600 行)
  - 模式切换 (多边形/填涂)
  - 完整标注表单 (部位/分型/阶段/VASI/脱色程度/备注/训练标记)
  - 多白斑管理列表
  - AI 预标注回显 (蓝色半透明 + 提示)
  - Ctrl+Z/Y 撤销重做
  - 加载已有标注 (编辑模式)
- **重写** `web/admin/src/views/ImageLabeling.vue` (23 KB)
  - 缩略图点击 → 打开 1400×92vh 全屏编辑器
  - AI 一键预标注按钮 (机器人图标 + 旋转动画)
  - 实时显示 AI 标注数 / 管理员标注数
  - 移动端响应式 (768px 切换布局)

### 后端 (FastAPI)
- **修改** `web/backend/api/image_label.py` (新增 3 个端点, 1 个增强)
  - `POST /admin/image-labels/{id}/ai-pretrain` — AI 推理生成 contours (走 VASI service, 不入库)
  - `GET /admin/image-labels/{id}/annotations` — 加载已有人工标注 (编辑回显)
  - `DELETE /admin/image-labels/{id}/annotations` — 清空重做
  - `GET /admin/image-labels/training-manifest` — 下载训练数据 manifest
  - 增强 `POST /admin/image-labels/training-export` — 写入 JSON manifest 到 `/root/subskin/data/training_manifests/`

### 不变 (向后兼容)
- `image_label_annotations` 表 (字段全部就位)
- `POST /admin/image-labels/{id}/label` (已支持 annotations 列表)
- 数据库 schema 完全无修改

---

## 数据流

```
[用户上传照片]
    ↓
[VASI 推理] → ai_details.contours → image_label.ai_*
    ↓
[Admin 点击"开始标注"]
    ↓
[打开 LabelingEditor] → 加载 ai_details.contours 作为 AI 预标注 (蓝色)
    ↓
[Admin 点击"AI 一键预标注"] → POST /ai-pretrain → VASIService 重新推理
    ↓ (返回 contours 实时回显)
[Admin 圈选 / 填涂] → 在 AI 基础上微调
    ↓
[确认提交] → POST /label → 写 image_label_annotations (多行, 区分 source=admin)
    ↓
[Training export] → 打包 (image_url, region_contour, mask_data) 三元组
```

---

## 训练数据 manifest 结构

```json
{
  "export_time": "2026-06-02T15:30:00",
  "split_ratio": "80/10/10",
  "total_count": 152,
  "include_ai": true,
  "include_user": true,
  "items": [
    {
      "image_label_id": 1234,
      "image_url": "https://subskin.cn/data/uploads/abc.jpg",
      "image_hash": "sha256:...",
      "split": "train",
      "body_site": "face",
      "is_vitiligo": true,
      "vitiligo_type": "non_segmental",
      "vitiligo_stage": "progressing",
      "area_percentage": 3.5,
      "vasi_score": 0.45,
      "depigmentation_level": 0.85,
      "admin_notes": "边界清晰, 近期扩散",
      "contours": [
        {
          "region_index": 0,
          "body_site": "face",
          "is_vitiligo": true,
          "vitiligo_type": "non_segmental",
          "area_percentage": 2.1,
          "polygon": [[0.1, 0.2], [0.3, 0.25], ...],
          "bbox": {"x": 0.1, "y": 0.2, "w": 0.25, "h": 0.15},
          "notes": "右颧骨处"
        }
      ],
      "mask_count": 0
    }
  ]
}
```

> 填涂模式 (mask_data) 数据量大, manifest 不内嵌, 通过 `image_label_id` 反查:
> `GET /admin/image-labels/{id}/annotations` 即可拿到每张图的 PNG mask data URL。

---

## 部署流程

按 AGENTS.md 规范, 当前环境为生产, 所有改动**必须先部署到 staging 验收**:

1. **后端** — `web/backend/` 改动
   - 重启: `systemctl restart subskin-backend`
   - 验证: `curl http://localhost:8000/api/vasi/admin/image-labels/{id}/ai-pretrain` (POST, 需 admin token)

2. **前端 admin** — `web/admin/` 改动
   - 构建: `cd /root/subskin/web/admin && npm run build`
   - 部署 staging: `rsync -av dist/ /usr/share/nginx/html/subskin-staging/`
   - 部署正式: `rsync -av dist/ /usr/share/nginx/html/subskin-admin/`

3. **nginx 刷新**: `nginx -s reload`

---

## 使用指南 (给运营/皮肤科医生)

1. 进入 admin → "图片打标管理"
2. 选择 "待标注" 标签页
3. 点击缩略图或 "开始标注" 按钮
4. 弹出全屏编辑器:
   - **AI 一键预标注** 按钮 — 机器人图标, 点击后 10s 等待 AI 推理
   - 蓝色半透明多边形 = AI 预标注
   - 切换到 "多边形圈选" / "像素填涂" 模式
   - 右侧填写: 部位/分型/阶段/VASI/备注
   - 勾选 "作为训练数据" — 默认为勾选
5. 确认提交 → 数据库写入多行 annotations
6. "导出" 按钮 → 训练集/验证集/测试集划分 + manifest 下载

---

## 风险点 & 已知限制

1. **AI 预标注性能**: 调用 VLM 推理约 10-30s, 用 `precision="quick"`, 正式版可加 cache
2. **Mask 数据大小**: 大面积填涂的 PNG data URL 可能 1-2MB, 建议 800×600 以下图片
3. **多边形坐标**: 归一化坐标 (0-1), 与 ai_details 一致, 训练时可乘 image_width/height 还原
4. **千问 VLM 集成**: 当前用 SubSkin 自有 VASI service (qwen-vl-plus), 暂未单独拉千问 SKILL 集成 (自有体系已覆盖, 风格统一)
5. **服务端 base_url**: `_download_image_to_bytes` 走外网拉图, 若 OSS 限内网需改用本地路径

---

## 后续可扩展

- [ ] 半自动预标注: AI 标注后自动填入轮廓, 管理员仅微调
- [ ] 多图片批量标注: 一次打开多张图, 共享表单状态
- [ ] 标注质量评估: 管理员间一致性 (Cohen's Kappa) 统计
- [ ] 主动学习: VLM 推理时优先选"不确定"的图片请求人工标注
- [ ] 千问 VL 直接调用: 在 admin 端集成千问 SKILL 异步推理 (降级方案)
