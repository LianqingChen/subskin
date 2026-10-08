# Research Findings

Initial context: SubSkin is a vitiligo-focused PWA with AI Q&A, a personal journal/assessment workflow, community sharing, hospital information, and reports. User privacy constraints rule out selling identifiable patient data. Actual willingness to pay, retention, traffic, and costs are not yet established in this review.

## Repository findings
- Current module source of truth: web/shared/site-modules.json; primary navigation is 问答 / 记录 / 分享 / 公益. Old README and July plans use superseded names.
- July master plan emphasizes AI-assisted longitudinal records, revisit summaries, and peer support. August refinement explicitly defers clinician onboarding, trial matching, and group treatment statistics.
- Older strategy documents contain unsupported exclusivity and clinical-causality claims; these are aspirations, not validated differentiation or clinical evidence.
- September plans focus on photo comparability, manual verification, reporting reliability, and independent hospital information; reliability is a prerequisite for charging for measurements.
- No actual revenue, willingness-to-pay, retention, or unit cost evidence established. Planning targets must not be treated as actual metrics.
- Initial market search finds PatientsLikeMe partnership and commission models and skin-monitoring subscriptions; primary pages require closer inspection.

## Latest deployment context
- DEPLOY_LOG.md latest production frontend is September 16. September 17 hospital flow, September 18 interactive map, and latest report refinements are pending staging changes, not all production capabilities.
- Existing direction includes basic photo records, mask verification, paired comparison, shareable reports/artwork, medical report interpretation, and hospital experience information.
- Candidate model: free trust/community layer; paid convenience around longitudinal records and revisit preparation; conditional institution-funded follow-up software later. Research services are optional future work, not a present data-sales strategy.
- Do not charge for access to one's existing records, privacy protections, or measurement reliability; avoid financial incentives to repeat unnecessary photo scans.

## Primary external evidence
- SkinVision official support offers single checks and time-based plans; this establishes packaging precedent, not willingness to pay for vitiligo tracking in China.
- Miiskin official provider pricing offers usage-based practice software and enterprise implementations: https://miiskin.com/pro/plans-pricing/ . Different geography and clinical service model; only evidence that institution-facing dermatology workflow services can be charged for.
- China's PIPL, Articles 28–30, treats medical health information as sensitive; purpose, necessity, protections, and separate consent matter: https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm . Research is not automatically authorized by ordinary product consent.
- PatientsLikeMe research/dataforgood page returned an internal tool error. Use its official support/partner material as an alternative; do not infer current revenue from historical descriptions.

## Evidence qualification
- The segmentation ACCEPTANCE.md explicitly describes future implementation checks, not an achieved model benchmark. Do not claim clinical accuracy from this document.
- SkinVision support confirms single, three-month, yearly plans and partner-funded discounts/free access. Its use case differs from SubSkin; prices are not a domestic benchmark.
- PatientsLikeMe partners page fetch was forbidden (403). Official help-center index is accessible and links directly to current business model articles.

## Final evidence and decision
PatientsLikeMe official business-model article (updated 2026-08-27) lists patient-support programs, research collaborations, trial support and partner products/services. This supports institution-funded services as a precedent, not a Chinese market forecast. Final recommendation and validation assumptions are recorded in assessment.md.
