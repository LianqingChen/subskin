# SubSkin 管理后台（admin.subskin.cn）打开缓慢 · 性能诊断与整改方案

| 项目 | 内容 |
|---|---|
| 文档类型 | 性能诊断报告 + 可执行整改方案（供后续 Agent 执行） |
| 诊断日期 | 2026-10-24 |
| 诊断对象 | `admin.subskin.cn`（`web/admin/` 独立 SPA）+ 共享 Nginx / 主机网络 |
| 线上版本 | `version.json` → `buildTime: 1792823588376`（2026-10-24 14:33 构建，`env: admin`） |
| 当前状态 | 诊断阶段仅 `modprobe tcp_bbr` 加载了内核模块（拥塞控制仍是 cubic）；Nginx 配置、前端源码、构建产物均未变更。**2026-10-24 复核修订后开始执行 P0 / P1-a，进度见 §8** |
| 结论一句话 | 后端与数据库不慢；慢在**首屏 2.89MB 未压缩资源 + 所有静态资源被 `no-store` 禁止缓存**，每次打开都要重新完整下载 |

> ⚠️ **给执行 Agent 的第一条提醒**
> 本报告中的"实测网络速度"是在东京出口的沙箱（103.170.233.116）上对生产服务器测得的，绝对带宽不代表国内用户；**字节数、响应头、日志统计、配置状态是客观的，可以据此整改**。

---

## 0. 执行约束（先读，避免违规）

依据 `/root/subskin/AGENTS.md`：

1. **管理后台没有 staging**：`web/admin/` 构建即上线（`npx vite build` → `/usr/share/nginx/html/subskin-admin/`）。
2. **Nginx 配置是生产配置**：`/etc/nginx/conf.d/subskin-admin.conf` 只影响 admin；`/etc/nginx/nginx.conf` 影响全站（subskin.cn / staging / admin / 其它 vhost）。改完必须 `nginx -t` 再 `systemctl reload nginx`。
3. **后端是三个环境共享单实例**：本次整改**不需要**改后端逻辑，也不要重启后端（除 P3 图片转码需要改 `labeling_admin.py` 时）。
4. **不要为了 P0/P1 去动 `web/app/`**，主站与 admin 是两个工程。
5. **P2 构建前必读**（2026-10-24 复核后重写）：
   - 线上 dist（`buildTime` 1792823588376）**已经包含**当前工作区的在途改动（打标重构、公开图库；`labeling-*`、`ExternalGallery`、`AuthThumb` 等 chunk 来自未跟踪源码），且 `web/admin/src` 下没有比该构建更新的文件。所以"构建会首次发布在途改动"的担心不成立；**真实风险是 P2 回归与在途改动混在一起，难以归因**。
   - `vite.config.ts` 把 `outDir` 写死为生产目录且 `emptyOutDir: true`：**任何不带 `--outDir` 的构建都会直接覆盖生产**。
   - 因此 P2 必须：① 先 `npx vite build --outDir /tmp/admin-baseline` 构建基线并记录体积；② P2 改动同样先构建到临时目录，用 `npx vite preview --outDir <dir> --port 5175` 验证（preview 默认继承 `server.proxy`，连接真实后端 127.0.0.1:8000，只做只读回归）；③ 回归通过后才执行不带 `--outDir` 的正式构建。
   - `web/admin` 下有大量 `??` 未跟踪源码（如 `useAuthImage.ts`、`components/labeling/`、`api/training.ts`）。**不要 `git stash` / `git clean` / `git checkout`**，否则线上已在用的源码会丢失。

---

## 1. 结论（TL;DR）

| 层 | 是否瓶颈 | 证据 |
|---|---|---|
| 前端资源体积 | ✅ **主因** | 首屏 2.89MB（`index.js` 1.45MB + `Dashboard.js` 1.02MB + CSS 143KB + 字体 185KB） |
| Nginx 压缩 | ✅ **主因** | 全站 `gzip` 关闭，`nginx -T \| grep -c gzip` = 0；带 `Accept-Encoding: gzip,br` 仍返回裸 body |
| HTTP 缓存 | ✅ **主因** | 带 hash 的 `/assets/*` 返回 `cache-control: no-cache, no-store, must-revalidate`，刷新即重下 |
| 前端打包策略 | ⚠️ 次因 | 全量注册 naive-ui（打进 5 个项目未使用的组件）；Dashboard 全量 `echarts`（1.02MB）同步加载 |
| 打标图片接口 | ⚠️ 次因 | `size=full` 直接回 982KB PNG，且 `private, no-store`，每次进工作台/灯箱重下 |
| TCP 链路 | ⚠️ 放大因素 | 客户端链 RTT 220ms、重传 258 段、`cwnd` 塌到 1、交付速率 50–95KB/s；服务器拥塞控制 = `cubic` |
| 后端 API | ❌ 否 | 最慢接口 248ms（30 天趋势），其余 ≤ 20ms |
| 数据库 | ❌ 否 | 主库 63MB，`user_events` 32,988 行，索引齐全 |

