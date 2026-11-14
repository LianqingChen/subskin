"""Source-only numbered-region inference for the journal worker."""

import copy
import hashlib
import json

import cv2
import numpy as np
from PIL import Image, ImageDraw

from ml.vlm_labeling import fuse, protocol, regions

VALID = set("BNLOXMU")
RULES = "你执行普通光RGB照片的可见外观AI初审，程序生成像素，你只按给定编号判读，不输出坐标或多边形，不声称已达到金标准。\nB背景=衣服、床单、桌墙、物品、浓密头发；N正常皮肤=唇红、眉区皮肤及保留色素岛；L=可见减色/脱色白斑，可为淡粉/米白/淡棕，不要求纯白；O遮挡=指甲、眼睛开口、鼻孔、覆盖皮肤的饰物或印刷标记；X=隐私模糊/打码不可读；M=同一区域混有不同类别，需要像素工具细分；U仅确实不可读的窄边界，不能用于漏答编号或工具失败。\n先建立此人同光照下的正常与减色皮肤参照。连续脱色斑中的细小毛囊色点与稀疏毛发不逐点挖洞；可见成片保留色素的岛与周围正常皮仍判N。不要因白斑不是纯白就漏标。高光、褶皱提亮、阴影不能直接决定N或L。稀疏毛发间可见皮肤按实际外观；眉区保留正常皮肤口径，唇红为N。不要从常见解剖位置猜白斑，不凑类别数量或占比，自动解析提示及自动参照均可能错误。\n颜色只依据干净RGB；编号图与青线图只定位。出现单独的干净图与青线图时，先读干净图的颜色。不要让青线的颜色改变判断。\n外观标签与临床分型分别记录；只有RGB时临床候选必须unconfirmed、image_only、review_required:true，不作诊断或病期确认，不从照片推定Fitzpatrick。\n\n通用观察规则（效果待验证，仍以干净原图为准）：\n对每个候选，同时检查“正常皮肤因受光或阴影发生变化”和“可见减色或脱色”两种解释。不能因更亮就判L，也不能因处于阴影、更暗就判N。结合邻近同光照皮肤的相对色调、色度、过渡和可见表面，给出编号判读。\n\n先在局部相近光照下比较，再联系整图的连续表面和可见外观。不同光照中的相同RGB外观可以属于不同类别，同类皮肤也可能明暗差别很大。不能用单一绝对色卡、全图亮度排序或固定肤色值替代判读。\n\n边缘核验允许同时存在清晰边缘和缓变边缘；不要求所有减色区都比邻域更亮、具有锐利色度阶跃或达到固定饱和差。纹理仅用于辅助核对皮肤表面、光照与遮挡，不把“必须改变纹理”设成白斑条件。\n\nAI选出的参照始终是暂定假设。重复回答一致或颜色工具高置信不等于角色正确。参照应考虑高光正常皮、阴影内减色区等不同光照情形；缺少可信同光照参照时，不机械外推，不为凑齐N/L样本强取参照，也不自动推翻已有判读。\n\nM只用于目标区域确实跨越不同类别的边界；同类内部的明暗、色调或纹理变化本身不构成M。模型犹豫或前后分歧应记录为算法待复核信息，不能据此把可读的整块皮肤改成不可读或255；真正的隐私模糊与模糊边界仍按既有类别规范处理。\n\n按物体与皮肤的语义区分背景和遮挡：衣服、铺巾、墙、桌面属于B；指甲、眼鼻开口、覆盖皮肤的饰物或印刷标记按既有规范属于O。仅暗、偏色或低饱和不能构成遮挡证据，阴影下可见的皮肤继续按其外观判读。\n"


