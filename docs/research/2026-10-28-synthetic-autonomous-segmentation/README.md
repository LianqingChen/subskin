# 自动合成分割试验（离线）

这是一个仅用程序生成图像和掩码的**方法学试点**，不是临床数据集、真实皮肤模拟器或可部署模型。不读取真实图片和人工病灶标注，不下载预训练模型，不改变现网服务。

## 运行

依赖 Python、NumPy、OpenCV、Pillow、PyTorch；本次使用 Python 3.14、NumPy 2.5.2、OpenCV 5.0.0、PyTorch 2.13.0+cu130 的 CPU。无 GPU 要求。示例（从项目根目录）：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/experiment.py \
  --rule docs/research/2026-10-28-synthetic-autonomous-segmentation/baseline_lesion_draft.py \
  --output /tmp/synthetic-pilot.json --epochs 5 --train 512 --test 128 --seeds 2
```

脚本生成 64×64 程序图；训练生成种子 10000 起、验证 200000 起、测试 300000 起，形态测试使用多椭圆而非训练时的极坐标边界。不同分区仍共享颜色、纹理和其他渲染假设，因此不能称为独立真实域或完全独立生成器。每组使用相同生成种子，不使用真实底图。种子 0、1 控制初始化和批次顺序；数据集固定。阈值仅在验证集以正样本平均 Dice 选择，未优化无斑误报。由于针对第一轮结果决定了复查轮数，当前测试集也仅是开发性合成测试，不是最终盲测集。

基线是代码中的 `draft_lesion`，在全图都视为已知皮肤的理想条件下运行；它不是完整的现网端到端链路。记录的 SHA256 对应该次执行的源文件；冻结副本为 `baseline_lesion_draft.py`；若现网逻辑改变，应重新核对基线。四组 CNN 随机初始化，没有大模型和真实训练数据；模型与结果不得注册上线。

- simple：简单斑块训练；
- diverse：形状、局部光照干扰和无斑例；
- diverse_augmented：在 diverse 上加入光度增强及其监督损失；
- diverse_consistency：与增强组同样的训练，加预测一致性损失。

结果里的 positive Dice 仅对正样本平均，small 指生成参数的小半径而非真实病例；无斑假阳性为负样本内预测占全图比例；面积误差为全图像素占比误差的绝对值（百分点）。不存在病人、临床诊断、皮肤分割、真实面积或真实泛化结论。

## 第二轮：不同合成机制和成对曝光变化

先阅读 `round2-protocol.md`，它在测试结果产生前固定了条件与阈值规则。运行：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/test_round2.py
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round2.py \
  --output /tmp/round2-results.json --preview /tmp/round2-preview.png
```

`round2.py` 同目录读取第一轮脚本和冻结规则源码；512 张训练、128 张验证、128 张测试，15 epoch，随机种子 0/1。测试只改变合成生成方式及同图曝光，仍没有真实照片和预训练模型。`round2-report.md` 汇总试验结果。

## 第三轮：生成式底图与 SAM 编码器

`round3-protocol.md` 是运行测试前固定的方案。`generated/` 中三张图均由内置图像生成工具独立生成，作为训练、验证、测试底图按文件分离；不是用户照片。运行 `test_round3.py` 检查哈希、种子和合成标签。需要 PyTorch、NumPy、OpenCV、Pillow、项目安装的 `segment_anything` 源码以及本项目已有 SAM ViT-B 权重；请指向实际环境中的路径：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/test_round3.py
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round3.py \
  --sam-package .venv/lib/python3.9/site-packages/segment_anything \
  --sam-weights models/sam_vit_b_01ec64.pth \
  --output /tmp/round3-results.json --preview /tmp/round3-preview.png
```

预训练内容是否包含白癜风未知；实验只保证下游训练/测试素材由模型生成且无需人工病灶掩码。SAM 输入与位置编码采用非标准缩小设置，只作为冻结编码器研究。不得用于线上推理或将合成指标描述为真实识别准确率。

## 第四轮：独立虚拟底图与困难条件

测试前的条件和指标固定在 `round4-protocol.md`。两张新的虚拟底图 `test4-light.png`、`test4-dark.png` 按完整文件与训练、验证、第三轮测试底图区分；各自生成 32 个中等色差正例、32 个弱色差正例、32 个合成高光负例。复现命令（实际 Python 与 SAM 路径应按本机环境指定）：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/test_round4.py
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round4.py \
  --images docs/research/2026-10-28-synthetic-autonomous-segmentation/generated \
  --sam-package .venv/lib/python3.9/site-packages/segment_anything \
  --sam-weights models/sam_vit_b_01ec64.pth \
  --output /tmp/round4-results.json --head-dir /tmp/round4-heads
```

