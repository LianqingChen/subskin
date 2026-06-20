---
title: 白友社区标签栏改版：关注/推荐/同城
type: feat
status: active
date: 2026-04-25
---

# 白友社区标签栏改版：关注/推荐/同城

## Overview

将白友社区顶部标签栏从 `推荐/热门/最新` 改为 `关注/推荐/同城`，默认显示推荐页。推荐内容基于用户浏览行为智能排序。关注页基于真实的用户关注关系。同城页基于用户地理位置进行城市级推荐。同时构建完整的用户社交关系系统（关注/取关/拉黑/举报）。

## Problem Frame

当前社区标签栏（推荐/热门/最新）功能单一：
- "热门" 和 "推荐" 区分度低，用户感知模糊
- 没有社交关注关系，无法追踪感兴趣的用户
- 没有地理位置维度，无法发现同城病友
- 个性化推荐虽然已有基础设施，但未充分发挥

用户需要：
1. 真正个性化的智能推荐
2. 关注感兴趣的用户，看到他们的新帖子
3. 发现同城的病友和内容

## Requirements Trace

- R1. 标签栏改为 关注/推荐/同城 三个标签
- R2. 默认显示推荐页（已有基础，需优化）
- R3. 用户关注系统：关注/取关/拉黑/举报
- R4. 关注页：显示所有关注用户的新帖
- R5. 同城页：基于用户地理位置的城市级帖子推荐
- R6. 地理位置授权流程（浏览器权限弹窗 + 隐私提示）
- R7. 关注/推荐/同城 三种 feed 均需分页加载

## Scope Boundaries

- 不包括即时通讯/私信功能
- 不包括兴趣圈子/话题群组
- 不包括基于用户画像的深度推荐模型（仅使用已有交互日志）
- 地理位置仅用于同城推荐，不用于用户跟踪或广告
- 隐私方面：地理位置仅前端获取后传给服务器用于筛选，不持久化存储位置历史
- 搜索框语义保持纯文本/标签搜索不变，不做改动
- 后台 API 仍然支持 `hot`/`latest` feed_type（兼容性），但前端不再暴露

## Context & Research

### 已有的基础设施

| 组件 | 文件位置 | 状态 |
|------|----------|------|
| 推荐引擎 | `web/backend/services/recommendation.py` | ✅ 已有 `_personalized_recommend`、`_hot_posts`、`_following_posts`（雏形） |
| 社区API | `web/backend/api/community.py` | ✅ 已支持 `feed_type` 参数: `recommend`/`hot`/`following` |
| 交互日志 | `web/backend/database/models.py` UserInteractionLog | ✅ 已有，用于推荐学习 |
| CommunityService | `web/backend/services/community.py` | ✅ 已有基础 CRUD |
| 社区前端页 | `web/app/src/views/CommunityPage.vue` | ✅ 已有标签栏 + FeedWaterfall 结构 |
| PostCard 组件 | `web/app/src/components/community/PostCard/*.vue` | ✅ 3 种卡片类型 |

### 缺失的组件

| 组件 | 描述 |
|------|------|
| UserFollow 模型 | 用户关注关系（followee_id, follower_id） |
| UserBlock 模型 | 拉黑关系（blocker_id, blocked_id） |
| UserReport 模型 | 举报记录（reporter_id, target_id, reason） |
| Follow API | POST/GET/DELETE /community/follow 系列端点 |
| Block API | POST/GET/DELETE /community/block 系列端点 |
| Report API | POST /community/report |
| 前端地理位置逻辑 | navigator.geolocation + 权限管理 |
| 推荐引擎 _local_posts | 同城 feed 逻辑 |

## Key Technical Decisions

