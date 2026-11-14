"""The standard protocol every vision model follows (SKILL.md §2 explains each step).

  P0 gate      privacy.check — nothing leaves the server without it
  P1 regions   local superpixels + per-region stats (no model)
  P2 triage    model looks at the whole image: body site, this person's normal/lesion colours
  P3 judge     per tile: clean crop + numbered crop -> one code per region (rubric.md)
  P4 fuse      verdicts -> pixels with out-of-fold colour model (fuse.py)
  P5 recheck   regions where colour contradicts the verdict -> zoomed second look
  P6 review    model inspects the filled draft per tile, lists wrong regions
  P7 save      labels + decision file (seg params + verdicts) -> replayable without the model
"""

import concurrent.futures as cf
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw

from ml.pixel_labeling import features, system_io as sio
from ml.vlm_labeling import fuse, regions
from ml.vlm_labeling.client import ProviderQuotaExhausted, VLM, image_part
from web.backend.models.image_label import VITILIGO_TYPE_CHOICES
from web.backend.utils.body_sites import normalize as normalize_body_site, site_labels

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / ".agents" / "skills" / "vlm-vitiligo-labeling"
VALID = set("LNBOXMU")


_RUBRIC: Optional[str] = None


def rubric() -> str:
    """Rubric text, frozen for the whole run (set by ``run``) so editing rubric.md mid-run
    cannot mix two versions inside one result."""
    return _RUBRIC if _RUBRIC is not None else (SKILL / "rubric.md").read_text()


