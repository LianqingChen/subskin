"""Run the frozen five-density white-patch method for one consented RGB image."""

from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
import base64
import hashlib
import logging
import json
from threading import Event

import cv2
import numpy as np
from PIL import Image
from threadpoolctl import threadpool_limits

from web.backend.exceptions import RGBSegmentationError
from web.backend.services.rgb_segmentation import artifacts, bailian_consent as consent
from web.backend.services.rgb_segmentation.images import png_bytes

WORK = artifacts.PROJECT_ROOT / "data/research/autonomous-vlm-v1"
WEIGHTS = (
    WORK / "public_finetune/resnet18-appearance-v1/joint_v2/run01/selected.safetensors"
)
WEIGHTS_SHA256 = "124f8d8ebdff20cdba054176ca04f4da48a205083851ed9b97793db902a90521"  # pragma: allowlist secret (checkpoint checksum)
logger = logging.getLogger(__name__)
DENSITIES = (600, 700, 800, 900, 1000)


class BailianClient:
    def __init__(self, key, before_send, rgb_sha, original, stop):
        from openai import OpenAI

        self.client = OpenAI(
            api_key=key, base_url=consent.BASE_URL, timeout=600, max_retries=0
        )
        self.before_send = before_send
        self.model = consent.MODEL
        self.rgb_sha = rgb_sha
        self.original = original
        self.last_response_id = None
        self.triage = None
        self.requests = 0
        self.stop = stop

    def request(
        self, stage, images, text, ids=None, triage=False, qa=False, allowed_codes=None
    ):
        from openai import APIError
        from ml.vlm_labeling.diary_protocol import (
            RULES,
            advisory_qa_valid,
            decode,
            prepare_panels,
            profile,
        )
        from web.backend.utils.body_sites import site_labels

        if triage:
            text = text.replace("body_sites中文列表", "body_sites标准代码列表")
            text += (
                " body_sites 请只返回以下标准代码。细部观察可写进 appearance_tags。"
                + json.dumps(site_labels(), ensure_ascii=False)
            )
            text += (
                " appearance_tags 写 colour_terms、morphology、border、pigment_islands、white_hair。"
                "另填 affected_body_sites 标准部位代码列表。"
            )
        panels, text = prepare_panels(self.original, stage, images, text)
        parts = []
        for panel in panels:
            data = png_bytes(np.asarray(panel.convert("RGB")))
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(data).decode("ascii")
                    },
                }
            )
        parts.append({"type": "text", "text": text})
        locked = {}
        for attempt in range(2):
            if self.stop.is_set():
                raise RGBSegmentationError(
                    "BAILIAN_UNAVAILABLE", "百炼分析暂不可用", 503
                )
            self.requests += 1
            if self.requests > 150:
                raise RGBSegmentationError(
                    "BAILIAN_UNAVAILABLE", "百炼分析达到请求上限"
                )
            self.before_send(stage, self.rgb_sha)
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": RULES},
                        {"role": "user", "content": parts},
                    ],
                    **profile(self.model),
                )
            except APIError as exc:
                status = getattr(exc, "status_code", None)
                code = "BAILIAN_QUOTA" if status == 429 else "BAILIAN_UNAVAILABLE"
                raise RGBSegmentationError(code, "百炼分析暂不可用", 503) from None
            choice = response.choices[0] if response.choices else None
            if (
                response.model != self.model
                or not response.id
                or choice is None
                or choice.finish_reason != "stop"
            ):
                raise RGBSegmentationError(
                    "BAILIAN_INVALID_RESPONSE", "百炼未返回完整判读", 503
                )
            self.last_response_id = response.id
            try:
                doc = json.loads(choice.message.content or "{}")
            except ValueError:
                doc = {}
            if not isinstance(doc, dict):
                doc = {}
            if qa:
                if advisory_qa_valid(doc, set(ids)):
                    return doc
                diagnostic = {"allowed_tile_ids": ids, "required": "advisory QA JSON"}
            elif triage:
                clinical = doc.get("clinical_assessment")
                mapping = doc.get("lesion_map")
                valid = (
                    isinstance(doc.get("body_sites"), list)
                    and bool(doc["body_sites"])
                    and all(
                        isinstance(v, str) and v in site_labels()
                        for v in doc["body_sites"]
                    )
                    and all(
                        isinstance(doc.get(field), str) and doc[field].strip()
                        for field in (
                            "skin_tone_description",
                            "normal_color",
                            "lesion_color",
                        )
                    )
                    and isinstance(doc.get("appearance_tags"), dict)
                    and type(doc.get("lesion_present")) is bool
                    and isinstance(clinical, dict)
                    and clinical.get("status") == "unconfirmed"
                    and clinical.get("evidence_scope") == "image_only"
                    and clinical.get("review_required") is True
                    and isinstance(mapping, dict)
                    and all(str(i) in mapping or f"T{i}" in mapping for i in ids)
                )
                if valid:
                    self.triage = doc
                    return doc
                diagnostic = {
                    "required": "complete triage JSON including clinical review status",
                    "tile_ids": ids,
                }
            else:
                parsed, diagnostic = decode(doc, ids)
                if allowed_codes:
                    rejected = [
                        i for i, value in parsed.items() if value not in allowed_codes
                    ]
                    diagnostic["invalid"] += [f"invalid_code:{i}" for i in rejected]
                    for i in rejected:
                        del parsed[i]
                parsed.update(locked)
                if (
                    set(parsed) == set(ids)
                    and not diagnostic.get("invalid")
                    and not diagnostic.get("unknown")
                ):
                    return parsed
                if not attempt:
                    locked = parsed
            parts.append(
                {
                    "type": "text",
                    "text": "仅修复输出结构与编号完整性：" + json.dumps(diagnostic),
                }
            )
        raise RGBSegmentationError(
            "BAILIAN_INVALID_RESPONSE", "百炼未返回完整判读", 503
        )


