# 审计证据

证据分为 UI 实测、离线实验、代码核验、文献和待验证假设。

- staging version: 1789090799175；production: 1788097546229；API health 正常。当前源码并非生产前端已同步版本，审计需分开。
- 当前已有 measure_layers、common ROI 配准、人工双层 mask 编辑；_mock_result 实际抛异常，不能根据陈旧注释误报为随机生成。
- 访客选图触发鉴权质检接口，checkQuality catch 清空结果；开始按钮依赖质检完成，待浏览器复现。
- 质检使用全图 Laplacian/均值亮度，soft_failures 不会 poor，无皮肤也只是 acceptable。
- CUA 两次超时，已切换隔离的本地 headless Chrome/Playwright 测试；无读取浏览器私密会话。

- 已在真实 staging Chrome 375px 完成未登录选部位→上传合成图片→补齐视角日期：质检返回 401，页面提示重选照片，开始分析 disabled。P0 转化阻断实证。
- 375/768/1024/1440 首页未发现页面横向溢出；这不等于完成所有结果/编辑页和 iOS PWA 测试。
- useCameraQuality 无任何调用方；当前 BodyPartCamera 未接实时质检，不可因为旧 composable 存在就声称在线实时质检。
- 默认视觉 prompt 同时禁止诊断和要求分期/好转；assess_vasi 重置 stage，结果 visual_features 描述仍来自模型，需要隔离。
- spot_compare._merge_results 已只取通过门禁的像素 evidence，不能误报为直接展示 VLM 估算变化。
- U-Net trainer 按图片随机 split，未按 patient 分组；offline benchmark 脚本虽检查患者泄漏但不约束训练器。
