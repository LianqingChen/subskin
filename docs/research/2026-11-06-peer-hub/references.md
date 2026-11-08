# 同行页（知识共建中枢）外部调研归档 · 2026-11-06

> 配套设计文档：[`docs/specs/2026-11-06-peer-knowledge-hub-design.md`](../../specs/2026-11-06-peer-knowledge-hub-design.md)
>
> **核验口径**：✅ = 本轮已打开官方页面/权威来源核对；🔶 = 仅搜索摘要或二手来源；⚠️ = 凭背景知识、未核验，落地前必须复核。星标数、价格、API 限额均会变化，引用前请重新打开链接。

---

## 1. 开源项目（GitHub）

### 1.1 本体与生物医学知识图谱

| 项目 | 状态 | 许可 | 可复用点 | 注意 |
|---|---|---|---|---|
| MONDO（Monarch Initiative） | ✅ 白癜风 = `MONDO:0008661`；另有 `MONDO:1010125` generalized vitiligo、`MONDO:1010122` trichrome vitiligo、`MONDO:0011684` 白癜风相关多发自身免疫病易感性 1 | CC BY 4.0 ⚠️ | 疾病节点主键；xref 可串联 DOID/MeSH/OMIM/UMLS | xref 本轮未逐条核对 |
| DOID | ⚠️ 白癜风 DOID:12306 | CC0 ⚠️ | 交叉映射 | 复核 ID |
| HPO | ⚠️ | 自定义许可，商用看条款 | 表型术语（色素脱失、Koebner 现象等） | 中文译名需自核 |
| Open Targets Platform | ⚠️ | 数据 CC0 / 代码 Apache-2.0 ⚠️ | 疾病—靶点关联（JAK1/2/3、TYK2、IFNG、CXCL10 等），GraphQL / parquet | 疾病 ID 用 EFO/MONDO |
| PrimeKG（Harvard, *Sci Data* 2023） | ⚠️ | 代码 MIT，数据见 Dataverse | 抽白癜风子图做冷启动 | 静态快照，缺 2025 后新药 |
| Hetionet | ⚠️ | CC0 | 教学参考 | 基本不再更新 |
| PubTator 3.0（NCBI） | ⚠️ | 公共领域（部分全文受出版商限制） | PubMed 实体/关系标注 API，可用于抽药名、基因 | 速率限制，需缓存 |
| SemMedDB / UMLS / SNOMED CT | ⚠️ | 需许可证 | — | **不建议**：许可门槛，中国非 SNOMED 成员国 |

### 1.2 LLM 构建知识图谱

| 项目 | 状态 | 许可 / 规模 | 中文 | 结论 |
|---|---|---|---|---|
| **LightRAG**（HKUDS） | ✅ | MIT，约 40.5k★；支持增量更新与按文档删除（2025-08 起删除后自动重建图）；生产推荐 PostgreSQL，可接 Neo4j/Memgraph、Milvus/Qdrant；官方 OpenAI 兼容示例，推荐 Qwen3 系列做抽取 | 好 | **小团队首选的检索增强层** |
| **KAG**（蚂蚁 OpenSPG） | ✅ | Apache-2.0，约 9.2k★；最新 0.8.0（2025-06-27）；Schema 约束构建、图谱与文本互索引、逻辑形式多跳推理；需 Docker + OpenSPG 引擎 | 最友好 | 能力强但重，规模上来后再评估 |
| Microsoft GraphRAG | ⚠️ | MIT | 需改 prompt | 索引成本高，适合一次性批处理 |
| Neo4j LLM Graph Builder | ⚠️ | Apache-2.0 | 取决于模型 | 原型快，引入 Neo4j 运维 |
| OntoGPT / SPIRES（Monarch） | ⚠️ | BSD-3 | 英文为主 | **本体约束抽取思路**最契合：输出直接带 CURIE |
| KGGen（Stanford 2025） | ⚠️ | MIT ⚠️ | 英文为主 | 实体聚类去重思路可借鉴 |
| iText2KG | ⚠️ | 待核 | — | 增量、自定义 schema |

### 1.3 文献 / 临床试验数据源

| 源 | 状态 | 复用要点 |
|---|---|---|
| PubMed E-utilities | ⚠️ 无 key ~3 req/s，有 key ~10 req/s | 题录可展示+链接；摘要版权属出版商，不宜大段转载 |
| Europe PMC REST | ⚠️ | 开放获取子集（CC BY 等）可复用全文 |
| ClinicalTrials.gov API v2 | ✅ 页面可访问（如 NCT07865312、NCT06218082） | 美国政府数据，可展示；`query.cond=vitiligo` |
| OpenAlex | ⚠️ CC0 | 元数据、引用关系，适合聚合底座 |
| bioRxiv/medRxiv | ⚠️ | 必须标"预印本，未经同行评议" |
| Semantic Scholar | ⚠️ | 商用看条款 |
| PaperQA2（FutureHouse） | ⚠️ Apache-2.0 | 带引用溯源的文献问答，借鉴设计 |
| ChiCTR / WHO ICTRP / NMPA / CDE | ⚠️ | 无友好 API；抓取需评估合规与 robots |