def helper_probability(rgb):
    from ml.vlm_labeling.diary_helper_model import Dual, infer
    import torch

    from safetensors.torch import load

    raw = WEIGHTS.read_bytes()
    if hashlib.sha256(raw).hexdigest() != WEIGHTS_SHA256:
        raise RGBSegmentationError("MODEL_UNAVAILABLE", "本地辅助分割暂不可用", 503)
    torch.set_num_threads(2)
    model = Dual()
    model.load_state_dict(load(raw), strict=True)
    return infer(model, rgb, {"window": 256, "stride": 128, "scales": [1.0, 0.5]})


def masks_from_labels(labels, visible):
    excluded = np.isin(labels, (3, 4))
    skin = np.isin(labels, (1, 2)) | ((labels == 255) & visible)
    return {
        "skin": skin,
        "lesion": labels == 2,
        "uncertain": (labels == 255) & skin,
        "excluded": excluded,
    }


def judge_smallspots(client, rgb, labels, rows):
    from types import SimpleNamespace
    from ml.vlm_labeling.diary_fusion import SMALLSPOT_BATCH, SMALLSPOT_ROUNDS
    from ml.vlm_labeling.diary_protocol import card_sheets

    reg = SimpleNamespace(
        seg=labels, table={ident: {"bbox": box} for _, ident, box in rows}
    )
    accepted = []
    for offset in range(0, len(rows), SMALLSPOT_BATCH):
        ids = [ident for _, ident, _ in rows[offset : offset + SMALLSPOT_BATCH]]
        clean, marked = card_sheets(rgb, reg, ids)
        frames = [client.original, clean, marked]
        votes = []
        for round_index in range(SMALLSPOT_ROUNDS):
            votes.append(
                client.request(
                    f"smallspot_{offset // SMALLSPOT_BATCH}_{round_index}",
                    frames,
                    "第一张是整张照片，第二张是干净的局部，第三张青线只标位置。"
                    "对照本人邻近正常皮肤的色调，区分脱色、高光和阴影。"
                    "逐编号判定 L 白斑、N 正常或反光、U 不确定。"
                    '返回完整 JSON {"regions":{"编号":"L/N/U"}}。编号：'
                    + json.dumps(ids),
                    ids=ids,
                    allowed_codes={"L", "N", "U"},
                )
            )
        accepted.extend(
            ident
            for ident in ids
            if sum(v[ident] == "L" for v in votes) * 2 > SMALLSPOT_ROUNDS
        )
    return accepted