def rubric_version(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip().split()[0]
    return "?"


# ---------------------------------------------------------------- P1
def prepare(task_id: int, n_skin: int = regions.DEFAULT_SKIN_REGIONS, *, rgb: Optional[np.ndarray] = None):
    if rgb is None:
        rgb = sio.load_image(task_id)
    feats, side = features.cached(task_id, rgb)
    R = regions.build(rgb, feats, side, features.NAMES, n_skin=n_skin)
    return rgb, feats, side, R


def _hints(R: regions.Regions, ids: List[int]) -> str:
    """Local parser hints (mediapipe) — the model may overrule them."""
    out = {"hair": [], "clothes": [], "eye": [], "lips": [], "bg": []}
    for i in ids:
        t = R.table[i]
        if t["eyes"] > 0.5:
            out["eye"].append(i)
        elif t["lips"] > 0.5:
            out["lips"].append(i)
        elif t["p_hair"] > 0.7:
            out["hair"].append(i)
        elif t["p_clothes"] > 0.7:
            out["clothes"].append(i)
        elif t["p_bg"] > 0.7:
            out["bg"].append(i)
    parts = [f"{k}: {v}" for k, v in out.items() if v]
    return ("本地人体解析器的提示（可能有错，你可以推翻）：" + "；".join(parts)) if parts else ""


# ---------------------------------------------------------------- P2
def _body_site_codes(items: List[Any]) -> List[str]:
    codes = [normalize_body_site(item) for item in items if isinstance(item, str)]
    return list(dict.fromkeys(code for code in codes if code))


def _triage_tags(value: Any) -> Dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    raw_sites = data.get("body_sites")
    if not isinstance(raw_sites, list):
        raw_sites = [data.get("body_site")]
    codes = _body_site_codes(raw_sites)
    reported_affected = data.get("affected_body_sites")
    affected_codes = (_body_site_codes(reported_affected)
                      if isinstance(reported_affected, list) and data.get("lesion_present") is not False else [])
    labels_by_code = site_labels()
    body_sites = [labels_by_code[code] for code in codes]
    details = data.get("body_site_observations")
    details = details if isinstance(details, list) else []
    observed_sites = list(dict.fromkeys(v.strip() for v in [*details, *raw_sites] if
                                        isinstance(v, str) and v.strip() and v.strip() not in labels_by_code))
    legacy_site = data.get("body_site")
    legacy_site = legacy_site if isinstance(legacy_site, str) else ""
    tone = data.get("skin_tone_description", data.get("skin_tone"))
    tone = tone.strip() if isinstance(tone, str) else ""
    if "fitzpatrick" in tone.lower() or re.fullmatch(r"(?:type\s*)?(?:[ivx]+|[1-6])\s*型?", tone, re.I):
        tone = ""

    appearance = data.get("appearance_tags")
    appearance = appearance if isinstance(appearance, dict) else {}
    values = {
        "colour_terms": ("淡白", "乳白", "瓷白", "粉白", "浅棕过渡", "不确定"),
        "morphology": ("点状", "斑片状", "融合片状", "线状", "不确定"),
    }
    visible = {}
    for field, options in values.items():
        items = appearance.get(field)
        items = items if isinstance(items, list) else []
        visible[field] = list(dict.fromkeys(v for v in items if v in options)) or ["不确定"]
    border = appearance.get("border")
    visible["border"] = border if border in ("清晰", "模糊", "混合") else "不确定"
    for field in ("pigment_islands", "white_hair"):
        observed = appearance.get(field)
        visible[field] = observed if observed in ("有", "未见") else "不确定"

    clinical = data.get("clinical_assessment")
    clinical = clinical if isinstance(clinical, dict) else {}
    raw_types = clinical.get("candidate_types")
    raw_types = raw_types if isinstance(raw_types, list) else []
    aliases = {"非节段型": "非节段型(寻常型)", "非节段型（寻常型）": "非节段型(寻常型)"}
    types = [aliases.get(v, v) for v in raw_types if isinstance(v, str)]
    types = list(dict.fromkeys(v for v in types if v in VITILIGO_TYPE_CHOICES))
    return {
        "body_sites": body_sites, "body_site_codes": codes, "body_site_observations": observed_sites,
        "affected_body_site_codes": affected_codes,
        "affected_body_sites": [labels_by_code[code] for code in affected_codes],
        "body_site": "、".join(body_sites or observed_sites) or legacy_site,
        "skin_tone_description": tone, "skin_tone": tone,
        "normal_color": data.get("normal_color"), "lesion_color": data.get("lesion_color"),
        "lesion_present": data.get("lesion_present"),
        "lesion_map": data["lesion_map"] if isinstance(data.get("lesion_map"), dict) else {},
        "pitfalls": data.get("pitfalls", []), "appearance_tags": visible,
        "clinical_assessment": {
            "candidate_types": types or ["未确定"], "status": "unconfirmed",
            "evidence_scope": "image_only", "review_required": True,
        },
    }


def triage(vlm: VLM, rgb: np.ndarray, R: regions.Regions) -> Dict[str, Any]:
    ov = regions.overview(rgb, R)
    q = ("第一张是普通光原图，第二张是分块定位图。按可见 RGB 描述，无需给坐标。输出 JSON："
         '{"body_sites": ["部位代码"], "body_site_observations": ["可见细部位置"],'
         ' "affected_body_sites": ["可见白斑所在的部位代码"],'
         ' "skin_tone_description": "可见肤色描述",'
         ' "normal_color": "此人正常肤色的描述",'
         ' "lesion_color": "此人白斑的颜色描述", "lesion_present": true/false,'
         ' "lesion_map": {"T编号": "该分块里白斑在哪（例如：左上大片、右下小点、无）"},'
         ' "appearance_tags": {"colour_terms": ["淡白/乳白/瓷白/粉白/浅棕过渡/不确定"],'
         ' "morphology": ["点状/斑片状/融合片状/线状/不确定"], "border": "清晰/模糊/混合/不确定",'
         ' "pigment_islands": "有/未见/不确定", "white_hair": "有/未见/不确定"},'
         ' "clinical_assessment": {"candidate_types": ["未确定"], "status": "unconfirmed",'
         ' "evidence_scope": "image_only", "review_required": true},'
         ' "pitfalls": ["这张图里容易误判的东西：高光位置、阴影、发际、唇、眼等"]}'
         "\n图上青色框是分块 T0、T1……，lesion_map 请覆盖每个分块。"
         "body_sites 记录图中可见的部位。affected_body_sites 只记录原图上可见白斑所在的部位，"
         "没有可确认的白斑部位时填空数组。两字段均使用下列代码。方向或细部位置写入 body_site_observations。"
         + json.dumps(site_labels(), ensure_ascii=False) +
         "。仅根据普通光图像记录可见肤色。临床候选需要临床审核，图像依据不足时使用未确定。")
    r = vlm.ask("triage", rubric(), [image_part(Image.fromarray(rgb)), image_part(ov), {"type": "text", "text": q}])
    return _triage_tags(r.get("data"))


def _tile_overview(rgb: np.ndarray, tile: Dict, size: int = 448) -> Image.Image:
    H, W = rgb.shape[:2]
    s = size / max(H, W)
    im = Image.fromarray(rgb).resize((int(W * s), int(H * s)), Image.BILINEAR)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = [int(v * s) for v in tile["box"]]
    d.rectangle([x0, y0, x1, y1], outline=(0, 255, 255), width=3)
    return im


# ---------------------------------------------------------------- P3
def judge_tile(vlm: VLM, rgb: np.ndarray, R: regions.Regions, tile: Dict, tri: Dict[str, Any]) -> Dict[int, str]:
    clean, marked, _ = regions.render_tile(rgb, R, tile)
    ids = tile["regions"]
    ctx = {k: tri.get(k) for k in ("body_site", "skin_tone", "normal_color", "lesion_color")}
    ctx["this_tile"] = (tri.get("lesion_map") or {}).get(f"T{tile['id']}")
    text = (f"分块 T{tile['id']}（第 1 张图青框位置）。第 2 张是原图放大，第 3 张是同一位置的编号图。\n"
            f"整图判读（供参考）：{json.dumps(ctx, ensure_ascii=False)}\n"
            f"{_hints(R, ids)}\n"
            f"需要判读的编号（共 {len(ids)} 个，一个都不能少）：{ids}\n"
            "对照第 2 张原图的颜色判断，第 3 张只用来认编号。按规范输出 JSON。")
    parts = [image_part(_tile_overview(rgb, tile)), image_part(clean), image_part(marked), {"type": "text", "text": text}]
    out = _codes(vlm.ask(f"judge:T{tile['id']}", rubric(), parts)["data"], ids)
    missing = [i for i in ids if i not in out]
    if missing:
        parts[-1] = {"type": "text", "text": text + f"\n上次漏掉了这些编号，请只给它们：{missing}"}
        out.update(_codes(vlm.ask(f"judge:T{tile['id']}:missing", rubric(), parts)["data"], missing))
    return out


def _codes(data: Any, ids: List[int]) -> Dict[int, str]:
    reg = data.get("regions", data) if isinstance(data, dict) else {}
    out = {}
    want = set(ids)
    for k, v in (reg.items() if isinstance(reg, dict) else []):
        try:
            k = int(str(k).strip().lstrip("#"))
        except ValueError:
            continue
        v = str(v).strip().upper()[:1]
        if k in want and v in VALID:
            out[k] = v
    return out


# ---------------------------------------------------------------- P5
def contact_sheet(rgb: np.ndarray, R: regions.Regions, ids: List[int], labels: np.ndarray = None,
                  cell: int = 300) -> Image.Image:
    """Each flagged region zoomed with its outline in cyan; caption = region id."""
    cols = 4
    rows = (len(ids) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 28)), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    f = regions._font(20)
    H, W = rgb.shape[:2]
    for j, rid in enumerate(ids):
        t = R.table[rid]
        x0, y0, x1, y1 = t["bbox"]
        side = max(x1 - x0, y1 - y0) * 3 + 40
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        bx0, by0 = max(0, cx - side // 2), max(0, cy - side // 2)
        bx1, by1 = min(W, bx0 + side), min(H, by0 + side)
        crop = rgb[by0:by1, bx0:bx1].copy()
        m = (R.seg[by0:by1, bx0:bx1] == rid).astype(np.uint8)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(crop, cnts, -1, (0, 255, 255), 1)
        im = Image.fromarray(crop).resize((cell, int(cell * crop.shape[0] / max(crop.shape[1], 1))) if crop.shape[1] >= crop.shape[0]
                                          else (int(cell * crop.shape[1] / max(crop.shape[0], 1)), cell), Image.LANCZOS)
        ox, oy = (j % cols) * cell, (j // cols) * (cell + 28)
        sheet.paste(im, (ox, oy + 28))
        d.text((ox + 6, oy + 3), f"#{rid}", fill=(0, 255, 255), font=f)
    return sheet


def recheck(vlm: VLM, rgb: np.ndarray, R: regions.Regions, ids: List[int], tri: Dict[str, Any],
            batch: int = 12) -> Dict[int, str]:
    out: Dict[int, str] = {}
    ref = {k: tri.get(k) for k in ("normal_color", "lesion_color")}
    for b in range(0, len(ids), batch):
        chunk = ids[b:b + batch]
        sheet = contact_sheet(rgb, R, chunk)
        H, W = rgb.shape[:2]
        text = (f"复核：下面每个小图里青色细线围起来的是一个区域，标题是编号。整图参照：{json.dumps(ref, ensure_ascii=False)}。"
                "这些区域第一次的判读与颜色统计矛盾，请只看青线内部、对照周围皮肤重新判读，代码同规范（L/N/M/B/O/X/U）。"
                f"编号：{chunk}。输出 JSON。")
        small = Image.fromarray(rgb).resize((int(W * 512 / max(H, W)), int(H * 512 / max(H, W))))
        try:
            r = vlm.ask(f"recheck:{b // batch}", rubric(), [image_part(small), image_part(sheet), {"type": "text", "text": text}])
        except ProviderQuotaExhausted:
            raise
        except RuntimeError as e:   # provider content filter / outage: keep first verdicts for this batch
            print(f"  recheck batch {b // batch} skipped: {str(e)[:120]}")
            continue
        out.update(_codes(r["data"], chunk))
    return out


# ---------------------------------------------------------------- P6
def review_tile(vlm: VLM, rgb: np.ndarray, R: regions.Regions, tile: Dict, labels: np.ndarray,
                rnd: int = 0) -> Dict[int, str]:
    clean, marked, _ = regions.render_tile(rgb, R, tile, labels=labels)
    ids = tile["regions"]
    text = (f"审稿：分块 T{tile['id']}。第 1 张原图放大，第 2 张是当前标注稿（红色半透明=白斑，未着色=正常皮/背景，白线=区域边界，数字=编号）。"
            "逐个对比两张图，找出**标错的编号**：漏标的白斑、把正常皮/高光标成了白斑、背景/遮挡标错。"
            "只列需要修改的编号和正确代码；全部正确就输出空对象。"
            '输出 JSON：{"regions": {"编号": "正确代码"}, "notes": "原因"}')
    r = vlm.ask(f"review{rnd}:T{tile['id']}", rubric(), [image_part(clean), image_part(marked), {"type": "text", "text": text}])
    return _codes(r["data"], ids)


# ---------------------------------------------------------------- driver
def frozen_run_inputs(out_dir: Path) -> Dict[str, Any]:
    path = out_dir / "run_inputs.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _sha256_array(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()


def _run_preparation(task_id, model, out_dir, n_skin, recheck_on, review_rounds, rubric_path):
    frozen = out_dir / "rubric.snapshot.md"
    manifest = frozen_run_inputs(out_dir)
    if not frozen.is_file():
        if manifest:
            raise ValueError("Frozen rubric snapshot is missing")
        frozen.write_text(Path(rubric_path or SKILL / "rubric.md").read_text(encoding="utf-8"), encoding="utf-8")
    rub = frozen.read_text(encoding="utf-8")
    if manifest and rubric_path and Path(rubric_path).read_text(encoding="utf-8") != rub:
        raise ValueError("Resume requires the same frozen rubric")

    old_decision = out_dir / "decision.json"
    if not manifest and old_decision.is_file():
        old = json.loads(old_decision.read_text(encoding="utf-8"))
        if old["task_id"] != task_id or old["model"] != model:
            raise ValueError("Existing run belongs to a different image task or model")

    settings = {"n_skin": n_skin, "recheck_on": recheck_on, "review_rounds": review_rounds}
    identity = {
        "task_id": task_id, "model": model, "feature_names": list(features.NAMES),
        "rubric_sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(), "settings": settings,
    }
    if manifest:
        changed = [name for name, value in identity.items() if value != manifest.get(name)]
        if changed:
            raise ValueError(f"Resume input changed: {', '.join(changed)}")
    rgb = sio.load_image(task_id)
    identity.update(rgb_shape=list(rgb.shape), rgb_pixels_sha256=_sha256_array(rgb))
    if manifest and any(identity[name] != manifest[name] for name in ("rgb_shape", "rgb_pixels_sha256")):
        raise ValueError("Frozen source RGB changed")

    seg_path, regions_path = out_dir / "seg.npy", out_dir / "regions.json"
    geometry_ready = seg_path.is_file() and regions_path.is_file()
    geometry_origin = "legacy_existing" if geometry_ready else "new"
    if manifest and not geometry_ready:
        raise ValueError("Frozen run geometry is missing")
    if geometry_ready:
        geometry = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (seg_path, regions_path)}
        if manifest and geometry != manifest["geometry_sha256"]:
            raise ValueError("Frozen run geometry changed")
        R = load_run(out_dir)
        if R.seg.shape != rgb.shape[:2]:
            raise ValueError("Existing run geometry does not match the image grid")
        if not manifest:
            settings["n_skin"] = R.params["n_skin"]
        feats, _ = features.cached(task_id, rgb)
    else:
        exchanges = out_dir / "exchanges.jsonl"
        if old_decision.is_file() or (exchanges.is_file() and exchanges.stat().st_size):
            raise ValueError("Run with model replies is missing its saved geometry")
        _, feats, _, R = prepare(task_id, n_skin=n_skin, rgb=rgb)
        temp_seg = seg_path.with_suffix(".tmp")
        with temp_seg.open("wb") as stream:
            np.save(stream, R.seg, allow_pickle=False)
        temp_regions = regions_path.with_suffix(".tmp")
        temp_regions.write_text(json.dumps({"table": R.table, "tiles": R.tiles, "params": R.params}),
                                encoding="utf-8")
        temp_seg.replace(seg_path)
        temp_regions.replace(regions_path)
        geometry = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (seg_path, regions_path)}
    if feats.shape[:2] != rgb.shape[:2]:
        raise ValueError("Prepared image features do not match the image grid")
    features_sha256 = _sha256_array(feats)
    if manifest:
        if features_sha256 != manifest["features_sha256"]:
            raise ValueError("Frozen image features changed")
    else:
        record = {**identity, "geometry_sha256": geometry, "geometry_origin": geometry_origin,
                  "features_sha256": features_sha256}
        path = out_dir / "run_inputs.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    return rgb, feats, R, rub