def decode(document, expected):
    expected = set(expected)
    valid = {}
    seen = set()
    invalid = []
    unknown = []
    rows = document.get("regions") if isinstance(document, dict) else None
    form = (
        "mapping"
        if isinstance(rows, dict)
        else "id_code_records"
        if isinstance(rows, list)
        else "unsupported"
    )
    if isinstance(rows, dict):
        items = list(rows.items())
    elif isinstance(rows, list):
        items = []
        for row in rows:
            if not isinstance(row, dict) or "id" not in row or "code" not in row:
                invalid.append("invalid_record")
                continue
            items.append((row["id"], row["code"]))
    else:
        return (
            {},
            {
                "container": form,
                "missing": sorted(expected),
                "invalid": ["regions_mapping_or_id_code_records_required"],
                "complete": False,
            },
        )
    for key, value in items:
        if isinstance(key, bool) or not (
            type(key) is int or (isinstance(key, str) and key.isdigit())
        ):
            invalid.append("invalid_ID")
            continue
        i = int(key)
        if i not in expected:
            unknown.append(i)
            continue
        if i in seen:
            valid.pop(i, None)
            invalid.append("duplicate_ID:" + str(i))
            continue
        seen.add(i)
        if not isinstance(value, str) or value.strip().upper() not in VALID:
            invalid.append("invalid_code:" + str(i))
            continue
        valid[i] = value.strip().upper()
    missing = sorted(expected - set(valid))
    return (
        valid,
        {
            "container": form,
            "missing": missing,
            "invalid": invalid,
            "unknown": unknown,
            "complete": not (missing or invalid or unknown),
            "medical_codes_inferred_or_changed": False,
        },
    )


def freeze(scene, image_sha256, model, response_id):
    if not isinstance(image_sha256, str) or len(image_sha256) != 64:
        raise ValueError("source_image_fingerprint_required")
    if (
        not isinstance(model, str)
        or not model
        or (not isinstance(response_id, str))
        or (not response_id)
    ):
        raise ValueError("scene_producer_required")
    fields = {
        k: copy.deepcopy(scene.get(k))
        for k in ["body_sites", "normal_color", "lesion_color"]
    }
    if (
        not isinstance(fields["body_sites"], list)
        or not fields["body_sites"]
        or any((not isinstance(x, str) for x in fields["body_sites"]))
    ):
        raise ValueError("body_sites_required")
    if any(
        (
            not isinstance(fields[k], str) or not fields[k].strip()
            for k in ["normal_color", "lesion_color"]
        )
    ):
        raise ValueError("visible_colour_descriptions_required")
    value = {
        "source_image_sha256": image_sha256,
        "producer_model": model,
        "producer_response_id": response_id,
        "reference_status": "model_provisional_not_Gold",
        "visible_frame": fields,
    }
    value["reference_sha256"] = hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return value


