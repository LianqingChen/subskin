# 第七十四轮预设：新增生成无斑纹理的配对续训

用内置 imagegen 各生成一张 light-arm、dark-arm、light-hand、dark-hand 虚拟底图，固定提示 `Fictional computer-generated [light/dark]-toned human [forearm/hand] with realistic healthy skin texture, natural creases, hair follicles and subtle shadows, no white patches or scars, isolated against a flat bright cyan background visible in all four corners, horizontal photographic composition, no text or watermark.` 不使用真实患者照片；不重试、挑选或替换失败源，保存所有提示与hash。自动用原生四角像素中位色作为青幕基准，所有角R<130、G/B>150，角间欧氏最大差≤45；按原比例将原生像素缩放到512并用基准色填边，背景定义为距基准RGB欧氏距离≤45，腐蚀7×7得到非青幕核心，核心占画布10–90%。该核心可能包含指甲、毛发或偶发生成伪影；提示要求无斑不保证模型输出无斑，阴性标签只是弱假设、非医疗真值。若任一源缺失或自动门槛失败，不进行训练，完整报告失败。

每源复制6次，共24个弱阴性配对（两幅输入与标签完全相同，核心=1，其余=255，不生成伪白斑）；此类配对的排序损失为0。将第69轮训练计划中96旧配对缩减到随机72对，加24弱阴性配对；原96个程序正负配对不变，总步数保持192对/轮。其余均固定第69轮起点、两种子、三轮、随机种子、同步增强、优化器、CE+Dice及0.1排序损失；额外负例及旧样本比例同时改变，不能仅归因于生成器纹理。无第73轮困难阴性附加项。第70/71轮已观察源仅用于完成后的诊断，绝不加入训练；开发320图及诊断不用于选checkpoint。固定最后一轮，检查第47轮联合门槛并对比第69轮同种子。

在第71轮相同已观察场景、位置、曝光上比较，基线逐项复现；保留所有生成和推理失败，不调参、不启用。归档生成图、青幕核心、标签假设、哈希、训练和评估结果；生成模型预训练来源未知，不能推断真实患者表现或99.99%。不改共享后端、registry保持禁用、不部署。
