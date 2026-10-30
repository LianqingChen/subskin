# Pixel-level vitiligo labeling

Training-grade five-class masks for the admin labeling workspace, and the loop that makes the
AI first draft better with every approved human gold.

**Normative docs (read these, not this README):**

- Skill: [`.agents/skills/vitiligo-pixel-labeling/SKILL.md`](../../.agents/skills/vitiligo-pixel-labeling/SKILL.md)
- Lessons: [`.agents/skills/vitiligo-pixel-labeling/LESSONS.md`](../../.agents/skills/vitiligo-pixel-labeling/LESSONS.md)

**Entry point:** `python -m ml.pixel_labeling <draft|compose|view|grid|prep|gallery|apply|review|train|bench> …`

| Module | Role |
|--------|------|
| `gold.py` | Approved golds, read from the DB |
| `features.py` / `pixel_model.py` | General pixel model `pixel-gb-v2` (leave-one-group-out card in `models/pixel_gb_v2.json`) |
| `face_gb.py` | Legacy face-plaque model calibrated on 180 |
| `core.py` | Skin masks, whiteness scores, candidate composition |
| `ops.py` | Named post-ops used by decision files (each tied to a lesson) |
| `metrics.py` / `bench.py` | Gold metrics; regression bench (`bench/latest.md`, `bench/history.jsonl`) |
| `review.py` | AI draft vs human revision, numbered disagreement regions |

Decision files in `decisions/` replay through `compose` (base + ops + polygons). Human-vs-AI review
JSONs go in `reviews/`. Working images and feature caches live under `data/labeling_work/` (gitignored).
