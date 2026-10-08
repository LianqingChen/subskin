# 发现
主入口web/backend/app/main.py；启动时Base.metadata.create_all。现有模型只有sam_vit_b；无可验证专用RGB权重。现有vasi_promptable已用预测锁，需要保留并扩展全部候选；主API有user-scoped cache_key。新任务与旧assess接口可并存，旧前端保持旧请求。现有人工核对立即finalize，新版需revision锁与不可恢复质检门禁。

线上首个RGB任务已生成非空uncertain候选，confirmed lesion为空；AnnotationEvidence默认candidate层掩盖现有候选。useVasiAssess.cancelPending在unmount后对lastRGBJobId调用cancel；服务端将完成但未保存的draft弃用。修复只改前端显示/生命周期，保留服务端取消迟到任务的语义。未读取/复制患者图像，不将候选数量当准确率。

精简编辑方案：旧MaskEditor约1400行且含缩放、吸附、多工具与教学文案，改为独立精简组件，保留旧调用以兼容其他页面。上传img使用56dvh，地址栏导致布局变化；新入口改svh避免滚动改变尺寸。RGB编辑确认接受RGBA alpha>32，新编辑器导出二值alpha，展示统一使用opacity0.4。候选只预填，可编辑，确认前不测量；无需后端修改。

当前上传56svh照片+48px图注+日期/分析/更多设置+父容器padding与全局55px底栏相加会溢出。全局AppHeader=56px、BottomNav=54px内容+1px边框+safe-bottom；新工作页显式预留，内部照片minmax(0,1fr)，按钮自适应固定行；原home/result/history不受影响。浏览器工具本轮返回空浏览器清单、fetch failed，实机不可用。倒计时以90s任务预算做参考，按时间戳计算，归零继续真实状态、不伪造成功。