> 仓库现状：`src/crawlers/` 已有 pubmed、semantic_scholar、crossref、clinical_trials、omicsdi、cma、foundation_news 等爬虫，`src/scheduler/` 每周日 03:00 增量；本地库约 7,855 篇文献（7,282 来自 PubMed）。**数据源层不是从零开始。**

### 1.4 患者研究平台 / 公民科学

| 项目 | 可借鉴 |
|---|---|
| Open Humans（MIT ⚠️） | "成员按项目授予访问权"的授权模型 |
| Zooniverse Panoptes（Apache-2.0 ⚠️） | 众包任务分级、项目内成就 |
| Sage Bionetworks Synapse | 数据使用条款、受控访问、数据集 DOI —— **机构合作治理的参照** |
| REDCap | 机构常用 EDC，对接导出即可，别重造 |
| OHDSI OMOP CDM（Apache-2.0） | 研究导出层映射到 OMOP/FHIR 提升机构信任；内部存储不必采用 |
| Apple ResearchKit/CareKit | 只借鉴电子知情同意交互 |

### 1.5 皮肤影像数据集治理

| 数据集 | 状态 | 要点 |
|---|---|---|
| **SCIN（Google, 2024）** | ✅ | 2023-03 至 11 月在美国 Google 搜索皮肤相关查询投放广告招募；"after a digital informed consent process"自愿捐赠；收到 5,749 份，5,631 份为有效皮肤图像；皮肤科医生打诊断标签，含自报 Fitzpatrick 与外行估计 Monk 肤色；发布于 SCIN Data Use License。**最接近 SubSkin 的"公众自愿捐图"范式** |
| ISIC Archive | ⚠️ | 许可标注清晰，以黑色素瘤为主，无白癜风 |
| Fitzpatrick17k | ⚠️ | 爬取自图谱网站，授权不清，不宜商用 |
| DDI（Stanford） | ⚠️ | 申请式获取，非商用 |
| 白癜风专用 | — | 公开数据少且许可参差（仓库已有 Roboflow/COCO 审计脚本）。**自有授权数据是稀缺资产，治理优先于规模** |

---

## 2. 全球同类组织与公司

| 机构 | 状态 | 模式 | 对 SubSkin 的启示 |
|---|---|---|---|
| **Vitiligo Research Foundation (VRF)** | ✅ | 2010 年 Dmitry Aksenov 创立；**CloudBank**：患者用工具追踪病情，数据"匿名收集存储"，研究者可访问；2,834 个独立数据集、生物样本库（870 份血液/血清、1,062 份毛囊）采用联邦网络模式；Patient Journey Map 研究用了 CloudBank 982 份记录 + 532 份问卷；AI 助手 Vitiligo.ai；与加拿大 Skinopathy 合作自拍识别 | 白癜风领域最像的先例。其公开页面**未说明同意流程、未说明结果如何回馈患者** —— 正是 SubSkin 可以做得更好的地方 |
| **Evidation** | ✅ 官方 Help Center/FAQ | 10,000 积分 = 10 美元；可兑 PayPal、礼品卡、预付卡、银行转账或**捐给慈善**；🔶 第三方称每日活动积分上限约 40 | **积分兑换的最接近参照：小额、封顶、可捐赠** |
| PatientsLikeMe | 🔶 | 患者自报症状/用药/疗效，聚合数据卖给医药企业；2017 年 iCarbonX 入股引发 CFIUS 审查，2019 年被 UnitedHealth 收购 | **所有权变更是信任的最大风险** |
| 23andMe | 🔶 | 2025-03 申请破产；Regeneron 2.56 亿美元中标后被 TTAM 以 3.05 亿美元反超，2025-07 交割，涉 1,500 万+ 用户数据；多州起诉 | 同意书须写明并购/破产时数据去向，并保留删除和研究退出权 |
| ComPaRe（法国 AP-HP） | 🔶 | 慢病电子队列（5.8–7 万人），电子知情同意 + 医院伦理批准，公立研究团队可申请使用；**患者可提出研究问题** | 让患者参与提问比积分更能留人；公立机构背书 |
| Healx（英国） | 🔶 | Healnet 罕见病知识图谱 + 患者组织合作做老药新用（Ataxia UK、FARA、FRAXA） | "患者组织 + AI 知识图谱 + 药企"三方模式 |
| Owkin（法国） | 🔶 | 联邦学习：模型进医院训练，数据不出院；开源 Substra | "数据不动、分析进来"的机构合作方式 |
| **医渡科技 YiduCore** | ✅ 官网 | 院内专病库 → 标准化字段 → 授权合规前提下的跨院研究网络；截至 2025-09 处理近 70 亿份授权医疗记录、专病库覆盖 98 个疾病领域 | 国内专病库标准做法；SubSkin 的差异在"患者端主动贡献 + 院外纵向记录" |
| Global Vitiligo Foundation | 🔶 | 2016 年注册，源自 Henry Ford 医院的 Vitiligo Working Group | 潜在学术合作对象 |
| VIRTUAL-UK 白癜风登记 | ✅ NCT06218082 | 英国成人与儿童白癜风登记 | 登记研究的数据字段可参考 |
| 中国白癜风精准医学研究联盟 | 🔶 | 安徽医科大学 + 复旦大学皮肤病研究所牵头（2018） | 潜在合作方；偏遗传与样本 |
| 《白癜风诊疗共识（2024 版）》 | 🔶 | 中华医学会皮肤性病学分会白癜风研究中心等 | 知识图谱中"指南推荐"层的权威来源 |
| Folia、Carenity、Inspire、HealthUnlocked、PicnicHealth、All of Us、BenevolentAI、Insilico、零氪、百度灵医等 | ⚠️ 未检索 | — | 如需可下一轮专项调研 |