1. **关注关系用单独关联表**：`user_follows` 表（followee_id, follower_id），支持双向查询
2. **拉黑与关注互斥**：拉黑自动取关，关注时检查是否已被拉黑
3. **同城用城市名匹配**：前端通过经纬度反向地理编码获取城市名，传到后端筛选帖子（帖子需标注城市字段）
4. **帖子增加 city 字段**：在 Post 模型上新增 `city` 可空字段，发布时可根据用户 IP 或授权获取
5. **推荐逻辑分层**：推荐页 = 个性化推荐（80%）+ 探索发现（20%）；关注页 = 按时间线聚合关注用户帖子；同城页 = 同城市帖子 + 按热度排序
6. **分页统一**：三种 feed 统一使用 `offset/limit` 分页
7. **前端标签默认为推荐**：`activeFeedType` 默认值改为 `'recommend'`

## Implementation Units

### Phase 1: 数据库与后端基础设施

- [ ] **Unit 1: 用户社交关系模型**

**Goal:** 创建 UserFollow、UserBlock、UserReport 三个数据库模型

**Dependencies:** None

**Files:**
- Modify: `web/backend/database/models.py` (新增 3 个模型)
- Test: `tests/backend/database/test_social_models.py`

**Approach:**
- `UserFollow`: id, followee_id(FK→users), follower_id(FK→users), created_at
  - `__table_args__ = (UniqueConstraint("followee_id", "follower_id"),)`
  - `backref` 到 User: `"following"` (我关注的) 和 `"followers"` (关注我的)
- `UserBlock`: id, blocker_id(FK→users), blocked_id(FK→users), created_at
  - `__table_args__ = (UniqueConstraint("blocker_id", "blocked_id"),)`
- `UserReport`: id, reporter_id(FK→users), target_user_id(FK→users), post_id(FK→posts, nullable), reason, created_at

**Patterns to follow:**
- 现有模型使用 SQLAlchemy 声明式基类 + relationship + backref 模式
- 参考 `Bookmark` 模型的 UniqueConstraint 模式

**Test scenarios:**
- 用户 A 关注用户 B，验证 UserFollow 记录存在
- 重复关注返回错误或静默忽略
- 用户 A 拉黑用户 B，验证互斥关系
- 举报请求包含必填字段

**Verification:**
- 数据库迁移脚本执行成功
- 模型关系可以正确创建和查询

- [ ] **Unit 2: 社交关系 API 端点**

**Goal:** 实现关注/取关/拉黑/举报 API 端点

**Dependencies:** Unit 1 (模型)

**Files:**
- Create: `web/backend/api/social.py`
- Modify: `web/backend/app/main.py` (注册 router)
- Test: `tests/backend/api/test_social.py`

**Approach:**
- `POST /api/community/follow/{user_id}` — 关注用户
- `DELETE /api/community/follow/{user_id}` — 取关
- `GET /api/community/follow/following` — 我关注的列表
- `GET /api/community/follow/followers` — 关注我的列表
- `POST /api/community/block/{user_id}` — 拉黑用户（自动取关）
- `DELETE /api/community/block/{user_id}` — 取消拉黑
- `GET /api/community/block/list` — 已拉黑用户列表
- `POST /api/community/report` — 举报（接收 target_user_id, post_id?, reason）
- 关注者列表默认仅自己可见（隐私保护），后续可扩展为"公开/仅好友"

**Patterns to follow:**
- 参考 `web/backend/api/community.py` 的 `@router.post("/posts/{post_id}/like")` 模式
- 使用 `Depends(auth)` 进行认证

**Test scenarios:**
- 未登录用户返回 401
- 关注不存在用户返回 404
- 拉黑后自动取关
- 举报记录写入数据库

**Verification:**
- API 测试全部通过
- 手动 curl 验证端点行为

- [ ] **Unit 3: Post 模型增加城市字段**

**Goal:** 在 Post 模型上新增 `city` 字段，支持同城推荐

**Dependencies:** None

**Files:**
- Modify: `web/backend/database/models.py` (Post 增加 city 列)
- Modify: `web/backend/models/community.py` (响应模型中增加 city)
- Modify: `web/backend/api/community.py` (create/update post 支持 city 参数)
- Test: `tests/backend/services/test_community.py`

