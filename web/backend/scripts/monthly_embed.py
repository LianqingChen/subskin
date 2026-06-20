"""
Monthly incremental embedding script — vectorizes documents where embedding IS NULL.

Runs on the 1st of each month at 03:00 via systemd timer.
Can also be triggered manually: python -m scripts.monthly_embed
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from web.backend.database.database import SessionLocal
from web.backend.services.rag import batch_embed_unembedded


def main() -> None:
    db = SessionLocal()
    try:
        print("开始每月增量向量化...")
        result = batch_embed_unembedded(db)
        print(
            "完成: 成功 %d, 失败 %d, 总计 %d"
            % (result["embedded_count"], result["failed_count"], result["total"])
        )
        if result["failed_count"] > 0:
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()