---

## 3. 前沿研发进展（示例素材，发布前须以药企公告/监管机构原文复核）

| 药物 | 状态 | 要点 | 来源 |
|---|---|---|---|
| Upadacitinib（AbbVie） | 🔶 | Viti-Up-1/2 III 期达到 48 周 T-VASI50 与 F-VASI75 共同主要终点（T-VASI50：19.4% vs 5.9%；21.5% vs 5.9%）；AAD 2026 发布；**2026-07 欧盟批准**用于适合系统治疗的 ≥12 岁非节段型白癜风；2026-10 公布 76 周持续复色数据；美国状态未确认 | Dermatology Times、Medscape |
| Ritlecitinib（Pfizer） | 🔶 | 2026-07 宣布 TRANQUILLO / TRANQUILLO 2 III 期在 52 周达到复色关键终点，计划申报 | DelveInsight 汇总 |
| Povorcitinib（Incyte；中国授权 Dermavon） | 🔶 | STOP-V1/V2 III 期 52 周结果发表于 *Nature Medicine*（2026-11），F-VASI75 优于安慰剂；**2025-12 获 NMPA 突破性治疗认定**；中国成人 III 期 NCT07865312 预计 2026-11 启动 | Nature Medicine、ClinicalTrials.gov |
| 芦可替尼乳膏 | 内部文档 | `docs/business/` 记载 NMPA 2026-01-30 批准（**本轮未复核**） | 内部 |

---

## 4. 中国合规要点

| 法规 | 状态 | 对同行页的约束 |
|---|---|---|
| 《个人信息保护法》第 28 条 | ✅ CAC 原文 | 医疗健康信息属敏感个人信息 |
| 《个人信息保护法》第 29 条 | ⚠️ 本轮未摘录原文（背景知识） | 处理敏感个人信息需**单独同意** |
| 《涉及人的生命科学和医学研究伦理审查办法》（国卫科教发〔2023〕4 号） | 🔶 | 不得欺骗、利诱、胁迫；参与者可随时无条件退出；合理支出可适当补偿 → **积分按"补偿/致谢"设计，不是"购买数据"**；研究使用须经合作机构伦理审查 |
| 《人类遗传资源管理条例》实施细则 | 🔶 | 人遗信息指基因、基因组等数据，**不含临床、影像数据** → 第一阶段不收基因检测报告即可规避 |
| 数据出境 | 🔶 阈值未核原文 | 境外合作只做境内分析或聚合输出 |
| 《广告法》第 16 条 | 🔶 多个政府普法页一致 | 医疗/药品广告不得含功效断言或保证、治愈率/有效率、与其他药品或机构比较、代言人推荐证明 |
| 《药品、医疗器械、保健食品、特殊医学用途配方食品广告审查管理暂行办法》第 11 条 | 🔶 | 不得使用专家、医师、**患者**等名义或形象作推荐、证明 → 病友故事、"生活妙招"不能变成药品/产品背书 |
| 《反不正当竞争法》有奖销售条款 | ⚠️ | 抽奖式最高奖金额上限（背景知识：5 万元）→ 若以后做抽奖兑换需法务确认 |
| 《人工智能生成合成内容标识办法》 | ⚠️ | AI 生成摘要须显式标识（站点已有 AI 内容标签） |
| 付费与"不当引诱"伦理文献 | 🔶 | Hastings Center、PMC11132984（2024 实验）、NHMRC 指南：付费本身不构成胁迫，关注与负担相称和公平性 |

