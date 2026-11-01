# 第七十七轮预设：未参与训练的不规则轮廓诊断

固定第69轮 tuned、75轮 paired、76轮 organic 各19/43种子共6模型及哈希，不训练或选择。内置imagegen生成两个新的抽象模板各一次，不挑选、不重试：
0: `A single solid white asymmetric irregular blot silhouette with scalloped edges, centered on a pure black square background. Flat binary stencil, wide black margin, no gray, no text, no holes, not a photograph.`
1: `A single solid white narrow branching organic silhouette with several tapered lobes, centered on a pure black square background. Flat binary stencil, wide black margin, no gray, no text, no holes, not a photograph.`
按第76轮白像素≥200、最大连通域占5%–60%、不接触边界、其他白色≤1%规则筛查；任意模板失败则所有阳性按失败记录，阴性仍评估。模板必须与第76轮训练模板的文件SHA不相同；相同SHA拒绝，不能排除视觉相似或预训练关联。

固定第71轮四源和控制、种子7005原位置和大小及曝光 .8/1/1.2，青幕和配准失败状态不变；在成功位置，将模板0置于大斑、模板1置于小斑，同第76轮缩放到原圆外接方形并按1.2/.8模糊；不按预测挑选或调整。程序生成色变 .06/.12/.28，alpha≥.5为全区域参考，大/小各alpha≥.8为核心，所有参考和成功预测保存哈希。若参考超皮肤核心或核心空则该位置拒绝；曝光sRGB乘法非物理模型，记录信号消失与饱和。每模型84条（72阳/12阴），总504条，源/位置/推理失败保留；无斑结果必须逐项复现第71轮 tuned和第75/76轮对应paired/organic对照。输出小核心召回、低色差完全漏检、整体Dice、相对面积误差、2像素容差的边界F1及阴性预测比例，均按自动核心评价。

全新模板生成在权重固定后，但皮肤源已观察、同模型多次使用、模板与训练生成器相同且可能相似，并非独立临床试验；形状小斑面积较圆形变化不能单独归因。合成alpha边界不是患者白斑真值，生成模型预训练来源未知。不得训练、选模型、启用或部署，registry保持禁用且前后哈希一致；无法证明真实患者或99.99%。
