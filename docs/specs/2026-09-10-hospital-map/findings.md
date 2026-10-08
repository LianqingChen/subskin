# Findings
- Vue 3 + TypeScript + Tailwind + ECharts already installed.
- Shared navigation source: web/shared/site-modules.json; AppHeader and BottomNav use explicit NAV_PATHS.
- Staging source contains pending September 10 changes; latest production timestamp 1788097546229.
- Backend single shared instance; avoid changing behavior for a preview-only launch.
- Official source pages verified: Huashan /xueke/detail/12.html, PUMC Dermatology /list/92.html, West China /department_pfxbk.html, XJTU First /lmby/ksdh_bf/nkxt/pfk.htm, Guangzhou 12 /zk/mz/pf/, Yueyang /Html/News/Articles/16097.html, PUMCH dermatology physician directory.
- GeoJSON downloaded successfully from Alibaba DataV GeoAtlas https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json (34 named regions plus maritime geometry). Keep original geometry and attribution; bundle locally for offline use.
- Explicit server SSH identity works. Existing git tree is extensively dirty; preserve unrelated work.
- AI module table loads JSON at backend startup, so new navigation source will take effect with a future authorized backend restart. No shared restart for this preview.
