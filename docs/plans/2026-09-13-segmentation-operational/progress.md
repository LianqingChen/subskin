# 进度
已核对vasi_pixel_refine、assessment_measurement、assessment_comparison、vasi_promptable。已阅读后端架构技能并沿用此前规划/前端规范。正在制作实施方案与机器可校验合同；只新增文档，不启动训练或上传照片。

用户明确收敛到普通手机RGB纯视觉方案。已删除专业光源识别、采集与建议分支，改为自然光/室内光抗干扰。主输出为像素面积与照片内占比，厘米保持有尺度才可扩展。

交付位于docs/specs/2026-09-13-vitiligo-segmentation：IMPLEMENTATION.md、agent-instructions.md、segmentation-result.schema.json、examples.synthetic.json、ACCEPTANCE.md。已通过结构/状态组合/示例公式与RGB-only范围检查。Schema不能代替工件所有权、像素一致性和测量资格的服务端校验，已明确标注。