研究权重只保存分割头和阈值，不是可直接注册上线的完整模型；SAM 架构、原始权重、非标准输入和位置编码插值均须一起使用。每组测试裁剪来自同一张虚拟底图；弱色差可能难以看见，高光属于人为构造的负例。

## 第五轮：困难训练对照

先阅读测试前固定的 `round5-protocol.md`。执行 `test_round5.py`，再在有 PyTorch、OpenCV、Pillow、SAM ViT-B 权重和 `segment_anything` 源代码的环境中运行：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round5.py \
  --images docs/research/2026-10-28-synthetic-autonomous-segmentation/generated \
  --sam-package .venv/lib/python3.9/site-packages/segment_anything \
  --sam-weights models/sam_vit_b_01ec64.pth \
  --output /tmp/round5-results.json --head-dir /tmp/round5-heads
```

研究头部与 SAM 非标准缩小编码器组合仅供复现，不是日记页可部署模型。测试是一张虚拟底图的多张裁剪；程序掩码是模拟编辑，非医学金标准。

## 第六轮：分歧和拒判

`round6-protocol.md` 预设校准集和风险-覆盖率统计；加载 `round5-heads/` 的四个研究用头部，不重新训练：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/test_round6.py
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round6.py \
  --images docs/research/2026-10-28-synthetic-autonomous-segmentation/generated \
  --heads docs/research/2026-10-28-synthetic-autonomous-segmentation/round5-heads \
  --sam-package .venv/lib/python3.9/site-packages/segment_anything \
  --sam-weights models/sam_vit_b_01ec64.pth --output /tmp/round6-results.json
```

每档拒判阈值只从此前公开的第四轮合成集校准，测试底图独立生成；拒判图片从自动输出中排除，但总体有效召回仍以全部正例为分母。研究代码不接入线上。

## 第七轮：五类合成分割

事前方案见 `round7-protocol.md`，五类契约检查可执行 `test_round7.py`。复现命令：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round7.py \
  --images docs/research/2026-10-28-synthetic-autonomous-segmentation/generated \
  --sam-package .venv/lib/python3.9/site-packages/segment_anything \
  --sam-weights models/sam_vit_b_01ec64.pth \
  --output /tmp/round7-results.json --preview /tmp/round7-preview.png --head-dir /tmp/round7-heads
```

训练头和缩小 U-Net 是研究用产物，合成测试不代表真实医学准确率。面积占比仅为照片中被判断可见皮肤内的浅色比例，非实际面积或临床 VASI。

## 第八轮：自动提取生成手臂轮廓

预设协议见 `round8-protocol.md`。两张虚拟手臂采用程序化青色背景提取，并对边缘标记忽略。依赖 SAM 代码和权重，示例：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/test_round8.py
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round8.py \
 --images docs/research/2026-10-28-synthetic-autonomous-segmentation/generated \
 --sam-package .venv/lib/python3.9/site-packages/segment_anything \
 --sam-weights models/sam_vit_b_01ec64.pth \
 --old-heads docs/research/2026-10-28-synthetic-autonomous-segmentation/round7-heads \
 --output /tmp/round8-results.json --preview /tmp/round8-preview.png --head-dir /tmp/round8-heads
```

`round8-diagnose.py` 另行用保存的权重统计精确率、召回及空预测，运行参数可通过 `--help` 查看。合成结果不能视作真实医学识别。

## 第九轮：虚拟手部多形态

协议、质量门槛及模型前的指缝分割修订见 `round9-protocol.md`；测试自动标签运行 `test_round9.py`。示例：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round9.py \
 --images docs/research/2026-10-28-synthetic-autonomous-segmentation/generated \
 --old-heads docs/research/2026-10-28-synthetic-autonomous-segmentation/round8-heads \
 --sam-package .venv/lib/python3.9/site-packages/segment_anything \
 --sam-weights models/sam_vit_b_01ec64.pth --output /tmp/round9-results.json \
 --preview /tmp/round9-preview.png --head-dir /tmp/round9-heads
```

预览与结论仅限生成图与程序掩码；不允许将研究头注册上线。

## 第十轮：损失消融与边界诊断

协议见 `round10-protocol.md`，检查运行 `test_round10.py`。复现需要第九轮研究头、生成源图及项目 SAM 权重：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round10.py \
 --images docs/research/2026-10-28-synthetic-autonomous-segmentation/generated \
 --old-heads docs/research/2026-10-28-synthetic-autonomous-segmentation/round9-heads \
 --sam-package .venv/lib/python3.9/site-packages/segment_anything \
 --sam-weights models/sam_vit_b_01ec64.pth --output /tmp/round10-results.json \
 --preview /tmp/round10-preview.png --head-dir /tmp/round10-heads
```

