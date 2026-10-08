# Findings
- compare_registered_masks rejects position IDs and date_confirmed before any feature matching. Uploaded PostImage references have no observation metadata or masks, so the current report pipeline cannot quantify them.
- compare_pair now uses CV only; its former VLM helper is excluded and its legacy prompt asks for inferred numeric changes. A new visual-only description path must not reuse that numeric prompt.
- Consent queries are available through services.consent.has_active_consent for ai_data and medical_photo. New third-party image analysis must check both.
- Report generation runs in an existing background thread and can accept an optional alignment payload without schema migration. Manual evidence must not overwrite shared automatic pair caches.
- The authenticated GVFS SSH control master at /run/user/1000/gvfsd-sftp/%C provides an authorized execution channel without reading credentials. Backend changes still need explicit shared-backend approval.

- Archived report reanalysis reads fresh authorized report references/URLs, matches the currently displayed pair, and uses original image/record IDs. It does not create another upload.
- Live model smoke used only generated diagrams and returned a compliant descriptive summary. Consent was mocked only in this isolated, synthetic-only process; production consent logic was not changed.
