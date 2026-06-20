---
name: vue-tsc-guard
description: "Vue TypeScript 类型守门员 — 在编辑阶段捕获类型错误，防止 deploy:prod 阻塞"
---

# Vue TSC Guard Skill

> Vue TypeScript 类型守门员 — 在编辑阶段捕获类型错误，防止 deploy:prod 阻塞
>
> **触发词**: TS错误、类型检查、vue-tsc、deploy阻塞、类型修复

---

## 核心原则

**`npm run deploy:prod` 使用 `vue-tsc -b` 做类型检查。任何 TS 错误都会阻塞生产部署。**

因此在修改 Vue/TS 文件时，必须在编辑完成后立即运行 `vue-tsc --noEmit` 验证。

---

## 常见阻塞错误及修复模式

### 1. 未使用变量 (TS6133)

```typescript
// ❌ 触发 TS6133
const coverUrl = computed(() => ...)
const { newType, oldType } = ...  // watch callback params

// ✅ 修复方案
// 方案 A：删除未使用的变量
// 方案 B：watch 回调只保留需要的参数
watch(activeFeedType, async () => { ... })  // 不声明参数
// 方案 C：使用下划线前缀（但 vue-tsc 默认不允许，需 tsconfig 设置）
```

### 2. 属性不存在 (TS2339)

```typescript
// ❌ 触发 TS2339 — composable 返回值缺少属性
const geo = useGeolocation()
geo.lat.value      // Property 'lat' does not exist
geo.setManualCity() // Property 'setManualCity' does not exist

// ✅ 修复：确保 composable 返回所有使用到的属性
return { city, lat, lng, loading, error, permissionDenied, requestCity, reset, setManualCity }
```

### 3. 类型导入缺失

```typescript
// ❌ 触发 TS2304/TS2792
import { AssessmentSnapshot } from '@/types'  // 类型已移除

// ✅ 修复：内联定义或更新导入
interface AssessmentSnapshot { ... }  // 内联定义
```

---

## 验证流程

### 编辑后立即检查

```bash
cd /root/subskin/web/app && npx vue-tsc --noEmit 2>&1 | head -30
```

**如果发现错误**:
1. 优先修复 TS 错误（不能绕过）
2. 禁止使用 `@ts-ignore` / `@ts-expect-error` / `as any`
3. 修复后再次验证

### 生产构建前最终检查

```bash
cd /root/subskin/web/app && npm run deploy:prod
```

这个命令内置了 `vue-tsc -b` 检查。如果通过，构建自动继续。如果失败，**必须先修复所有 TS 错误**。

---

## tsconfig 注意事项

SubSkin 使用 Python 3.9 兼容性约束，但前端 TypeScript 无版本限制。常见 tsconfig 问题：

- `noUnusedLocals: true` — 会捕获所有未使用的局部变量
- `noUnusedParameters: true` — 会捕获未使用的函数参数
- 确保修改的文件在 tsconfig 的 include 范围内