边界 F1 只对存在有效合成边界的图片统计，报告可计算数量；不可将其当作临床指标。

## 第十一轮：生成编辑对照与自动差分

使用已有纯虚拟底图和 `generated/round11-control.png`、`generated/round11-edited.png`，先阅读 `round11-protocol.md`；无临床金标准，结果仅供标签质量研究：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/test_round11.py
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round11.py \
 --source docs/research/2026-10-28-synthetic-autonomous-segmentation/generated/train8-arm.png \
 --control docs/research/2026-10-28-synthetic-autonomous-segmentation/generated/round11-control.png \
 --edited docs/research/2026-10-28-synthetic-autonomous-segmentation/generated/round11-edited.png \
 --out-dir /tmp/round11-output
```

固定门槛未通过，差分候选没有用来训练，不得注册上线。

## 第十二轮：生成编辑一致性与已知小斑对照

方案见 `round12-protocol.md`。`test_round12.py` 验证连通域和召回计数；`round12.py` 仅生成程序已知标签的正对照。生成模型编辑的自动差分仍使用 `round11.py`；事后平移和旋转诊断分别在 `round12-translation-diagnostic.py` 和 `round12-motion-diagnostic.py`。所有脚本参数可用 `--help` 查看。两组生成编辑均未通过质量门槛，不能将候选用于训练。

## 第十三轮：配准质量门槛

预设方案见 `round13-protocol.md`，结果为合成研究并保存在 `round13-results.json`。复现需 NumPy、OpenCV、Pillow：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/test_round13.py
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round13.py \
 --light docs/research/2026-10-28-synthetic-autonomous-segmentation/generated/test8b-arm.png \
 --medium docs/research/2026-10-28-synthetic-autonomous-segmentation/generated/test10-arm.png \
 --output /tmp/round13-results.json
```

该门槛只供研究：两个配准方法一致并不保证准确；不可用于模型注册或临床宣称。

## 第十四轮：纹理特征配准

`round14-protocol.md` 固定初始仿射对照；`round14-stress-protocol.md` 是观察初始结果后的附加压力方案。运行 `test_round14.py` 和 `test_round14_stress.py` 检查契约；`round14.py` 及 `round14-stress.py` 使用 `--images` 指向 generated 目录，并用 `--output` 指定结果路径。研究结果不能用于注册训练标签。

## 第十五轮：鲁棒亮度映射

`round15-protocol.md` 固定颜色映射及光照条件，`test_round15.py` 检查拟合与源图。复现命令：

```bash
OPENBLAS_NUM_THREADS=1 python docs/research/2026-10-28-synthetic-autonomous-segmentation/round15.py \
 --light docs/research/2026-10-28-synthetic-autonomous-segmentation/generated/test15-light.png \
 --dark docs/research/2026-10-28-synthetic-autonomous-segmentation/generated/test15-dark.png \
 --output /tmp/round15-results.json
```

模拟标签不能作为临床真值，研究结果不接入产品。

## 第十六轮：局部光照与模拟斑块大小

事先方案和初次门槛信息泄漏修复记录见 `round16-protocol.md` 与 `round16-report.md`。`test_round16.py` 包含自动门槛不得读取真值的检查；有效重跑数据为 `round16-results.json`，`round16-initial-invalid.json` 仅供错误审计，不应用作结论。

```bash
OPENBLAS_NUM_THREADS=1 python docs/research/2026-10-28-synthetic-autonomous-segmentation/round16.py \
 --light docs/research/2026-10-28-synthetic-autonomous-segmentation/generated/test16-light.png \
 --dark docs/research/2026-10-28-synthetic-autonomous-segmentation/generated/test16-dark.png \
 --output /tmp/round16-results.json
```

## 第十七轮：只读现网纯函数对照

`round17-protocol.md` 与 `round17-report.md` 记录合成样本、现网实际回退分支和研究候选映射；`round17-initial-results.json` 保留首轮，`round17-results.json` 额外包含事后 uncertain 并集诊断。运行需可导入项目推理纯函数、MediaPipe、NumPy、OpenCV、Pillow、PyTorch、SAM 权重与代码，且 registry disabled：

