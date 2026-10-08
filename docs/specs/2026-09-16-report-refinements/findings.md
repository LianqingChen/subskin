# Findings
- skin_report.py API中两处生成完成站内信；需排查其他分析/比较路径。
- 上轮公益新增只读接口与AI功能说明在源码中，尚未重启共享后端；不能在本轮静默激活。

只读汇总：现有9份completed comparison报告，7份not_comparable、2份visual_only，均未存面积变化或共同区域像素数。来源引用是3条记录，2条measured、1条partial，均有已核对RGB标注。可展示单图现成测量，但不能把单图占比直接当共同范围变化。
缺口：pi照片引用未携带其关联评估数据；自动微调只优化展示，未重新尝试共同ROI量化；UI仅有变化chips，无前/后量化表；历史报告无真实完成时间字段。
