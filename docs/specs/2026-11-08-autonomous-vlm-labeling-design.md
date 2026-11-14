# 自主视觉模型白斑打标设计

目标是让视觉模型根据原图自主调用通用图像工具形成逐像素标签，并通过外部金标评测和可审核的通用经验修订提升，而不是预置单图答案。

## 方案选择
1. 纯文字多边形：可跨模型，但像素边界与识别不稳定，保留作对照。
2. 视觉模型选择原图色彩/空间证据，加通用像素工具：采用。工具不含病例专用权重、固定ROI、金标参数；动作可重放。
3. 直接训练视觉模型权重：本阶段不采用；百炼所选DeepSeek接口不开放该能力，且用户要优先直接API方式。

## 闭环
教学会话可对照182原图和金标，总结不含病例坐标/身份/答案的规则。候选skill冻结后，新会话只看原图、skill和工具。模型可查看网格与局部放大、选择前景/背景颜色种子、请求分割、看填充涂层并调整。评测器在预测冻结后独立读取金标，计算白斑/皮肤Dice、召回、误差和逐像素一致性。优化器据评测修改通用规则，下一轮新会话重新出稿。模型自信不是验收信号。

## 工具边界
固定白名单动作；不允许任意代码或文件路径。只允许原图及当前运行衍生图，不允许访问金标、数据库、旧182候选或个人分类器。推理只使用预训练人体解析、颜色/局部对比图像算法和模型自己选的种子；所有输入与动作哈希、版本、模型返回ID及调用用量留痕。当前182按已有三类口径评测，五类扩展单独标明，不能静默混用。

## 复用
协议与工具模型无关，Qwen/DeepSeek适配器只管认证、图片和JSON封装。模型能否通过必须逐型号实测。任何新图不能使用上一图的绝对坐标、金标轮廓或专用阈值。

## 质量与停止
每次实验设置明确的调用/动作上限，保存超时和失败，不盲目重发。候选变更不能因为在182更好就自动推广；182过关后依用户顺序换图，旧图纳入回归。跨模型迁移单独列成绩。对金标有争议，保存原图证据供人复核，不自动改真值。

## 完成证明
必须分别证明182原图独立出稿、后续新图、多个模型、skill可使用与闭环真实改善；任何一项未证实就保持目标active。单次Dice或重放哈希不能代替整个目标。


## Measured replication and retention update

Historical v5 is a single-run regression reference, not a verified stable skill. Fresh same-input initial planning changed masks despite exact deterministic pixel-tool replay. Every future research retention requires at least two independent full two-round runs per model under identical frozen instructions, image context, request parameter/endpoint fingerprints and distinct response IDs; acceptance compares worst observed primary metrics. A promising first cohort triggers the second automatically. Two repetitions do not establish statistical or cross-image reliability. The fixed skin silhouette also prevents exact full-map reproduction and must become correctable; one source-only 3px contour test regressed and was rejected. Current objective remains unmet.


2026-11-08 用户确认：外观与临床分型分域记录
可见外观独立保存多身体部位、颜色、形态、边缘、色素岛、白毛和证据；临床域独立保存AI候选、用户自报、管理员确认及明确链接的患者档案。禁止用账号owner推定患者、禁止用AI共识或mask已批准状态替代新标签的人审。保留旧ImageLabel AI/user/admin字段与逐区域临床字段来源，避免覆盖已有人工值；多部位候选不可按列表首项猜主部位。研究契约及实际双模型初审packet已实现，后台DTO/UI/导出集成尚未实施。临床类型不由RGB单图确诊。


参考标注口径投影：研究验证要求
教学/校准前必须显式记录source与target标签规范。五类遮挡3不能在legacy三类任务中无条件当背景，特别是旧口径包含唇红；没有可靠一对一映射时，教学投影视图将3/4设为未知并忽略。原批准标注保持不变，派生视图不称为新金标。教学Dice说明仅统计可对应的已知像素；目标仍按未经投影的最新批准金标评分。新增保守投影适配器与契约尚属于研究流程，不代表图像质量达标或正式skill已完成。
