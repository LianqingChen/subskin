# SubSkin 社区后端 API

基于 FastAPI 的社区网站后端服务，提供用户认证、评论管理等功能。

## 项目结构

```
.
├── app/
│   └── main.py          # 主入口
├── api/
│   ├── user.py          # 用户登录注册
│   ├── comment.py       # 公开评论接口
│   ├── comment_admin.py # 管理员评论审核
│   └── content.py       # 内容接口（占位）
├── models/              # Pydantic 模型
│   ├── user.py
│   └── comment.py
├── services/            # 业务逻辑
│   ├── auth.py          # JWT 认证
│   └── comment.py       # 评论服务
├── database/
│   ├── database.py      # 数据库配置
│   ├── models.py        # ORM 模型
│   └── init_db.py       # 初始化脚本
├── requirements.txt     # 依赖
├── Dockerfile           # Docker 配置
├── start.sh             # 开发启动脚本
└── README.md
```

## 功能清单

- ✅ 用户注册 / 登录（JWT）
- ✅ 手机号码验证码登录/注册
- ✅ 评论提交
- ✅ 评论列表公开访问
- ✅ 管理员评论审核
- ✅ SQLite 开发数据库
- ✅ 生产环境支持 PostgreSQL

## API 文档

启动服务后访问：`http://localhost:8000/docs` 即可查看 Swagger 文档并在线测试。

## 本地开发

```bash
# 进入目录
cd web/backend

# 安装依赖
pip install -r requirements.txt

# 初始化数据库并创建管理员
python -m database.init_db

# 启动服务
./start.sh
```

默认管理员账号：
- 用户名: `admin`
- 密码: `admin`

**请务必修改默认密码！** 通过环境变量设置：

```bash
export ADMIN_USER=admin
export ADMIN_PASS=your-secure-password
export SECRET_KEY=your-secret-key-change-in-production
```

## 部署

参见 `../deploy/docker-compose.yml` 示例。

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `DATABASE_URL` | 数据库连接 URL | `sqlite:///./data/subskin.db`<br>生产环境示例：`postgresql://user:pass@localhost/subskin` |
| `SECRET_KEY` | JWT 密钥 | - |
| `ADMIN_USER` | 初始管理员用户名 | `admin` |
| `ADMIN_PASS` | 初始管理员密码 | `admin` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token 有效期 | `30` |
| `SMS_PROVIDER` | 短信服务商 | `log` (开发模式，打印不发送)<br>`aliyun` / `tencent` |
| `SMS_ACCESS_KEY_ID` | 短信 API Access Key | - |
| `SMS_ACCESS_KEY_SECRET` | 短信 API Secret | - |
| `SMS_SIGN_NAME` | 短信签名 | `SubSkin` |
| `SMS_TEMPLATE_CODE` | 短信模板码 | - |
