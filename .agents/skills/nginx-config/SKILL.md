---
name: nginx-config
description: "SubSkin Nginx 配置管理 — 三个环境的 nginx 配置"
---

# Nginx Config Skill

> SubSkin Nginx 配置管理 — 三个环境的 nginx 配置
>
> **触发词**: nginx配置、nginx修改、SSL、路由、反向代理

---

## 三个 Nginx 配置文件

| 环境 | 配置文件 | Server Name | Root |
|---|---|---|---|
| Production | `/etc/nginx/conf.d/subskin.conf` | `subskin.cn`, `www.subskin.cn` | `/usr/share/nginx/html/subskin/` |
| Staging | `/etc/nginx/conf.d/subskin-staging.conf` | `staging.subskin.cn` | `/usr/share/nginx/html/subskin-staging/` |
| Admin | `/etc/nginx/conf.d/subskin-admin.conf` | `admin.subskin.cn` | `/usr/share/nginx/html/subskin-admin/` |

**Repo 中的模板**在 `web/deploy/` 目录，但**服务器上的配置是实际生效的**（可能有细微差异）。

---

## 常见操作

### 查看/编辑配置

```bash
# 查看当前生效的配置
cat /etc/nginx/conf.d/subskin.conf
cat /etc/nginx/conf.d/subskin-staging.conf
cat /etc/nginx/conf.d/subskin-admin.conf
```

### 修改后验证

```bash
# 验证配置语法
nginx -t

# 如果通过，重启 nginx
systemctl restart nginx
```

### 关键配置项

每个配置文件都包含：
- SSL 证书路径（Let's Encrypt 或阿里云）
- `/api/*` 反向代理到 `127.0.0.1:8000`（uvicorn）
- `/encyclopedia/*` 指向 VitePress 百科目录
- SPA fallback：`try_files $uri $uri/ /index.html`
- 静态资源缓存策略
- Gzip 压缩配置

### ⛔ 禁止事项

- 修改 nginx 配置后**必须**先 `nginx -t` 验证再重启
- 不要删除 `/api/*` 反向代理（前端依赖后端 API）
- 不要修改 SSL 配置除非有新的证书
- 不要关闭 gzip（影响加载速度）