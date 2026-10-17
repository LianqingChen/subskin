# 白斑自动识别 + 后台打标/训练链路 — 任务计划（2026-10-17）

方案：`hermes_plan/2026-10-17-assessment-auto-detection-plan.md`。用户 10-17 批准"按顺序推进，并同步修订后台打标，打通 用户上传→管理员审核→模型训练"。

## 阶段
- [x] P1 后端 L1 皮肤解析 `skin_parsing.py` + L2 初稿 `lesion_draft.py`，接入 `inference._interactive_reference`（MediaPipe 不可用/未识别到人时保留旧阈值回退）；测试；离线评测 `eval_boundary_quality.py --source auto`
- [x] P2 前端记录页：初稿预填文案；L3 负点（点正常皮肤去除）
- [x] P3 后台后端：RGB 标注泄漏进旧训练的守卫；RGB 金标准审核状态 + 授权校验；重新生成 AI 初稿；数据集导出（ml manifest）；训练/评测任务；达标后登记
- [x] P4 后台前端：RGB 标识、授权状态、审核通过、训练面板 RGB 模型区
- [x] P5 测试回归、部署（测试前端 + 后台 + 后端/worker 重启）、DEPLOY_LOG、记忆

## 约束
- 后端/worker 共享，重启影响全部用户；worker 无网络、只读系统、2核/4G
- 后台构建即上线
- 正式前端不发，等用户确认
- 训练只用 `label_training_decision` 通过的授权数据；不下载公开数据集（许可证未批）

## 决策记录
- 初稿高置信写白斑层、窄带写 uncertain；对比不足时全部降为 uncertain（不硬给）
- 唇部计入皮肤但不自动标；眼/眉/眼镜不计皮肤

## 结果（2026-10-17 09:14 部署到测试环境/后台/共享后端）
- 新增：`services/rgb_segmentation/{skin_parsing,lesion_draft,dataset_pipeline,training_job}.py`、`api/rgb_training_admin.py`、后台 `components/training/RgbSegmentationPanel.vue`
- 测试：`tests/assessment/test_rgb_auto_draft.py`(6)、`test_rgb_dataset_pipeline.py`(5)、前端 tap-to-remove(1)；后端全量 541 过 / 15 既有失败
- 端到端冒烟（隔离目录）：6 合成用户 → 金标准 → 导出 → 子进程训练 2 轮 → 评测 → 门槛正确拒绝
- 现网数据：记录页标注 12 条、管理员已标 0、金标准 0 —— 训练链路已通，下一步是标注人力（建议先标 60~100 张、≥5 位用户）
- 未做：L5 纵向对齐；公开数据集预训练（许可证待批）；DINOv2（torch.hub 远程代码被权限拒绝）