**一句话给用户**：不是后端慢，是"一次要下 2.9MB、而且每次打开都重新下"。修 Nginx 两项配置即可去掉约 2/3 流量，并让重复打开接近 0 下载。

---

## 2. 实测数据（可复现）

### 2.1 首屏资源清单（`/#/dashboard`）

构建产物目录 `/usr/share/nginx/html/subskin-admin/`：

| 资源 | 原始大小 | gzip 后 | 说明 |
|---|---:|---:|---|
| `assets/index-C6INnhKC.js` | 1,516,258 B（1.45 MiB） | 422,292 B | Vue + Router + Pinia + **naive-ui 全量** |
| `assets/Dashboard-BURiJsh5.js` | 1,043,181 B（1.02 MB） | 344,915 B | **全量 echarts**，默认路由首屏即加载 |
| `assets/index-CQh8sKMn.css` | 142,850 B（139 KiB） | 23,345 B | Tailwind + 基础样式 |
| `assets/remixicon-CZw4FkzQ.woff2` | 189,216 B（185 KiB） | 188,163 B | 图标字体（woff2 已压缩） |
| `index.html` | 793 B | — | 不可缓存（正确） |
| **合计** | **≈ 2.89 MB** | **≈ 0.98 MB** | **gzip 可省约 66%** |

复现：
```bash
cd /usr/share/nginx/html/subskin-admin/assets
for f in index-C6INnhKC.js Dashboard-BURiJsh5.js index-CQh8sKMn.css remixicon-CZw4FkzQ.woff2; do
  printf "%-30s raw=%8d gzip=%8d\n" "$f" "$(stat -c%s "$f")" "$(gzip -c "$f" | wc -c)"
done
```

### 2.2 Nginx 响应头（关键证据）

```bash
curl -skI -H 'Host: admin.subskin.cn' -H 'Accept-Encoding: gzip, deflate, br' \
  https://127.0.0.1/assets/index-C6INnhKC.js
```
实际返回：
```
HTTP/2 200
content-length: 1516258
etag: "6adc512d-1722e2"
cache-control: no-cache, no-store, must-revalidate
（没有任何 content-encoding / vary）
```
字体同样：
```
content-type: font/woff2
content-length: 189216
cache-control: no-cache, no-store, must-revalidate
```

全局压缩状态：
```bash
nginx -T | grep -c gzip        # → 0
grep -n gzip /etc/nginx/nginx.conf   # → 无有效配置（仅 nginx.conf.default 里被注释的 #gzip on;）
```

### 2.3 访问日志统计（2026-10-24 00:00–20:56，`/var/log/nginx/access.log`）

| 指标 | 数值 |
|---|---|
| 来自 `admin.subskin.cn` referer 的请求 | **1,066 次 / 72.3 MB** |
| `assets/index-C6INnhKC.js` | **31 次 / 27.8 MB**（占后台流量 38%）；31 次**全是 200、零次 304**（完全没有缓存），其中仅 12 次传满 1.5MB，**19 次中途中断**（平均 940KB） |
| `assets/index-CQh8sKMn.css` | 35 次 / 4.4 MB |
| `assets/remixicon-CZw4FkzQ.woff2` | 16 次 / 2.9 MB |
| `api/vasi/admin/labeling/tasks/180/image?size=full` | 20 次，**每次 982,096 B** |
| 同页任务 187/188/189/193... 的 `size=full` | 各 16–19 次，单次 700KB–1MB |
| 全站 `/assets/*` 当日 | 6,585 次 / 83.7 MB |

复现：
```bash
cd /var/log/nginx
awk '$11 ~ /admin.subskin.cn/ {b+=$10; c++} END {printf "admin: %d req, %.1f MB\n", c, b/1048576}' access.log
awk '$11 ~ /admin.subskin.cn/ && $7 ~ /assets/ {u=$7; sub(/\?.*/,"",u); b[u]+=$10; c[u]++} END {for (u in b) printf "%8.1f MB %4d %s\n", b[u]/1048576, c[u], u}' access.log | sort -rn | head
```

> 解读：这些 hash 资源本应"一次下载、永久复用"，但因 `no-store`，一天内被重复请求 31 次；更严重的是其中约 61%（19/31）没下完就断了，说明相当一部分打开动作在首屏资源完成前就被放弃或卡死，与 §2.5 的丢包/低 `cwnd` 现象互相印证。

### 2.4 后端 API 与数据库（排除项）

直接对 `127.0.0.1:8000` 用管理员 JWT 压测（同一台机器，排除网络）：

| 接口 | 耗时 | 响应大小 |
|---|---:|---:|
| `GET /api/users/me` | 9.0 ms | 396 B |
| `GET /api/analytics/overview` | 16.6 ms | 119 B |
| `GET /api/analytics/trend?days=30` | **247.9 ms** | 1.5 KB |
| `GET /api/analytics/page-views?days=7` | 10.9 ms | 662 B |
| `GET /api/analytics/feature-usage?days=7` | 8.1 ms | 213 B |
| `GET /api/admin/users?page=1&page_size=20` | 9.9 ms | 6.2 KB |
| `GET /api/admin/llm/modules` | 4.9 ms | 4.3 KB |
| `GET /api/admin/prompts` | 3.7 ms | 12.5 KB |

