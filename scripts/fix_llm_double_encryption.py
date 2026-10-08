#!/usr/bin/env python
"""
一次性幂等修复脚本：修复 llm_module_configs 表中 DeepSeek 文本模块的
api_key 双重 Fernet 加密问题，并把这些模块切到 DeepSeek 官方。

根因（Eric 调查确认）：
  live 库 llm_module_configs 的 rag 等记录 api_key 被 Fernet 双重加密，
  运行时 decrypt_api_key() 只解密一次 → 返回内层密文 gAAAAA... 当作
  api_key 传给 OpenAI 兼容客户端 → 401 AuthenticationError → 问答报
  "AI 问答服务暂时不可用"。

本脚本逻辑（幂等、可重跑）：
  - 用 web/backend/.env 的 LLM_ENCRYPTION_KEY 初始化项目 Fernet
    （复用 llm_config_service 的密钥派生逻辑 _build_fernet/_get_fernet）
  - 读 .env 的 DEEPSEEK_API_KEY 明文
  - 对每个目标 DeepSeek 文本模块
    (rag / briefing / encyclopedia / summarizer / translator)：
      * 解密一次；
      * 若结果已是 DEEPSEEK_API_KEY 明文（单次加密、值正确）→ 仅同步
        provider/chat_model/base_url/is_active 元数据，不改 api_key（幂等跳过）；
      * 若解密一次后仍以 gAAAAA 开头（双重加密）→ 解密第二次拿内层明文，
        再用 encrypt_api_key(DEEPSEEK_API_KEY) 加密一次写回，并同步元数据；
      * 若解密一次得到的是“别的明文 key”（如旧百炼 key，单次加密但值错误）
        → 用 encrypt_api_key(DEEPSEEK_API_KEY) 重新加密一次写回，并同步元数据。
  - 对走 DashScope 的视觉/审核模块
    (content_safety / im_moderation / medical_report / vasi)：
      本次不强行改 provider（百炼 key 已 401 失效；medical_report/vasi 用
      qwen-vl-max 视觉模型，DeepSeek 无视觉能力），仅打印告警说明需用户后续
      提供新百炼 key 或单独切换。这些模块的双重加密会由 rekey_api_keys()
      的 bug 修复（见 llm_config_service.rekey_api_keys）在重启时自动修复。

只改 live 库 data/subskin.db；执行前请先备份。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 项目根 = scripts/ 的上一级
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 先加载后端 .env，拿到 LLM_ENCRYPTION_KEY / DEEPSEEK_API_KEY
from dotenv import load_dotenv  # noqa: E402

ENV_PATH = ROOT / "web" / "backend" / ".env"
load_dotenv(ENV_PATH, override=True)

# 强制使用 live 库绝对路径（覆盖 .env 中的相对 DATABASE_URL）
LIVE_DB = ROOT / "data" / "subskin.db"
os.environ["DATABASE_URL"] = f"sqlite:///{LIVE_DB}"

from web.backend.services.llm_config_service import (  # noqa: E402
    _get_fernet,
    encrypt_api_key,
)
from web.backend.database.database import SessionLocal  # noqa: E402
from web.backend.database.models import LLMModuleConfig  # noqa: E402

# 目标：切到 DeepSeek 官方的文本模块
DEEPSEEK_MODULES = ["rag", "briefing", "encyclopedia", "summarizer", "translator"]
# 走 DashScope 的视觉/审核模块：本次不改 provider，仅告警
DASHSCOPE_WARN_MODULES = ["content_safety", "im_moderation", "medical_report", "vasi"]

DESIRED_PROVIDER = "deepseek"
DESIRED_CHAT_MODEL = "deepseek-v4-flash"
DESIRED_BASE_URL = "https://api.deepseek.com/v1"


def mask(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def decrypt_once(fernet, stored: str | None) -> str:
    """用当前密钥解密一次；失败则原样返回（视为明文/不可解密）。"""
    if not stored:
        return ""
    try:
        return fernet.decrypt(stored.encode("utf-8")).decode("utf-8")
    except Exception:
        return stored


def sync_metadata(module: LLMModuleConfig) -> bool:
    """同步 provider/chat_model/base_url/is_active 到目标值，返回是否有变更。"""
    changed = False
    if module.provider != DESIRED_PROVIDER:
        module.provider = DESIRED_PROVIDER
        changed = True
    if module.chat_model != DESIRED_CHAT_MODEL:
        module.chat_model = DESIRED_CHAT_MODEL
        changed = True
    if module.base_url != DESIRED_BASE_URL:
        module.base_url = DESIRED_BASE_URL
        changed = True
    if not module.is_active:
        module.is_active = True
        changed = True
    return changed


def main() -> int:
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not deepseek_key:
        print("[ABORT] .env 未配置 DEEPSEEK_API_KEY，无法修复。")
        return 1
    if not LIVE_DB.exists():
        print(f"[ABORT] live 库不存在：{LIVE_DB}")
        return 1

    enc_key = os.getenv("LLM_ENCRYPTION_KEY") or os.getenv("LLM_CONFIG_ENCRYPTION_KEY")
    if not enc_key:
        print("[WARN] LLM_ENCRYPTION_KEY 未配置，将回退内置默认密钥（不安全）。")

    fernet = _get_fernet()
    print("=" * 78)
    print(f"live DB      : {LIVE_DB}")
    print(f"DEEPSEEK key : {mask(deepseek_key)}  (len={len(deepseek_key)})")
    print(f"目标 provider: {DESIRED_PROVIDER}  model={DESIRED_CHAT_MODEL}  base_url={DESIRED_BASE_URL}")
    print("=" * 78)

    db = SessionLocal()
    fixed = 0
    skipped = 0
    try:
        # ---- DeepSeek 文本模块：修复 + 切换 ----
        print("\n[DeepSeek 文本模块] rag/briefing/encyclopedia/summarizer/translator")
        print("-" * 78)
        for key in DEEPSEEK_MODULES:
            module = db.query(LLMModuleConfig).filter_by(module_key=key).first()
            if not module:
                print(f"  - {key:<14} NOT FOUND（跳过）")
                continue

            stored = module.api_key or ""
            d1 = decrypt_once(fernet, stored)

            if d1 == deepseek_key:
                # 已是单次加密、值正确 → 仅同步元数据
                meta_changed = sync_metadata(module)
                if meta_changed:
                    print(f"  - {key:<14} OK(api_key 已正确)  同步元数据(已更新)")
                else:
                    print(f"  - {key:<14} OK(已修复过，幂等跳过)")
                skipped += 1
                continue

            if d1.startswith("gAAAAA"):
                # 双重加密：解密第二次拿内层明文（仅用于日志），再用 deepseek key 加密一次
                d2 = decrypt_once(fernet, d1)
                module.api_key = encrypt_api_key(deepseek_key)
                sync_metadata(module)
                print(
                    f"  - {key:<14} FIXED(双重加密) 内层明文={mask(d2)} -> "
                    f"deepseek key={mask(deepseek_key)}"
                )
                fixed += 1
                continue

            # 单次加密但值错误（如旧百炼 key）/ 或明文旧数据
            module.api_key = encrypt_api_key(deepseek_key)
            sync_metadata(module)
            print(
                f"  - {key:<14} FIXED(值错误) 旧值={mask(d1)} -> "
                f"deepseek key={mask(deepseek_key)}"
            )
            fixed += 1

        if fixed:
            db.commit()
        else:
            print("\n(DeepSeek 模块无 api_key 改动；仅元数据改动如需也会提交)")
            # 即使只改元数据也要提交
            db.commit()

        # ---- DashScope 视觉/审核模块：仅告警，不改 provider ----
        print("\n[DashScope 视觉/审核模块] 仅告警，不改 provider/不切 deepseek")
        print("-" * 78)
        for key in DASHSCOPE_WARN_MODULES:
            module = db.query(LLMModuleConfig).filter_by(module_key=key).first()
            if not module:
                print(f"  - {key:<16} NOT FOUND（跳过）")
                continue
            stored = module.api_key or ""
            d1 = decrypt_once(fernet, stored)
            double = d1.startswith("gAAAAA")
            inner = decrypt_once(fernet, d1) if double else d1
            status = "双重加密(将由 rekey 重启时自动修复)" if double else "单次加密"
            print(
                f"  - {key:<16} provider={module.provider:<10} "
                f"model={module.chat_model or '-':<14} {status}  "
                f"内层明文={mask(inner)}"
            )
        print(
            "  ! 告警：百炼(DASHSCOPE) key 已 401 失效；medical_report/vasi 使用 "
            "qwen-vl-max 视觉模型，DeepSeek 无视觉能力，请勿盲目切到 deepseek。"
        )
        print(
            "  ! 建议：后续提供新的百炼 key（单独更新这两类模块的 api_key），"
            "或为审核类文本模块单独评估切换方案。"
        )

        print("\n" + "=" * 78)
        print(f"修复完成：DeepSeek 模块 修复={fixed}  幂等跳过={skipped}")
        print("（DashScope 模块未做改动，仅打印告警）")
        print("=" * 78)
        return 0
    except Exception as e:  # noqa: BLE001
        db.rollback()
        print(f"[ERROR] 修复失败，已回滚：{e}")
        import traceback

        traceback.print_exc()
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
