# 外部调研、参考项目与证据索引

访问日期：2026-10-06。采用GitHub公开API、官方站点、NICE、政府法律文件和Europe PMC医学索引。没有下载患者数据、权重或商业许可材料，也未进行模型复现。下述“可参考”均不等于临床有效或可直接商用。

## 1. GitHub项目与工具

| 编号/项目 | 已核实内容 | 许可证/成熟度 | 对SubSkin的作用与建议 |
|---|---|---|---|
| G1 [GloW-VSNet 白癜风分割](https://github.com/YuhanZheng0327/Weakly-Supervised-Vitiligo-Lesion-Segmentation) | 医生涂鸦引导弱监督全视野白癜风分割，关联Medical Image Analysis论文；最后推送2025-12 | API未显示LICENSE；README有demo且说明更多细节待发布 | 最贴近任务；联系确认代码/权重/数据许可，先独立复现小样本，不直接部署 |
| G2 [Vitiligo-Identification-CNN](https://github.com/birajadash/Vitiligo-Identification-CNN) | TensorFlow/Keras二分类；README明确Google图片搜索收集 | MIT代码；2024最后推送；未核实独立临床验证 | 可看基础实验，但其网络图片来源/标签方式不适合作为生产数据路线 |
| G3 [VIRdb](https://github.com/samuelbharti/VIRdb) | 白癜风差异表达基因、蛋白靶点与天然化合物信息资源 | 仓库CC0；2020最后推送；上游内容和时效另查 | 可参考“疾病—靶点—药物—证据”结构，是研究知识库而非照片识别模型 |
| G4 [SCIN](https://github.com/google-research-datasets/scin) | 5000+自愿贡献、10000+图；症状/病史、医生回顾标签、肤色 | 专用SCIN Data Use License；公开已知重复和缺失问题 | 最值得参考的用户贡献流程、数据卡和标签来源；不是白癜风分割专用集 |
| G5 [Derm Foundation](https://github.com/Google-Health/derm-foundation) | 皮肤图像embedding和使用notebook | 代码Apache2；权重按HAI-DEF；官方已标legacy | 可作已有基线；新项目官方推荐MedSigLIP |
| G6 [Fitzpatrick17k](https://github.com/mattgroh/fitzpatrick17k) | 16577临床图、114类疾病、从两图谱来源整理肤型标签 | 仓库API未给license；上游图权利必须另审 | 参考公平性和标签主观性；不因可下载就商用，不把肤型当肤色真值 |
| G7 [MedSAM](https://github.com/bowang-lab/MedSAM) | 医学图像提示分割及轻量相关实现 | Apache2代码；数据/权重/依赖条款仍核对 | 可减少标注操作；RGB白斑域需实测，不能代替医生参考 |
| G8 [nnU-Net](https://github.com/MIC-DKFZ/nnUNet) | 医学分割配置、训练和推理框架 | Apache2；活跃维护 | 适合做可复现基线，RGB任务仍需适配；首期轻量U-Net可能更经济 |
| G9 [MONAI](https://github.com/Project-MONAI/MONAI) | 医疗图像变换、训练与评测组件 | Apache2；活跃维护 | 按需使用，避免首期多框架并存 |
| G10 [Label Studio](https://github.com/HumanSignal/label-studio) | 图像/文本/时序标注、导出、ML接线 | 开源代码Apache2；企业功能有独立条件 | 现有标注后台不足时自托管补充；先复用自己的画布 |
| G11 [CVAT](https://github.com/cvat-ai/cvat) | 自托管图像/视频标注、任务/数据管理 | Community MIT；企业/托管功能另议 | 批量像素标注候选；必须接私有权限与临时访问 |

搜索方法：[GitHub vitiligo仓库检索](https://github.com/search?q=vitiligo&type=repositories)，并通过`api.github.com/search/repositories?q=vitiligo`及仓库/readme API核对。多数返回为研究实验或演示；本次没有找到经过核实、可直接部署且包含完整患者授权—专家标注—临床验证—研究合作的白癜风平台。该结论限于本次检索，不能宣称全球没有类似项目。

项目星数仅用于发现线索，既不代表质量也不代表临床有效；不以星数制定模型优先级。

## 2. 公共数据与基础模型的实际可用性

| 编号/资源 | 已核实事实 | 可以借鉴 | 使用限制 |
|---|---|---|---|
| D1 [SCIN官方说明](https://research.google/blog/scin-a-new-resource-for-representative-dermatology-images/) | 自愿同意、IRB研究、近景/远景、1–3医生回顾标签；明确不等同临床确诊 | 与SubSkin患者贡献方式高度接近；可参考数据卡、未知和质控 | 专用[数据许可](https://github.com/google-research-datasets/scin/blob/main/LICENSE)需逐条遵守；禁止重新识别。不能假定有像素mask或足够白癜风病例 |
| D2 [DDI](https://ddi-dataset.github.io/) | 656张/570患者、多肤色、病理参考；官方条款仅个人非商业研究 | 公平性与域外测试方法、独立诊断参考 | 不能直接用于商业训练/服务；用途需要单独许可。并非白癜风专用集 |
| D3 [ISIC Archive](https://www.isic-archive.com/) | 皮肤图像集合、研究/挑战/标注基础设施；主要肿瘤相关 | 图库元数据、集合版本、质量和标注工作流 | 集合、成像方式及每项许可证分别核对，不当作手机白癜风图集 |
| D4 [HAM10000论文](https://www.nature.com/articles/sdata2018161) | 10015张色素性皮肤病灶皮肤镜图，7类 | 分组数据与模型评测实例 | 图像域/任务不匹配；论文开放许可不自动代表全部数据用于商业无条件许可 |
| D5 [MedSigLIP官方](https://developers.google.com/health-ai-developer-foundations/medsiglip) / [模型卡](https://huggingface.co/google/medsiglip-448) | 医学图像与文本embedding，含多种医学影像域；按HAI-DEF条款 | 冻结特征+小样本分类/检索基线，控制训练成本 | 没有证明白癜风分型/活动临床性能；需适配、许可与本地验证 |
| D6 [Derm Foundation模型卡](https://developers.google.com/health-ai-developer-foundations/derm-foundation/model-card) | 页面明确legacy、推荐MedSigLIP；只生成embedding，不提供诊断 | 对现有实验可比较 | 代码Apache2不覆盖权重HAI-DEF；新依赖选择按当前状态 |

数据与代码可获得性、允许的法律用途、疾病/人群/成像匹配、临床参考质量、像素标签和独立测试，是六个不同条件。任何一项不满足，不能作为直接商用模型的数据来源。

## 3. 全球公司与项目对标

| 编号/项目与主要市场 | 本次核实的产品方向 | 对SubSkin启发 | 不可类推的部分 |
|---|---|---|---|
| C1 [Vitiligo Research Foundation](https://vrfoundation.org/)，全球非营利 | 官网与[Research Tools](https://vrfoundation.org/tools)可读：教育、AI Guide、地图、Biobank/CloudBank、研究资助和患者试验连接 | **最接近整体规划的案例**：患者长期记录、临床资料和研究资源连接；可参考[研究协作入口](https://vrfoundation.org/researchers_opportunities) | 官网规模/匿名化/疗法表述属于机构自述，需独立审阅；页面仍有2021资助内容，数量与项目实时性不能假定 |
| C2 [SkinVision](https://www.skinvision.com/)，欧洲/国际 | 手机皮肤风险检查、皮肤健康监测，团队/科学页面 | 用户图像引导、长期监测与付费服务设计 | 聚焦皮肤癌风险，不能推导白癜风准确率或中国注册/收费可行性 |
| C3 [Skin Analytics DERM的NICE指导](https://www.nice.org.uk/guidance/htg746/chapter/1-Recommendations)，英国 | NHS远程皮肤科疑似皮肤癌转诊路径中使用；证据生成期有条件推荐 | 机构集成、限定用途、前瞻证据与成本评估 | 不是白癜风工具；不是无条件自动诊断许可；深肤色需专业复核等保障 |
| C4 [Miiskin](https://miiskin.com/) / [机构方案](https://miiskin.com/pro/plans-pricing/)，美国/国际 | 患者照片提交、皮肤科工作流、同意模板、支付、机构服务 | 复诊资料、远程采集和按使用/机构付费更贴近当前商业阶段 | 持牌医生/地区许可和支付条件不同，中国不能直接复制诊疗模式 |
| C5 [Skinive](https://skinive.com/)，欧洲/国际 | AI skin scanner、mole checker与追踪 | 用户图像入口、持续记录的产品表达 | 官网营销不证明白癜风任务有效，不照搬精度或资质声明 |
| C6 [Haut.AI](https://haut.ai/)，欧洲/国际美容行业 | AI皮肤分析、护肤产品推荐、品牌接入 | 图像质量、B2B组件、推荐与测量的界面 | 偏美容商业，官网精度自述不是白癜风临床证据；不能让商品利益左右医学结论 |
| C7 [PatientsLikeMe商业说明](https://support.patientslikeme.com/hc/en-us/articles/201245750-How-does-PatientsLikeMe-make-money)，美国 | 既有2026-09-20研究记录了患者支持/研究/试验合作方向 | 患者社区与机构服务可有不同付款方 | 本次官方页403，仅历史研究参照，未重新完整核实当前模式 |
| C8 [UMass Vitiligo Clinic & Research Center](https://www.umassmed.edu/vitiligo/)，美国 | 白癜风临床与转化研究方向为既有公开线索 | 医院PI、患者研究、机制研究协作可作后续联系清单 | 本次官网403，未核实最新队列/项目规模，不计可直接合作资源 |
| C9 [VALIANT研究](https://pubmed.ncbi.nlm.nih.gov/37647073/)，国际研究 | 17国3541纳入分析患者；线上患者自报的横断面负担调查 | 患者结局、心理/生活质量及多国调查设计 | 不是纵向图库、治疗试验或训练模型；描述/假设生成不证明治疗因果 |
| C10 [VIRdb](https://github.com/samuelbharti/VIRdb)，研究资源 | 差异基因、靶点和相关化合物 | 未来研究百科连接公开组学的结构 | 不代表候选药已有效，不能用计算靶点直接推荐治疗 |

对标结果：整体患者—数据—研究协作学VR Foundation的CloudBank/Biobank思路，用户贡献与数据卡学SCIN，图库基础设施学ISIC，标注与研究任务学白癜风分割论文，记录/机构工作流学Miiskin，医学用途验证学NICE DERM，科研知识结构学VIRdb。每项学习解决一个具体问题，无需复制其他平台所有功能。SubSkin首年只做信息与软件数据，不开展生物样本采集。

## 4. 医学与政策证据

| 编号 | 来源 | 本方案使用的事实/含义 |
|---|---|---|
| M1 | [全球负担系统综述，PMID38552651](https://pubmed.ncbi.nlm.nih.gov/38552651/)；[DOI](https://doi.org/10.1016/S2468-2667(24)00026-4) | 2024；医生确诊终生患病率建模0.36%，口径/区间明确；不套为中国商业付费市场 |
| M2 | [BAD白癜风指南，PMID34160061](https://pubmed.ncbi.nlm.nih.gov/34160061/)；[DOI](https://doi.org/10.1111/bjd.20596) | 临床指南可作编辑/医学评审基础；具体建议须读全文并考虑中国适用性 |
| M3 | [GloW-VSNet，PMID41468636](https://pubmed.ncbi.nlm.nih.gov/41468636/)；[DOI](https://doi.org/10.1016/j.media.2025.103920) | 弱监督白癜风分割；摘要说明两公共两私有数据集。先核实实际数据可用性，不假定公开所有资料 |
| M4 | [白癜风AI数字测量，PMID42081176](https://pubmed.ncbi.nlm.nih.gov/42081176/)；[DOI](https://doi.org/10.1007/s13555-026-01736-8) | 2026研究使用临床试验交叉偏振照片、U-Net和F-VASI一致性；该成像域不能泛化到普通手机照片 |
| M5 | [可解释白癜风/炎症后减色鉴别，PMID42497363](https://pubmed.ncbi.nlm.nih.gov/42497363/)；[DOI](https://doi.org/10.2196/81942) | 332张，patient-wise交叉验证；小规模受限二分类，不能推出开放场景所有白斑鉴别性能 |
| M6 | [DDI公平性论文，PMID35960806](https://pubmed.ncbi.nlm.nih.gov/35960806/)；[DOI](https://doi.org/10.1126/sciadv.abq6147) | 多肤色域外性能与医生图像标签也可能有偏差，必须分组评估 |
| M7 | [VALIANT负担研究，PMID37647073](https://pubmed.ncbi.nlm.nih.gov/37647073/)；[DOI](https://doi.org/10.1001/jamadermatol.2023.2787) | 患者心理与生活质量是研究价值；自报横断面数据不用于治疗因果 |
| M8 | [鲁索替尼三期原研究，PMID36260792](https://pubmed.ncbi.nlm.nih.gov/36260792/)；[DOI](https://doi.org/10.1056/NEJMoa2118828) | 随机试验的人群、终点、时间和对照必须记录；治疗知识不能靠购物/帖子推断 |
| M9 | [DermNet白癜风](https://dermnetnz.org/topics/vitiligo) | 分类、鉴别、评分和治疗科普框架；二级参考，图片/文字复用需许可 |
| R1 | [中华人民共和国个人信息保护法](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm) | 医疗健康敏感信息、单独同意、撤回、提供第三方/跨境等规则影响产品架构 |
| R2 | [涉及人的生命科学和医学研究伦理审查办法](https://www.gov.cn/zhengce/zhengceku/2023-02/28/content_5743658.htm) | 2023；使用健康记录、行为等信息研究纳入适用考量。研究伦理路径需机构确认 |
| R3 | [NICE DERM推荐与证据要求](https://www.nice.org.uk/guidance/htg746/chapter/1-Recommendations) | 当前页面2026-03更新，3年证据生成和持续监督；不等于完成所有医学有效性证明 |
| R4 | [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api) | 提供试验记录接口；需要更新时间、状态和地区校验，不能保证招募有效或可入组 |

医学索引使用Europe PMC `resultType=core`读取。对有全文限制的资料只采用已核实摘要，不宣称完整批判性评读。技术性能数字来自各研究的特定条件，不设置为SubSkin已达到的精度。

## 5. 当前项目证据地图

下列路径相对于仓库根目录，行号以2026-10-06工作区为准。

| 编号 | 文件 | 关键位置/证据 |
|---|---|---|
| L1 | `web/shared/site-modules.json:2` | 当前主导航与下线百科、就医经验归属、调养无真实购买 |
| L2 | `web/app/src/router/index.ts:187` | 百科重定向；88为照片对比，24为科普辅助路由 |
| L3 | `web/backend/models/vasi.py:27` | 记录、分型/阶段、图层、用户修正、训练Sample/Run/Version |
| L4 | `web/backend/models/image_label.py:51` | 类型/阶段枚举；68为ImageLabel，171区域Annotation；143训练资格 |
| L5 | `web/admin/src/router/index.ts` | 标注列表、工作区、训练面板、内容生成与规划归档真实路由 |
| L6 | `web/backend/services/vasi_model_trainer.py:78` | 旧样本收集，99排除用户删除；491逐图随机切分；MIN_SAMPLES=8仅技术门槛 |
| L7 | `web/backend/api/image_label.py:1513` | 旧导出随机split；1133加入训练样本；不能替代对象级研究授权 |
| L8 | `ml/rgb_segmentation/dataset.py:23` | 明确清单/权利、subject隔离、hash和五类像素 |
| L9 | `ml/rgb_segmentation/train.py`与`README.md:42` | validation选checkpoint、输出不自动激活；随机初始化研究基线 |
| L10 | `configs/rgb_segmentation_registry.json:2` | enabled=false、unregistered、not_trained、automatic_measurement=false |
| L11 | `web/backend/services/rag.py:598` | 向量/关键词检索；1635来源响应；已有RAG基础 |
| L12 | `web/backend/database/models.py:257` | Document来源；665/695百科文章/修订；184档案、1234治疗事件 |
| L13 | `web/backend/api/consent.py:29` | 当前四类同意；175后撤回事件；未证明具体研究对象和合作方范围 |
| L14 | `web/backend/database/models.py:638` | AuditLog模型及可更新撤回字段，不能仅凭类注释证明防篡改 |
| L15 | `web/backend/services/account_deletion.py` | 账户/文件/病例删除及ImageLabel墓碑，完整衍生/备份回收仍需测试 |
| L16 | `web/backend/app/main.py:379` | RAG、记录、RGB、consent、百科、标注/训练等已挂载路由 |
| L17 | `web/backend/api/vasi_training_admin.py:200` | 手动激活对共享服务立即生效，必须另设发布保护 |
| L18 | `web/app/src/data/care-catalog.ts:1` | 静态目录，无真实品牌价格/交易；记录工具有筹备条目 |
| L19 | `src/crawlers/pubmed_crawler.py`、`web/backend/services/content_generation.py` | 文献搜索与生成来源能力；不等于知识库事实均已审阅 |
| L20 | `DEPLOY_LOG.md` | 累计staging差异、共享后端影响、生产全量同步规则 |
| L21 | `web/backend/services/rgb_segmentation/review.py:198` | 记录页面积取用户核对后的掩膜（`final_area_percentage`）；`final_vasi_score`固定写0.0，当前没有VASI输出 |

重要区分：旧训练默认未自动激活与患者级自循环是不同实现；应审计每条路径，不能概括“所有模型都安全自动迭代”。RGB注册未训练也不证明历史U-Net绝无线上权重；本次未读取真实模型和患者数据，不推断生产模型实际精度。

## 6. 在线只读核查

本次请求：

- `https://staging.subskin.cn/version.json`：buildTime1790946023606，env=staging，lastProdBuildTime1790785135093。
- `https://subskin.cn/version.json`：buildTime1790785135093，env=production。
- 后端本机health：HTTP200，status=ok。
- 测试站记录页可见部位选择、拍照、相册、白斑对比、最近记录与登录入口。
- 测试站调养可见15项静态选购参考和筹备中的记录工具，主导航四项与源码吻合。

未登录、未上传、未获取患者历史或管理数据。线上入口存在不证明整条用户流程、临床有效性或研究授权链已验收。以上为调研时（约08:30 CST）读数，当时两环境存在累计差异。

**2026-10-06 09:16 CST复核**：测试站buildTime=1791248871004（09:07 CST），其lastProdBuildTime=1791248767263；正式站buildTime=1791248767263（09:06 CST），后端health仍为ok。两者吻合，说明调研后已完成一次正式发布并同源重建测试，当前不再有版本差异。版本读数随发布变化，只代表读取时刻；实施前以DEPLOY_LOG和当时的version.json重新核对。

## 7. 调研限制与后续核实

Google普通请求返回JS重定向，Bing完整查询结果偏离，本方案没有使用它们推断竞争格局。GitHub API和原始资料替代搜索引擎进行了有效核查。

Skin Analytics、PatientsLikeMe和UMass部分官方页受403限制；Skin Analytics使用NICE可读来源，后两项明确为限定参考。FDA页面请求未获得有效资料，未据其作监管审批结论；美国药物说明由文献/DermNet支持，任何中国上市适应证需再查NMPA和说明书。

VIRdb等旧项目需核实维护状态和上游来源；GloW-VSNet代码/权重/数据授权需联系作者。首次论文标题检索还返回鲁索替尼研究的读者来信，已用原研究DOI及PMID36260792重新核对，正式引用只用原研究。

待核实事项：当前真实独立用户/有效图片/训练权利/医学参考数量；实际收入和成本；合作医院及预算负责人；诊断/测量软件在中国的监管定性与注册要求；供应商数据留存/跨境；未成年人/样本/人类遗传资源的专门路径。实施前用授权的聚合审计形成基线，不在公开策划文档写入患者信息。

公开项目的地理市场、产品描述和商业结构只用于比较；不代表最新完整市场调查、公司估值、融资额或实际合作意向。
