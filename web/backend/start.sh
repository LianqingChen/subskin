#!/bin/bash
# SubSkin Backend 启动脚本

# 激活虚拟环境（如果使用）
# source ../../.venv/bin/activate

# 设置 PYTHONPATH 以支持模块导入
export PYTHONPATH=/root/subskin:/root/subskin/web/backend

# 启动 uvicorn
# Bind to 127.0.0.1 by default — the backend must NOT be exposed directly to
# the internet; nginx fronts it and terminates TLS. Exposing 0.0.0.0 bypassed
# nginx's auth/rate-limit/security headers and served raw API on :8000.
# Override with HOST env var if a different bind is explicitly required.
HOST="${HOST:-127.0.0.1}"
# --reload is a development convenience; in production it should be off (set
# RELOAD=0 or rely on the systemd unit which doesn't pass --reload).
RELOAD_FLAG=""
if [ "${RELOAD:-1}" = "1" ]; then
  RELOAD_FLAG="--reload"
fi
uvicorn app.main:app --host "$HOST" --port 8000 $RELOAD_FLAG
