# Image Labeling Module — Full Overhaul Design Spec

**Date:** 2026-06-11
**Status:** Approved → Implementation
**Approach:** C — Balanced Full Overhaul (3 milestones)

---

## Goals

1. **Smarter painting tools** — flood fill, lasso, polygon, grabcut (M3)
2. **Multi-lesion management** — label multiple lesions per image
3. **Active learning loop** — VASI identifies uncertain cases → admin labels → retrain → metrics improve
4. **Batch workflow** — keyboard-driven quick-classify for obvious cases
5. **Training dataset dashboard** — manage splits, view quality, trigger export/retrain

---

## Architecture

```
web/admin/src/
├── views/
│   ├── ImageLabeling.vue          ← Refactor: list + stats (simplified)
│   ├── LabelingWorkspace.vue      ← NEW: dedicated workspace page (route /labeling/:id)
│   ├── TrainingDashboard.vue      ← NEW: dataset & model metrics
│   └── BatchLabeling.vue          ← NEW: quick-classify mode
│
├── components/labeling/
│   ├── LabelingEditor.vue         ← Refactor: thinner orchestration
│   ├── MaskEditorAdmin.vue        ← Refactor: modular tool host
│   ├── tools/                     ← NEW: pluggable canvas tools
│   │   ├── BaseTool.ts            ← tool interface contract
│   │   ├── BrushTool.ts           ← existing brush logic extracted
│   │   ├── FloodFillTool.ts       ← NEW: flood fill with tolerance
│   │   ├── LassoTool.ts           ← NEW: freehand lasso selection
│   │   ├── PolygonTool.ts         ← NEW: polygon vertex selection
│   │   ├── GrabCutTool.ts         ← NEW: interactive segmentation (M3)
│   │   └── EraserTool.ts          ← existing eraser extracted
│   ├── LesionPanel.vue            ← NEW: multi-lesion list manager
│   ├── LesionCard.vue             ← NEW: single lesion detail card
│   ├── QuickClassify.vue          ← NEW: keyboard-driven batch widget
│   ├── TrainingEligibility.vue    ← NEW: quality gate indicator
│   └── ShortcutPanel.vue          ← NEW: visible keyboard reference
│
├── composables/                   ← NEW: shared state logic
│   ├── useCanvasTools.ts          ← tool switching, cursor, state
│   ├── useLesionManager.ts        ← multi-lesion CRUD
│   ├── useLabelHistory.ts         ← undo/redo (extracted from canvas)
│   └── useTrainingPipeline.ts     ← sync status, eligibility
│
├── stores/labeling.ts             ← Extend: active learning queue
└── api/labeling.ts                ← Extend: new endpoints
```

### Key Decisions

1. **Tool plugin architecture** — each tool implements `BaseTool` interface. MaskEditorAdmin is a canvas host that delegates to the active tool.
2. **Workspace page** — dedicated route `/#/labeling/:id` gives browser history, deep-linking, more space. Modal stays as quick-edit option.
3. **Multi-lesion first-class** — `LesionPanel` manages a list of `LesionCard` instances. Data model already supports this (`ImageLabelAnnotation.region_index`).
4. **Active learning queue** — backend-driven priority list. Low-confidence images bubble to top. After N new labels, model retrains.

---

## Canvas Tool System

### BaseTool Interface

```typescript
interface ToolContext {
  skinCanvas: HTMLCanvasElement
  lesionCanvas: HTMLCanvasElement
  overlayCanvas: HTMLCanvasElement
  naturalSize: { width: number; height: number }
  brushSize: number
  transform: { scale: number; offsetX: number; offsetY: number }
  clientToImage: (x: number, y: number) => [number, number] | null
}

interface BaseTool {
  name: string
  icon: string          // remixicon class
  shortcut: string      // single key
  cursor: string        // CSS cursor
  onActivate(ctx: ToolContext): void
  onDeactivate(): void
  onPointerDown(pos: [number, number], ctx: ToolContext): void
  onPointerMove(pos: [number, number], ctx: ToolContext): void
  onPointerUp(ctx: ToolContext): void
  onKeyDown(key: string, ctx: ToolContext): void
}
```

### Tools

| Tool | Shortcut | Description |
|------|----------|-------------|
| Skin Brush | `B` | Paint skin region (blue) — existing, extracted |
| Lesion Brush | `L` | Paint lesion area (pink) — existing, extracted |
| **Flood Fill** | `G` | Click to fill connected region, tolerance 0-64. Operates on original image pixels. |
| **Lasso** | `S` | Freehand draw selection boundary → fill as lesion or skin |
| **Polygon** | `P` | Click vertices → double-click/Enter to close → fill |
| Eraser | `E` | Erase from either layer — existing, extracted |
| **GrabCut** | `C` | Draw fg/bg strokes → OpenCV-style segmentation (M3) |

### Tool State Machine

```
[Idle] → keypress → [Tool Activated] → pointer events → [Drawing] → pointerup → [Idle]
                                                                     → snapshot to undo history
```

---

## Active Learning Pipeline

### Flow

```
1. User uploads image → VASI assessment runs
2. Model produces: confidence score, mask, classification
3. confidence < threshold (configurable, default 0.7)?
   → YES: enters admin priority queue (sorted by 1-confidence = uncertainty)
   → NO:  auto-accepted, goes to training pool
4. Admin labels from queue → training_eligible=true
5. When new_labeled_count >= min_samples (default 20):
   → auto-sync to VasiTrainingSample table
   → trigger RL optimizer retrain
   → update VasiModelVersion with new metrics
6. Dashboard shows: precision/recall trend, queue depth, samples/week
```

