# Reviewed contour → creative sticker

The user approved the design in conversation: identify the reviewed white-patch overlay, peel the same contour off the source photo, reveal the creative pixels, and settle into the journal poster. The interaction is reversible through “查看来源”.

## Implementation

- Reuse `silhouette()` for the artwork and its original mask bounds. Preserve all holes and relative positions. Never generate approximate contours.
- The story preview starts with the annotated source photograph. A transparent sticker follows the exact source coordinates and moves into the same bounds used by the portrait poster renderer.
- Keep a source thumbnail visible below the preview. A corner handle supports pointer dragging; a labeled range supports scrubbing and keyboard input. Buttons reveal/reverse the motion.
- Reuse existing cloud/island/stars generation, fallback poster and protected image loading. Selection/revision changes reset the interaction. In-flight AI updates retain the reveal position.
- Loading failures show the existing creative poster plus a source retry action. They must not prevent downloading or sharing the poster.
- Respect reduced motion, dark mode, 44px controls and mobile scrolling. Cancel animation and discard stale asynchronous image loads on selection change/unmount.
- No new route, API, backend, database or sharing behavior. This updates the presentation of the existing contour-story feature.

## Verification and deployment

Type check; use synthetic masks with disjoint regions and holes to test alignment and reversible motion; check 375/768/1024/1440px, keyboard, touch, reduced motion and source failure. Record pending changes before staging build. Verify staging version/PWA/health and unchanged production assets. Production deployment requires the user's later explicit instruction.