def fusion_drafts(
    rgb, base, aided, probabilities, key, before_send, source_sha, original, stop
):
    from ml.vlm_labeling.diary_fusion import (
        boundary_candidate,
        confirm_smallspots,
        sparse_candidates,
    )

    variants = {"boundary_lesion": boundary_candidate(rgb, aided)}
    seed, candidates = sparse_candidates(rgb, base)
    state = {"status": "not_sparse", "proposed": 0, "judged": 0, "accepted": 0}
    if candidates is None:
        return variants, state
    labels, rows, proposed = candidates
    state.update(status="no_candidates", proposed=proposed)
    if not rows:
        return variants, state
    client = BailianClient(key, before_send, source_sha, original, stop)
    try:
        accepted = judge_smallspots(client, rgb, labels, rows)
    except RGBSegmentationError as exc:
        if exc.code in ("CANCELLED", "BAILIAN_CONSENT_REQUIRED"):
            raise
        logger.info("Small-spot comparison unavailable (%s)", exc.code)
        state.update(status="unavailable", requests=client.requests)
    else:
        state.update(
            status="completed",
            judged=len(rows),
            accepted=len(accepted),
            requests=client.requests,
        )
        variants["smallspot_lesion"] = confirm_smallspots(
            base, seed, aided, labels, accepted, probabilities
        )
    return variants, state


def run(rgb, key, before_send, *, compare_fusion=False):
    from ml.pixel_labeling import features
    from ml.vlm_labeling import fuse, regions
    from ml.vlm_labeling.review_packet import _review_tags
    from ml.vlm_labeling.diary_fusion import apply_fixed_helper
    from ml.vlm_labeling.diary_protocol import (
        anchored_votes,
        legacy_vote,
        run_branch,
        skin_mask,
    )

    cv2.setNumThreads(2)
    image = png_bytes(rgb)
    source_sha = hashlib.sha256(image).hexdigest()
    original = Image.fromarray(rgb)
    with threadpool_limits(limits=2):
        feature, side = features.feature_maps(rgb)
        try:
            skin = skin_mask(rgb)
        except ValueError:
            raise RGBSegmentationError(
                "SKIN_UNVERIFIED", "照片中未识别到足够的可见皮肤", 422
            ) from None
        probabilities = helper_probability(rgb)
        ballots, candidates = [], []
        stop = Event()

        def run_density(density):
            client = BailianClient(key, before_send, source_sha, original, stop)
            reg = regions.build(rgb, feature, side, features.NAMES, n_skin=density)
            reg.tiles = regions.make_tiles(reg)
            codes = run_branch(client, rgb, feature, features.NAMES, reg)
            try:
                first, anchored, _, _ = anchored_votes(
                    client, rgb, reg, feature, features.NAMES, codes
                )
            except RuntimeError as exc:
                if str(exc) not in (
                    "Current source verdicts lack an anchor class",
                    "Source judgment did not produce two lesion/normal colour anchors",
                ):
                    raise
                first, _ = fuse.fuse(feature, features.NAMES, reg.seg, codes)
                anchored = first
            return first, anchored, _review_tags(client.triage)

        with ThreadPoolExecutor(max_workers=len(DENSITIES)) as workers:
            futures = [workers.submit(run_density, density) for density in DENSITIES]
            completed, _ = wait(futures, return_when=FIRST_EXCEPTION)
            error = next(
                (item.exception() for item in completed if item.exception()), None
            )
            if error is not None:
                stop.set()
                raise error
            for future in futures:
                first, anchored, tags = future.result()
                ballots.extend((first, anchored))
                candidates.append(tags)
        base, _ = legacy_vote(ballots, skin)
        selected = apply_fixed_helper(base, np.stack(ballots), probabilities)
        if compare_fusion:
            variants, smallspots = fusion_drafts(
                rgb,
                base,
                selected,
                probabilities,
                key,
                before_send,
                source_sha,
                original,
                stop,
            )
    output = masks_from_labels(selected, skin)
    if not output["skin"].any():
        raise RGBSegmentationError(
            "SKIN_UNVERIFIED", "照片中未识别到足够的可见皮肤", 422
        )
    from ml.vlm_labeling.review_packet import summarize_tag_candidates

    tags = summarize_tag_candidates(candidates)
    return output, {
        "source": "bailian_diary_preview",
        "model_id": consent.MODEL,
        "provider": consent.PROVIDER,
        "refiner": "public_resnet18_joint_v2",
        "weights_sha256": WEIGHTS_SHA256,
        "automatic_measurement": False,
        "confidence_calibrated": False,
        "ai_tags": {"review_state": "pending", **tags},
        **(
            {
                "fusion_preview": {
                    "version": "cross-branch-v1",
                    "smallspots": smallspots,
                },
                "fusion_lesions": variants,
            }
            if compare_fusion
            else {}
        ),
    }
