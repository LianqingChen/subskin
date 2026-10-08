# 手帐审计交付包

- AUDIT.md：主报告，13类交付内容映射、20项问题和实施方案。
- CODE_EVIDENCE.md：代码摘录、行号和链接。
- *.mmd：当前流程、新流程、推荐架构。
- run_offline_probes.py：14例合成模块探针；不使用患者照片，不连DB/在线AI。
- evidence/ui-evidence.json：真实测试环境访客上传401阻断与4种宽度检查。
- evidence/offline-probes.json：逐例原始指标、运行库版本、测试源码hash。
- evidence/synthetic-contact-sheet.png：输入与CV输出的对照。
- evidence/*-reference.png、*-prediction.png：合成参考Mask与输出Mask。
- evidence/regression.xml：31项已有回归通过。
- evidence/real-image-test-matrix.json：尚未运行的真人矩阵，字段明确为null，非测试结果。

在线已登录闭环、真人准确率、生产运行态和真机PWA仍待补验证。没有业务代码修改、部署或重启。
