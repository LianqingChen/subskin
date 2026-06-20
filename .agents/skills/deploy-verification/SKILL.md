---
name: deploy-verification
description: "SubSkin 部署验证 — 对比 staging 与 production 的一致性"
---

# Deploy Verification Skill

> SubSkin 部署验证 — 对比 staging 与 production 的一致性
>
> **触发词**: 部署验证、环境对比、staging对比、production检查、一致性检查

---

## 验证流程

### 1. Bundle 大小对比

```bash
# 对比两个环境的关键 bundle 大小
echo "=== Key Bundle Size Comparison ==="
for name in CommunityPage AssessmentPage ProfilePage DigitalHuman DashboardPage ChatAssistantPage; do
  prod=$(ls /usr/share/nginx/html/subskin/assets/${name}-*.js 2>/dev/null | xargs wc -c 2>/dev/null | awk '{print $1}')
  stg=$(ls /usr/share/nginx/html/subskin-staging/assets/${name}-*.js 2>/dev/null | xargs wc -c 2>/dev/null | awk '{print $1}')
  echo "${name}: prod=${prod}B staging=${stg}B"
done
```

**评估规则**:
- 差异 < 5%：正常（chunking 策略差异）
- 差异 5-20%：需检查是否有功能缺失/新增
- 差异 > 20%：⚠️ 可能有重大不一致，需详细排查

### 2. 文件列表对比

```bash
# 比较两个环境 assets 目录的文件列表差异
diff <(ls /usr/share/nginx/html/subskin/assets/ | sort) <(ls /usr/share/nginx/html/subskin-staging/assets/ | sort)
```

**评估规则**:
- 只有 hash 后缀不同：正常（每次构建 hash 变化）
- staging 有额外文件：可能是新增功能，需确认是否应在 production 也存在
- production 有 staging 缺少的文件：⚠️ 功能缺失，需修复

### 3. 功能性对比（关键差异项）

检查以下功能在两个环境中是否一致：

| 功能 | Production 检查 | Staging 检查 | 必须一致 |
|---|---|---|---|
| 同城分享 Tab | `strings CommunityPage-*.js | grep "local\|同城"` | 同上 | ✅ |
| CityPicker | `ls assets/CityPicker*` | 同上 | ✅ |
| useGeolocation | `ls assets/useGeolocation*` | 同上 | ✅ |
| 暗色模式 | HTML body class 无残留 dark: | 同上 | ✅ |

### 4. 数据库连接

```bash
# 验证后端能正常访问数据库
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/community/categories | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Categories: {len(d)}')"
```

### 5. 完整验证报告格式

```
## 部署验证报告

| 检查项 | Production | Staging | 状态 |
|---|---|---|---|
| buildTime | xxx | xxx | ✅/❌ |
| PWA manifest | 正确 | 正确 | ✅/❌ |
| Backend health | OK | OK | ✅/❌ |
| 同城功能 | 存在 | 存在 | ✅/❌ |
| CommunityPage 大小 | 20.7KB | 16.8KB | 差异% |
| 总文件数差 | N | N | ✅/❌ |

### ⚠️ 发现的差异
1. [描述]

### ✅ 一致性确认
1. [描述]
```