**Approach:**
- Post 模型: `city = Column(String(100), nullable=True, index=True)` — 城市名
- Pydantic 响应模型: `city: Optional[str] = None`
- 发布帖子 API 增加可选 `city` 参数
- 已有帖子 city 为 null（不迁移历史数据）

**Migration:**
```python
ALTER TABLE posts ADD COLUMN city VARCHAR(100)
```

**Test scenarios:**
- 发布帖子时指定 city，验证保存成功
- 不指定 city 时正常发布
- API 响应包含 city 字段

**Verification:**
- 数据库列添加成功
- API 返回数据包含 city 字段

- [ ] **Unit 8: 关注按钮 UI 组件**

**Goal:** 在用户头像/卡片上增加关注/取关按钮

**Dependencies:** Unit 1, Unit 2 (后端 APIs 已就绪)

**Files:**
- Create: `web/app/src/components/community/FollowButton.vue`
- Modify: `web/app/src/views/PostDetailPage.vue` (作者区域增加关注按钮)

**Approach:**
- `FollowButton` 组件:
  - Props: `targetUserId, initialFollowed`
  - 显示 "关注" 或 "已关注"，点击切换
  - 调用 `POST /api/community/follow/{id}` / `DELETE /api/community/follow/{id}`
  - 灰色 "关注" 按钮 → 点击 → 红色 "已关注" 状态

**Patterns to follow:**
- 参考现有点赞按钮的交互模式
- 参考 `PostDetailPage.vue` 中的 author card 区域

**Test scenarios:**
- 未登录点击关注 → 弹出登录框
- 已登录点击关注 → 按钮变为"已关注"
- 再次点击 → 取关成功
- 拉黑用户后 → 关注按钮隐藏或禁用

**Verification:**
- 手动测试关注/取关流程
- 关注后在"关注"标签页看到对方帖子

### Phase 2: 后端推荐逻辑

- [ ] **Unit 4: 推荐引擎接入真实关注关系**

**Goal:** 修改 `_following_posts` 使用真实的 UserFollow 关系

**Dependencies:** Unit 1 (UserFollow 模型)

**Files:**
- Modify: `web/backend/services/recommendation.py`
  - `_following_posts`: 从 UserFollow 查询 followee_ids
- Test: `tests/backend/services/test_recommendation.py`

**Approach:**
- 当前 `_following_posts` 使用点赞过的作者作为关注来源 → 改为查询 `UserFollow.followee_id`
- 如果没有任何关注，降级为热门推荐（已有逻辑）
- 按发布时间降序排列
- 过滤被拉黑用户的帖子（查询 UserBlock）

**Test scenarios:**
- 用户关注了 A，关注页显示 A 的新帖
- 用户没有关注任何人，关注页降级为热门
- 拉黑 B 后，B 的帖子不出现在关注页
- 被拉黑用户无法关注拉黑者

**Verification:**
- 关注页正确显示关注用户的帖子
- 拉黑后帖子不再显示
- 测试覆盖关注/未关注/拉黑三种情况

- [ ] **Unit 5: 同城推荐 _local_posts**

**Goal:** 实现同城 feed 逻辑

**Dependencies:** Unit 3 (Post.city 字段)

**Files:**
- Modify: `web/backend/services/recommendation.py`
  - 新增 `_local_posts(city, page, page_size)` 方法
  - 更新 `get_feed` 支持 `feed_type="local"`
- Modify: `web/backend/api/community.py`
  - `list_posts` 支持 `feed_type="local"` 和 `city` 参数
- Test: `tests/backend/services/test_recommendation.py`

**Approach:**
- `_local_posts(city, page, page_size)`:
  - 查询 `Post.city == city AND Post.is_private == False`
  - 按热度排序（like_count * 2 + comment_count * 3 + read_count * 0.1）
  - 支持分页
- API 端: `GET /api/community/posts?feed_type=local&city=深圳市`

**Test scenarios:**
- 指定城市，返回该城市的帖子
- 城市名大小写不敏感
- 城市无帖子时返回空列表
- 不同城市返回不同结果

**Verification:**
- API 返回正确的同城帖子
- 前端传入城市参数后获取正确数据

