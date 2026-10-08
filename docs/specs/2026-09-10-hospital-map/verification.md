# 就医地图首版验收记录

Staging buildTime: **1789003112112** (2026-09-10)
Production remains **1788097546229**. No backend restart or database write.

## ✅ 通过项
- `npm run type-check` passes; `npm run build` deploys successfully.
- `node scripts/verification/hospital-directory.cjs`: 9 meaningful pure-logic checks pass, covering official-source/coordinate completeness, province/city filtering and empty state, combined search, comparison cap/removal, bookmarks, synchronous account isolation, storage failures, corrupted-storage preservation, review draft owner isolation.
- Public `/hospitals` HTTP 200; returned HTML equals deployed index byte-for-byte; live entry JS contains `/hospitals` and lazy-loaded HospitalMapPage.
- Public version.json / manifest / sw.js equal deployed files byte-for-byte.
- 7 source-backed hospital records, 6 provinces/cities. No fabricated doctors, ratings, review counts or treatment outcomes.
- Composables own feature state; page does not call API; components separated by map/card/detail/dialog/form/compare.
- Sharing is not implemented or implied: all save actions labeled local drafts; records partitioned by account, no API transmission.
- Existing source changes and production deploy history preserved; existing user data untouched.

## 📋 Schema.org 检查
- CollectionPage JSON-LD inserted on mount, removed on unmount. No fabricated AggregateRating or Review schema.

## 📱 PWA/响应式检查
- Staging manifest name SubSkin [STAGING], theme #1e293b, 9 icons; production manifest name and theme unchanged.
- SW exists and exceeds 3 KB; index references match existing assets; injectManifest successfully precaches new assets (no standalone workbox file required with bundled custom SW).
- Native dialog uses showModal for focus trap, Escape closes and restores prior focus; max height uses dvh and safe area padding.
- Mobile fourth BottomNav entry, desktop AppHeader entry, collapsible 208px sidebar, mobile map/list mode, labels and 44px controls implemented.
- Browser tools createBrowserTab (IAB and Chrome) and getTab time out; inventory can list tabs only. **375/768/1024/1440 visual and real click verification remains unverified.** No claim of browser acceptance.

## 🟡 建议优化 / 下一阶段
- Precise branch geocoding/navigation; expand directory through verified official sources.
- Authenticated public reviews, user tags, reports/moderation, immutable consent audit, withdrawal and anti-advertising measures.
- Longitudinal follow-up, time/cost/context comparisons without treating self-reported outcomes as causal evidence.
- AI navigation metadata updated in shared source; running backend reads at startup and will load it on a future explicitly authorized restart. No restart for this preview.

## Resolved issue
Existing shared city dataset omitted Nanjing, Chengdu, Xian, Guangzhou. First regression caught missing coordinates. Hospital module now supplies explicit city centers and merges them into its own city filter, leaving unrelated geographic behavior unchanged.
