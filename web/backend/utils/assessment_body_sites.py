"""Shared, non-diagnostic body-site labels for assessment protocols.

Derived from ``web/shared/body-sites.json``; stored labels must never change
because existing assessments persist them.
"""

from web.backend.utils.body_sites import site_labels

BODY_SITE_LABELS = site_labels()
