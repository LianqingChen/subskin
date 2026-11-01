# Direct story creation and a calmer diary

## Scope

Refinement requested after the first story-discovery staging build. Keep the approved name 我的轮廓故事 and subtitle 把你的白斑轮廓变成一幅画.

## Experience

- Chat opens /assessment/story, a focused flow: choose body site and take/select a photo, inspect quality, confirm contour, generate art. It never lands on the general diary homepage.
- Reuse assessment storage and authorization. Explain that a photograph is saved privately to diary when the user confirms it; publication remains opt-in.
- Confirmation action explicitly says it will save and create art. Existing consent checks, failures, retries and fallback template remain in force.
- Diary homepage has one primary action to start a record, up to three recent records, and a quiet story link. Body selection and camera/gallery are disclosed after starting a record. Remove the full-height draggable panel and default 3D scene.
- Comparison creation remains available in the comparison section of My records; record-to-record comparison remains in the record list.
- Story history selection retains the creative intent. Existing records require explicit creation, with contour review when necessary.

## Implementation and validation

Frontend-only, reusable capture/review/story components, no API changes or additional automatic generation on general diary visits. Preserve all drafts and records. Run vue-tsc and build on the server; deploy staging only. Check entry routes, PWA, production version unchanged, and record UI verification limitations accurately.

## Responsive refinement requested after trial

The 1440px browser measurement showed a 184px mismatch between the navigation and body. Normal diary screens and the exam tab now share `.page`, a 56px toolbar and document scrolling. Desktop (>=1024px) uses an action column and a recent-record column; below that breakpoint content stays single-column. Photo capture and contour review use `.page-narrow` for both toolbar and body. Mobile tabs have visible 44px targets with text labels; decorative icons appear on larger screens. Keep one primary action per section; place optional creative action below the capture card. Verify overflow and alignment at 320/375/768/1024/1440/1920 plus landscape and theme variants. Real-browser evidence must be distinguished from untested Firefox/Safari/WeChat/Huawei devices.
