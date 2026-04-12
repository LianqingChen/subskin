# 阶段1：功能盘点清单

> 盘点时间: 2026-04-09
> 盘点范围: 前端页面、导航栏、后端API

---

## 📋 功能分类总览

| 分类 | 数量 | 保留 | 移除 | 暂停 |
|------|------|------|------|------|
| 前端导航项 | 5 | 3 | 0 | 2 |
| 社区功能模块 | 7 | 1 | 1 | 5 |
| 后端API路由 | 5 | 3 | 0 | 2 |

---

## ✅ 保留的3个核心功能

### 1. AI科普问答
- **前端入口**: 导航栏"AI问答"
- **页面链接**: `/subskin/chat.html`
- **后端API**: `/api/rag`
- **状态**: ✅ 已有，保留
- **说明**: 基于现有功能，无需修改

### 2. AI病情量化追踪（VASI评分）
- **前端入口**: 需新增（导航栏）
- **页面链接**: 需新增 `/vasi/`
- **后端API**: 需新增 `/api/vasi`
- **状态**: 🚧 待开发（阶段2）
- **说明**: 这是MVP最高优先级功能

### 3. 病友经验分享社区
- **前端入口**: 导航栏"社区"
- **页面链接**: `/community/`
- **后端API**: `/api/comment` → 需升级为 `/api/community`
- **状态**: 🚧 需升级（阶段3）
- **说明**: 基于现有评论系统升级，增强社区功能

---

## ❌ 移除的功能

### 导航栏 - 闲置转让
- **导航项**: 社区 → 内容 → 闲置转让
- **页面链接**: `/community/market/transfer`
- **原因**: 电商相关功能，非核心
- **操作**: 从导航栏和侧边栏移除
- **影响**: 低（次要功能）

---

## ⏸️ 暂停的功能（暂不移除，降级处理）

### 导航栏 - 百科
- **导航项**: 导航栏"百科"
- **页面链接**: `/encyclopedia/`
- **原因**: 知识库内容，但不是MVP核心功能
- **操作**: 从主导航栏移除，可作为子页面链接
- **影响**: 中（内容仍保留，仅隐藏入口）
- **备注**: 作为知识支撑保留，不主动展示

### 导航栏 - 动态
- **导航项**: 导航栏"动态"
- **页面链接**: `/news/`
- **原因**: 研究动态，但不是MVP核心功能
- **操作**: 从主导航栏移除，可作为子页面链接
- **影响**: 中（内容仍保留，仅隐藏入口）
- **备注**: 作为知识支撑保留，不主动展示

### 社区 - 心情驿站
- **导航项**: 社区 → 内容 → 心情驿站
- **页面链接**: `/community/chat/mood`
- **原因**: 与"病友经验分享"重合度较高
- **操作**: 保留入口，但降低优先级
- **影响**: 低

### 社区 - 治疗经验
- **导航项**: 社区 → 内容 → 治疗经验
- **页面链接**: `/community/treatment/overview`
- **原因**: 与"病友经验分享"重合度较高
- **操作**: 保留入口，但降低优先级
- **影响**: 低

### 社区 - 医院点评
- **导航项**: 社区 → 内容 → 医院点评
- **页面链接**: `/community/hospitals/reviews`
- **原因**: 与"在线挂号"功能关联，非MVP核心
- **操作**: 保留入口，但降低优先级
- **影响**: 低

### 后端API - 内容管理
- **API路由**: `/api/content`
- **原因**: 暂时不需要独立的内容管理
- **操作**: 保留API，但不公开入口
- **影响**: 低

### 后端API - 评论管理
- **API路由**: `/api/comment`
- **原因**: 将升级为 `/api/community`
- **操作**: 保留并升级
- **影响**: 无

---

## 📊 现有前端导航结构

### 当前主导航栏 (config.js)
```javascript
nav: [
  { text: '首页', link: '/' },
  { text: 'AI问答', link: '/subskin/chat.html' },
  { text: '百科', link: '/encyclopedia/' },        // ⏸️ 暂停
  { text: '社区', link: '/community/about' },
  { text: '动态', link: '/news/' },                // ⏸️ 暂停
]
```

