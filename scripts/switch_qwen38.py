#!/usr/bin/env python3
"""一次性迁移：三大模块切换为 qwen3.8-max（视觉 qwen3.7-plus）+ 更新 DashScope API key。

用法：
    NEW_DASHSCOPE_API_KEY=sk-... python3 scripts/switch_qwen38.py

幂等：可重复执行。只改 vasi / medical_report / skin_report 三个模块。
API key 通过环境变量传入，不硬编码。
"""
import os
import sys
from pathlib import Path

ROOT = Path("/root/subskin")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

NEW_KEY = os.environ.get("NEW_DASHSCOPE_API_KEY", "").strip()
if not NEW_KEY:
    print("ERROR: 请设置 NEW_DASHSCOPE_API_KEY 环境变量")
    sys.exit(1)

ENV_PATH = ROOT / "web" / "backend" / ".env"

# ── 1. 更新 .env ──
env_text = ENV_PATH.read_text(encoding="utf-8")
updated_lines = []
changed = {"key": False, "chat": False, "vision": False}
for line in env_text.splitlines():
    if line.startswith("DASHSCOPE_API_KEY="):
        updated_lines.append(f"DASHSCOPE_API_KEY={NEW_KEY}")
        changed["key"] = True
    elif line.startswith("DASHSCOPE_CHAT_MODEL="):
        updated_lines.append("DASHSCOPE_CHAT_MODEL=qwen3.8-max")
        changed["chat"] = True
    elif line.startswith("DASHSCOPE_VISION_MODEL="):
        updated_lines.append("DASHSCOPE_VISION_MODEL=qwen3.7-plus")
        changed["vision"] = True
    else:
        updated_lines.append(line)
ENV_PATH.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
print("✓ .env updated:", changed)

# 重新加载 env（拿到 LLM_ENCRYPTION_KEY）
env = {}
for line in (ENV_PATH.read_text(encoding="utf-8")).splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
for k in ("LLM_ENCRYPTION_KEY", "DATABASE_URL", "DASHSCOPE_API_KEY"):
    os.environ[k] = env.get(k, "")

# ── 2. 更新 DB llm_module_configs ──
from web.backend.services.llm_config_service import encrypt_api_key, decrypt_api_key
from web.backend.database.database import SessionLocal
from web.backend.database.models import LLMModuleConfig

TARGETS = ["vasi", "medical_report", "skin_report"]

db = SessionLocal()
try:
    for module_key in TARGETS:
        m = db.query(LLMModuleConfig).filter(LLMModuleConfig.module_key == module_key).first()
        if not m:
            print(f"⚠ {module_key}: 模块行不存在，跳过（启动时 init_defaults 会自动补齐）")
            continue
        m.chat_model = "qwen3.8-max"
        m.vision_model = "qwen3.7-plus"
        m.provider = "dashscope"
        m.api_key = encrypt_api_key(NEW_KEY)
        m.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        m.is_active = True
        print(f"✓ {module_key}: chat={m.chat_model} vision={m.vision_model} key={decrypt_api_key(m.api_key)[:8]}...")
    db.commit()
finally:
    db.close()

print("\n完成。请重启后端：systemctl restart subskin-backend")