### Phase 3: 前端改版

- [ ] **Unit 6: 前端标签栏改为 关注/推荐/同城**

**Goal:** 修改 CommunityPage.vue 标签栏

**Dependencies:** None (先改 UI，后端接口已就绪)

**Files:**
- Modify: `web/app/src/views/CommunityPage.vue`

**Approach:**
- `activeFeedType` 类型改为 `'follow' | 'recommend' | 'local'`
- 默认值保持 `'recommend'`
- 标签数组: `[{ key: 'follow', label: '关注' }, { key: 'recommend', label: '推荐' }, { key: 'local', label: '同城' }]`
- `loadPosts` 中 `feed_type` 映射: `'follow' → 'following'`, `'recommend' → 'recommend'`, `'local' → 'local'`
- 当 `activeFeedType === 'local'` 时，调用 `navigator.geolocation` 获取位置（见 Unit 7）
- 搜索框保持不变（支持标签搜索和文本搜索）

**Patterns to follow:**
- 现有 `v-for` 渲染标签按钮的模式
- 现有 `activeFeedType` 切换 + `watch` 重新加载数据的模式

**Test scenarios:**
- 切换到"关注"标签，发送 feed_type=following 请求
- 切换到"推荐"标签，发送 feed_type=recommend 请求
- 切换到"同城"标签，触发地理位置授权
- 默认进入社区时，"推荐"标签高亮

**Verification:**
- 三个标签正确渲染和切换
- API 请求参数正确

- [ ] **Unit 7: 前端地理位置授权**

**Goal:** 实现浏览器地理位置获取，传递给同城 API

**Dependencies:** Unit 6

**Files:**
- Modify: `web/app/src/views/CommunityPage.vue`
- Create: `web/app/src/composables/useGeolocation.ts`

**Approach:**
- 新建 `useGeolocation` composable:
  - `getCity(): Promise<string | null>` — 调用 `navigator.geolocation.getCurrentPosition()`
  - 使用本地 GeoJSON 城市边界数据进行反向地理编码（点面判断），无需在线 API
  - 缓存结果到 localStorage，避免每次请求
  - 处理权限拒绝、超时、位置不可用等情况
- 在 CommunityPage 中，当切换到同城标签时：
  1. 检查 localStorage 是否有缓存的 city
  2. 如果没有，调用 `getCity()`
  3. 如果用户拒绝，显示手动选择城市的提示
  4. 将城市名作为参数传给 API

**Privacy:**
- 只有用户主动切换到同城标签时才请求位置
- 位置数据仅用于本次请求，不服务端持久化
- 明显提示用户"我们将获取您的位置以推荐同城内容"

**Test scenarios:**
- 用户允许位置 → 获取城市名 → 调用同城 API
- 用户拒绝位置 → 显示"请手动选择城市"
- 位置获取超时 → 优雅降级
- 已缓存城市 → 直接使用缓存

**Verification:**
- 同城标签页首次切换时显示权限提示
- 授权后正确传递城市参数

**Goal:** 实现浏览器地理位置获取，传递给同城 API

**Dependencies:** Unit 6

**Files:**
- Modify: `web/app/src/views/CommunityPage.vue`
- Create: `web/app/src/composables/useGeolocation.ts`

**Approach:**
- 新建 `useGeolocation` composable:
  - `getCity(): Promise<string | null>` — 调用 `navigator.geolocation.getCurrentPosition()`
  - 使用 `reverseGeocode(lat, lng)` 将经纬度转换为城市名（使用免费反向地理编码 API 或本地映射表）
  - 缓存结果到 localStorage，避免每次请求
  - 处理权限拒绝、超时、位置不可用等情况
- 在 CommunityPage 中，当切换到同城标签时：
  1. 检查 localStorage 是否有缓存的 city
  2. 如果没有，调用 `getCity()`
  3. 如果用户拒绝，显示手动选择城市的提示
  4. 将城市名作为参数传给 API

