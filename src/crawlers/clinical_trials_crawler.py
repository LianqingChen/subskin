"""ClinicalTrials.gov v2 API crawler for vitiligo clinical trials."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime
from typing import Any

import requests

from src.models.trial import (
    ClinicalTrial,
    Intervention,
    InterventionType,
    Location,
    TrialPhase,
    TrialStatus,
)
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
DEFAULT_CACHE_TTL = 86400.0  # 24 hours
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0
BACKOFF_FACTOR = 2.0
DEFAULT_PAGE_SIZE = 20

JAK_KEYWORDS = [
    "jak inhibitor",
    "janus kinase",
    "ruxolitinib",
    "tofacitinib",
    "upadacitinib",
    "ritlecitinib",
    "povorcitinib",
    "baricitinib",
    "delgocitinib",
    "opzelura",
]

_STATUS_MAP: dict[str, TrialStatus] = {
    "RECRUITING": TrialStatus.RECRUITING,
    "ACTIVE_NOT_RECRUITING": TrialStatus.ACTIVE_NOT_RECRUITING,
    "COMPLETED": TrialStatus.COMPLETED,
    "TERMINATED": TrialStatus.TERMINATED,
    "SUSPENDED": TrialStatus.SUSPENDED,
    "WITHDRAWN": TrialStatus.WITHDRAWN,
    "NOT_YET_RECRUITING": TrialStatus.NOT_YET_RECRUITING,
    "ENROLLING_BY_INVITATION": TrialStatus.ENROLLING_BY_INVITATION,
}

_PHASE_MAP: dict[str, TrialPhase] = {
    "PHASE1": TrialPhase.PHASE1,
    "PHASE2": TrialPhase.PHASE2,
    "PHASE3": TrialPhase.PHASE3,
    "PHASE4": TrialPhase.PHASE4,
    "NA": TrialPhase.NOT_APPLICABLE,
    "EARLY_PHASE1": TrialPhase.EARLY_PHASE1,
}

_INTERVENTION_TYPE_MAP: dict[str, InterventionType] = {
    "DRUG": InterventionType.DRUG,
    "BIOLOGICAL": InterventionType.BIOLOGICAL,
    "DEVICE": InterventionType.DEVICE,
    "PROCEDURE": InterventionType.PROCEDURE,
    "BEHAVIORAL": InterventionType.BEHAVIORAL,
    "DIETARY_SUPPLEMENT": InterventionType.DIETARY_SUPPLEMENT,
    "RADIATION": InterventionType.RADIATION,
    "OTHER": InterventionType.OTHER,
}


class CrawlerError(Exception):
    pass


class APIError(CrawlerError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ClinicalTrialsCrawler:
    """Crawler for ClinicalTrials.gov v2 API.

    Args:
        cache: Cache instance for storing API responses.
        rate_limiter: Optional rate limiter (defaults to 1 req/s).
        cache_ttl: Cache TTL in seconds (defaults to 24 hours).
        session: Optional requests.Session for HTTP calls.
        base_url: API base URL (defaults to the official endpoint).
    """

    def __init__(
        self,
        cache: Cache,
        rate_limiter: RateLimiter | None = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
        session: requests.Session | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self._cache = cache
        self._rate_limiter = rate_limiter or RateLimiter(requests_per_second=1.0)
        self._cache_ttl = cache_ttl
        self._session = session or requests.Session()
        self._base_url = base_url
        self._session.headers.setdefault(
            "User-Agent",
            "SubSkin/1.0 (vitiligo research; +https://github.com/subskin)",
        )

    def _build_cache_key(self, params: dict[str, Any]) -> str:
        sorted_items = sorted(
            (k, str(v)) for k, v in params.items() if v is not None
        )
        raw = "&".join(f"{k}={v}" for k, v in sorted_items)
        return f"ctgov:{hashlib.sha256(raw.encode()).hexdigest()}"

    def _request_with_retry(
        self,
        params: dict[str, Any],
        max_retries: int = MAX_RETRIES,
        initial_backoff: float = INITIAL_BACKOFF,
    ) -> dict[str, Any]:
        """Make an API request with exponential backoff on 5xx/429/timeout errors.

        Raises:
            APIError: If all retries are exhausted or a non-retryable error occurs.
        """
        backoff = initial_backoff
        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                self._rate_limiter.acquire()
                response = self._session.get(
                    self._base_url, params=params, timeout=30
                )

                if response.status_code >= 500:
                    raise APIError(
                        f"Server error: HTTP {response.status_code}",
                        status_code=response.status_code,
                    )

                if response.status_code == 429:
                    raise APIError(
                        "Rate limited: HTTP 429",
                        status_code=429,
                    )

                if response.status_code >= 400:
                    raise APIError(
                        f"Client error: HTTP {response.status_code}",
                        status_code=response.status_code,
                    )

                return response.json()  # type: ignore[no-any-return]

            except (
                requests.ConnectionError,
                requests.Timeout,
            ) as exc:
                last_exception = exc
                logger.warning(
                    "Request failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
            except APIError as exc:
                last_exception = exc
                # Non-retryable: 4xx errors except 429
                if (
                    exc.status_code is not None
                    and exc.status_code < 500
                    and exc.status_code != 429
                ):
                    raise
                logger.warning(
                    "API error (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )

            if attempt < max_retries:
                logger.info("Retrying in %.1f seconds...", backoff)
                time.sleep(backoff)
                backoff *= BACKOFF_FACTOR

        raise APIError(
            f"All {max_retries + 1} attempts failed. Last error: {last_exception}"
        )

    def _fetch_page(
        self,
        query: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query.cond": query,
            "pageSize": page_size,
            "format": "json",
        }
        if page_token is not None:
            params["pageToken"] = page_token

        cache_key = self._build_cache_key(params)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for key %s", cache_key)
            return cached  # type: ignore[no-any-return]

        logger.debug("Cache miss for key %s, fetching from API", cache_key)
        data = self._request_with_retry(params)
        self._cache.set(cache_key, data, ttl=self._cache_ttl)
        return data

    @staticmethod
    def _parse_date(date_struct: dict[str, Any] | None) -> str | None:
        """Extract date from v2 API struct ``{"date": "YYYY-MM-DD", ...}``."""
        if date_struct is None:
            return None
        return date_struct.get("date")

    @staticmethod
    def _parse_phase(phases: list[str] | None) -> TrialPhase:
        if not phases:
            return TrialPhase.NOT_APPLICABLE

        phase_priority = [
            TrialPhase.PHASE4,
            TrialPhase.PHASE3,
            TrialPhase.PHASE2,
            TrialPhase.PHASE1,
            TrialPhase.EARLY_PHASE1,
            TrialPhase.NOT_APPLICABLE,
        ]

        mapped = [_PHASE_MAP.get(p, TrialPhase.NOT_APPLICABLE) for p in phases]

        for p in phase_priority:
            if p in mapped:
                return p

        return TrialPhase.NOT_APPLICABLE

    @staticmethod
    def _parse_status(status_str: str | None) -> TrialStatus:
        if status_str is None:
            return TrialStatus.UNKNOWN
        return _STATUS_MAP.get(status_str, TrialStatus.UNKNOWN)

    @staticmethod
    def _parse_interventions(
        interventions_data: list[dict[str, Any]] | None,
    ) -> list[Intervention]:
        if not interventions_data:
            return []

        result: list[Intervention] = []
        for item in interventions_data:
            name = item.get("name", "Unknown")
            type_str = item.get("type", "OTHER")
            intervention_type = _INTERVENTION_TYPE_MAP.get(
                type_str, InterventionType.OTHER
            )
            description = item.get("description")

            drug_class: str | None = None
            combined = f"{name} {description or ''}".lower()
            if any(kw in combined for kw in JAK_KEYWORDS):
                drug_class = "JAK inhibitor"

            result.append(
                Intervention(
                    name=name,
                    type=intervention_type,
                    description=description,
                    drug_class=drug_class,
                )
            )
        return result

    @staticmethod
    def _parse_locations(
        locations_data: list[dict[str, Any]] | None,
    ) -> list[Location]:
        if not locations_data:
            return []

        result: list[Location] = []
        for loc in locations_data:
            result.append(
                Location(
                    facility=loc.get("facility", "Unknown"),
                    city=loc.get("city"),
                    state=loc.get("state"),
                    country=loc.get("country", "Unknown"),
                    status=loc.get("status"),
                )
            )
        return result

    def _parse_study(self, study: dict[str, Any]) -> ClinicalTrial | None:
        try:
            protocol = study.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            conditions_module = protocol.get("conditionsModule", {})
            interventions_module = protocol.get("armsInterventionsModule", {})
            design_module = protocol.get("designModule", {})
            sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
            contacts_module = protocol.get("contactsLocationsModule", {})

            nct_id = id_module.get("nctId", "")
            if not nct_id:
                logger.warning("Skipping study with missing NCT ID")
                return None

            title = id_module.get("briefTitle", "Untitled")

            conditions = conditions_module.get("conditions", [])
            condition = "; ".join(conditions) if conditions else "Vitiligo"

            interventions = self._parse_interventions(
                interventions_module.get("interventions", [])
            )
            phase = self._parse_phase(design_module.get("phases", []))
            status = self._parse_status(status_module.get("overallStatus"))

            enrollment_info = design_module.get("enrollmentInfo", {})
            enrollment = enrollment_info.get("count")

            lead_sponsor = sponsor_module.get("leadSponsor", {})
            sponsor = lead_sponsor.get("name", "Unknown")

            collaborators_data = sponsor_module.get("collaborators", [])
            collaborators = [
                c.get("name", "") for c in collaborators_data if c.get("name")
            ]

            start_date = self._parse_date(
                status_module.get("startDateStruct")
            )
            completion_date = self._parse_date(
                status_module.get("completionDateStruct")
            )
            last_update_date = self._parse_date(
                status_module.get("lastUpdatePostDateStruct")
            )

            locations = self._parse_locations(
                contacts_module.get("locations", [])
            )

            url = f"https://clinicaltrials.gov/ct2/show/{nct_id}"
            study_type = design_module.get("studyType")

            return ClinicalTrial(
                nct_id=nct_id,
                title=title,
                condition=condition,
                interventions=interventions,
                phase=phase,
                status=status,
                enrollment=enrollment,
                sponsor=sponsor,
                collaborators=collaborators,
                start_date=start_date,
                completion_date=completion_date,
                last_update_date=last_update_date,
                locations=locations,
                url=url,
                study_type=study_type,
                crawled_at=datetime.now(),
            )
        except Exception:
            nct = (
                study.get("protocolSection", {})
                .get("identificationModule", {})
                .get("nctId", "unknown")
            )
            logger.exception("Failed to parse study: %s", nct)
            return None

    def search(
        self,
        query: str,
        max_results: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[ClinicalTrial]:
        """Search for clinical trials matching *query*, paginating automatically.

        Raises:
            APIError: If an unrecoverable API error occurs.
        """
        trials: list[ClinicalTrial] = []
        page_token: str | None = None

        while True:
            data = self._fetch_page(
                query=query,
                page_size=page_size,
                page_token=page_token,
            )

            studies = data.get("studies", [])
            for study in studies:
                trial = self._parse_study(study)
                if trial is not None:
                    trials.append(trial)

                if max_results is not None and len(trials) >= max_results:
                    return trials[:max_results]

            page_token = data.get("nextPageToken")
            if not page_token or not studies:
                break

        return trials

    def search_vitiligo_trials(
        self,
        max_results: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[ClinicalTrial]:
        return self.search(
            query="vitiligo",
            max_results=max_results,
            page_size=page_size,
        )

    def search_jak_inhibitor_trials(
        self,
        max_results: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[ClinicalTrial]:
        all_trials = self.search(
            query="vitiligo AND JAK inhibitor",
            max_results=None,
            page_size=page_size,
        )

        jak_trials = [t for t in all_trials if t.is_jak_inhibitor_trial()]

        if max_results is not None:
            return jak_trials[:max_results]
        return jak_trials

    def get_trial_by_nct_id(self, nct_id: str) -> ClinicalTrial | None:
        cache_key = f"ctgov:nct:{nct_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return self._parse_study(cached)

        params: dict[str, Any] = {
            "query.id": nct_id,
            "pageSize": 1,
            "format": "json",
        }

        self._rate_limiter.acquire()
        data = self._request_with_retry(params)

        studies = data.get("studies", [])
        if not studies:
            return None

        raw_study = studies[0]
        self._cache.set(cache_key, raw_study, ttl=self._cache_ttl)
        return self._parse_study(raw_study)
