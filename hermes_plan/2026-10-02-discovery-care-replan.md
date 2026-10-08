# 发现与调养页面重新规划

## 目标
发现回归病友内容浏览；调养按电商的搜索、分类、筛选、商品、详情、购物清单路径组织，避免医疗焦虑营销。

## 阶段
- 调研：完成。并行检查现有页面及 GitHub 源码，主要文件已直接复核。
- 设计：用户已确认。详见 `docs/specs/2026-10-02-discovery-care-design.md`。
- 实施：前端完成并部署测试环境1790918768440，正式环境未修改。
- 验证：类型检查、10项代码回归、四屏宽明暗8组浏览器、PWA/公网版本/health与正式指纹核验通过。

## 调研记录
- `web/shared/site-modules.json` 当前显式将科普与种草归入发现；调养为外部购买导购，不是站内支付商城。
- Medusa storefront `src/modules/store/templates/index.tsx`：分类/排序 refinement 与商品列表分离，响应式纵向/横向布局，商品列表独立加载骨架。
- Medusa `src/modules/products/components/product-preview/index.tsx`：商品图片、标题、价格作为列表核心，详情由独立路由承接。
- Vercel Commerce `app/search/layout.tsx`：分类、结果、排序三区分离；`components/layout/navbar/index.tsx`：搜索与购物车作为稳定工具入口。

## 错误与恢复
- 两个 librarian 代理因 Go 模型订阅不可用而失败：改用直接读取 GitHub raw 源码，不将失败当作调研结果。
- 浏览器 MCP 缺少 chrome-for-testing：尚未完成在线视觉核验，不宣称页面截图验证通过。

## 进度
2026-10-02：仅调研与设计文档，无产品代码或后端修改，无部署。
- 直接源码复核确认15条静态选购参考；代理报告中14条统计不准确，不采纳。
- 不采纳将发现改为商品分类卡的建议，用户要求的电商布局仅针对调养。
- 不采纳桌面完全移除左栏建议，桌面沿用w-52可折叠侧栏，手机横滑分类。
- 自审完成：无假销量、价格、订单，保留旧链接与清单数据，知识风险不因视觉简化消失。
- 实施代理认证失败、独立审查代理超时；主会话直接完成实现与验证，不宣称代理审查通过。
- 已新增 useCareCatalog/useDiscoveryFeed/useDiscoverySearch，社区View拆分；useCareCart保留存储键与账号隔离。
- 共享后端不重启：上一轮未批准的rag等改动仍在源码中，本次仅同步JSON描述并明确记录待启用。
- 浏览器实际使用既有npm缓存Playwright与Chromium；已补齐视觉验收，32张截图与results.json在/tmp/opencode/discovery-care-20261002。
- 验收发现并修复：原生dialog的Tab地址栏出口；旧请求失败覆盖新状态；CSS变量调色板不支持primary色/透明度变体的暗色背景。测试脚本另修正路由完成等待与桌面标题定位，未弱化功能断言。
- 最终正式版本1790785135093，HTML/version SHA256不变；源码未提交Git，不触碰既有其他修改。
- 后续修正：用户要求发现顶部标签/排序/搜索始终单行；定位flex-wrap及变长文本宽度，局部改为不换行、右侧固定、左侧收缩横滑。staging1790928580172，六屏宽×短/长城市×三状态36项浏览器单行检查通过，既有10回归/type-check/build/PWA/health与正式指纹通过。