`AnalyticsService` 直调（跳过 HTTP）：`overview` 13–22ms、`trend(30)` 245ms（逐日 3 条 SQL × 30 天）、`page_views` 9ms、`feature_usage` 6ms。

数据库（**注意不要看错库**）：
```
主库（生产，systemd WorkingDirectory=/root/subskin + DATABASE_URL=sqlite:///./data/subskin.db）
  /root/subskin/data/subskin.db                     63 MB
  user_events 32,988 / users 25 / posts 107 / vasi_assessments 5
  索引：ix_user_events_created_at / event_type / uid / client_fingerprint 均在
另一个库（不同用途，排查用户数据时不要用它）
  /root/subskin/web/backend/data/subskin.db         189 MB（documents 7841 等）
```

> 后端唯一的可优化点是 `trend` 的 N+1（30 天 × 3 查询 = 90 条 SQL，245ms）。**与"页面打开慢"无关**，列为可选优化。

### 2.5 网络链路（放大因素）

观察真实的 admin 客户端 `150.241.210.223` 的 TCP 状态：
```
rtt:241ms  retrans:258/2325  cwnd:1  ssthresh:2  delivery_rate:95kbps  lost:2
rtt:234ms  retrans:141/1174  cwnd:2  delivery_rate:52kbps
```
服务器拥塞控制：
```bash
sysctl net.ipv4.tcp_congestion_control   # → cubic
sysctl net.ipv4.tcp_available_congestion_control  # → reno cubic（诊断中 modprobe tcp_bbr 后变为 reno cubic bbr，模块至今已加载）
```
> 主机虚拟化类型为 `kvm`（`systemd-detect-virt`），内核参数可写，不存在"容器禁止改拥塞控制"的情况。
同机单连接 vs 8 并发（东京 → 服务器）：
```
单连接 415 KB/s（HTTP/2 所有资源共用这一条连接）
8 并发 2,652 KB/s（≈ 6.4 倍）
```
**含义**：HTTP/2 把 2.9MB 全压在一根连接上；一旦这条连接丢包，`cwnd` 塌到 1–2，页面就会"卡住很久"。**减少字节数 + 换 BBR，是这条链路上最有效的两件事。**

---

## 3. 根因清单

### R1 · Nginx 全局未开启 gzip（P0）
- 位置：`/etc/nginx/nginx.conf`（`http{}` 内无 `gzip`；模板 `nginx.conf.default:33` 是注释）
- 影响：JS/CSS/JSON/HTML 全部裸传，首屏多传约 1.9MB。

### R2 · 带 hash 的静态资源被禁止缓存（P0）
- 位置：`/etc/nginx/conf.d/subskin-admin.conf`
  ```nginx
  location / {
      try_files $uri $uri/ /index.html;
      add_header Cache-Control "no-cache, no-store, must-revalidate" always;
      include /etc/nginx/snippets/subskin-security-headers.conf;
  }
  ```
- 问题：admin 没有为 `/assets/` 单独配置 location，所有 Vite hash 产物继承了 `no-store`。
- 影响：日志中同一文件一天被下载 31 次（27.8MB）。

### R3 · 前端包体过大（P2）
- `web/admin/src/main.ts`：
  ```ts
  import naive from 'naive-ui'   // 第 3 行
  app.use(naive)                 // 第 11 行
  ```
  全量注册导致主包把未使用组件也打进去。实测在 `index-*.js` 中命中 `cascader / color-picker / transfer / carousel / slot-machine`，而源码里这些组件的使用数为 **0**。
- `web/admin/src/views/Dashboard.vue:92`：`import * as echarts from 'echarts'`，整包 1.02MB，且是**静态 import**，阻塞首屏渲染（Dashboard 还是 `/` 的默认重定向目标）。

### R4 · 打标图片 1MB PNG + no-store（P3）
- `web/backend/api/labeling_admin.py:127`：
  ```python
  headers = {"Cache-Control": "private, no-store"}
  if size == "full":
      return Response(content=image, media_type="image/png", headers=headers)
  ```
- 实测单张 982,096 B；灯箱/工作台每次打开都重新拉。
- `web/admin/src/components/labeling/GalleryLightbox.vue:43` 使用 `useAuthImage(id)`，默认 `size='full'`（`useAuthImage.ts:5` 默认值），灯箱翻页每张约 1MB。
- 注意：`GalleryLightbox.vue`、`useAuthImage.ts`、`labeling_admin.py` 目前都是**未跟踪文件**（`??`），行号随在途改动会漂移，改前以 grep 为准。

### R5 · 拥塞控制（P1，放大因素）
- `cubic` 在高丢包/高 RTT 链路上恢复慢；BBR 模块可用（已加载）但未启用。
- ~~TLS 会话复用缺失~~（2026-10-24 复核撤回）：实测 TLS1.2 `openssl s_client -reconnect` 6 次连接中 5 次 `Reused`，nginx 默认的 session ticket 已在工作；`ssl_session_cache` 被注释只影响 session-id 方式，收益很小。原报告的验证命令在 TLS1.3 下永远显示 `New`（`s_client` 行为），不能作为依据。该项降为可选，见 P1-b。

