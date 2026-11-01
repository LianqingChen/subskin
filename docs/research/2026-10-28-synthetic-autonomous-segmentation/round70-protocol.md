# 第七十轮预设：全新虚拟源的冻结模型多曝光对照

在查看结果之前固定四个全新imagegen生成源，编号 light-arm、dark-arm、light-hand、dark-hand；四个固定提示各一张：`Fictional computer-generated [light/dark]-toned human [forearm/hand], realistic skin texture, photographed under soft neutral light, isolated on a uniform solid cyan background with cyan visible in all four corners. No skin patches, no scars, no text, no watermark. Horizontal frame.` 方括号按编号替换为 light/dark 和 forearm/hand。然后对每个成功源用第61轮保持原图提示各生成一张控制 C，独立调用，不重试或挑选。四张全新源及四控制全部存档、提示、来源、hash、图像尺寸和失败；生成器预训练来源未知，不保证其无斑或无真实图训练。

源原生四角青色、按比例缩放填边512、皮肤核心占画布10%–90%、控制宽高比与源差≤1%、ECC仿射对齐合法，否则此源全部预设样本记失败。成功源的 C 对齐后采用第69轮自动安全取点和大/小圆生成方式（种子7005，按源固定各两个位置），每位置用 .06/.12/.28 三种RGB向255混合；控制原图作无斑阴性。阳性与阴性均用固定sRGB数值系数 .8/1.0/1.2 模拟曝光（裁剪到0–255），该处理不是相机物理模型，记录核心饱和比例及参考核心中阳性/阴性实际数值未变的比例。每源18阳/3阴，四源共72阳/12阴，不因饱和或样本差而剔除；程序alpha≥.5完整区域、大/小alpha≥.8核心作参照，程序参考非临床真值，阴阳共享C不独立。

固定第68轮 ranking-19/43 和第69轮 tuned-19/43 四个模型，不训练或调阈值，按第66轮512画布评估argmax。每样本记录大小核心召回、整体Dice、面积相对误差、核心内外预测、曝光及色差；低色差逐源/曝光分别记完全漏检，阴性记录核心预测。任何生成、坐标、推理错误逐例记失败；先验仅合计数据不改变模型选取。模型、源、控制、每例参数及预测哈希归档，全部失败保留；4模型×84例=336条记录。独立的全新虚拟源只是对这次调试的来源隔离，并不能保证与大模型预训练或其他数据无相似性；非真实患者评价，不能证明99.99%。仅离线，不训练、不更改registry或部署。