```bash
python docs/research/2026-10-28-synthetic-autonomous-segmentation/test_round17.py
python docs/research/2026-10-28-synthetic-autonomous-segmentation/round17.py \
 --project-root /root/subskin \
 --images docs/research/2026-10-28-synthetic-autonomous-segmentation/generated \
 --sam-package .venv/lib/python3.9/site-packages/segment_anything \
 --sam-weights models/sam_vit_b_01ec64.pth \
 --output /tmp/round17-results.json --preview /tmp/round17-preview.png
```

命令只调用纯函数，不调用后台 job、数据库或上传；候选的并集诊断不构成真实测量。不同 Python/MediaPipe 版本可能走不同分支，需报告实际版本与模型返回 source。

## 第十八轮：虚拟人体与本机兼容诊断

`round18-protocol.md` 固定原始方案，`round18-original-results.json` 保留现网原代码在本机 MediaPipe 1.0.1 下的 ValueError；`round18-shim-protocol.md` 说明后续仅进程内的单通道维兼容处理及其限制。`round18-shim.py` 不会修改仓库中的 backend 文件或 registry，需本机 PyTorch、MediaPipe、项目 SAM 与四个研究头。请勿将 shim 视为线上已修复或将模拟区域当作临床标注；脚本命令参数使用 `--help` 查询。

## 第十九轮：原版训练器合成契约

`round19-protocol.md` 和 `round19-report.md` 记录自动生成的清单、项目原版训练/评测及事后政策、MediaPipe 维度诊断。`round19-synthetic-dataset.tar.gz` 仅包含虚拟数据，解压后 manifest 标记 `synthetic=true`，显式 opt-in 才能验证或训练；`round19-artifacts/run/model.pt` 为未启用研究权重，不允许按现有 registry 注册。所有 `review_reference` 值明确写有 no-human-review，不代表人工审核。

可在有项目依赖且 registry 禁用的隔离环境执行 `test_round19.py`，再通过 `round19_prepare.py --help` 和 `round19_run.py --help` 查看重建/训练参数；事后 `round19_policy.py` 和 `round19_baseline_shim.py` 分别重现未复核政策及仅内存的本机维度兼容诊断。所有输出目录须是新的空目录，不连接后台 job 或数据库。

## 第二十轮：无已标见病灶样本消融

协议与局限见 `round20-protocol.md` / `round20-report.md`。`round20-synthetic-datasets.tar.gz` 含相同验证/测试的两份 synthetic 清单与程序图，`round20-artifacts/` 为未启用的研究权重和评估。可在隔离环境运行 `test_round19.py`、`test_round20.py`；具体重建与训练参数见 `round20_prepare.py --help`、`round20_train_one.py --help`。`round20_union.py` 是观察结果后补充的 uncertain 并集覆盖诊断，绝非确认测量。

## 第二十一轮：验证集阈值筛选

`round21-protocol.md` 固定校准门槛，`round21-report.md` 记录两组都无合格阈值；`round21-synthetic-datasets.tar.gz` 为仅含程序合成图和掩码的清单。`round21.py` 的 `--help` 列出离线参数，输入为两份 manifest 和第 20 轮权重；`test_round21.py` 检查空预测和不完整验证不能通过。研究阈值不会写入产品。

第 22 轮针对病灶损失的离线对照及结果见 [round22-report.md](round22-report.md)；它未证实真实照片性能，也没有启用任何模型。

第 23 轮针对无斑补充模型的跨来源事后复测见 [round23-report.md](round23-report.md)。

第 24 轮等训练量增加虚拟来源的对照结果见 [round24-report.md](round24-report.md)。

第 25 轮三个训练种子的事后复测见 [round25-report.md](round25-report.md)，暴露了全无斑预测的训练不稳定问题。

第 26 轮验证门槛防塌缩试验见 [round26-report.md](round26-report.md)：两次已知塌缩轨迹都没有合格 checkpoint。

第 27 轮白斑像素加权训练及其误报取舍见 [round27-report.md](round27-report.md)。

第 28 轮加权模型的验证阈值及全新虚拟来源评估见 [round28-report.md](round28-report.md)。

第 29 轮配对合成有斑/无斑训练见 [round29-report.md](round29-report.md)。

第 30 轮同批次配对一致性损失对照见 [round30-report.md](round30-report.md)。

第 31 轮局部光照困难样本训练见 [round31-report.md](round31-report.md)。

第 32 轮合成病灶配对排序损失见 [round32-report.md](round32-report.md)。

第 33 轮同形状的合成色差梯度测试见 [round33-report.md](round33-report.md)。

第 34 轮弱色差训练与新虚拟来源测试见 [round34-report.md](round34-report.md)。

