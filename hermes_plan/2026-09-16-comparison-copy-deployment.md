# 对比文案与手动预览状态部署验证

## 结果
已部署 staging，buildTime 1789517776353。生产版本 1789178116492 不变；共享后端未变更。

## 修改范围
- web/app/src/views/VasiComparePage.vue：删除指定拍摄位置长提示。
- web/app/src/components/tracker/AssessmentVisualHome.vue：单行副标题“两张照片或两次记录”。
- web/app/src/components/report/ReportManualAlignment.vue：编辑状态通知、预览/生成状态文案、打开时清空就绪。
- web/app/src/components/report/ComparisonViews.vue：调整时隐藏旧提示，标记旧结果。

## 验证
- 对照两份补丁 manifest，4 个源文件修改前哈希均一致；未覆盖其他改动。
- 远程 npm run type-check、npm run build 通过。
- 浏览器使用部署后的真实静态资源，API 全部模拟：两次记录、两张照片的编辑/收起/重开/重新分析导航通过；手动能力关闭时维持禁用。无真实用户数据读写。
- 四种宽度 375/768/1024/1440 的副标题均 white-space: nowrap，实际高度 16px 与行高相等，无文字溢出。
- staging 公网 version.json 与远程文件一致；manifest、9 个图标、SW、入口 JS/CSS 资源检查通过。
- 后端 health 返回 {"status":"ok","service":"subskin-backend"}。
- 正式 index SHA256：0f53d0f9c8199eab673c5270522152679ae6188796db9a51759689144c42bc28（与发布前一致）。

## 限制
这次为前端发布；当前手动对齐仍是预览，实际手动分析服务候选未获得明确启用许可，因此未激活。
