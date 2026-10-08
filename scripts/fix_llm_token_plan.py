#!/usr/bin/env python
"""幂等脚本：把 llm_module_configs 表中 4 个百炼视觉/审核模块切到 Token Plan。

变更内容：
  - base_url  → Token Plan 专属 compatible-mode URL
  - chat_model/vision_model → Token Plan 清单内模型
      vasi / medical_report → qwen3.7-plus（视觉理解，已实测 200）
      content_safety / im_moderation → qwen3.6-flash（文本+视觉，已实测 200）
  - api_key → .env 的 DASHSCOPE_API_KEY（sk-sp-）Fernet 单次加密写回
  - provider 保持 dashscope，is_active=1

幂等：解密一次若已是新 key 则仅同步元数据，不改 api_key。
只改 live 库 data/subskin.db；执行前请先备份。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

ENV_PATH = ROOT / "web" / "backend" / ".env"
load_dotenv(ENV_PATH, override=True)

LIVE_DB = ROOT / "data" / "subskin.db"
os.environ["DATABASE_URL"] = f"sqlite:///{LIVE_DB}"

from web.backend.services.llm_config_service import (  # noqa: E402
    _get_fernet,
    encrypt_api_key,
)
from web.backend.database.database import SessionLocal  # noqa: E402
from web.backend.database.models import LLMModuleConfig  # noqa: E402

TP_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

MODULE_TARGETS = {
    "vasi": {"chat_model": "qwen3.7-plus", "vision_model": "qwen3.7-plus"},
    "medical_report": {"chat_model": "qwen3.7-plus", "vision_model": "qwen3.7-plus"},
    "content_safety": {"chat_model": "qwen3.6-flash", "vision_model": "qwen3.6-flash"},
    "im_moderation": {"chat_model": "qwen3.6-flash", "vision_model": "qwen3.6-flash"},
}


def mask(key: str | None) -> str:
    if not key:
        return ""
    return f"{key[:4]}****{key[-4:]}" if len(key) > 8 else "****"


def decrypt_once(fernet, stored: str | None) -> str:
    if not stored:
        return ""
    try:
        return fernet.decrypt(stored.encode("utf-8")).decode("utf-8")
    except Exception:
        return stored


def main() -> int:
    new_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not new_key:
        print("[ABORT] .env 未配置 DASHSCOPE_API_KEY，无法切换。")
        return 1
    if not LIVE_DB.exists():
        print(f"[ABORT] live 库不存在：{LIVE_DB}")
        return 1

    fernet = _get_fernet()
    print("=" * 78)
    print(f"live DB       : {LIVE_DB}")
    print(f"新 key 掩码    : {mask(new_key)}  (len={len(new_key)})")
    print(f"目标 base_url : {TP_BASE_URL}")
    print("=" * 78)

    db = SessionLocal()
    fixed = 0
    skipped = 0
    try:
        for mkey, target in MODULE_TARGETS.items():
            module = db.query(LLMModuleConfig).filter_by(module_key=mkey).first()
            if not module:
                print(f"  - {mkey:<16} NOT FOUND（跳过）")
                continue

            stored = module.api_key or ""
            d1 = decrypt_once(fernet, stored)
            key_changed = False
            if d1 == new_key:
                pass  # api_key 已是目标值
            else:
                # 双重加密 / 单次加密但值错误 / 明文旧 key → 统一用新 key 加密一次
                module.api_key = encrypt_api_key(new_key)
                key_changed = True

            meta_changed = False
            if module.base_url != TP_BASE_URL:
                module.base_url = TP_BASE_URL
                meta_changed = True
            if module.chat_model != target["chat_model"]:
                module.chat_model = target["chat_model"]
                meta_changed = True
            if module.vision_model != target["vision_model"]:
                module.vision_model = target["vision_model"]
                meta_changed = True
            if module.provider != "dashscope":
                module.provider = "dashscope"
                meta_changed = True
            if not module.is_active:
                module.is_active = True
                meta_changed = True

            if key_changed:
                print(
                    f"  - {mkey:<16} api_key 已更新 -> {mask(new_key)}  "
                    f"元数据={'同步' if meta_changed else '否'}  "
                    f"model={target['chat_model']}"
                )
                fixed += 1
            elif meta_changed:
                print(
                    f"  - {mkey:<16} api_key 已正确(幂等)  元数据已同步  "
                    f"model={target['chat_model']}"
                )
                fixed += 1
            else:
                print(f"  - {mkey:<16} 已是目标状态(幂等跳过)")
                skipped += 1

        db.commit()
        print("\n" + "=" * 78)
        print(f"完成：更新={fixed}  幂等跳过={skipped}")
        print("=" * 78)
        return 0
    except Exception as e:  # noqa: BLE001
        db.rollback()
        print(f"[ERROR] 切换失败，已回滚：{e}")
        import traceback

        traceback.print_exc()
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
