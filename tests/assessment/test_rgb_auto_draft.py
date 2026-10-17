"""Parsed-skin lesion draft: synthetic photos only (no user images in tests)."""

import numpy as np


def _photo(contrast=1.0, seed=0):
    h, w = 320, 256
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    light = 0.85 + 0.3 * xx / w  # strong left-to-right illumination gradient
    tan = np.array([186.0, 140.0, 108.0])
    pale = tan + contrast * (np.array([238.0, 214.0, 204.0]) - tan)
    img = tan[None, None, :] * light[..., None]
    patches = ((yy - 100) ** 2 + (xx - 80) ** 2 <= 36 ** 2) | (
        (yy - 220) ** 2 + (xx - 180) ** 2 <= 30 ** 2
    )
    img[patches] = (pale[None, :] * light[..., None])[patches]
    img += rng.normal(0, 2.0, img.shape)
    skin = np.zeros((h, w), bool)
    skin[20:300, 20:236] = True
    return np.clip(img, 0, 255).astype(np.uint8), skin, patches & skin


def test_draft_prefills_light_patches_despite_illumination_gradient():
    from web.backend.services.rgb_segmentation.lesion_draft import draft_lesion

    img, skin, truth = _photo()
    out = draft_lesion(img, skin, np.zeros_like(skin))
    lesion = out["lesion"]
    assert out["check"]["status"] == "draft"
    iou = (lesion & truth).sum() / (lesion | truth).sum()
    assert iou > 0.8
    assert not (lesion & ~skin).any()
    assert not (out["uncertain"] & lesion).any()
    # The thin review band never dominates the draft.
    assert out["uncertain"].sum() < 0.5 * lesion.sum()


def test_low_contrast_photo_only_offers_candidates():
    from web.backend.services.rgb_segmentation.lesion_draft import draft_lesion

    img, skin, _ = _photo(contrast=0.02)
    out = draft_lesion(img, skin, np.zeros_like(skin))
    assert out["check"]["status"] in ("low_contrast", "implausible_share")
    assert not out["lesion"].any()


def test_no_draft_region_is_never_auto_marked():
    from web.backend.services.rgb_segmentation.lesion_draft import draft_lesion

    img, skin, truth = _photo()
    lips = np.zeros_like(skin)
    lips[70:130, 50:110] = True
    out = draft_lesion(img, skin, lips)
    assert not (out["lesion"] & lips).any()


def test_infer_rgb_prefers_parsed_skin_and_keeps_measurement_manual(monkeypatch):
    from web.backend.services.rgb_segmentation import inference, skin_parsing

    img, skin, truth = _photo()
    monkeypatch.setattr(inference, "registered_model", lambda: None)
    monkeypatch.setattr(
        skin_parsing,
        "parse_skin",
        lambda rgb: {"skin": skin, "no_draft": np.zeros_like(skin), "faces": 0},
    )
    masks, meta = inference.infer_rgb(img)
    assert meta["source"] == "parsed_skin_draft"
    assert meta["automatic_measurement"] is False
    assert meta["draft_check"]["status"] == "draft"
    assert (masks["skin"] == skin).all()
    assert masks["lesion"].any() and not (masks["lesion"] & ~skin).any()
    assert not masks["excluded"].any()


def test_infer_rgb_falls_back_when_parser_sees_no_person(monkeypatch):
    from web.backend.services.rgb_segmentation import inference, skin_parsing

    img, _, _ = _photo()
    monkeypatch.setattr(inference, "registered_model", lambda: None)
    monkeypatch.setattr(skin_parsing, "parse_skin", lambda rgb: None)
    _, meta = inference.infer_rgb(img)
    assert meta["source"] == "interactive_rgb_reference"


def test_parser_refuses_unpinned_model_files(tmp_path, monkeypatch):
    from web.backend.services.rgb_segmentation import skin_parsing

    (tmp_path / skin_parsing.SEGMENTER[0]).write_bytes(b"not the pinned model")
    monkeypatch.setattr(skin_parsing, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(skin_parsing, "_models", {})
    img, _, _ = _photo()
    assert skin_parsing.parse_skin(img) is None