---

## 4. 整改方案

### 优先级总览

| 优先级 | 内容 | 预计收益 | 风险 | 耗时 |
|---|---|---|---|---|
| **P0** | 开启 gzip + `/assets/` 长缓存 | 首屏 2.89MB → **≈1.0MB**；重复打开静态资源 **≈0** | 低（配置层，可回滚） | 10 分钟 |
| **P1** | BBR（`ssl_session_cache` 降为可选） | 高丢包链路吞吐提升（幅度以实测为准） | 中低（全局网络参数） | 10 分钟 |
| **P2** | echarts 按需 + naive-ui 按需（仅方案 A）+ chunk 加载失败兜底 | 原始体积 Dashboard 约 -0.6MB；gzip 后合计约 -0.3–0.4MB，P0+P2 后首屏约 0.6–0.7MB | 中（需临时目录构建 + 全路由回归） | 半天 |
| **P3** | 打标图 WebP/JPEG + 允许私有缓存 | 单图 1MB → 100–200KB | 中（影响标注画质，需产品确认） | 半天 |
| **P4** | 静态资源上 CDN | 国内首屏 1s 级 | 高（DNS/证书/备案） | 1–2 天 |

建议执行顺序：**P0 → P1 → 观察 1 天 → P2 → P3 →（可选）P4**。

---

### P0 · Nginx：gzip + 静态资源长缓存

#### P0-a 开启 gzip

推荐先放在 **admin 的 server 块**（影响面最小，符合"最小爆炸半径"），验证后再决定是否提升到 `http{}` 全站。

编辑 `/etc/nginx/conf.d/subskin-admin.conf`，在 `server { ... }` 内（`root` 之后即可）加入：

```nginx
    # ── 压缩（2026-10-24 性能整改）──
    gzip on;
    gzip_vary on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_disable "msie6";
    gzip_types
        text/plain
        text/css
        text/xml
        application/javascript
        application/json
        application/xml
        application/rss+xml
        image/svg+xml;
```

注意事项：
- **不要**把 `image/png`、`image/jpeg`、`font/woff2` 加进 `gzip_types`（已压缩，纯浪费 CPU）。
- 若确认要全站受益，可把同一段挪到 `/etc/nginx/nginx.conf` 的 `http{}` 内；此时会影响 subskin.cn / staging，需按 AGENTS.md 提前告知用户。
- `gzip_static on` 需要预生成 `.gz` 文件；**本次不做**（Vite 默认不产出），如后续要上，配合 `vite-plugin-compression`。

#### P0-b 给 `/assets/` 加长缓存

在 `/etc/nginx/conf.d/subskin-admin.conf` 的 `server{}` 内，**放在 `location / {` 之前**：

```nginx
    # Vite 产物文件名带内容 hash，可长期缓存；构建会清空目录并按内容重新生成文件名，
    # 只要 index.html 不缓存，就不会出现旧 hash 404。
    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
        include /etc/nginx/snippets/subskin-security-headers.conf;
    }
```

要点：
- **`Cache-Control` 这一行绝对不要加 `always`**：`always` 会让 404/5xx 也带上 `immutable, max-age=1y`。构建用 `emptyOutDir`，发版瞬间文件缺失产生的 404 会被浏览器缓存一年，该浏览器之后一直白屏。不带 `always` 时只有 2xx/3xx 带缓存头。（安全头 snippet 里自带 `always`，不受影响。）
- **不要写 `expires 1y;`** 与 `add_header Cache-Control` 同时使用，否则会输出两个 `Cache-Control` 头；只保留 `add_header`。
- `add_header` 在子 location 中出现会**取消继承** server 级的 `add_header`，所以必须重复 `include` 安全头片段（现有配置也是这么做的）。
- `location /` 与 `location = /index.html` 的 `no-store` **保持原样**，`version.json` 也继续走 `no-store`。
- 不要把 `/api/` 纳入缓存；后端响应头不动。
- 发版副作用（需要 P2 里的兜底）：`emptyOutDir: true` 会删掉上一版 chunk。已打开的旧标签页点到没访问过的懒加载路由时，会请求到已被删除的文件而 404（原先是 `try_files` 回落成 `index.html` 返回 200 + HTML，同样导致 `import()` 失败）。immutable 不能缓解这一点——浏览器只会缓存访问过的 chunk。`/assets/` 不带 `try_files`，缺失文件返回真正的 404，这是预期行为；前端兜底见 P2-d。

#### P0 验证