---

## 5. 激励研究（⚠️ 出处细节待检索）

- Gneezy & Rustichini (2000) "Pay enough or don't pay at all"：小额金钱激励可能降低参与意愿。
- Deci, Koestner & Ryan (1999) 元分析：可预期的外在奖励削弱内在动机。
- Mellström & Johannesson (2008)：献血付费的挤出效应；允许把报酬捐给慈善可抵消挤出效应。
- 健康数据捐赠态度的系统综述：主要动机是利他和对机构的信任，主要担忧是隐私与商业化。

**设计含义**：精神认可先行；"你的贡献帮助了什么"的反馈最强；物质回报小额、封顶、可捐赠，且不按照片数量或病情严重度定价。

---

## 来源链接

- MONDO 检索：https://www.ebi.ac.uk/ols4/api/search?q=vitiligo&ontology=mondo&exact=true
- SCIN：https://github.com/google-research-datasets/scin
- LightRAG：https://github.com/HKUDS/LightRAG
- KAG：https://github.com/OpenSPG/KAG
- GraphRAG：https://github.com/microsoft/graphrag
- OntoGPT：https://github.com/monarch-initiative/ontogpt
- PrimeKG：https://github.com/mims-harvard/PrimeKG
- Open Targets：https://platform.opentargets.org
- PubTator3：https://www.ncbi.nlm.nih.gov/research/pubtator3/
- ClinicalTrials.gov API：https://clinicaltrials.gov/data-api/api
- OpenAlex：https://docs.openalex.org
- Europe PMC：https://europepmc.org/RestfulWebService
- PaperQA2：https://github.com/Future-House/paper-qa
- Open Humans：https://github.com/OpenHumans/open-humans
- Zooniverse Panoptes：https://github.com/zooniverse/panoptes
- OMOP CDM：https://github.com/OHDSI/CommonDataModel
- Synapse：https://www.synapse.org
- VRF tools：https://vrfoundation.org/tools
- VRF Wikipedia：https://en.wikipedia.org/wiki/Vitiligo_Research_Foundation
- VRF Patient Journey Map：https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11747489/
- Evidation Help：https://help.evidation.com/hc/en-us/articles/360012331334-What-is-Evidation
- Evidation FAQ：https://www.evidationapp.com/frequently-asked-questions
- PatientsLikeMe 收购：https://www.cnbc.com/2019/06/24/unitedhealth-buys-patientslikeme-after-cfius-forced-sale.html
- 23andMe：https://www.bio-itworld.com/news/2025/07/02/anne-wojcicki-buys-back-23andme-for-305m-promises-data-security
- 23andMe 数据转让分析：https://foleyhoag.com/news-and-insights/publications/alerts-and-updates/2025/july/23andme-bankruptcy-update-how-the-proceedings-highlight-best-practices-for-handling-and-transferring/
- ComPaRe：https://pubmed.ncbi.nlm.nih.gov/41128184/
- Healx：https://healx.ai/healx-launches-partnership-with-ataxia-uk-and-fara-to-find-treatments-for-rare-neurodegenerative-condition/
- Owkin：https://www.owkin.com/blog/story-of-the-1st-federated-learning-model-at-owkin
- 医渡科技：https://www.yidutech.com/solution01.html ；https://www.yidutech.com/news-detail.html?id=325
- GVF：https://globalvitiligofoundation.org/about-gvf/
- VIRTUAL-UK：https://clinicaltrials.gov/study/NCT06218082
- 中国白癜风精准医学研究联盟：https://ahmu-derm.ahmu.edu.cn/2024/0731/c9831a160555/page.htm
- 白癜风诊疗共识 2024：http://www.pifukezazhi.com/CN/10.35541/cjd.20240260
- Upadacitinib III 期：https://www.dermatologytimes.com/view/phase-3-data-show-upadacitinib-drives-progressive-repigmentation-in-non-segmental-vitiligo
- Povorcitinib STOP-V：https://www.nature.com/articles/s41591-026-04739-2
- Povorcitinib 中国 III 期：https://clinicaltrials.gov/study/NCT07865312
- 伦理审查办法：https://wjw.ningbo.gov.cn/art/2023/10/17/art_1229128391_58955310.html
- 个人信息保护法：https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm
- 人遗实施细则解读：https://www.junhe.com/legal-updates/2190?locale=zh
- 广告法普法：https://www.thepaper.cn/newsDetail_forward_26691346
- 付费与不当引诱：https://www.thehastingscenter.org/irb_article/money-coercion-and-undue-inducement-attitudes-about-payments-to-research-participants/ ；https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11132984/
