#!/usr/bin/env python3
"""对比 VASI 视觉模型：qwen-vl-max vs qwen3-vl-plus (+ qvq-plus)
- 同一 prompt（VASI v5.0 默认 prompt）
- 同一组真实图像
- 输出对比表 + 叠加可视化
"""
import os, sys, json, base64, time, traceback
from pathlib import Path

ROOT = Path("/root/subskin")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load .env manually
env = {}
for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
API_KEY = env.get("DASHSCOPE_API_KEY")
assert API_KEY, "No DASHSCOPE_API_KEY"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Same prompt as VASI v5.0 default static prompt (from vasi.py L1038-1168)
PROMPT = open("/tmp/vasi_prompt.txt").read()

import openai
client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)

MODELS = ["qwen-vl-max", "qwen3-vl-plus", "qvq-plus"]

IMAGES = [
    ("small_2.4MB", "data/uploads/vasi/1778982711_746295e9.jpg"),
    ("mid_2.7MB",   "data/uploads/vasi/1778935155_f19b02c6.jpg"),
    ("large_3.0MB", "data/uploads/vasi/1780474134_e630b5b2.jpg"),
]

def call_model(model: str, image_path: str) -> dict:
    img_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode()
    mime = "image/jpeg"
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": PROMPT},
                ]
            }],
            temperature=0.1,
            max_tokens=4096,
            timeout=120,
        )
        dt = time.time() - t0
        content = (resp.choices[0].message.content or "").strip()
        usage = resp.usage
        tok_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        tok_out = getattr(usage, "completion_tokens", 0) if usage else 0
        # strip fences
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:].strip()
            elif content.startswith("\n"):
                content = content.strip()
        # try parse
        try:
            parsed = json.loads(content)
            ok = True
            err = None
        except Exception as e:
            # try to find {...}
            i, j = content.find("{"), content.rfind("}")
            if i >= 0 and j > i:
                try:
                    parsed = json.loads(content[i:j+1])
                    ok = True
                    err = "extracted"
                except Exception as e2:
                    parsed = None
                    ok = False
                    err = f"json: {e2}"
            else:
                parsed = None
                ok = False
                err = f"json: {e}"
        return {
            "model": model, "ok": ok, "err": err, "latency_s": round(dt, 2),
            "tokens_in": tok_in, "tokens_out": tok_out,
            "raw": content[:2000], "parsed": parsed,
        }
    except Exception as e:
        dt = time.time() - t0
        return {"model": model, "ok": False, "err": str(e)[:300], "latency_s": round(dt, 2),
                "tokens_in": 0, "tokens_out": 0, "raw": "", "parsed": None}

def summarize(parsed):
    if not parsed:
        return {"lesions": "-", "vasi": "-", "depig": "-", "bbox_tight": "-", "conf": "-"}
    lesions = parsed.get("suspected_lesions") or []
    n = len(lesions)
    vasi = parsed.get("vasi_score", "-")
    depig = parsed.get("overall_depigmentation", "-")
    # bbox tightness: avg estimated_size_percent vs bbox area
    tight_scores = []
    for L in lesions:
        bbox = L.get("bbox")
        size_pct = L.get("estimated_size_percent")
        if bbox and len(bbox) == 4 and size_pct:
            bw = max(0, bbox[2] - bbox[0])
            bh = max(0, bbox[3] - bbox[1])
            bbox_area_pct = bw * bh * 100  # in % of image
            if bbox_area_pct > 0:
                # tightness ratio = lesion / bbox area, target >=0.5
                ratio = size_pct / bbox_area_pct
                tight_scores.append(min(ratio, 1.0))
    tight = f"{sum(tight_scores)/len(tight_scores):.2f}" if tight_scores else "-"
    conf = parsed.get("confidence", "-")
    return {"lesions": n, "vasi": vasi, "depig": depig, "bbox_tight": tight, "conf": conf}

def main():
    outdir = ROOT / "tmp" / "vlm_compare"
    outdir.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, img in IMAGES:
        print(f"\n=== Image: {label} ({img}) ===")
        results[label] = {}
        for model in MODELS:
            print(f"  calling {model}...", flush=True)
            r = call_model(model, img)
            results[label][model] = r
            s = summarize(r.get("parsed"))
            print(f"    ok={r['ok']} {r['latency_s']}s  lesions={s['lesions']} vasi={s['vasi']} depig={s['depig']} bbox_tight={s['bbox_tight']} conf={s['conf']}")
            if not r["ok"]:
                print(f"    ERR: {r['err']}")
    
    # save raw
    (outdir / "raw_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    
    # print summary table
    print("\n\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    header = f"{'image':<14} {'model':<18} {'ok':<4} {'lat(s)':<7} {'lesions':<8} {'vasi':<6} {'depig':<6} {'tight':<7} {'conf':<5} {'tok_in':<7} {'tok_out':<7}"
    print(header)
    print("-" * len(header))
    for label, _ in IMAGES:
        for model in MODELS:
            r = results[label][model]
            s = summarize(r.get("parsed"))
            print(f"{label:<14} {model:<18} {str(r['ok']):<4} {r['latency_s']:<7} {str(s['lesions']):<8} {str(s['vasi']):<6} {str(s['depig']):<6} {str(s['bbox_tight']):<7} {str(s['conf']):<5} {r['tokens_in']:<7} {r['tokens_out']:<7}")
    print()
    print(f"Raw saved to {outdir}/raw_results.json")

if __name__ == "__main__":
    main()