第 35 轮低色差信号的忽略监督见 [round35-report.md](round35-report.md)。

第 36 轮 SAM 冻结特征头在同一合成色差集上的事后比较见 [round36-report.md](round36-report.md)。

第 37 轮冻结 SAM 预训练与随机编码器的同架构对照见 [round37-report.md](round37-report.md)。

第 38 轮冻结 SAM 分割头的白斑加权训练见 [round38-report.md](round38-report.md)。

第 39 轮合成病灶配对局部裁剪训练见 [round39-report.md](round39-report.md)。

第 40 轮固定训练量扩大虚拟来源的对照见 [round40-report.md](round40-report.md)。

第 41 轮固定多来源的弱色差训练对照见 [round41-report.md](round41-report.md)。

第 42 轮多虚拟来源验证和训练选择见 [round42-report.md](round42-report.md)。

第 43 轮合成无斑困难像素抑制见 [round43-report.md](round43-report.md)。

第 44 轮多来源验证条件概率门槛试验见 [round44-report.md](round44-report.md)。

第 45 轮高召回与保守模型联合筛查见 [round45-report.md](round45-report.md)。

第 46 轮误报连通域过滤及事后小斑诊断见 [round46-report.md](round46-report.md)。

第 47 轮多来源小可见核心训练与验证见 [round47-report.md](round47-report.md)。

第 48 轮小核心训练的轻量无斑抑制对照见 [round48-report.md](round48-report.md)。

第 49 轮局部亮度对比通道对照见 [round49-report.md](round49-report.md)。

第 50 轮同步曝光训练与共同可评估区域诊断见 [round50-report.md](round50-report.md)。

第 51 轮同形状的两种颜色合成机制对照见 [round51-report.md](round51-report.md)。

第 52 轮固定数量混合颜色机制训练与开发验证见 [round52-report.md](round52-report.md)。

第 53 轮逐图色差匹配的混合机制训练见 [round53-report.md](round53-report.md)。

第 54 轮色域保护匹配失败及事后可行性诊断见 [round54-report.md](round54-report.md)。

第 55 轮约束优先色域匹配及训练对照见 [round55-report.md](round55-report.md)。

第 56 轮生成式编辑自动差分标签的受控对齐研究见 [round56-report.md](round56-report.md)。

第 57 轮双无斑控制差分的受控对照见 [round57-report.md](round57-report.md)。

第 58 轮差分伪标签的确认与未知分层见 [round58-report.md](round58-report.md)。

第 59 轮局部不稳定区域及独立无斑控制试验见 [round59-report.md](round59-report.md)。

第 60 轮自动差分提示 SAM 的伪标签筛查见 [round60-report.md](round60-report.md)。

第 61 轮实际生成式编辑漂移可行性见 [round61-report.md](round61-report.md)。

第 62 轮生成控制漂移上的已知干预见 [round62-report.md](round62-report.md)。

第 63 轮双生成控制亮度均值配对对照见 [round63-report.md](round63-report.md)。

第 64 轮固定尺度平滑差分见 [round64-report.md](round64-report.md)。

第 65 轮新增生成控制与完整区域评分见 [round65-report.md](round65-report.md)。

第 66 轮冻结模型对生成控制干预图评估见 [round66-report.md](round66-report.md)。

第 67 轮冻结模型重叠小块推理见 [round67-report.md](round67-report.md)。

第 68 轮合成正负配对排序训练见 [round68-report.md](round68-report.md)。

第 69 轮生成控制图程序配对与离线续训见 [round69-report.md](round69-report.md)。

第 70 轮全新虚拟源冻结模型多曝光对照见 [round70-report.md](round70-report.md)。

第 71 轮分尺寸安全区域与可配对取点见 [round71-report.md](round71-report.md)。

第 72 轮固定概率门槛的误报与漏检折衷见 [round72-report.md](round72-report.md)。

第 73 轮生成控制训练中的轻量困难阴性抑制见 [round73-report.md](round73-report.md)。

第 74 轮新增生成无斑纹理的配对续训见 [round74-report.md](round74-report.md)。

第 75 轮同虚拟纹理的自动正负配对见 [round75-report.md](round75-report.md)。

第 76 轮生成模型的不规则轮廓配对训练见 [round76-report.md](round76-report.md)。

第 77 轮未参与训练的不规则轮廓诊断见 [round77-report.md](round77-report.md)。

第 78 轮防止细小合成参考核心退化见 [round78-report.md](round78-report.md)。

全程猜想、验证、结论与后续方案见 [综合研究报告（截至第78轮）](comprehensive-research-report-2026-10-31.md)。
