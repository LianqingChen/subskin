"""Tests for ClinicalTrials.gov v2 API crawler."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.crawlers.clinical_trials_crawler import (
    APIError,
    ClinicalTrialsCrawler,
    CrawlerError,
)
from src.models.trial import (
    InterventionType,
    TrialPhase,
    TrialStatus,
)
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter


def _make_study(
    nct_id: str = "NCT12345678",
    title: str = "A Study of Ruxolitinib for Vitiligo",
    conditions: list[str] | None = None,
    interventions: list[dict[str, Any]] | None = None,
    phases: list[str] | None = None,
    overall_status: str = "RECRUITING",
    enrollment_count: int | None = 100,
    sponsor_name: str = "Incyte Corporation",
    start_date: str | None = "2025-01",
    completion_date: str | None = "2027-06",
    locations: list[dict[str, Any]] | None = None,
    study_type: str = "INTERVENTIONAL",
) -> dict[str, Any]:
    if conditions is None:
        conditions = ["Vitiligo"]
    if interventions is None:
        interventions = [
            {
                "type": "DRUG",
                "name": "Ruxolitinib cream",
                "description": "A JAK inhibitor applied topically",
            }
        ]
    if phases is None:
        phases = ["PHASE3"]
    if locations is None:
        locations = [
            {
                "facility": "Mayo Clinic",
                "city": "Rochester",
                "state": "Minnesota",
                "country": "United States",
                "status": "RECRUITING",
            }
        ]

    study: dict[str, Any] = {
        "protocolSection": {
            "identificationModule": {
                "nctId": nct_id,
                "briefTitle": title,
            },
            "statusModule": {
                "overallStatus": overall_status,
                "startDateStruct": {"date": start_date} if start_date else None,
                "completionDateStruct": (
                    {"date": completion_date} if completion_date else None
                ),
                "lastUpdatePostDateStruct": {"date": "2026-03-01"},
            },
            "conditionsModule": {"conditions": conditions},
            "armsInterventionsModule": {"interventions": interventions},
            "designModule": {
                "phases": phases,
                "studyType": study_type,
                "enrollmentInfo": {"count": enrollment_count},
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": sponsor_name},
                "collaborators": [{"name": "NIH"}],
            },
            "contactsLocationsModule": {"locations": locations},
        }
    }
    return study


def _make_api_response(
    studies: list[dict[str, Any]] | None = None,
    next_page_token: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {"studies": studies or []}
    if next_page_token is not None:
        response["nextPageToken"] = next_page_token
    return response


def _mock_response(
    json_data: dict[str, Any], status_code: int = 200
) -> MagicMock:
    mock = MagicMock(spec=requests.Response)
    mock.status_code = status_code
    mock.json.return_value = json_data
    return mock


@pytest.fixture
def cache() -> Cache:
    return Cache()


@pytest.fixture
def rate_limiter() -> RateLimiter:
    return RateLimiter(requests_per_second=1000.0)


@pytest.fixture
def crawler(cache: Cache, rate_limiter: RateLimiter) -> ClinicalTrialsCrawler:
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    return ClinicalTrialsCrawler(
        cache=cache,
        rate_limiter=rate_limiter,
        session=session,
    )


class TestSearchBasic:
    def test_search_returns_trials(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study()
        api_data = _make_api_response(studies=[study])
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        trials = crawler.search("vitiligo", max_results=10)

        assert len(trials) == 1
        trial = trials[0]
        assert trial.nct_id == "NCT12345678"
        assert trial.title == "A Study of Ruxolitinib for Vitiligo"
        assert trial.status == TrialStatus.RECRUITING
        assert trial.phase == TrialPhase.PHASE3
        assert trial.sponsor == "Incyte Corporation"
        assert trial.enrollment == 100
        assert trial.start_date == "2025-01"
        assert trial.completion_date == "2027-06"
        assert trial.study_type == "INTERVENTIONAL"
        assert "NCT12345678" in trial.url
        assert isinstance(trial.crawled_at, datetime)

    def test_search_empty_results(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        api_data = _make_api_response(studies=[])
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        trials = crawler.search("nonexistent_condition")

        assert trials == []

    def test_search_max_results_limits_output(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        studies = [
            _make_study(nct_id=f"NCT{10000000 + i}") for i in range(5)
        ]
        api_data = _make_api_response(studies=studies)
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        trials = crawler.search("vitiligo", max_results=3)

        assert len(trials) == 3


class TestPagination:
    def test_pagination_follows_next_page_token(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        page1_study = _make_study(nct_id="NCT10000001")
        page2_study = _make_study(nct_id="NCT10000002")

        page1 = _make_api_response(
            studies=[page1_study], next_page_token="token_page2"
        )
        page2 = _make_api_response(studies=[page2_study])

        crawler._session.get.side_effect = [  # type: ignore[union-attr]
            _mock_response(page1),
            _mock_response(page2),
        ]

        trials = crawler.search("vitiligo")

        assert len(trials) == 2
        assert trials[0].nct_id == "NCT10000001"
        assert trials[1].nct_id == "NCT10000002"
        assert crawler._session.get.call_count == 2  # type: ignore[union-attr]

    def test_pagination_stops_at_max_results(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        page1_studies = [
            _make_study(nct_id=f"NCT{10000000 + i}") for i in range(3)
        ]
        page1 = _make_api_response(
            studies=page1_studies, next_page_token="more"
        )

        crawler._session.get.return_value = _mock_response(page1)  # type: ignore[union-attr]

        trials = crawler.search("vitiligo", max_results=2)

        assert len(trials) == 2
        assert crawler._session.get.call_count == 1  # type: ignore[union-attr]


class TestCaching:
    def test_cached_response_avoids_api_call(
        self, crawler: ClinicalTrialsCrawler, cache: Cache
    ) -> None:
        study = _make_study()
        api_data = _make_api_response(studies=[study])
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        trials_first = crawler.search("vitiligo")
        trials_second = crawler.search("vitiligo")

        assert len(trials_first) == 1
        assert len(trials_second) == 1
        assert crawler._session.get.call_count == 1  # type: ignore[union-attr]


class TestRetryLogic:
    def test_retries_on_server_error(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study()
        success_data = _make_api_response(studies=[study])

        crawler._session.get.side_effect = [  # type: ignore[union-attr]
            _mock_response({}, status_code=500),
            _mock_response(success_data),
        ]

        with patch("src.crawlers.clinical_trials_crawler.time.sleep"):
            trials = crawler.search("vitiligo")

        assert len(trials) == 1

    def test_retries_on_timeout(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study()
        success_data = _make_api_response(studies=[study])

        crawler._session.get.side_effect = [  # type: ignore[union-attr]
            requests.Timeout("timed out"),
            _mock_response(success_data),
        ]

        with patch("src.crawlers.clinical_trials_crawler.time.sleep"):
            trials = crawler.search("vitiligo")

        assert len(trials) == 1

    def test_retries_on_connection_error(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study()
        success_data = _make_api_response(studies=[study])

        crawler._session.get.side_effect = [  # type: ignore[union-attr]
            requests.ConnectionError("connection refused"),
            _mock_response(success_data),
        ]

        with patch("src.crawlers.clinical_trials_crawler.time.sleep"):
            trials = crawler.search("vitiligo")

        assert len(trials) == 1

    def test_raises_after_max_retries_exhausted(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        crawler._session.get.return_value = _mock_response(  # type: ignore[union-attr]
            {}, status_code=500
        )

        with (
            patch("src.crawlers.clinical_trials_crawler.time.sleep"),
            pytest.raises(APIError, match="All .* attempts failed"),
        ):
            crawler.search("vitiligo")

    def test_does_not_retry_on_client_error(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        crawler._session.get.return_value = _mock_response(  # type: ignore[union-attr]
            {}, status_code=404
        )

        with pytest.raises(APIError, match="Client error"):
            crawler.search("vitiligo")

        assert crawler._session.get.call_count == 1  # type: ignore[union-attr]

    def test_retries_on_rate_limit_429(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study()
        success_data = _make_api_response(studies=[study])

        crawler._session.get.side_effect = [  # type: ignore[union-attr]
            _mock_response({}, status_code=429),
            _mock_response(success_data),
        ]

        with patch("src.crawlers.clinical_trials_crawler.time.sleep"):
            trials = crawler.search("vitiligo")

        assert len(trials) == 1


class TestParsing:
    def test_parse_interventions_with_jak_detection(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(
            interventions=[
                {
                    "type": "DRUG",
                    "name": "Ruxolitinib",
                    "description": "Topical JAK inhibitor cream",
                },
                {
                    "type": "DRUG",
                    "name": "Placebo",
                    "description": "Vehicle cream",
                },
            ]
        )

        trial = crawler._parse_study(study)
        assert trial is not None
        assert len(trial.interventions) == 2
        assert trial.interventions[0].drug_class == "JAK inhibitor"
        assert trial.interventions[0].type == InterventionType.DRUG
        assert trial.interventions[1].drug_class is None

    def test_parse_locations(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(
            locations=[
                {
                    "facility": "Shanghai Skin Disease Hospital",
                    "city": "Shanghai",
                    "country": "China",
                    "status": "RECRUITING",
                },
                {
                    "facility": "Mayo Clinic",
                    "city": "Rochester",
                    "state": "Minnesota",
                    "country": "United States",
                },
            ]
        )

        trial = crawler._parse_study(study)
        assert trial is not None
        assert len(trial.locations) == 2
        assert trial.locations[0].country == "China"
        assert trial.locations[1].state == "Minnesota"

    def test_parse_multiple_phases_picks_highest(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(phases=["PHASE1", "PHASE2"])
        trial = crawler._parse_study(study)
        assert trial is not None
        assert trial.phase == TrialPhase.PHASE2

    def test_parse_no_phases_returns_not_applicable(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(phases=[])
        trial = crawler._parse_study(study)
        assert trial is not None
        assert trial.phase == TrialPhase.NOT_APPLICABLE

    def test_parse_unknown_status_returns_unknown(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(overall_status="SOME_NEW_STATUS")
        trial = crawler._parse_study(study)
        assert trial is not None
        assert trial.status == TrialStatus.UNKNOWN

    def test_parse_missing_optional_fields(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(
            enrollment_count=None,
            start_date=None,
            completion_date=None,
            locations=[],
            interventions=[],
        )
        trial = crawler._parse_study(study)
        assert trial is not None
        assert trial.enrollment is None
        assert trial.start_date is None
        assert trial.completion_date is None
        assert trial.locations == []
        assert trial.interventions == []

    def test_parse_study_with_missing_nct_id_returns_none(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(nct_id="")
        trial = crawler._parse_study(study)
        assert trial is None

    def test_parse_collaborators(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study()
        trial = crawler._parse_study(study)
        assert trial is not None
        assert "NIH" in trial.collaborators

    def test_parse_conditions_joined(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(conditions=["Vitiligo", "Skin Depigmentation"])
        trial = crawler._parse_study(study)
        assert trial is not None
        assert trial.condition == "Vitiligo; Skin Depigmentation"


class TestSearchVitiligoTrials:
    def test_search_vitiligo_trials_delegates_to_search(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study()
        api_data = _make_api_response(studies=[study])
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        trials = crawler.search_vitiligo_trials(max_results=5)

        assert len(trials) == 1
        call_args = crawler._session.get.call_args  # type: ignore[union-attr]
        assert call_args[1]["params"]["query.cond"] == "vitiligo"


class TestSearchJAKInhibitorTrials:
    def test_filters_to_jak_trials_only(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        jak_study = _make_study(
            nct_id="NCT10000001",
            title="Ruxolitinib for Vitiligo",
            interventions=[
                {"type": "DRUG", "name": "Ruxolitinib", "description": "JAK inhibitor"}
            ],
        )
        non_jak_study = _make_study(
            nct_id="NCT10000002",
            title="Phototherapy for Vitiligo",
            interventions=[
                {"type": "DEVICE", "name": "NB-UVB Light", "description": "Phototherapy"}
            ],
        )

        api_data = _make_api_response(studies=[jak_study, non_jak_study])
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        jak_trials = crawler.search_jak_inhibitor_trials()

        assert len(jak_trials) == 1
        assert jak_trials[0].nct_id == "NCT10000001"

    def test_jak_filter_respects_max_results(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        studies = [
            _make_study(
                nct_id=f"NCT{10000000 + i}",
                interventions=[
                    {"type": "DRUG", "name": "Ruxolitinib", "description": "JAK inhibitor"}
                ],
            )
            for i in range(5)
        ]
        api_data = _make_api_response(studies=studies)
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        jak_trials = crawler.search_jak_inhibitor_trials(max_results=2)

        assert len(jak_trials) == 2


class TestGetTrialByNctId:
    def test_fetches_single_trial(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(nct_id="NCT99999999")
        api_data = _make_api_response(studies=[study])
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        trial = crawler.get_trial_by_nct_id("NCT99999999")

        assert trial is not None
        assert trial.nct_id == "NCT99999999"

    def test_returns_none_when_not_found(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        api_data = _make_api_response(studies=[])
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        trial = crawler.get_trial_by_nct_id("NCT00000000")

        assert trial is None

    def test_caches_fetched_trial(
        self, crawler: ClinicalTrialsCrawler
    ) -> None:
        study = _make_study(nct_id="NCT99999999")
        api_data = _make_api_response(studies=[study])
        crawler._session.get.return_value = _mock_response(api_data)  # type: ignore[union-attr]

        crawler.get_trial_by_nct_id("NCT99999999")
        crawler.get_trial_by_nct_id("NCT99999999")

        assert crawler._session.get.call_count == 1  # type: ignore[union-attr]


class TestExceptionHierarchy:
    def test_api_error_is_crawler_error(self) -> None:
        assert issubclass(APIError, CrawlerError)

    def test_api_error_stores_status_code(self) -> None:
        err = APIError("test", status_code=503)
        assert err.status_code == 503
        assert "test" in str(err)
