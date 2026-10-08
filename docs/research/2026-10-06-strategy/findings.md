# Findings

## 初始事实
- 主导航事实来源：`web/shared/site-modules.json`，待核对完整路由。
- 现有源码包含 vasi_training_admin、rgb_segmentation、consent、account_deletion、hospital、planning_archive 等；不能仅凭文件名判定已闭环。
- 已有商业与功能研究：`docs/research/2026-09-20-business-model/`、`docs/research/2026-09-27-fourth-module/`。
- 工作区有大量既存变更；本次只添加独立战略研究文件。

## 证据约定
- 本地：路径+行号；“源码存在”不等于已临床有效。
- 外部：原始URL+访问日期+核实事实；营销陈述与独立医学证据分别标注。

## 已核实现状
- 2026-10-06读取 `web/shared/site-modules.json`：主导航为问答、记录、发现、调养；就医经验为发现辅助入口；百科明确offline。
- `web/app/src/router/index.ts`：百科路由重定向首页；白斑报告列表重定向记录；存在科普/种草辅助路由。
- `web/backend/models/vasi.py` 有三层mask、VasiTrainingSample、VasiModelVersion、VasiTrainingRun、PatientModel和AutoLoop模型。
- GitHub公开仓库搜索成功；白癜风关键词结果多为低星实验代码，不能据此认定成熟临床模型。
- 用户预算：50万–100万元，作为首期实施约束。

## 读取限制
- 误查 `models/audit_log.py`（不存在）；已定位真实文件 `models/audit.py`，继续核查。

## 训练与授权关键发现
- `services/vasi_model_trainer.py:491`旧U-Net训练按图片随机20%测试，未携带subject_id；`api/image_label.py:1547`旧导出亦逐图随机划分。
- `ml/rgb_segmentation/dataset.py:36`显式训练授权；63、75行拒绝受试者/重复图跨split；train使用validation选checkpoint，test锁定。
- 旧 `ImageLabel` docstring仍写删除后保留训练，但当前训练/导出代码显式排除is_user_deleted；应修正文档并继续审计所有缓存/备份/权重，不据注释断言真实泄露。
- 当前consent类型terms/privacy/ai_data/medical_photo；没有已核实的对象级研究协议、合作方范围及数据集撤回闭环。
- `ml/rgb_segmentation/README.md`明确随机初始化基线、非临床确诊、当前自动测量覆盖率0；这为规划设定能力边界。

## 外部调研记录
- Google普通HTTP搜索返回JS重定向；Bing结果偏离完整查询。改用GitHub API、官方页面、医学文献API；不使用偏离结果作为竞争格局证据。
- GitHub原始元数据与README已保存github-evidence.json；搜索结果保存search-evidence.json（含限制，不作为有效事实）。

## 全球证据概要
- SCIN：官方GitHub说明5000+贡献、10000+图，有同意、医生回顾标注和肤色；官方博客明确回顾标签不等于临床确诊。
- GloW-VSNet：GitHub映射到DOI 10.1016/j.media.2025.103920、PMID41468636；README无仓库license，商业使用需确认。README称2025，文献卷期2026，日期区分。
- VIRdb：白癜风基因/蛋白靶点资料库，CC0仓库，2020最后推送；资料时效及上游数据许可需重审。
- DDI：656图/570患者、多肤色、活检参考；官方条款仅个人非商业研究，禁止商业使用，不能作为商业模型直接数据源。
- Derm Foundation官方页面2026-06-05已标legacy，建议新项目MedSigLIP；仓库Apache2不自动覆盖权重条款。
- SkinVision、Miiskin、Skinive、HautAI与VRF官方站点可读取；HautAI数字属营销自述，不引用为白癜风准确率。
- SkinAnalytics与PatientsLikeMe官方页Cloudflare阻挡；NICE/公开文献或已有研究只作限定来源，不宣称本次完整核实。
- 进一步定位VRF真实Research Tools页面：Biobank（临床信息与生物样本）、CloudBank（患者病情/治疗追踪与研究访问）、研究资助，最接近整体规划；页面规模为官网自述且未说明更新时间，正式方案不作为可靠实时规模。
- 文献标题搜索误返鲁索替尼读者来信PMID36652364；按DOI10.1056/NEJMoa2118828重新核实原研究PMID36260792。正式参考只用原研究。
- 对公开网页正文中的个人姓名与联系方式不作本地持久保存；证据JSON仅保留项目元数据、来源/请求状态与文献标识。正文事实已提炼于方案。
