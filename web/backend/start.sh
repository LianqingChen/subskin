#!/bin/bash
# SubSkin Backend 启动脚本

# 激活虚拟环境（如果使用）
# source ../../.venv/bin/activate

# 设置 PYTHONPATH 以支持模块导入
export PYTHONPATH=/root/subskin:/root/subskin/web/backend

# 启动 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
