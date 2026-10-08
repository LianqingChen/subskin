# 2026-08-16 小白管家：真 3D 形象（金斑蝶/梅花鹿）+ 长按拖动到任意位置

## 需求

1. AI 助手（小白管家）图标支持长按后拖动到页面任意位置
2. 形象从静态图案升级为真实 3D 小动物；用户后续指定：**默认=网站 Logo 的金斑蝶**，另加**梅花鹿**选项（不要熊猫）

## 最终实现（v2：金斑蝶 + 梅花鹿，程序化建模）

### 形象 — `utils/butlerCreatures.ts` + `ButlerCreature3D.vue`

- **程序化建模（Three.js 代码建模，零外部模型/零下载）**，替换 v1 的熊猫 GLB 方案
- **金斑蝶（默认，mascot=real）**：CanvasTexture 手绘纹样（品牌橙渐变 + 放射黑翅脉 + 墨色宽边 + 白点斑列）+ 黑色天鹅绒身体/白点/触角；V 形扇翅动画，心情映射（开心/思考/打招呼/飞行/拖拽各有动作）
- **梅花鹿（mascot=deer，新增）**：栗色圆身 + 14 枚梅花白斑 + 奶油胸鼻 + 小鹿角；摆耳/点头/甩尾/蹦跳
- 渲染器通用化：`creature` prop（butterfly/deer）热切换；ACES 色调映射；WebGL 失败回退 SVG 卡通形象；reduced-motion / 页面隐藏 / dispose 处理
- 配色教训：白底按钮上 3D 形象需要高饱和深色（v1 浅橙在白底上几乎不可见，v2 加深为 #f97316 主橙 + 墨色 #241a14）

### 拖动 — `FloatingButler.vue`（同 v1）

- 长按 350ms 进入拖动（提示气泡+震动+放大），松手放置并 localStorage 持久化（视口比例）
- 拖到左右边缘=隐藏（边缘偷看）；拖回底部角落=恢复默认锚点；短按=开面板不误触

### 变更文件

- 新增：`utils/butlerCreatures.ts`、`components/butler/ButlerCreature3D.vue`
- 删除：`components/butler/ButlerPanda3D.vue`（v1 熊猫 GLB 渲染器）
- 修改：`FloatingButler.vue`、`ButlerPanel.vue`、`ButlerAppearancePicker.vue`、`types/index.ts`（+deer）、`utils/butler.ts`（素材表去 real）、后端 `models/user.py`（Literal +deer，additive，已重启）
- 依赖：three@0.185（v1 引入；程序化建模后 Draco/GLB 不再使用，public/draco 与 panda GLB 保留未删）

## 验证（Chromium 138 headless 实测 staging）

- 金斑蝶/梅花鹿 canvas 均正常渲染，视觉确认：金斑蝶=橙翅墨边白点黑身 V 形，梅花鹿=栗身白斑小角；零 console/page 错误
- 长按出提示 → 拖动跟手 → 松手 (130,400) 精确放置并持久化；刷新恢复
- 拖到左边缘 → 隐藏+偷看按钮出现；点击唤回
- 短按 → 面板正常打开（拖动不误触）

## 同日应急：全站 SSL 证书过期（P0）

- `*.subskin.cn` 通配符证书 8-15 过期（手动 DNS 验证、续期 hook 脚本丢失，三域名全挂）
- admin 新签独立证书（至 11-14）；正式/WWW/staging 切到 `/etc/letsencrypt/live/subskin.cn/`（至 10-13）；nginx reload 后四域名恢复 200
- nginx 原配置备份：`/root/nginx-cert-backup-20260816/`
- ⚠️ 遗留：10-13 前需换用可自动续期的 HTTP-01 方案