def run(task_id: int, model: str, out_dir: Path, workers: int = 4, review_rounds: int = 0,
        recheck_on: bool = True, n_skin: int = regions.DEFAULT_SKIN_REGIONS,
        log=print, gold_for_sim: Optional[np.ndarray] = None, rubric_path: Optional[Path] = None) -> Dict[str, Any]:
    global _RUBRIC
    out_dir.mkdir(parents=True, exist_ok=True)
    rgb, feats, R, rub = _run_preparation(task_id, model, out_dir, n_skin, recheck_on, review_rounds, rubric_path)
    _RUBRIC = rub
    if model.startswith("sim:"):
        from ml.vlm_labeling.sim import SimVLM
        vlm = SimVLM(model, gold_for_sim, R)
    else:
        vlm = VLM(model, out_dir / "exchanges.jsonl")
    dec: Dict[str, Any] = {"task_id": task_id, "model": model, "provider": vlm.provider, "rubric": rubric_version(rub),
                           "started": dt.datetime.now().isoformat(timespec="seconds"), "regions": R.params,
                           "n_regions": len(R.table), "n_tiles": len(R.tiles), "steps": []}
    log(f"[P1] {len(R.table)} regions, {len(R.tiles)} tiles")

    tri = triage(vlm, rgb, R)
    dec["triage"] = tri
    log(f"[P2] triage: {json.dumps({k: tri.get(k) for k in ('body_site', 'skin_tone', 'lesion_present')}, ensure_ascii=False)}")

    verdicts: Dict[int, str] = {}
    issues: List[Dict[str, Any]] = []
    quota_error = None
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(judge_tile, vlm, rgb, R, t, tri): t for t in R.tiles}
        for f in cf.as_completed(futs):
            tile = futs[f]
            expected = set(tile["regions"])
            try:
                result = f.result()
            except ProviderQuotaExhausted as error:
                quota_error = error
                issues.append({"tile": tile["id"], "error_type": type(error).__name__})
                continue
            except Exception as e:  # noqa: BLE001
                issues.append({"tile": tile["id"], "error_type": type(e).__name__})
                log(f"  tile T{tile['id']} failed")
                continue
            missing = expected - result.keys()
            extra = result.keys() - expected
            duplicate = expected & verdicts.keys()
            if missing or extra or duplicate:
                issues.append({"tile": tile["id"], "missing_region_ids": sorted(missing),
                               "unexpected_region_ids": sorted(extra), "duplicate_region_ids": sorted(duplicate)})
            verdicts.update({i: result[i] for i in expected & result.keys()})
    expected_ids = {row["id"] for row in R.table}
    missing = expected_ids - verdicts.keys()
    extra = verdicts.keys() - expected_ids
    complete = not (issues or missing or extra)
    coverage = {"complete": complete, "expected_regions": len(expected_ids),
                "answered_regions": len(expected_ids & verdicts.keys()),
                "explicitly_uncertain_regions": sum(code == "U" for code in verdicts.values()),
                "missing_region_ids": sorted(missing), "unexpected_region_ids": sorted(extra),
                "tile_issues": sorted(issues, key=lambda item: item["tile"])}
    coverage_path = out_dir / "judgment_coverage.json"
    temp_coverage = coverage_path.with_suffix(".json.tmp")
    temp_coverage.write_text(json.dumps(coverage, ensure_ascii=False, indent=1))
    temp_coverage.replace(coverage_path)
    if quota_error is not None:
        raise quota_error
    if not complete:
        raise RuntimeError(f"Region judgment incomplete. See {coverage_path}")
    dec["steps"].append({"step": "judge", "counts": _count(verdicts)})
    log(f"[P3] verdicts {_count(verdicts)}")

    labels, info = fuse.fuse(feats, features.NAMES, R.seg, verdicts)
    _save_stage(out_dir, "p4_fuse", rgb, labels)
    log(f"[P4] fused; {len(info['disagree'])} regions contradict colour")

    if recheck_on and info["disagree"]:
        ids = [d["id"] for d in info["disagree"]]
        new = recheck(vlm, rgb, R, ids, tri)
        changed = {k: v for k, v in new.items() if v != verdicts.get(k)}
        verdicts.update(new)
        dec["steps"].append({"step": "recheck", "asked": ids, "changed": changed})
        labels, info = fuse.fuse(feats, features.NAMES, R.seg, verdicts)
        _save_stage(out_dir, "p5_recheck", rgb, labels)
        log(f"[P5] recheck {len(ids)} -> changed {len(changed)}")

    for rnd in range(review_rounds):
        fixes: Dict[int, str] = {}
        with cf.ThreadPoolExecutor(workers) as ex:
            futs = [ex.submit(review_tile, vlm, rgb, R, t, labels, rnd) for t in R.tiles]
            for f in cf.as_completed(futs):
                try:
                    fixes.update(f.result())
                except ProviderQuotaExhausted:
                    raise
                except Exception as e:  # noqa: BLE001
                    log(f"  review failed: {e}")
        changed = {k: v for k, v in fixes.items() if v != verdicts.get(k)}
        verdicts.update(changed)
        dec["steps"].append({"step": f"review{rnd}", "changed": changed})
        labels, info = fuse.fuse(feats, features.NAMES, R.seg, verdicts)
        _save_stage(out_dir, f"p6_review{rnd}", rgb, labels)
        log(f"[P6] review round {rnd}: changed {len(changed)}")
        if not changed:
            break

    dec["verdicts"] = {str(k): v for k, v in sorted(verdicts.items())}
    dec["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    np.save(out_dir / "labels.npy", labels)
    json.dump(dec, open(out_dir / "decision.json", "w"), ensure_ascii=False, indent=1)
    return {"labels": labels, "decision": dec, "info": info}


def load_run(out_dir: Path) -> regions.Regions:
    meta = json.load(open(out_dir / "regions.json"))
    return regions.Regions(seg=np.load(out_dir / "seg.npy", allow_pickle=False), table=meta["table"], tiles=meta["tiles"],
                           params=meta["params"])


def verdicts_from_log(out_dir: Path, R: regions.Regions, upto: str = "review") -> Dict[int, str]:
    """Rebuild verdicts from the exchange log (judge -> recheck -> review), so fusion changes can be
    evaluated on frozen model answers without calling the model again."""
    from ml.vlm_labeling.client import extract_json

    order = {"judge": 0, "recheck": 1, "review": 2}
    stop = order[upto]
    recs = [json.loads(line) for line in open(out_dir / "exchanges.jsonl")]
    v: Dict[int, str] = {}
    for phase in ("judge", "recheck", "review"):
        if order[phase] > stop:
            break
        for r in recs:
            if not r.get("parsed") or not r["step"].startswith(phase):
                continue
            data = extract_json(r["reply"])
            if phase == "judge":
                tid = int(r["step"].split(":T")[1].split(":")[0])
                ids = R.tiles[tid]["regions"]
            elif phase == "review":
                tid = int(r["step"].split(":T")[1])
                ids = R.tiles[tid]["regions"]
            else:
                ids = [t["id"] for t in R.table]
            v.update(_codes(data, ids))
    for t in R.table:
        v.setdefault(t["id"], "U")
    return v


def check_replay_inputs(out_dir: Path, decision: Dict[str, Any], rgb: np.ndarray, feats: np.ndarray) -> None:
    """Check the inputs used to reconstruct a saved decision on its original image grid."""
    manifest = frozen_run_inputs(out_dir)
    if not manifest:
        return
    identity = {
        "task_id": decision["task_id"], "model": decision["model"],
        "rgb_shape": list(rgb.shape), "rgb_pixels_sha256": _sha256_array(rgb),
        "feature_names": list(features.NAMES), "features_sha256": _sha256_array(feats),
    }
    changed = [key for key, value in identity.items() if manifest.get(key) != value]
    if changed:
        raise ValueError(f"Run {out_dir.name} differs from its frozen inputs: {', '.join(changed)}")
    for name in ("seg.npy", "regions.json"):
        if hashlib.sha256((out_dir / name).read_bytes()).hexdigest() != manifest["geometry_sha256"].get(name):
            raise ValueError(f"Run {out_dir.name} does not match its frozen {name}")
    if hashlib.sha256((out_dir / "rubric.snapshot.md").read_bytes()).hexdigest() != manifest["rubric_sha256"]:
        raise ValueError(f"Run {out_dir.name} does not match its frozen rubric")


def replay(out_dir: Path) -> np.ndarray:
    """Labels from a saved decision (no model call): same regions + same verdicts -> same pixels."""
    dec = json.load(open(out_dir / "decision.json"))
    rgb = sio.load_image(dec["task_id"])
    feats, _ = features.cached(dec["task_id"], rgb)
    check_replay_inputs(out_dir, dec, rgb, feats)
    seg = np.load(out_dir / "seg.npy", allow_pickle=False)
    if seg.shape != rgb.shape[:2]:
        raise ValueError(f"Run {out_dir.name} segmentation does not match the image grid")
    labels, _ = fuse.fuse(feats, features.NAMES, seg, {int(k): v for k, v in dec["verdicts"].items()})
    return labels


def _count(v: Dict[int, str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for c in v.values():
        out[c] = out.get(c, 0) + 1
    return dict(sorted(out.items()))


def overlay(rgb: np.ndarray, labels: np.ndarray) -> np.ndarray:
    im = rgb.astype(np.float32).copy()
    for k, c in {1: (0, 200, 0), 2: (255, 0, 0), 3: (0, 90, 255), 4: (160, 0, 200), 255: (255, 230, 0)}.items():
        m = labels == k
        im[m] = 0.55 * im[m] + 0.45 * np.array(c)
    return im.clip(0, 255).astype(np.uint8)


def _save_stage(out_dir: Path, name: str, rgb: np.ndarray, labels: np.ndarray, gold: Optional[np.ndarray] = None):
    np.save(out_dir / f"{name}.npy", labels)
    Image.fromarray(overlay(rgb, labels)).save(out_dir / f"{name}.jpg", quality=85)


# ---------------------------------------------------------------- P5b anchored boundary recheck
def boundary_regions(R: regions.Regions, verdicts: Dict[int, str]) -> List[int]:
    """Skin regions (L/N/M) that touch a region with a different lesion verdict — where the
    remaining error lives once region verdicts are ~95% right."""
    seg = R.seg
    pairs = set()
    for a, b in ((seg[:, :-1], seg[:, 1:]), (seg[:-1, :], seg[1:, :])):
        m = (a != b) & (a >= 0) & (b >= 0)
        for x, y in zip(a[m].tolist(), b[m].tolist()):
            pairs.add((x, y))
    out = set()
    skin = {"L", "N", "M"}
    for x, y in pairs:
        vx, vy = verdicts.get(x, "U"), verdicts.get(y, "U")
        if vx in skin and vy in skin and (vx != vy or "M" in (vx, vy)):
            out.update((x, y))
    return sorted(out)


def anchor_swatches(R: regions.Regions, verdicts: Dict[int, str], p_lesion: np.ndarray, k: int = 2) -> Dict[str, List[int]]:
    """This person's most certain normal-skin and lesion regions (no gold): large regions whose
    out-of-fold colour probability agrees strongly with the verdict."""
    rid = np.where(R.seg >= 0, R.seg, R.seg.max() + 1)
    rp = np.bincount(rid.ravel(), p_lesion.ravel()) / np.maximum(np.bincount(rid.ravel()), 1)
    def pick(code, key):  # noqa: E306
        c = [t for t in R.table if verdicts.get(t["id"]) == code and t["area"] >= np.median([u["area"] for u in R.table])]
        c.sort(key=key)
        return [t["id"] for t in c[:k]]
    return {"N": pick("N", lambda t: rp[t["id"]]), "L": pick("L", lambda t: -rp[t["id"]])}


def anchored_recheck(vlm, rgb: np.ndarray, R: regions.Regions, ids: List[int], swatches: Dict[str, List[int]],
                     batch: int = 12, tag: str = "anchor", workers: int = 4) -> Dict[int, str]:
    ref = contact_sheet(rgb, R, swatches["N"] + swatches["L"], cell=220)

    def one(b):
        chunk = ids[b:b + batch]
        sheet = contact_sheet(rgb, R, chunk)
        text = ("对照复核。第 1 张是**这个人自己的参照色卡**（青线内）："
                f"编号 {swatches['N']} 是此人确定的正常皮肤，编号 {swatches['L']} 是此人确定的白斑。\n"
                "第 2 张每个小图青线内是一个待判区域。只拿青线内部的颜色去和参照色卡比："
                "更像正常皮色卡给 N，更像白斑色卡给 L，青线内明显两种都有给 M。"
                "不要看亮度高低（受光会变亮），看色调：正常皮偏黄/橙/褐，白斑偏粉/米白。"
                f"编号：{chunk}。输出 JSON：{{\"regions\": {{\"编号\": \"代码\"}}}}")
        try:
            r = vlm.ask(f"{tag}:{b // batch}", rubric(), [image_part(ref), image_part(sheet), {"type": "text", "text": text}])
        except ProviderQuotaExhausted:
            raise
        except RuntimeError as e:
            print(f"  {tag} batch {b // batch} skipped: {str(e)[:100]}")
            return {}
        return {k: v for k, v in _codes(r["data"], chunk).items() if v in "LNM"}

    out: Dict[int, str] = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for res in ex.map(one, range(0, len(ids), batch)):
            out.update(res)
    return out


# ---------------------------------------------------------------- P0b route by lesion pattern
ROUTES = {
    # oracle ceilings (perfect verdicts, ±2px): 182 600r 0.981; 192 600r 0.806 vs 1500r 0.921; 207 600r 0.708 vs 1500r 0.929
    "patches": (600, 700, 800, 900, 1000),
    "scattered": (1200, 1400, 1600, 1800, 2000),
}


def regions_for_spot(task_id: int, rgb: np.ndarray, spot_px_1024: float, lo: int = 600, hi: int = 2000) -> int:
    """Region count so that one region is ~1/6 of the model-estimated typical spot diameter.
    Gold-measured need (dev): spot/region diameter ratio >= ~3.5 works (263 3.45, others 6-13);
    192 (2.0) and 207 (1.5) failed.  The model over-estimates spot size ~1.5-1.8x, hence /6."""
    H, W = rgb.shape[:2]
    d = float(spot_px_1024) * max(H, W) / 1024.0
    feats, side = features.cached(task_id, rgb)
    ix = {n: i for i, n in enumerate(features.NAMES)}
    skin = ((feats[..., ix["mp_face"]] + feats[..., ix["mp_body"]]) > 0.5) | side["proposal"]
    area = float(skin.sum())
    r = max(d / 6.0, 4.0)
    return int(np.clip(area / (np.pi * (r / 2) ** 2), lo, hi))


def lesion_pattern(vlm, rgb: np.ndarray) -> Dict[str, Any]:
    """One look at the whole image: are the lesions large patches or scattered small spots?
    Decides region granularity before any region is drawn (no gold, no human)."""
    H, W = rgb.shape[:2]
    s = 1024 / max(H, W)
    im = Image.fromarray(rgb).resize((int(W * s), int(H * s)), Image.LANCZOS)
    text = ("看这张白癜风照片，只判断白斑的形态，输出 JSON："
            '{"pattern": "patches" 或 "scattered", "typical_spot_px": 典型单个白斑直径（按这张 1024 宽的图估计像素）, "why": "一句话"}。'
            "patches = 白斑主要是成片的大斑（单块直径大于图宽的 1/20）；"
            "scattered = 白斑主要是很多散在的小点/碎斑（米粒大小、成群分布）。")
    r = vlm.ask("pattern", "你是皮肤科医生。", [image_part(im), {"type": "text", "text": text}])
    d = r["data"] if isinstance(r["data"], dict) else {}
    pat = str(d.get("pattern", "patches")).strip().lower()
    d["pattern"] = pat if pat in ROUTES else "patches"
    return d
