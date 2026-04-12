import pytest
from pydantic import ValidationError

from src.models.trial import (
    ClinicalTrial,
    TrialPhase,
    TrialStatus,
    Intervention,
    InterventionType,
    Location,
)


def test_trial_basic_validation_and_methods():
    trial = ClinicalTrial(
        nct_id="NCT00000001",
        title="Vitiligo Jak inhibitor study",
        condition="Vitiligo",
        phase=TrialPhase.PHASE2,
        status=TrialStatus.RECRUITING,
        sponsor="Big Pharma",
        url="https://clinicaltrials.gov/ct2/show/NCT00000001",
        interventions=[
            Intervention(
                name="Tofacitinib",
                type=InterventionType.DRUG,
                drug_class="JAK inhibitor",
            )
        ],
        locations=[Location(facility="Center A", country="USA")],
    )

    assert trial.is_active()
    assert trial.nct_id.startswith("NCT")
    assert trial.get_countries() == ["USA"]

    assert trial.is_jak_inhibitor_trial()  # type: ignore[attr-defined]

    assert trial.is_completed() is False
    assert trial.to_dict()["nct_id"] == "NCT00000001"


def test_trial_validation_and_enumerations():
    with pytest.raises(ValidationError):
        # invalid nct_id pattern
        ClinicalTrial(
            nct_id="NCT123",
            title="Invalid nct",
            condition="Vitiligo",
            phase=TrialPhase.PHASE1,
            status=TrialStatus.RECRUITING,
            sponsor="S",
            url="https://example.com",
        )

    trial = ClinicalTrial(
        nct_id="NCT00000002",
        title="Jak inhibitors in vitiligo",
        condition="Vitiligo",
        phase=TrialPhase.PHASE3,
        status=TrialStatus.ACTIVE_NOT_RECRUITING,
        sponsor="Spon",
        url="https://clinicaltrials.gov/ct2/show/NCT00000002",
        interventions=[Intervention(name="Ruxolitinib", type=InterventionType.DRUG)],
        locations=[Location(facility="Center B", country="Canada")],
    )
    assert trial.is_active()
    assert TrialPhase.PHASE3 in {trial.phase}

    # test date validators on fields
    trial.start_date = "2021-05"
    trial.completion_date = "2022-12"
    trial.last_update_date = "2023-01-15"
    assert trial.start_date == "2021-05"
    assert trial.completion_date == "2022-12"
    assert trial.last_update_date == "2023-01-15"

    update = trial.update if hasattr(trial, "update") else None
    # TrialUpdate model can be constructed separately
    from src.models.trial import TrialUpdate

    t_update = TrialUpdate(status=TrialStatus.COMPLETED)
    assert t_update is not None

    from src.models.trial import TrialSearchResult

    tr = TrialSearchResult(trial=trial, relevance_score=0.9)
    assert tr.relevance_score == 0.9


def test_jak_inhibitor_detection_with_various_names():
    trial = ClinicalTrial(
        nct_id="NCT00000003",
        title="Study of Jak inhibitors",
        condition="Vitiligo",
        phase=TrialPhase.PHASE2,
        status=TrialStatus.RECRUITING,
        sponsor="Sponsor",
        url="https://example.com/NCT00000003",
        interventions=[
            Intervention(
                name="Janus kinase inhibitor (generic)", type=InterventionType.DRUG
            )
        ],
        locations=[Location(facility="Loc", country="USA")],
    )
    assert trial.is_jak_inhibitor_trial()  # type: ignore[attr-defined]


def test_nct_id_pattern_validation():
    with pytest.raises(ValidationError):
        ClinicalTrial(
            nct_id="NCT1234",
            title="Bad id",
            condition="Vitiligo",
            phase=TrialPhase.PHASE1,
            status=TrialStatus.RECRUITING,
            sponsor="S",
            url="https://example.com",
        )