### 精简后主导航栏
```javascript
nav: [
  { text: '首页', link: '/' },
  { text: 'AI问答', link: '/subskin/chat.html' },
  { text: 'AI病情量化', link: '/vasi/' },                 // 🆕 新增
  { text: '病友社区', link: '/community/' },          // 🔄 更新
]
```

### 当前社区侧边栏
```javascript
'/community/': [
  {
    text: '关于',
    items: [
      { text: '关于社区', link: '/community/about' }
    ]
  },
  {
    text: '内容',
    items: [
      { text: '心情驿站', link: '/community/chat/mood' },
      { text: '经验分享', link: '/community/chat/experience' },
      { text: '治疗经验', link: '/community/treatment/overview' },
      { text: '医院点评', link: '/community/hospitals/reviews' },
      { text: '饮食生活', link: '/community/lifestyle/diet' },
      { text: '心理调节', link: '/community/lifestyle/mental-health' },
      { text: '闲置转让', link: '/community/market/transfer' }  // ❌ 移除
    ]
  }
]
```

### 精简后社区侧边栏
```javascript
'/community/': [
  {
    text: '关于',
    items: [
      { text: '关于社区', link: '/community/about' }
    ]
  },
  {
    text: '内容',
    items: [
      { text: '经验分享', link: '/community/experience' },     // 🔄 优化
      { text: '治疗经验', link: '/community/treatment' },       // 🔄 优化
      { text: '医院点评区', link: '/community/hospitals' },     // 🔄 降级
      { text: '心情驿站', link: '/community/mood' },           // 🔄 降级
    ]
  },
  {
    text: '知识库',      // 🆕 新增 - 指向百科和动态
    items: [
      { text: '百科知识', link: '/encyclopedia/' },
      { text: '最新动态', link: '/news/' },
    ]
  }
]
```

---

## 🔧 现有后端API路由

### 当前API (main.py)
```python
app.include_router(user.router, prefix="/api/user", tags=["用户"])
app.include_router(content.router, prefix="/api/content", tags=["内容"])         # ⏸️ 暂停
app.include_router(comment.router, prefix="/api/comment", tags=["评论"])        # 🔄 升级
app.include_router(comment_admin.router, prefix="/api/admin/comment", tags=["管理员-评论管理"])
app.include_router(rag.router, prefix="/api/rag", tags=["AI问答"])
```

### 精简后API
```python
app.include_router(user.router, prefix="/api/user", tags=["用户"])
app.include_router(rag.router, prefix="/api/rag", tags=["AI问答"])
app.include_router(comment.router, prefix="/api/comment", tags=["评论"])        # 保留，阶段3升级为 /api/community
app.include_router(comment_admin.router, prefix="/api/admin/comment", tags=["管理员-评论管理"])
# 🆕 新增（阶段2）
# app.include_router(vasi.router, prefix="/api/vasi", tags=["VASI评估"])
# 🆕 新增（阶段3）
# app.include_router(community.router, prefix="/api/community", tags=["社区"])
```

---

## 📝 改动清单

### 前端改动
1. **config.js** - 导航栏精简
   - ✅ 保留：首页、AI问答
   - 🆕 新增：AI病情量化
   - 🔄 更新：社区 → 病友社区
   - ⏸️ 暂停：百科、动态（移出主导航栏）

2. **config.js** - 社区侧边栏精简
   - ❌ 移除：闲置转让
   - 🔄 降级：医院点评、心情驿站
   - 🔄 优化：经验分享、治疗经验
   - 🆕 新增：知识库（指向百科和动态）

3. **index.md** - 首页改造
   - 重新设计为3个核心功能的卡片式布局
   - 移除所有非核心功能入口

### 后端改动
1. **API路由暂不改动**（阶段2-3再修改）
   - 保留现有API，避免破坏性改动
   - 阶段2新增VASI API
   - 阶段3升级评论API为社区API

---

## ✅ 审核标准

- [x] 所有功能已分类（保留/移除/暂停）
- [x] 导航栏改动清单明确
- [x] 后端API改动清单明确
- [x] 改动影响已评估
- [x] 无功能遗漏

---

## 📌 下一步

1. 前端精简改造（Day 2）
   - 修改 config.js 导航栏
   - 修改 config.js 侧边栏
   - 修改 index.md 首页

2. 后端API梳理（Day 3）
   - 创建MVP API设计文档
   - 确认数据库schema

---
