"""Model-agnostic VLM labeling protocol (Set-of-Mark + per-image pixel fusion).

Any OpenAI-compatible vision model follows the same protocol; the rubric it reads lives in
``.agents/skills/vlm-vitiligo-labeling/rubric.md`` so every lesson learned from a gold label
improves every model.  Workflow + rules: ``.agents/skills/vlm-vitiligo-labeling/SKILL.md``.
"""
