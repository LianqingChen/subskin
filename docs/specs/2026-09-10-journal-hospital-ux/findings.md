# Findings

## Confirmed from source
- HospitalQuickReviewCta renders its picker with `open && !selected`; the selected-hospital “换一家” button cannot display it.
- Quick CTA emits pick to HospitalReviewPage.pick, which scrolls to reviewSection, disrupting the write flow.
- autoOpen is watched as a one-way boolean; page never resets quickPickerOpen after choosing, so subsequent true assignments cannot reopen it reliably.
- AssessmentVisualHome uses an absolute body scene with an overlapping scroll panel at every viewport width; desktop cannot use the extra width for side-by-side tasks.
- AssessmentCapture disables analysis for missing view/date/quality but provides no consolidated next-required-action hint.
- AssessmentRecords silently drops a selected record when a third is selected using slice(-1), and no selection feedback exists until exactly two are selected.
- HospitalPicker reports “还没有收录这家医院” for every empty filter combination, even when onlyMarked/onlyReviewed or service filters are responsible.
- Hospitals search follows three stacked geographic inputs on mobile; multiple equally strong writing/create actions compete with exploration.
- Key text frequently uses text-xs or text-[11px]; hospital top action “看避坑汇总” overstates a section that shows ordinary hospital reviews.

## Evidence limits
Browser in-app navigation timed out. Existing Chrome hospital tab belongs to another session and cannot be selected. No current screenshots or authenticated flow verification yet. Prior deployment logs are historical context only.

- Composer required doctorName/treatmentName are hidden under showMore. Typing 20 characters auto-expands optional fields via watcher. HospitalCard shows 已有评分 when reviews exist but rating is absent.
