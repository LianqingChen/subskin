# Findings
- Home comparison currently bypasses site selection; gallery multi-select supports 4 files and queues before checking site.
- QuickPhotoComparePage repeats body-site selection and has four-file capacity; useQuickPhotoCompare lacks count/site validation at submission.
- Saved-record comparison accepts 2–4 ids, and stale items survive a failed load. Active records UI already selects two.
- The record stack adds 16px top margin after the 44px panel toggle and 16px bottom padding. Body model starts at the mobile scene top.

- Scoped CSS marks only the final selector element; the plain .panel-toggle + section rule loses to Tailwind space-y. Prefixing the record-stack selector fixes specificity without important declarations.
- Comparison upload requests send exactly two saved images in chronological order and carry the previously selected body_site. Records mode queries history with that body_site and sends exactly two vasi_ids.
