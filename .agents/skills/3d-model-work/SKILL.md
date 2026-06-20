---
name: 3d-model-work
description: "SubSkin Three.js 3D 模型工作 — 数字人/熊猫模型的加载和渲染"
---

# 3D Model Work Skill

> SubSkin Three.js 3D 模型工作 — 数字人/熊猫模型的加载和渲染
>
> **触发词**: 3D模型、数字人、DigitalHuman、熊猫模型、Three.js、GLB、3D渲染

---

## 项目中的 3D 资源

| 文件 | 用途 | 大小 |
|---|---|---|
| `panda_opt.glb` | 低质量熊猫模型（快速加载） | 1.4MB |
| `panda_webp.glb` | WebP纹理熊猫模型 | 14.8MB |
| `panda_resized.glb` | 重采样熊猫模型 | 17.7MB |
| `panda_compressed.glb` | Draco压缩熊猫模型 | 7.4MB |
| `panda.png` | 熊猫备用图片 | 1.1MB |
| `butterfly_mascot.png` | 吉祥物蝴蝶图片 | 0.55MB |
| `cyber_panda.png` / `cyber_panda_2d.jpg` | 2D熊猫图片 | 0.97MB / 0.25MB |

所有 GLB 文件位于部署根目录 `/usr/share/nginx/html/subskin*/`，源文件在 `web/app/public/`。

---

## DigitalHuman.vue 关键架构

```
web/app/src/components/tracker/DigitalHuman.vue
```

- SVG-based 木头小人身体部位图（正面12部位 + 背面12部位）
- `rain`/`wave` 模式的天气动画
- `butterfly_mascot` 吉祥物动画
- 点击部位 → 触发 `@select(bodyPart)` 事件
- 部位映射来自 `bodySites.ts` 枚举

**NOT 3D anymore** — DigitalHuman 从 Three.js 3D 模型改为 SVG 木头小人。生产环境 bundle 约 9.8KB。

---

## 常见操作

### 检查 3D 模型文件

```bash
# 检查模型文件是否存在于两个环境
ls -la /usr/share/nginx/html/subskin/*.glb /usr/share/nginx/html/subskin-staging/*.glb
```

### 检查 DigitalHuman bundle

```bash
# 比较两个环境的 DigitalHuman 大小（应该一致或仅微差）
wc -c /usr/share/nginx/html/subskin/assets/DigitalHuman-*.js /usr/share/nginx/html/subskin-staging/assets/DigitalHuman-*.js
```

### Draco 解码器

Three.js Draco 解码器位于部署目录 `/usr/share/nginx/html/subskin*/draco/`，用于解压压缩的 GLB 文件。

---

## ⚠️ 注意事项

- DigitalHuman 目前是 **SVG 木头小人**，不是 Three.js 3D 模型
- 熊猫模型 GLB 文件仍保留在部署目录，DashboardPage 可能使用
- 修改 DigitalHuman 时必须确保 SVG 部位图完整（正面12+背面12 = 24部位）
- 生产环境的 DigitalHuman bundle 约 9.8KB，如果突然变大说明有问题