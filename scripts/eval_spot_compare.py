"""评估配对对比引擎（spot_compare）与 VASI 数值真值的一致率。

用法（repo 根目录）：
    .venv/bin/python scripts/eval_spot_compare.py --user-id 9

对 spot_comparisons 缓存中两端均为 VASI 测评（有 vasi_score）的图对：
- 真值趋势：vasi 变化率 ≤ -5% 为 improving，≥ +5% 为 worsening，否则 stable
- 引擎趋势：merged.trend_en
输出混淆矩阵、一致率与不一致样本明细（供 prompt 迭代）。
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("eval")


def vasi_trend(score_a: float, score_b: float) -> str:
    if score_a == 0:
        return "improving" if score_b < score_a else "stable"
    pct = (score_b - score_a) / score_a * 100
    if pct <= -5:
        return "improving"
    if pct >= 5:
        return "worsening"
    return "stable"


def main() -> int:
    parser = argparse.ArgumentParser(description="评估配对对比引擎一致率")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--db", type=str, default="data/subskin.db")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 引擎结果 + 两端 VASI 分数（metrics_json 内已快照）
    query = "SELECT id, user_id, ref_a, ref_b, body_site, metrics_json FROM spot_comparisons"
    if args.user_id:
        query += " WHERE user_id = ?"
    rows = cur.execute(query, (args.user_id,) if args.user_id else ()).fetchall()

    matrix = {t: {t2: 0 for t2 in ("improving", "stable", "worsening")} for t in ("improving", "stable", "worsening")}
    disagreements = []
    usable = 0
    for r in rows:
        try:
            m = json.loads(r["metrics_json"])
        except Exception:
            continue
        vasi = m.get("vasi") or {}
        sa, sb = vasi.get("score_a"), vasi.get("score_b")
        merged = m.get("merged") or {}
        # 重复上传照片的短路结果与 VASI 噪声样本不参与评估
        if merged.get("duplicate"):
            continue
        if sa is None or sb is None or not merged.get("trend_en"):
            continue
        truth = vasi_trend(float(sa), float(sb))
        pred = merged["trend_en"]
        matrix[truth][pred] += 1
        usable += 1
        if truth != pred:
            disagreements.append(
                {
                    "pair": f"{r['ref_a']}→{r['ref_b']}",
                    "site": r["body_site"],
                    "vasi": f"{sa}→{sb}",
                    "truth": truth,
                    "pred": pred,
                    "size_pct": merged.get("size_change_percent"),
                    "melanin": f"{merged.get('melanin_score_a')}→{merged.get('melanin_score_b')}",
                    "conf": merged.get("confidence"),
                    "capture_note": merged.get("capture_note"),
                }
            )

    if usable == 0:
        print("无可用评估样本（需要两端均有 VASI 分数的图对）")
        return 1

    print(f"评估样本：{usable} 对\n")
    header = f"{'真值/预测':<14}{'improving':>12}{'stable':>10}{'worsening':>12}"
    print(header)
    for truth in ("improving", "stable", "worsening"):
        row = matrix[truth]
        print(f"{truth:<12}{row['improving']:>12}{row['stable']:>10}{row['worsening']:>12}")

    correct = sum(matrix[t][t] for t in matrix)
    print(f"\n总一致率：{correct}/{usable} = {correct / usable * 100:.1f}%")

    # 好转召回（用户价值核心：不漏报好转）
    imp_total = sum(matrix["improving"].values())
    if imp_total:
        print(f"好转召回：{matrix['improving']['improving']}/{imp_total}")
    wor_total = sum(matrix["worsening"].values())
    if wor_total:
        print(f"加重召回：{matrix['worsening']['worsening']}/{wor_total}")

    if disagreements:
        print(f"\n==== 不一致样本（{len(disagreements)}）====")
        for d in disagreements:
            print(json.dumps(d, ensure_ascii=False))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
