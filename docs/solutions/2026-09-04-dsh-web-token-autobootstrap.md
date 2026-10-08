# dsh.subskin.cn 免 token 登录：nginx 自动引导 DSH 浏览器会话

日期：2026-09-04

## 问题

`dsh.subskin.cn`（DeepSeek Harness Web，反代本机 3080）有两层认证：

1. nginx Basic Auth（用户名 `admin`，`/etc/nginx/auth/dsh.htpasswd`）
2. DSH 应用自身的 token 认证——URL 里必须带 `?token=<launch token>` 才能种下签名 cookie

launch token 由 `processLaunchToken()`（内存 WeakMap）在**每次进程启动时随机生成**，只打印到 journal，无任何 CLI 参数 / 配置文件 / 环境变量可以固定或关闭（已核实 `dsh web --help`、`settings.yaml`、源码 `dsh-client-connection/lib/index.js`）。新浏览器（或 cookie 过期后）打开站点会看到 401 "dsh web authentication required; reopen the URL printed by dsh web"，形同"打不开"。

注意：签名 cookie 的 secret 持久化在 `/root/.dsh/.credentials.yaml`（`records["client-connection/browser-session"]`），**cookie 本身可跨重启存活**（Max-Age 30 天）；token 只在新浏览器首次引导时需要。

## 方案

让 nginx 在 DSH 应用返回 401（浏览器尚无有效会话）时，自动重定向到带当前 token 的 URL 完成引导，全程对用户不可见。用户只需 Basic Auth 用户名密码。

### 改动清单

| 文件 | 作用 |
|------|------|
| `/usr/local/bin/dsh-sync-token.sh` | 从 journal（限本进程启动后）提取新 launch token，写入 nginx map 变量并 reload nginx；失败不会拖垮 dsh-web 启动 |
| `/etc/systemd/system/dsh-web.service.d/override.conf` | `ExecStartPost=/usr/local/bin/dsh-sync-token.sh`，每次启动/重启后自动同步 |
| `/etc/nginx/conf.d/dsh.conf` | `location /` 增加 `proxy_intercept_errors on` + `error_page 401 = @dsh_bootstrap`；`@dsh_bootstrap` 见下 |
| `/etc/nginx/conf.d/dsh-token.conf` | 自动生成的 map（`$dsh_token`），勿手改 |

### `@dsh_bootstrap` 的三个分支（顺序重要）

1. `$dsh_has_basic_auth = 0`（map 自 `$http_authorization`）→ 原样 `401`。**必须**：`error_page` 同样会截获 nginx 自身 Basic Auth 的 401，不加此分支会把它也变成 302，浏览器永远弹不出密码框（且 token 会泄露给未认证者）。
2. `$arg_token` 非空仍 401 → 如实 `401`，防止重启竞态下的重定向循环。
3. 其余（已过 Basic Auth、无有效会话）→ `302 $uri?token=$dsh_token`，应用种下 30 天 cookie 后自动回到原页面。

### 踩坑记录

- `if ($http_authorization = "")` 判断**缺失的**请求头不可靠（变量"未找到"≠空串），必须先经 `map` 归一化再比较。
- auth_basic 自带的 `WWW-Authenticate` 质询头在 error_page 内部重定向后会保留；当前 401 响应里会出现两条相同的质询头，RFC 允许、浏览器正常弹框，无功能影响。

## 验证（2026-09-04 实测通过）

- 无凭据 → 401 + Basic 质询（浏览器弹密码框）✓
- 正确凭据 + 新浏览器 → 302 → `/?token=…` → 200 + `dsh-auth-*` cookie ✓
- 仅凭 cookie → 200、零重定向 ✓
- 带无效 token → 如实 401、无循环 ✓
- `/dsh-admin/`（9099）不受影响 ✓
- `systemctl restart dsh-web` → ExecStartPost 自动同步新 token 并 reload nginx ✓
- 重启前引导的 cookie 在重启后依然有效（secret 持久化）✓

## 运维提示

- token 泄露风险：`$dsh_token` 只会出现在**已通过 Basic Auth** 的响应 Location 头里，token 单独泄露无用（所有请求仍被 Basic Auth 挡住）。
- 若手动改了 `dsh.conf`，`nginx -t && systemctl reload nginx` 即可；`dsh-token.conf` 会在下次 dsh-web 重启时自动重写。
- 兜底：自动引导失效时，仍可手动 `journalctl -u dsh-web --no-pager | grep 'token='` 取最新 token 访问。