```bash
nginx -t && systemctl reload nginx

# 1) 压缩生效
curl -skI -H 'Host: admin.subskin.cn' -H 'Accept-Encoding: gzip' \
  https://127.0.0.1/assets/index-C6INnhKC.js | grep -iE 'content-encoding|content-length|vary'
# 期望：content-encoding: gzip；content-length ≈ 422xxx；vary: Accept-Encoding

# 2) 长缓存生效
curl -skI -H 'Host: admin.subskin.cn' \
  https://127.0.0.1/assets/index-C6INnhKC.js | grep -i cache-control
# 期望：cache-control: public, max-age=31536000, immutable

# 3) index.html 仍不可缓存
curl -skI -H 'Host: admin.subskin.cn' https://127.0.0.1/ | grep -i cache-control
# 期望：no-cache, no-store, must-revalidate

# 3b) 缺失的 hash 文件必须是 404 且不带 immutable（防止 404 被缓存一年）
curl -skI -H 'Host: admin.subskin.cn' https://127.0.0.1/assets/does-not-exist-XXXX.js | grep -iE 'HTTP/|cache-control'
# 期望：404，且没有 cache-control 头

# 3c) 安全头仍在 /assets/ 上
curl -skI -H 'Host: admin.subskin.cn' https://127.0.0.1/assets/index-C6INnhKC.js | grep -iE 'strict-transport|x-content-type|x-frame'

# 4) 浏览器二次打开：DevTools Network 里静态资源应显示 "(memory cache)/(disk cache)"，
#    服务器 access.log 不再新增 /assets/* 记录
```

#### P0 回滚
```bash
# 备份文件名在执行时已固定，回滚直接用实际文件名（见 §8 登记）
cp /etc/nginx/conf.d/subskin-admin.conf.bak-<执行时的时间戳> /etc/nginx/conf.d/subskin-admin.conf
nginx -t && systemctl reload nginx
```
> 执行前务必先备份：`cp -a /etc/nginx/conf.d/subskin-admin.conf /etc/nginx/conf.d/subskin-admin.conf.bak-$(date +%F-%H%M)`，并把实际文件名记入 §8。

---

### P1 · 主机网络：BBR + TLS 会话复用

#### P1-a BBR

```bash
# 1. 加载模块（诊断时已 modprobe，此处幂等；未加载时 available 只有 reno/cubic）
modprobe tcp_bbr
sysctl net.ipv4.tcp_available_congestion_control   # 期望出现 bbr

# 2. 持久化模块
echo tcp_bbr > /etc/modules-load.d/tcp_bbr.conf

# 3. 启用 fq + bbr
cat > /etc/sysctl.d/99-subskin-bbr.conf <<'EOF'
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF
sysctl --system

# 4. 验证
sysctl net.ipv4.tcp_congestion_control          # → bbr
ss -tin state established '( sport = :443 )' | grep -m1 -A1 bbr
```

注意：
- 这是**全局**内核参数，主站/staging 也会受益，但同时改变全部出向 TCP 行为。建议在低峰执行，并在执行后 24h 观察 `/var/log/nginx/error.log`、`ss -ti` 的重传率。
- 主机为 `kvm`，参数可写；若 `sysctl --system` 后 `tcp_congestion_control` 仍不是 bbr，则跳过本项，不要强行折腾。
- BBR 只改善**服务器发出**的流量（即下载方向），对本场景正好是主要方向。
- 回滚：`sysctl -w net.ipv4.tcp_congestion_control=cubic && sysctl -w net.core.default_qdisc=pfifo_fast && rm /etc/sysctl.d/99-subskin-bbr.conf /etc/modules-load.d/tcp_bbr.conf`（`default_qdisc` 执行前先记下原值再回填）。

#### P1-b TLS 会话复用（**可选，默认不做**）

实测 TLS1.2 已能复用会话（见 R5），本项收益很小，仅在后续发现握手确为瓶颈时再做。`/etc/nginx/nginx.conf` 中被注释的：
```nginx
# ssl_session_cache shared:SSL:1m;
# ssl_session_timeout  10m;
```
改为在 `http{}` 内启用（或写入各 server 块）：
```nginx
ssl_session_cache   shared:SSL:10m;
ssl_session_timeout 10m;
ssl_session_tickets on;
```
验证：必须加 `-tls1_2`（TLS1.3 下 `-reconnect` 永远显示 `New`，不可靠）：`openssl s_client -connect 127.0.0.1:443 -servername admin.subskin.cn -tls1_2 -reconnect </dev/null 2>/dev/null | grep -E '^(Reused|New)'`。

---

### P2 · 前端构建优化（正式构建即上线；先在临时目录验证）

#### 前置
1. 阅读 §0 第 5 条：在途改动已在线上，**禁止 stash / clean / checkout**；构建与验证一律先用 `--outDir` 指向临时目录。
2. 先跑类型检查：`cd web/admin && npx vue-tsc --noEmit`。
3. 基线：`npx vite build --outDir /tmp/admin-baseline`，记录 `ls -lS /tmp/admin-baseline/assets | head`。
4. 正式构建会直接发布到 `admin.subskin.cn`，**没有回滚目录**；正式构建前把当前 dist 备份：
   ```bash
   cp -a /usr/share/nginx/html/subskin-admin /root/deploy-backups/subskin-admin-$(date +%F-%H%M)
   ```

#### P2-a 移除 naive-ui 全量注册

`web/admin/src/main.ts`：
```diff
-import naive from 'naive-ui'
 ...
 app.use(createPinia())
 app.use(router)
-app.use(naive)
 app.mount('#app')
```

