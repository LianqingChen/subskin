#!/usr/bin/env python3
"""白斑识别准确度评估脚本（边缘 / 大小 / 颜色）

对同一组白斑测试图，用不同「视觉模型 × 提示词」跑 VASI 视觉分析，
量化对比边缘（edge_points 数量/边界类型/bbox 贴合度）、大小（面积%）、
颜色（脱色等级/对比度/颜色档）三个维度，输出对比表 + JSON。

用法：
  # 对比多个视觉模型（默认读取 DB 中 vasi 模块配置的 key / base_url）
  python3 scripts/eval_vitiligo_accuracy.py --models qwen3-vl-plus qwen3.7-plus qwen3-vl-max

  # 对比不同提示词（old = 历史静态提示词, db = 当前后台提示词）
  python3 scripts/eval_vitiligo_accuracy.py --models qwen3.7-plus --prompt-mode db

  # 离线分析已有结果（不调用 API）
  python3 scripts/eval_vitiligo_accuracy.py --offline

结果写入 tmp/vlm_compare/eval_accuracy_<ts>.json
"""
import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path("/root/subskin")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# 加载后端 .env（拿到 API key / 加密密钥 / DB URL）
ENV = {}
for line in (ROOT / "web" / "backend" / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    ENV[k.strip()] = v.strip().strip('"').strip("'")
os.environ.setdefault("LLM_ENCRYPTION_KEY", ENV.get("LLM_ENCRYPTION_KEY", ""))
os.environ.setdefault("DATABASE_URL", ENV.get("DATABASE_URL", ""))

IMAGES = [
    ("small_2.4MB", "data/uploads/vasi/1778982711_746295e9.jpg"),
    ("mid_2.7MB", "data/uploads/vasi/1778935155_f19b02c6.jpg"),
    ("large_3.0MB", "data/uploads/vasi/1780474134_e630b5b2.jpg"),
]

# 旧的静态提示词（切换前的基线，用于对比提示词改进效果）
OLD_VASI_PROMPT = """你是一位资深皮肤科AI助手，请精确分析这张皮肤照片中的白斑（白癜风）特征。
重要：你不是医生，不能医疗诊断。用"观察到""可见"等客观措辞。
【皮肤背景评估】观察皮肤区域，估计Fitzpatrick分型 I-VI；白斑脱色永远相对周围正常皮肤判定。
【色素脱失等级量化标准】0级<0.10/1级0.10-0.20/2级0.20-0.40/3级>0.40（contrast_to_skin=明度差比值0-1）。
【边缘识别要求】bbox紧贴白斑边界；edge_points给3-8个沿轮廓边界关键点，覆盖最外凸/最内凹；边缘清晰沿过渡带外缘取点，模糊沿最外圈脱色带取点。
【输出】只返回JSON。suspected_lesions 每项含 center/bbox/edge_points/estimated_size_percent/depigmentation_level/contrast_to_skin/boundary_type/confidence；visual_features 含 visibility/color/border/shape/surface/distribution；另有 classification/stage/overall_depigmentation/confidence。
"""


def load_prompt(mode: str) -> str:
    if mode == "old":
        return OLD_VASI_PROMPT
    # db: 读管理后台当前提示词
    from web.backend.database.database import SessionLocal
    from web.backend.services.llm_prompt_service import LLMPromptService
    db = SessionLocal()
    try:
        return LLMPromptService.get_prompt(db, "vasi", "vision_analysis")
    finally:
        db.close()


def call_model(model: str, api_key: str, base_url: str, prompt: str, image_path: str):
    import openai
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    img = Path(image_path).read_bytes()
    b64 = base64.b64encode(img).decode()
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            temperature=0.0,
            max_tokens=8192,
            timeout=120,
        )
        dt = time.time() - t0
        content = (resp.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:].strip()
        parsed = None
        try:
            parsed = json.loads(content)
        except Exception:
            i, j = content.find("{"), content.rfind("}")
            if i >= 0 and j > i:
                try:
                    parsed = json.loads(content[i:j + 1])
                except Exception:
                    parsed = None
        return {"model": model, "ok": parsed is not None, "latency_s": round(dt, 2), "parsed": parsed}
    except Exception as e:
        return {"model": model, "ok": False, "latency_s": round(time.time() - t0, 2), "error": str(e)[:200], "parsed": None}


