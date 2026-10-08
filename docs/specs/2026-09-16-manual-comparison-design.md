# Same-site comparison with manual alignment

## User objective
Allow comparison without requiring the same stored observation-position ID. Add drag, rotation and uniform scale adjustment for a pair, and analyze the adjusted pair. The normal flow remains automatic first; manual adjustment is available before analysis.

## Interaction
- Keep 两次记录 before 两张照片 and all primary start actions above content.
- Both input paths offer an automatic/manual alignment choice once two images are available.
- Manual view fixes the earlier image and overlays the later one. Support pointer dragging, rotation, scale and opacity controls plus reset. Touch gestures must not trigger page navigation. Keyboard controls and 44px buttons remain available.
- Starting in manual mode confirms the displayed transform and analyzes the same pair. Changing either source resets the transform.
- Keep original images unchanged. Store transform/provenance only on the resulting report, never overwrite original masks, photos or an automatic pair cache.

## Backend behavior
- Remove matching observation ID and date-confirmed booleans as unconditional image-comparison gates. Same owner/site, image availability, reviewed masks, compatible measurement methods, image alignment and common visible area still determine numeric eligibility.
- For valid reviewed masks, compute differences from the verified shared pixel coordinate system; manual transforms require an independent feature-residual check before numeric measurement.
- Without valid masks/registration, still provide a visual report. Optional AI observations use the existing vision provider only with active ai_data and medical_photo consent. No estimated percentages or disease progression labels from unvalidated images.
- Manual rotation is in-plane, scaling uniform. No nonuniform distortion, perspective warp or arbitrary lesion reshaping.
- Reject nonfinite/out-of-range transforms, wrong reference IDs, inaccessible/mixed-site sources and insufficient overlap. Exactly two photos/records for manual requests.
- Exact duplicate content retains duplicate semantics; it is not a temporal observation.
- Version the gate-policy fingerprint so prior not-comparable caches do not retain the old position-ID restriction.

## Coordinate contract
`manual-similarity-v1`: moving image B is initially fitted inside reference A without cropping. Scale multiplies that fit; angle rotates around B's center; translation is expressed as fractions of A width/height. Defaults scale=1, rotation=0, x=y=0. Backend EXIF-normalizes both images and converts this contract to its prepared image coordinates. Reference/moving IDs bind the transform to the intended pair.

## Deployment
Frontend may be staged for interaction review with a capability check. Older backends must never silently discard an alignment request; manual analysis stays unavailable until capability exists. Prepare backend changes in an isolated candidate directory with tests and baseline hashes. Do not edit/restart the shared backend until explicit user confirmation, as required by AGENTS.md.

## Acceptance
Synthetic transforms and pixel/mask consistency, invalid transforms, overlap and ownership validation, no-metadata automatic pair, manual numeric and visual-only paths, consent/no-consent/model failure, cache separation, pointer/keyboard/responsive UI, existing auto flows and staging PWA. No real user photo or third-party AI call in tests.