`web/admin/src/App.vue` 目前依赖全局注册的 3 个 provider，需改为本地导入：
```diff
-import { darkTheme } from 'naive-ui'
+import { darkTheme, NConfigProvider, NDialogProvider, NMessageProvider } from 'naive-ui'
```
（模板里是 `<n-config-provider>` 等 kebab-case，本地注册后可直接解析。）

**只走方案 A**（2026-10-24 复核）：模板里有 40 多种 `<n-*>` 组件、约 20 个文件、kebab/Pascal 写法混用，方案 B 手工补 import 极易漏，漏了只会在运行时报 "Failed to resolve component"。若 npm 源不可用，**跳过 P2-a，仅做 P2-b/P2-d**。

- **方案 A**：引入 `unplugin-vue-components` + `NaiveUiResolver`，按使用自动注册，彻底不依赖全局注册：
  ```bash
  cd /root/subskin/web/admin && npm i -D unplugin-vue-components
  ```
  ```ts
  // vite.config.ts
  import Components from 'unplugin-vue-components/vite'
  import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'
  // plugins: [vue(), tailwindcss(), Components({ resolvers: [NaiveUiResolver()], dts: false }), ...]
  ```
  `useMessage` / `useDialog` 在各文件已显式从 `naive-ui` 导入，不受影响。
  构建后必须逐路由点一遍（login / dashboard / users / moderation / hospital-risk / content-gen / llm-config / prompt-config / image-labeling / external-gallery / training / site-maintenance / dev-docs / planning），控制台不得出现 "Failed to resolve component"。

预期：主包显著缩小（naive-ui 全量约 700KB+ 未压缩的一部分），具体数值以构建报告为准，**不要照抄本文档的估算**。

#### P2-b echarts 按需 + 延迟加载

`web/admin/src/views/Dashboard.vue`（最小改动版，先做这一步即可拿到大部分收益）：

```diff
-import * as echarts from 'echarts'
+import { use, init, graphic } from 'echarts/core'
+import type { EChartsType } from 'echarts/core'
+import { LineChart } from 'echarts/charts'
+import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
+import { CanvasRenderer } from 'echarts/renderers'
+
+use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])
```

修改点：
1. `echarts.init(el, 'dark', { renderer: 'canvas' })` → `init(el, 'dark', { renderer: 'canvas' })`，**保留 `'dark'`**。
   - 复核结论：echarts 5.6.0 的 `echarts/core` 重导出 `lib/core/echarts.js`，其中已 `registerTheme('light', ...)` / `registerTheme('dark', ...)`（`:2268-2269`），按需引入后 `'dark'` 依然可用，视觉不变。（原稿称需去掉主题，是错误的。）
   - 已核对 Dashboard 的 `setOption`：3 条 `line` 系列 + `tooltip` / `legend` / `grid` / 类目轴与数值轴 + `LinearGradient`，上面注册列表完整。
2. `new echarts.graphic.LinearGradient(...)` → `new graphic.LinearGradient(...)`；图表变量类型改为 `let trendChart: EChartsType | null = null`。
3. （**可选，做完 1–2 再考虑**）如果想让首屏完全不等图表库：把上面 6 行 echarts import 全部删掉，改成在 `onMounted` 里动态加载：
   ```ts
   async function loadChartLib() {
     const [core, charts, comps, renderers] = await Promise.all([
       import('echarts/core'), import('echarts/charts'),
       import('echarts/components'), import('echarts/renderers'),
     ])
     core.use([charts.LineChart, comps.GridComponent, comps.TooltipComponent, comps.LegendComponent, renderers.CanvasRenderer])
     return { init: core.init, graphic: core.graphic }
   }
   ```
   `initTrendChart` 改为 `async`，先 `const { init, graphic } = await loadChartLib()` 再建图；`EChartsType` 继续用 `import type`（不产生运行时体积）。注意 `loadChartLib()` 要缓存结果，避免每次 resize/切换重复加载。
4. `manualChunks`（可选，配合 P0 长缓存后收益主要在首次）：
   ```ts
   build: {
     rollupOptions: { output: { manualChunks: { echarts: ['echarts/core', 'echarts/charts', 'echarts/components', 'echarts/renderers'] } } }
   }
   ```

预期：Dashboard chunk 1.02MB → 约 0.35–0.45MB（gzip 后约 110–140KB，较现状 gzip 后 345KB 省约 200KB+），且不再阻塞首屏。

#### P2-c 图标字体（推荐评估）
`main.ts` 全量引入 `remixicon/fonts/remixicon.css`（185KB woff2，**不可再压缩**）。P0+P2 之后它会占首屏传输量近三成，是剩余最大的单项。可选做法：只打包实际用到的图标（内联 SVG 或 iconify 按需）；至少保持现状并在验收中单列统计。

#### P2-d chunk 加载失败兜底（新增）
`router/index.ts` 与 `main.ts` 目前没有任何 chunk 加载失败处理。发版后旧标签页点到懒加载路由会 404 并卡住。在 `main.ts` 中加入：
```ts
window.addEventListener('vite:preloadError', () => { window.location.reload() })
```
（如需防循环刷新，可用 `sessionStorage` 标记一次后不再刷新。）

