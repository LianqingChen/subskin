---
name: pwa-verification
description: "SubSkin PWA 架构验证 — 每次部署后必须验证的关键指标"
---

# PWA Verification Skill

> SubSkin PWA 架构验证 — 每次部署后必须验证的关键指标
>
> **触发词**: PWA验证、PWA检查、部署验证、manifest检查、service worker验证

---

## 检查清单（每次部署后 MUST 执行）

### 1. version.json 验证

```bash
# 检查 staging
cat /usr/share/nginx/html/subskin-staging/version.json | python3 -m json.tool
# 检查 production
cat /usr/share/nginx/html/subskin/version.json | python3 -m json.tool
```

**必须通过**:
- `buildTime` 是当前部署时间戳（不是旧值）
- `env` 正确：staging = `"staging"`, production = `"production"`
- production 有 `lastProdBuildTime` 字段

### 2. manifest.webmanifest 验证

```bash
# 解析并对比两个环境的 manifest
cat /usr/share/nginx/html/subskin-staging/manifest.webmanifest | python3 -m json.tool
cat /usr/share/nginx/html/subskin/manifest.webmanifest | python3 -m json.tool
```

**必须通过**:
- staging `name` = `"SubSkin [STAGING]"`, production `name` = `"SubSkin更懂你"`
- staging `theme_color` = `"#1e293b"` (slate), production `theme_color` = `"#26A69A"` (teal)
- staging `short_name` = `"SubSkin-STG"`, production `short_name` = `"SubSkin"`
- 两者 `background_color` 都 = `"#ffffff"`
- icons 数组完整（72→512 + maskable）

### 3. Service Worker 验证

```bash
# 检查 sw.js 存在且大小合理
ls -la /usr/share/nginx/html/subskin-staging/sw.js
ls -la /usr/share/nginx/html/subskin/sw.js
```

**必须通过**:
- sw.js 存在且大小 > 3KB
- workbox-*.js 预缓存文件存在

### 4. index.html 验证

```bash
# 检查 HTML 引用正确
cat /usr/share/nginx/html/subskin-staging/index.html
cat /usr/share/nginx/html/subskin/version.json
```

**必须通过**:
- `<script src="/assets/index-*.js">` hash 与实际文件匹配
- `<link href="/assets/index-*.css">` hash 匹配
- `<link rel="manifest">` 存在
- `<meta name="theme-color">` 存在
- `<title>` 正确（staging 不带 [STAGING] 标记，只有 manifest 区分）

### 5. Backend Health

```bash
curl -s http://127.0.0.1:8000/api/health
```

**必须通过**:
- 返回 `{"status":"ok","service":"subskin-backend"}`

### 6. PWA 更新通知验证

- staging 用户应看到"测试环境有新版本可用"
- production 用户应看到"有新版本可用"
- 通知由 version.json 的 buildTime 变化触发（每30秒轮询）

---

## 快速一键验证脚本

将以上所有检查合并为一条命令：

```bash
echo "=== PWA Verification ===" \
&& echo "--- version.json ---" \
&& cat /usr/share/nginx/html/subskin-staging/version.json \
&& echo "" \
&& cat /usr/share/nginx/html/subskin/version.json \
&& echo "" \
&& echo "--- manifest name ---" \
&& python3 -c "import json; s=json.load(open('/usr/share/nginx/html/subskin-staging/manifest.webmanifest')); p=json.load(open('/usr/share/nginx/html/subskin/manifest.webmanifest')); print(f'staging: {s[\"name\"]} / theme: {s[\"theme_color\"]}'); print(f'prod:    {p[\"name\"]} / theme: {p[\"theme_color\"]}')" \
&& echo "--- sw.js size ---" \
&& wc -c /usr/share/nginx/html/subskin-staging/sw.js /usr/share/nginx/html/subskin/sw.js \
&& echo "--- backend health ---" \
&& curl -s http://127.0.0.1:8000/api/health \
&& echo ""