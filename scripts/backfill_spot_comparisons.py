"""为历史白斑照片批量回填配对对比识别结果（spot_comparisons 缓存）。

用法（repo 根目录）：
    .venv/bin/python scripts/backfill_spot_comparisons.py --user-id 9
    .venv/bin/python scripts/backfill_spot_comparisons.py --user-id 9 --min-gap-days 3 --force

按用户 + 部位构建照片时间线，对相邻照片对（间隔 ≥ min-gap-days）逐一执行
spot_compare.compare_pair。同一图对已有缓存会跳过（--force 重跑）。
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "web/backend/.env", override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill")


def main() -> int:
    parser = argparse.ArgumentParser(description="回填白斑照片配对对比结果")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--site", type=str, default=None, help="只处理指定部位 key（如 face）")
    parser.add_argument("--min-gap-days", type=int, default=1, help="相邻照片最小间隔天数")
    parser.add_argument("--include-drafts", action="store_true", help="包含 draft 状态的 VASI 测评")
    parser.add_argument("--force", action="store_true", help="忽略缓存强制重跑")
    args = parser.parse_args()

    from web.backend.database.database import SessionLocal
    from web.backend.database.models import ensure_spot_comparison_table
    from web.backend.services.spot_compare import (
        compare_pair,
        get_cached,
        iter_user_photo_timeline,
    )

    ensure_spot_comparison_table()
    db = SessionLocal()
    try:
        timeline = iter_user_photo_timeline(db, args.user_id, include_vasi_drafts=args.include_drafts)
        if args.site:
            timeline = [p for p in timeline if p["body_site"] == args.site]

        # 按部位分组（无部位的照片单独归入 None 组，不做配对）
        groups: dict = {}
        for p in timeline:
            if p["body_site"]:
                groups.setdefault(p["body_site"], []).append(p)

        total_pairs = 0
        done = 0
        skipped_cache = 0
        skipped_gap = 0
        failed = 0
        for site, photos in sorted(groups.items()):
            pairs = []
            for i in range(len(photos) - 1):
                a, b = photos[i], photos[i + 1]
                if (b["date"] - a["date"]).days < args.min_gap_days:
                    skipped_gap += 1
                    continue
                pairs.append((a, b))
            total_pairs += len(pairs)
            print(f"\n[{site}] {len(photos)} 张照片 → {len(pairs)} 个有效相邻对")
            for a, b in pairs:
                if not args.force and get_cached(db, a["ref"], b["ref"]):
                    skipped_cache += 1
                    continue
                m = compare_pair(db, args.user_id, a["ref"], b["ref"])
                if m:
                    done += 1
                    merged = m["merged"]
                    print(
                        f"  {a['date']}→{b['date']}  trend={merged['trend']} "
                        f"melanin={merged.get('melanin_score_a')}→{merged.get('melanin_score_b')} "
                        f"size={merged.get('size_change_percent')}% conf={merged['confidence']}"
                    )
                else:
                    failed += 1
                    print(f"  {a['date']}→{b['date']}  FAILED")

        print(
            f"\n==== 回填完成：有效对 {total_pairs}，新识别 {done}，"
            f"缓存跳过 {skipped_cache}，间隔跳过 {skipped_gap}，失败 {failed} ===="
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