#### P2 验证
```bash
cd /root/subskin/web/admin
npx vue-tsc --noEmit                                    # 必须 0 error
npx vite build --outDir /tmp/admin-p2                   # 临时目录，不影响生产
ls -lS /tmp/admin-p2/assets | head                      # 与基线对比，回填本报告
npx vite preview --outDir /tmp/admin-p2 --port 5175     # 连真实后端，做下方回归清单
# 回归全部通过 + 备份 dist 之后：
npx vite build                                          # 正式发布（不带 --outDir）
cat /usr/share/nginx/html/subskin-admin/version.json    # buildTime 已更新
```
回归清单（全部零控制台报错、图表正常渲染、表格/弹窗/消息提示正常）：
- [ ] `/#/login` 能登录、错误提示正常（依赖 `useMessage` provider）
- [ ] `/#/dashboard` 趋势图、7/14/30 切换、窗口 resize
- [ ] `/#/users` 列表/分页/封号弹窗
- [ ] `/#/moderation`、`/#/hospital-risk`
- [ ] `/#/llm-config`、`/#/prompt-config`
- [ ] `/#/image-labeling`、`/#/image-labeling/:id`、`/#/external-gallery`
- [ ] `/#/training`、`/#/site-maintenance`（含终端）
- [ ] `/#/dev-docs`、`/#/planning`

---

### P3 · 打标图片瘦身（需产品确认画质）

文件：`web/backend/api/labeling_admin.py`（`task_image`，约 113-138 行）

**前置（2026-10-24 复核新增）**：该文件是**未跟踪文件**（`git status` 为 `??`），**无法用 `git checkout` 回滚**。改动前必须 `cp web/backend/api/labeling_admin.py /root/deploy-backups/labeling_admin.py.$(date +%F-%H%M)`。

建议改法：
1. `size=full` **保持 PNG 原图**（标注画布需要像素级保真，不要动）。
2. 新增 `size=medium`（长边 ≤ 1600px，WebP q=85），供 `GalleryLightbox` 使用：
   ```python
   if size == "medium":
       photo.thumbnail((1600, 1600))
       out = io.BytesIO()
       photo.convert("RGB").save(out, format="WEBP", quality=85, method=4)
       body = out.getvalue()
       etag = hashlib.sha256(body).hexdigest()[:16]   # 文件头需 import hashlib
       return Response(content=body, media_type="image/webp",
                       headers={"Cache-Control": "private, max-age=3600",
                                "ETag": f'"{etag}"'})
   ```
   同时必须改三处，否则会出错：
   - 路由参数 `size: str = Query("full", pattern="^(full|thumb)$")` → `pattern="^(full|medium|thumb)$"`，否则 `size=medium` 返回 422。
   - 路由函数目前是 `async def`，里面做 Pillow 解码/编码是同步 CPU 工作，会阻塞共享后端的事件循环；改为普通 `def`（FastAPI 自动放入线程池）。
   - 前端 `GalleryLightbox.vue:43` 改为 `useAuthImage(..., 'medium')`，`useAuthImage` 与 `api/labeling.ts` 的 `fetchTaskImage` 联合类型都扩为 `'full' | 'medium' | 'thumb'`。
3. 缓存：把 `private, no-store` 改为 `private, max-age=3600`（浏览器私有缓存，不进共享缓存；这些是用户医疗影像，**禁止 public**）。若安全评审要求更严格，用 `private, no-cache` + ETag，让浏览器发 304 而不是重下 1MB。
4. 后端属于共享单实例：改完需 `systemctl restart subskin-backend`，会短暂影响三个环境 → **必须先告知用户**（AGENTS.md Rule 3）。

预期：灯箱单图 982KB → 100–200KB，且翻回上一张不再重下。

---

### P4 · CDN（可选，收益最大但改动最大）

- 现状：`admin.subskin.cn` DNS 直连 `124.174.0.212`，无 CDN。
- 若上国内 CDN：只把 `/assets/` 指到 CDN（`index.html`、`/api` 保持回源），需配置回源 Host、证书、缓存规则（与 P0-b 一致），并确认备案与日志合规。
- 收益：首屏从"受单连接拥塞控制限制"变成"就近边缘节点"，对高丢包客户端改善最明显。
- 风险：DNS/证书/回源配置属于生产变更，必须单独评审，不建议与 P0–P3 同批执行。

---

## 5. 验收标准（量化）

| 指标 | 现状 | 目标 |
|---|---|---|
| 首屏传输字节（新访客，dashboard） | ≈2.89 MB | **≤1.1 MB**（P0 后）；P2 后 ≤0.75 MB（其中 woff2 字体 188KB 不可压缩） |
| 重复打开静态资源下载 | 2.89 MB / 次 | **0 B**（仅 `index.html` 793B + API） |
| `assets/*` 响应头 | `no-store` | `public, max-age=31536000, immutable` |
| JS/CSS 响应头 | 无 `content-encoding` | `content-encoding: gzip` + `vary: Accept-Encoding` |
| 主包当日下载次数 | 31 次/天 | 每个浏览器每周 ≤1 次（发版才变） |
| 单图灯箱 | 982 KB PNG | ≤200 KB（P3） |
| 后端 API | ≤248ms | 不变 |
| `nginx -t` | — | 通过；reload 无 error |
| 控制台 | — | 全部路由 0 error / 0 "Failed to resolve component" |

