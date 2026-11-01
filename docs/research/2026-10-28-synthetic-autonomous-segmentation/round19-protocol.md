# 第十九轮预设方案：项目 RGB 训练器的合成数据契约验证

在训练结果前固定。只用 image_gen 虚拟身体底图及 r8/r9 程序生成五类标签，未使用实拍患者照片或人工白斑圈选。生成器及视觉预训练资料不能排除真实病例。每个底图独立生成调用并按底图哈希生成不含个人身份的伪匿名 subject，不能跨数据集拆分；相同主体的程序裁剪不得跨 split。

训练使用已有 train8-arm、train9-hand 各 64 个；验证使用已公开 test8b-arm、test9-hand 各 16 个；测试使用本轮新生成的 arm、手背各 16 个。测试两个底图各只有一张，程序变体高度相关、生成方法与训练共用，不能作为临床盲测或真实人群置信区间。r8/r9 生成五类及 255 自动边界，64×64 程序样本放大成 128×128 存储，图像双线性、标签最近邻，不增加真实细节。必须检查各类、正负例、底图哈希和 subject 不交叉。

使用仓库原版 `ml.rgb_segmentation.train`，显式 `allow_synthetic=True`，`side=128`、15 epoch、项目固定种子，验证集选模型；运行仓库原版 `evaluate` 的 TorchScript 与现网初稿基线。训练清单 synthetic=true；授权字段引用用户的本次虚拟试验请求；为满足程序字段要求，`dataset_review_id` 和 `review_reference` 使用明确的 `synthetic-generator-no-human-review` 自动来源标识，绝不宣称临床或人工审核。若原版验证器拒绝这些来源，则停止并记录，不伪造值或修改门禁。训练报告应保留 `training_source=synthetic`，`enabled=false`；registry 和后台不做任何修改，模型不可注册。

评价器输出为研究用原始掩码，不等同日记最终结果；现网 baseline 所用本机 MediaPipe 版本可能与远端不同，需额外逐例记录 `infer_rgb` 实际 source 和失败数。报告测试正例 Dice、像素精确率/召回、皮肤 Dice、误报、面积误差、样本及失败数量，注意 255 忽略比例，并明确测试集伪标签只代表程序编辑、不是医学真值。另验证导出 TorchScript 的输出五类及哈希，不把注册失败当作训练成功。用户目标的真实图像 99.99% 在当前合成约束下无法证明，不上线。

原版评估器的 TorchScript 路径使用原始 argmax，而日记页 `infer_rgb` 会将最大概率低于 0.7 的皮肤像素标为 uncertain。看过原评估结果后，补充一项事后策略诊断：固定训练出的权重及输入，不调参，按该映射调用 `apply_soft_quality` 和 `measure_rgb(reviewed=False)`，按实际成功/重拍/错误报告；用项目 `score_labels` 统计可比的合成有效像素，另列未确定面积及策略阻塞。它不修改结果、registry 或现场服务，也不能视作盲测或产品测量。

本机原版基线在初次评估中发生大量 MediaPipe 维度错误；事后补充隔离兼容诊断：复用第十八轮的仅进程内单通道维处理、相同模型和测试集，重新运行原版 baseline evaluator 并记录真实 source；原结果保留。此诊断发生在已观察测试结果之后，不能当盲测、不能断言远端同样存在错误，也不会修改共享后端。