### Priority Queue Sorting

```
priority_score = (1 - ai_confidence) * 0.6  // model uncertainty
               + age_days * 0.1              // slight boost for old items
               + has_user_correction * 0.3   // user disagreed with AI
```

### Backend Service

`web/backend/services/labeling_queue.py`:
- `compute_priority(label: ImageLabel) -> float`
- `get_queue(limit: int) -> list[ImageLabel]`
- `sync_to_training_samples() -> int` (returns count synced)
- `check_retrain_needed() -> bool`

---

## Database Changes

All additive (nullable columns, new tables). No destructive changes.

### image_labels — new columns

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `priority_score` | Float | NULL | Active learning priority |
| `active_learning_round` | Integer | NULL | Which round surfaced this |
| `last_model_version` | String | NULL | Model version when labeled |
| `labeling_duration_ms` | Integer | NULL | How long admin spent labeling |

### image_label_annotations — new columns

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `tool_used` | String | NULL | Which tool created this annotation |
| `edit_duration_ms` | Integer | NULL | Time spent on this lesion |

### New table: labeling_work_sessions

| Column | Type | Purpose |
|--------|------|---------|
| `id` | Integer PK | |
| `admin_user_id` | Integer FK | |
| `started_at` | DateTime | |
| `ended_at` | DateTime | nullable |
| `labels_completed` | Integer | default 0 |
| `labels_skipped` | Integer | default 0 |
| `total_edit_ms` | Integer | default 0 |

---

## API Endpoints

### New

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/vasi/admin/image-labels/queue` | Active learning priority queue (params: limit, min_confidence) |
| `GET` | `/vasi/admin/training/dashboard` | Dataset stats, model metrics, queue depth |
| `POST` | `/vasi/admin/training/export` | Export training-ready dataset (params: format, split) |
| `POST` | `/vasi/admin/training/sync-samples` | Manually sync labeled data to VasiTrainingSample |
| `POST` | `/vasi/admin/training/retrain` | Trigger VASI RL optimizer retrain |
| `GET` | `/vasi/admin/labeling/sessions` | Admin productivity metrics |
| `POST` | `/vasi/admin/labeling/sessions` | Start/end work session |

### Extended

| Method | Path | Change |
|--------|------|--------|
| `POST` | `/vasi/admin/image-labels/{id}/label` | Accept `lesions[]` array (multi-lesion), `tool_used`, `edit_duration_ms` |
| `GET` | `/vasi/admin/image-labels` | Add `sort_by=priority`, `active_learning_round` filter |

---

## Frontend Routes

| Route | Component | Purpose |
|-------|-----------|---------|
| `/#/image-labeling` | ImageLabeling.vue | List + stats (existing, enhanced) |
| `/#/image-labeling/:id` | LabelingWorkspace.vue | Full workspace for single image |
| `/#/image-labeling/batch` | BatchLabeling.vue | Quick-classify queue mode |
| `/#/training` | TrainingDashboard.vue | Dataset & model metrics |

---

## Milestone Plan

### M1: Core Tools + Multi-Lesion (3-4 days)

- Extract tool interface, refactor MaskEditorAdmin
- Implement FloodFillTool, LassoTool, PolygonTool
- Build LesionPanel + LesionCard
- Add ShortcutPanel
- Extend label API for multi-lesion

### M2: Active Learning + Batch (3-4 days)

- Backend: labeling_queue.py service
- Backend: priority scoring, queue endpoint
- Frontend: BatchLabeling view with QuickClassify
- Frontend: priority queue in ImageLabeling list
- TrainingEligibility indicator component

### M3: Training Pipeline + Metrics (2-3 days)

- TrainingDashboard view
- Sync-to-samples pipeline
- Export endpoint (COCO-format masks)
- Model metrics display (from VasiModelVersion)
- Work session tracking
- GrabCutTool (time-permitting)

---

## Error Handling

- Canvas tools: if image not loaded, tools show "waiting for image" state
- Flood fill: timeout after 3s for very large images (>20MP), fall back to "region too large" message
- API failures: toast with retry, queue position preserved
- Mask data too large (>5MB base64): auto-compress with canvas scaling before submit
- Active learning: if model not available, queue falls back to FIFO by date

## Testing Strategy

- Unit: each tool's core algorithm (flood fill, lasso polygon, polygon fill)
- Unit: priority score computation
- Integration: multi-lesion submit → retrieve → verify
- Integration: queue ordering with mock confidence scores
- E2E: full labeling flow (open image → use 3 tools → save → verify in list)
- Snapshot: canvas state after each tool operation

## Privacy & Security

- All existing privacy rules apply (AGENTS.md L3/L4 data handling)
- Work session tracking is admin-internal only — no user PII logged
- Training exports strip original_user_id, image_url (keep only hash + mask)
- Admin productivity metrics visible only to other admins

---

## References

- Existing: `MaskEditorAdmin.vue` (906 lines) — canvas host to refactor
- Existing: `LabelingEditor.vue` (718 lines) — orchestration to slim down
- Existing: `image_label.py` (1896 lines) — API to extend
- Existing: `vasi_rl_optimizer.py` — RL training to integrate with
- Existing: `VasiTrainingSample` model — target for sync pipeline
- Industry refs: CVAT, LabelMe, VGG Image Annotator, Supervisely