**地理编码方案:**
- 使用本地 GeoJSON 城市边界查找，而非在线 API：
  - 预置一份约 400 个中国城市的紧凑型 GeoJSON 文件
  - 使用 `turf.js` 的 `booleanPointInPolygon` 进行点面判断
  - 无 API 调用、无速率限制、无需网络
  - 文件体积小，可随前端构建打包

**Privacy:**
- 只有用户主动切换到同城标签时才请求位置
- 位置数据仅用于本次请求，不服务端持久化
- 明显提示用户"我们将获取您的位置以推荐同城内容"

**Test scenarios:**
- 用户允许位置 → 获取城市名 → 调用同城 API
- 用户拒绝位置 → 显示"请手动选择城市"
- 位置获取超时 → 优雅降级
- 已缓存城市 → 直接使用缓存

**Verification:**
- 同城标签页首次切换时显示权限提示
- 授权后正确传递城市参数

### Phase 4: 数据迁移

- [ ] **Unit 9: 数据库迁移脚本**

**Goal:** 为已有数据库添加新表和新列

**Dependencies:** Unit 1, Unit 3 (模型定义)

**Files:**
- Create: `web/backend/database/migration_add_social_models.py`
- Create: `web/backend/database/migration_add_post_city.py`

**Approach:**
```python
# user_follows
CREATE TABLE IF NOT EXISTS user_follows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    followee_id INTEGER NOT NULL REFERENCES users(id),
    follower_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(followee_id, follower_id)
)

# user_blocks
CREATE TABLE IF NOT EXISTS user_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocker_id INTEGER NOT NULL REFERENCES users(id),
    blocked_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(blocker_id, blocked_id)
)

# user_reports
CREATE TABLE IF NOT EXISTS user_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL REFERENCES users(id),
    target_user_id INTEGER NOT NULL REFERENCES users(id),
    post_id INTEGER REFERENCES posts(id),
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

# posts.city
ALTER TABLE posts ADD COLUMN city VARCHAR(100)
```

**Verification:**
- 建表 SQL 执行成功
- 插入测试数据成功
- 查询索引工作正常

## System-Wide Impact

- **API 路由**: 新增 `/api/community/follow/*`, `/api/community/block/*`, `/api/community/report`
- **数据库**: 新增 3 张表，posts 表新增 1 列
- **前端路由**: 不变，仅修改社区页面内部组件
- **推荐引擎**: `get_feed` 新增 `feed_type="local"` 分支
- **认证**: 所有社交操作需要登录（Depends(auth)）
- **隐私**: 地理位置使用需要用户授权，不可后台静默获取

## Risks & Dependencies

1. **地理位置 API 兼容性**: 部分浏览器或 HTTPS 环境拒绝位置请求 → 需要降级方案（手动输入城市）
2. **反向地理编码 API 可用性**: Nominatim 有调用频率限制 → 增加缓存和降级方案
3. **现有推荐引擎改动风险**: `_following_posts` 从点赞作者改为真实关注 → 确保降级逻辑完整
4. **数据库迁移**: 已有生产数据库需要安全迁移 → 使用事务 + 备份
5. **前端热更新**: Vite dev server 重启后需要验证所有组件正常工作

## Phased Delivery

### Phase 1 — 后端基础 + 关注按钮（Units 1, 2, 3, 8, 9）
数据库模型 → 社交 API → Post.city 字段 → 关注按钮组件 → 迁移脚本。完成后可测试关注/取关/拉黑/举报流程，关注按钮在帖子详情页可用。

### Phase 2 — 推荐引擎（Units 4, 5）
关注 feed 接入真实关系 → 同城 feed 逻辑。完成后三种 feed 类型后端就绪。

### Phase 3 — 前端改造（Units 6, 7, 8）
标签栏改版 → 地理位置 → 关注按钮。完成后全部功能可用。

## Documentation / Operational Notes

- 部署后需要运行迁移脚本创建新表
- 同城功能需要 HTTPS 环境（地理位置 API 要求安全上下文）
- 关注数和粉丝数可在用户资料页展示（后续）
- 推荐引擎的效果需要通过埋点持续优化