def local_text(stage, question, reference, image_sha256, model):
    original = {k: v for (k, v) in reference.items() if k != "reference_sha256"}
    digest = hashlib.sha256(
        json.dumps(
            original, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()
    if digest != reference.get("reference_sha256"):
        raise ValueError("scene_reference_mutated")
    if reference["source_image_sha256"] != image_sha256:
        raise ValueError("different_photo_scene_leak")
    if reference["producer_model"] != model:
        raise ValueError("other_model_answer_leak")
    return (
        question
        + "\n本次原图的暂定颜色语境（来自本模型对同一原图的全局判读，不是人工真值；按干净RGB仍可推翻）："
        + json.dumps(reference["visible_frame"], ensure_ascii=False)
        + "。阶段="
        + stage
        + "；语境版本="
        + reference["reference_sha256"]
    )


def context_pair(source, clean, marked, caption):
    if not all(
        (
            isinstance(im, Image.Image) and im.mode == "RGB"
            for im in [source, clean, marked]
        )
    ):
        raise ValueError("RGB PIL inputs required")
    if clean.size != marked.size or min(*source.size, *clean.size) <= 0:
        raise ValueError("clean/marked detail shapes must match")
    gap = 20
    top = 46
    width = source.width + clean.width + 3 * gap
    height = max(source.height, clean.height) + top + gap
    source_box = (gap, top, gap + source.width, top + source.height)
    detail_box = (
        2 * gap + source.width,
        top,
        2 * gap + source.width + clean.width,
        top + clean.height,
    )
    outputs = []
    for detail, kind in [(clean, "CLEAN detail"), (marked, "NUMBERED detail")]:
        panel = Image.new("RGB", (width, height), (23, 27, 31))
        panel.paste(source, source_box[:2])
        panel.paste(detail, detail_box[:2])
        draw = ImageDraw.Draw(panel)
        draw.text((gap, 14), "Same target - complete source RGB", fill="white")
        draw.text((detail_box[0], 14), caption + " | " + kind, fill="white")
        outputs.append(panel)
    return (
        outputs,
        {
            "source_box": list(source_box),
            "detail_box": list(detail_box),
            "board_size": [width, height],
            "source_rescaled": False,
            "detail_rescaled": False,
            "no_input_pixels_removed_or_recolored": True,
        },
    )


def prepare_panels(source, stage, images, text):
    if "_judgeT" in stage:
        old = "第一张是全图分块位置，第二张干净RGB，第三张编号图。"
    elif "_colour_recheck" in stage:
        old = "最后两张图位置逐格相同：倒数第二张为干净RGB，最后一张青线标目标。颜色只按干净图。"
    else:
        return (images, text)
    assert len(images) == 3 and text.count(old) == 1
    new = "两张图的左侧均为完整原始RGB。第一张右侧是干净局部，第二张右侧是对应编号或轮廓。用干净图判断颜色，用整图核对部位和光照。"
    (panels, boxes) = context_pair(source, images[1], images[2], stage)
    for panel, detail in zip(panels, images[1:]):
        assert panel.crop(boxes["source_box"]).tobytes() == source.tobytes()
        assert panel.crop(boxes["detail_box"]).tobytes() == detail.tobytes()
    return (panels, text.replace(old, new))


def advisory_qa_valid(doc, ids):
    if not isinstance(doc, dict):
        return False
    rows = doc.get("review_tile_ids")
    notes = doc.get("visible_concerns")
    return (
        isinstance(rows, list)
        and all((type(i) is int for i in rows))
        and (len(rows) == len(set(rows)))
        and set(rows).issubset(ids)
        and isinstance(notes, list)
        and all((isinstance(x, str) and len(x) <= 800 for x in notes))
        and (doc.get("assessment_scope") == "advisory_only_not_accuracy")
        and (doc.get("no_pixel_changes") is True)
    )


def profile(model):
    p = {
        "seed": 42,
        "temperature": 0.1,
        "max_tokens": 32768 if model.startswith("qwen") else 65536,
        "extra_body": {"enable_thinking": True, "enable_search": False},
    }
    if model.startswith("qwen"):
        p["extra_body"].update({"thinking_budget": 16384, "preserve_thinking": True})
    else:
        p["reasoning_effort"] = "high"
    return p


def card_sheets(rgb, reg, ids, cell=224):
    from ml.vlm_labeling import regions

    cols = 4
    rows = (len(ids) + 3) // 4
    clean = Image.new("RGB", (cols * cell, rows * (cell + 28)), (25, 25, 25))
    marked = clean.copy()
    dc = ImageDraw.Draw(clean)
    dm = ImageDraw.Draw(marked)
    font = regions._font(18)
    (H, W) = rgb.shape[:2]
    for j, i in enumerate(ids):
        (x0, y0, x1, y1) = reg.table[i]["bbox"]
        side = max(x1 - x0, y1 - y0) * 3 + 40
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        bx0 = max(0, cx - side // 2)
        by0 = max(0, cy - side // 2)
        bx1 = min(W, bx0 + side)
        by1 = min(H, by0 + side)
        part = rgb[by0:by1, bx0:bx1].copy()
        markedpart = part.copy()
        mask = (reg.seg[by0:by1, bx0:bx1] == i).astype(np.uint8)
        (contours, _) = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(markedpart, contours, -1, (0, 255, 255), 1)
        scale = cell / max(part.shape[:2])
        size = (
            max(1, round(part.shape[1] * scale)),
            max(1, round(part.shape[0] * scale)),
        )
        ox = j % cols * cell
        oy = j // cols * (cell + 28)
        for board, draw, pixels in [(clean, dc, part), (marked, dm, markedpart)]:
            board.paste(
                Image.fromarray(pixels).resize(size, Image.Resampling.LANCZOS),
                (ox, oy + 28),
            )
            draw.text((ox + 5, oy + 3), "#" + str(i), fill="white", font=font)
    return (clean, marked)


def apply_fuse(feats, names, reg, v):
    from ml.vlm_labeling import fuse

    (labels, info) = fuse.fuse(feats, names, reg.seg, v, refine_skin=True)
    if min(info["n_N"], info["n_L"]) < 200:
        for i, c in v.items():
            if c in ["M", "U"]:
                labels[reg.seg == i] = 255
    return (labels, info)


def paint(rgb, labels):
    z = rgb.astype(np.float32).copy()
    for c, color in {
        1: [50, 130, 235],
        2: [35, 225, 110],
        3: [235, 95, 60],
        4: [130, 130, 130],
        255: [255, 205, 20],
    }.items():
        z[labels == c] = 0.55 * z[labels == c] + 0.45 * np.array(color)
    return np.uint8(z.clip(0, 255))


def run_branch(client, rgb, feats, names, reg):
    overview = regions.overview(rgb, reg)
    tri = client.request(
        "raw_triage",
        [Image.fromarray(rgb), overview],
        '通读整图，只按可见RGB。输出JSON字段：body_sites中文列表、skin_tone_description可见肤色描述（非Fitzpatrick）、normal_color、lesion_color、lesion_present布尔、appearance_tags对象（颜色、边缘、连续性、色素岛等）、clinical_assessment={candidate_types:["undetermined"或未确认候选],status:"unconfirmed",evidence_scope:"image_only",review_required:true}、lesion_map按图中T分块编号描述。',
        ids=[t["id"] for t in reg.tiles],
        triage=True,
    )
    reference = freeze(tri, client.rgb_sha, client.model, client.last_response_id)

    def context(stage, text):
        return local_text(stage, text, reference, client.rgb_sha, client.model)

    def judge(tile):
        (clean, marked, _) = regions.render_tile(rgb, reg, tile)
        ids = tile["regions"]
        text = (
            "本分块初步描述（可依据原图推翻）："
            + str(
                tri["lesion_map"].get(
                    "T" + str(tile["id"]), tri["lesion_map"].get(str(tile["id"]))
                )
            )
            + "。第一张是全图分块位置，第二张干净RGB，第三张编号图。"
            + protocol._hints(reg, ids)
            + '。逐区返回完整JSON {"regions":{"编号":"B/N/L/O/X/M/U"}}。编号：'
            + json.dumps(ids)
        )
        return client.request(
            "raw_judgeT" + str(tile["id"]),
            [protocol._tile_overview(rgb, tile), clean, marked],
            context("P3", text),
            ids=ids,
        )

    v = {}
    for tile in reg.tiles:
        v.update(judge(tile))
    if set(v) != set(range(len(reg.table))):
        raise ValueError("Incomplete initial numbered-region judgment")

    _, info = apply_fuse(feats, names, reg, v)
    ids = [x["id"] for x in info["disagree"]]

    def recheck(start):
        selected = ids[start : start + 12]
        (clean, marked) = card_sheets(rgb, reg, selected)
        text = (
            '最后两张图位置逐格相同：倒数第二张为干净RGB，最后一张青线标目标。颜色只按干净图。逐区判断，可推翻先前暂定颜色语境，不按亮度直接判白斑。返回完整JSON {"regions":{"编号":"B/N/L/O/X/M/U"}}。编号：'
            + json.dumps(selected)
        )
        return client.request(
            "raw_colour_recheck" + str(start // 12),
            [Image.fromarray(rgb), clean, marked],
            context("colour_recheck", text),
            ids=selected,
        )

    for start in range(0, len(ids), 12):
        v.update(recheck(start))
    labels, _ = apply_fuse(feats, names, reg, v)
    filled = paint(rgb, labels)
    text = '完整涂层的建议性审查。第一张干净原图，第二张同图分块定位，第三张是本地工具实际填充涂层：蓝正常皮1、绿白斑2、橙遮挡3、灰隐私不可读4、黄未定255。以原图核对高光误扩、阴影内漏标、可见皮肤与背景边界。结果已经冻结，你只给待复核分块和可见问题，不修改像素，不宣称准确率或金标准达标。输出JSON {"review_tile_ids":[需要复核的T分块数字],"visible_concerns":["原图可见的问题或需要复核的原因"],"assessment_scope":"advisory_only_not_accuracy","no_pixel_changes":true}。允许返回空复核列表，但空列表不证明结果准确。'
    client.request(
        "raw_advisory_overlay_QA",
        [Image.fromarray(rgb), overview, Image.fromarray(filled)],
        context("P6advisory", text),
        ids=[t["id"] for t in reg.tiles],
        qa=True,
    )
    return v


def legacy_vote(maps, skin):
    votes = np.stack(maps)
    visible = np.isin(votes, (1, 2, 255)).sum(axis=0) > len(maps) / 2
    white = (votes == 2).sum(axis=0)
    labels = np.where(
        (votes == 3).sum(axis=0) > len(maps) / 2,
        3,
        np.where((votes == 4).sum(axis=0) > len(maps) / 2, 4, 0),
    ).astype(np.uint8)
    labels[visible] = np.where(white[visible] > len(maps) / 2, 2, 1)
    adapted = np.zeros(skin.shape, dtype=np.uint8)
    adapted[skin] = 1
    adapted[skin & (labels == 2)] = 2
    adapted[np.isin(labels, (4, 255))] = 255
    return adapted, int((visible & (white == len(maps) / 2)).sum())


def render_pair(left, right):
    board = Image.new(
        "RGB",
        (left.width + right.width + 20, max(left.height, right.height)),
        (25, 25, 25),
    )
    board.paste(left, (0, 0))
    board.paste(right, (left.width + 20, 0))
    return board


def anchored_votes(client, rgb, reg, feats, names, raw):
    p5_map, info = fuse.fuse(feats, names, reg.seg, raw)
    if "p_lesion" not in info:
        raise RuntimeError(
            "Source judgment did not produce two lesion/normal colour anchors"
        )
    swatches = protocol.anchor_swatches(reg, raw, info["p_lesion"])
    if not swatches["N"] or not swatches["L"]:
        raise RuntimeError("Current source verdicts lack an anchor class")
    clean_ref, marked_ref = card_sheets(rgb, reg, swatches["N"] + swatches["L"])
    reference = render_pair(clean_ref, marked_ref)
    ids = protocol.boundary_regions(reg, raw)
    anchored = raw.copy()
    for start in range(0, len(ids), 12):
        selected = ids[start : start + 12]
        clean, marked = card_sheets(rgb, reg, selected)
        text = (
            f"第一张为整张原图。第二张左侧为干净色卡，右侧同位置青线用于定位。"
            f"当前自动候选中正常参照编号为 {swatches['N']}，白斑参照编号为 {swatches['L']}。"
            "参考候选可能有误，比较本图相邻皮肤的相对减色外观。第三张左侧为待复核干净区域，"
            "右侧同位置为编号和青线。按干净原图判断，青线只定位。"
            '返回完整 JSON {"regions":{"编号":"B/N/L/O/X/M/U"}}。编号：'
            + json.dumps(selected)
        )
        result = client.request(
            f"anchor_{start // 12}",
            [Image.fromarray(rgb), reference, render_pair(clean, marked)],
            text,
            ids=selected,
        )
        anchored.update(
            {i: code for i, code in result.items() if code in ("L", "N", "M")}
        )
    final, _ = fuse.fuse(feats, names, reg.seg, anchored)
    return (
        p5_map,
        final,
        {
            "swatches": swatches,
            "queried_regions": len(ids),
            "changed": sum(raw[i] != anchored[i] for i in raw),
        },
        anchored,
    )


def skin_mask(rgb):
    from web.backend.services.rgb_segmentation import skin_parsing as sp
    import mediapipe as mp
    from mediapipe.tasks.python.vision import FaceLandmarksConnections as FM

    (h, w) = rgb.shape[:2]
    with sp._lock:
        model = sp._load("segmenter")
        assert model is not None, "pretrained_skin_parser_unavailable"
        im = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        res = model.segment(im)
        conf = np.stack([x.numpy_view() for x in res.confidence_masks], -1)
        if conf.shape[:2] != (h, w):
            conf = cv2.resize(conf, (w, h))
        mask = conf[..., sp.BODY_SKIN] + conf[..., sp.FACE_SKIN] > 0.5
        landmark = sp._load("landmarker")
        faces = landmark.detect(im).face_landmarks if landmark else []
    eyes = np.zeros((h, w), np.uint8)
    for face in faces:
        pts = np.array([[x.x * w, x.y * h] for x in face])
        for edges in [FM.FACE_LANDMARKS_LEFT_EYE, FM.FACE_LANDMARKS_RIGHT_EYE]:
            ids = sorted({e.start for e in edges} | {e.end for e in edges})
            cv2.fillConvexPoly(eyes, cv2.convexHull(pts[ids].astype("int32")), 1)
    mask &= ~eyes.astype(bool)
    if mask.mean() < 0.01:
        raise ValueError("skin_not_detected")
    return mask
