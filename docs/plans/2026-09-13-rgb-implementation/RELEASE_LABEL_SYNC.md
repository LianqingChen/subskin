# RGB后台同步增量：已确认部署

已上线：画笔互换与分母说明，staging buildTime 1789313653913。19项相关前端回归/type-check/build通过。

已上线的共享后端：
- RGB任务完成与用户确认后，同事务同步既有图片打标索引，保留原图/AI初始/用户revision。
- 管理员编辑使用互斥正常皮肤/白斑层；独立保存每次管理员Mask及父版本，不覆盖用户结果；面积按并集计算。
- 用户后续修订使样本重回待审，已有admin版保留；旧自动训练/随机拆分训练导出不接收新RGB样本。
- 用户删除/观察过期时，按任务来源清理新增后台Mask副本；补齐外键置空情况。
- 不新增表，不修改模型配置，不训练，不激活权重。

发布包：/root/subskin/data/release-candidates/rgb-admin-sync-20260913。
manifest.json包含10项源码/测试/脚本，before/after SHA；其中7项后端源文件、1项管理员Vue、1项测试、1项验证脚本。源码已于2026-09-14经用户确认同步live后端并重启后端/worker。
119项后端回归通过，RGB模块覆盖率86.92%；真实worker+SAM在合成图上的任务/取消/超时验证通过。
管理员类型检查与构建通过，测试预览已发布到https://staging.subskin.cn/admin-preview/；现有https://admin.subskin.cn未替换。

已完成：私有备份、manifest同步、共享后端/worker重启；补同步3条有效RGB记录（3份AI、2份用户确认），原图及AI版本校验通过。两站健康、worker、PWA、后台预览资源检查通过，用户原结果与数据库schema不变。正式患者/管理站前端未发布。上线报告见发布目录deployed-verification.json。

真实账号/手机与管理员画布视觉验收未完成：浏览器控制连接持续超时。模型版本控制台、授权数据集发布、训练调度为已完成设计，尚未实现。

数据库注意：运行服务实际连接/root/subskin/data/subskin.db；root .env的CLI默认值指向旧库。维护脚本应从运行服务核实连接并显式设置DATABASE_URL，断言实际engine路径后再读写，不直接照搬root .env。