def extract_metrics(parsed):
    """从 VLM 结果提取边缘/大小/颜色量化指标。"""
    if not parsed:
        return {"lesions": None, "edge_pts_avg": None, "boundary_types": {}, "size_pct_total": None,
                "size_cats": {}, "depig_avg": None, "contrast_avg": None, "color_level": None, "conf_avg": None}
    lesions = parsed.get("suspected_lesions") or []
    n = len(lesions)
    edge_pts = [len(L.get("edge_points") or []) for L in lesions]
    sizes = [L.get("estimated_size_percent") for L in lesions if L.get("estimated_size_percent") is not None]
    depigs = [L.get("depigmentation_level") for L in lesions if L.get("depigmentation_level") is not None]
    contrasts = [L.get("contrast_to_skin") for L in lesions if L.get("contrast_to_skin") is not None]
    confs = [L.get("confidence") for L in lesions if L.get("confidence") is not None]
    btypes = {}
    for L in lesions:
        btypes[L.get("boundary_type", "?")] = btypes.get(L.get("boundary_type", "?"), 0) + 1
    size_cats = {}
    for L in lesions:
        size_cats[L.get("size_category", "?")] = size_cats.get(L.get("size_category", "?"), 0) + 1
    vf = parsed.get("visual_features") or {}
    color_level = (vf.get("color") or {}).get("level", "?")

    def _avg(xs):
        return round(sum(float(x) for x in xs) / len(xs), 3) if xs else None

    return {
        "lesions": n,
        "edge_pts_avg": _avg(edge_pts),
        "boundary_types": btypes,
        "size_pct_total": round(sum(float(s) for s in sizes), 2) if sizes else None,
        "size_cats": size_cats,
        "depig_avg": _avg(depigs),
        "contrast_avg": _avg(contrasts),
        "color_level": color_level,
        "conf_avg": _avg(confs),
    }


def run_online(models, prompt_mode):
    from web.backend.utils.llm_config import get_llm_config
    config = get_llm_config("vasi")
    api_key = config["api_key"]
    base_url = config["base_url"]
    prompt = load_prompt(prompt_mode)
    print(f"base_url={base_url}  api_key={api_key[:8]}...  prompt_mode={prompt_mode} ({len(prompt)} chars)")

    results = {}
    for label, img in IMAGES:
        if not Path(img).exists():
            print(f"⚠ 跳过缺失图片 {img}")
            continue
        results[label] = {}
        for model in models:
            print(f"  {label} <- {model} ...", flush=True)
            r = call_model(model, api_key, base_url, prompt, img)
            results[label][model] = {**r, "metrics": extract_metrics(r.get("parsed"))}
            m = results[label][model]["metrics"]
            print(f"    ok={r['ok']} lat={r.get('latency_s')}s lesions={m['lesions']} edge_avg={m['edge_pts_avg']} "
                  f"size_total={m['size_pct_total']} depig={m['depig_avg']} contrast={m['contrast_avg']} color={m['color_level']}")
            if not r["ok"]:
                print(f"    ERR: {r.get('error')}")
    return results


def print_table(results, models):
    print("\n" + "=" * 130)
    print("白斑识别准确度对比（边缘 / 大小 / 颜色）")
    print("=" * 130)
    header = f"{'image':<12} {'model':<16} {'lesions':<8} {'edge_avg':<9} {'boundary':<22} {'size_total%':<11} {'depig':<6} {'contrast':<9} {'color':<12}"
    print(header)
    print("-" * 130)
    for label, _ in IMAGES:
        for model in models:
            r = results.get(label, {}).get(model)
            if not r:
                continue
            m = r.get("metrics", {})
            print(f"{label:<12} {model:<16} {str(m.get('lesions')):<8} {str(m.get('edge_pts_avg')):<9} "
                  f"{str(m.get('boundary_types')):<22} {str(m.get('size_pct_total')):<11} "
                  f"{str(m.get('depig_avg')):<6} {str(m.get('contrast_avg')):<9} {str(m.get('color_level')):<12}")


def analyze_offline():
    """离线分析已有 raw_results.json（qwen-vl-max vs qwen3-vl-plus vs qvq-plus）。"""
    p = ROOT / "tmp" / "vlm_compare" / "raw_results.json"
    if not p.exists():
        print("没有找到 tmp/vlm_compare/raw_results.json")
        return None
    data = json.loads(p.read_text())
    print("\n离线基线分析（来自历史 raw_results.json）：")
    print("=" * 130)
    print(f"{'image':<12} {'model':<16} {'lesions':<8} {'edge_avg':<9} {'boundary':<24} {'depig':<6} {'contrast':<9} {'color':<14}")
    print("-" * 130)
    for label in data:
        for model, r in data[label].items():
            m = extract_metrics(r.get("parsed"))
            print(f"{label:<12} {model:<16} {str(m['lesions']):<8} {str(m['edge_pts_avg']):<9} "
                  f"{str(m['boundary_types']):<24} {str(m['depig_avg']):<6} {str(m['contrast_avg']):<9} {str(m['color_level']):<14}")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["qwen3-vl-plus", "qwen3.7-plus", "qwen3-vl-max"])
    ap.add_argument("--prompt-mode", default="db", choices=["db", "old"])
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if args.offline:
        data = analyze_offline()
        if data:
            out = ROOT / "tmp" / "vlm_compare" / f"eval_offline_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
            print(f"\n结果已保存 {out}")
        return

    results = run_online(args.models, args.prompt_mode)
    print_table(results, args.models)
    out = ROOT / "tmp" / "vlm_compare" / f"eval_accuracy_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(f"\n结果已保存 {out}")


if __name__ == "__main__":
    main()