验收命令（发布后跑一遍并回填）：
```bash
# 传输体积（模拟浏览器 gzip）
for f in index-C6INnhKC.js Dashboard-BURiJsh5.js index-CQh8sKMn.css; do
  echo -n "$f  "; curl -sk -H 'Host: admin.subskin.cn' -H 'Accept-Encoding: gzip' \
    -o /dev/null -w 'code=%{http_code} size=%{size_download} ttfb=%{time_starttransfer}\n' \
    "https://127.0.0.1/assets/$f"
done
```

---

## 6. 回滚

| 变更 | 回滚 |
|---|---|
| Nginx（P0/P1-b） | `cp` 备份文件回原位 → `nginx -t` → `systemctl reload nginx` |
| 内核参数（P1-a） | `sysctl -w net.ipv4.tcp_congestion_control=cubic`；删除 `/etc/sysctl.d/99-subskin-bbr.conf` 与 `/etc/modules-load.d/tcp_bbr.conf`（`default_qdisc` 回填 §8 登记的原值） |
| 前端构建（P2） | `rm -rf /usr/share/nginx/html/subskin-admin && cp -a /root/deploy-backups/subskin-admin-<ts> /usr/share/nginx/html/subskin-admin` |
| 后端图片（P3） | 文件未跟踪，**不能用 git**：`cp /root/deploy-backups/labeling_admin.py.<ts> web/backend/api/labeling_admin.py` + `systemctl restart subskin-backend` |

> 前端没有 staging，构建前备份 dist 是**强制动作**。

---

## 7. 附：本次诊断使用的命令（可复现）

```bash
# 1) 体积
ls -lS /usr/share/nginx/html/subskin-admin/assets | head
gzip -c .../index-*.js | wc -c

# 2) 压缩/缓存头
nginx -T | grep -c gzip
curl -skI -H 'Host: admin.subskin.cn' -H 'Accept-Encoding: gzip, br' \
  https://127.0.0.1/assets/index-C6INnhKC.js

# 3) 日志
awk '$11 ~ /admin.subskin.cn/ {b+=$10; c++} END {printf "%d req, %.1f MB\n", c, b/1048576}' \
  /var/log/nginx/access.log

# 4) 后端（需要管理员 JWT；只读接口）
curl -s -o /dev/null -w '%{time_starttransfer}\n' \
  -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/analytics/trend?days=30

# 5) 链路
sysctl net.ipv4.tcp_congestion_control
ss -tin state established '( sport = :443 )' | head -20
```

---

## 8. 变更记录

| 日期 | 内容 | 执行人 |
|---|---|---|
| 2026-10-24 | 完成诊断，输出本报告；**未实施任何修改** | 诊断 Agent |
| 2026-10-24 | 复核修订：撤回 TLS 复用根因；修正 `always`+immutable 缓存 404 风险、echarts `'dark'` 误判、P3 回滚与 `medium` 参数遗漏、日志解读、§0 在途改动描述；新增 P2-d chunk 兜底；诊断阶段已加载 `tcp_bbr` 模块（登记） | 诊断 Agent |
| — | 每次生产变更（含 nginx/内核/构建）完成后，须同步在 `DEPLOY_LOG.md` 追加一条（沿用其格式，admin 构建附 buildTime） | 执行人 |
| 2026-10-24 21:51 | **P0 已执行**：备份 `/etc/nginx/conf.d/subskin-admin.conf.bak-2026-10-24-2151`；在 admin server 块加入 gzip 与 `location /assets/`（Cache-Control 不带 `always`）；`nginx -t` 通过，`systemctl reload nginx`。验证：GET `index-*.js` 1,516,258 → 426,056 B（`content-encoding: gzip`、`vary`、`immutable`），`Dashboard-*.js` → 348,505 B，CSS → 23,370 B；`woff2` 未压缩；`/assets/` 缺失文件 404 且无 cache-control；`index.html`/`version.json` 仍 `no-store`；安全头齐全；`/api/health` 200；subskin.cn / staging 200。注：reload 后最初几次请求由旧 worker 应答，结果不准，约 10 秒后复测正常。 | 执行 Agent |
| 2026-10-24 21:53 | **P1-a 已执行**：写入 `/etc/modules-load.d/tcp_bbr.conf`、`/etc/sysctl.d/99-subskin-bbr.conf`，`sysctl -p` 生效。原值：`tcp_congestion_control=cubic`、`default_qdisc=fq_codel`（回滚时回填）。仅新连接使用 bbr。待 24h 后检查重传率与 `/var/log/nginx/error.log`。 | 执行 Agent |
| — | P1-b（可选，默认不做）/ P2 / P3 执行后在此登记（含构建体积对比） | 待填 |
