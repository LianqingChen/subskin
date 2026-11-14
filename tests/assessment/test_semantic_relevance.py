"""Evidence-only contract; no model download or clinical accuracy claim."""
import pytest
from ml.rgb_segmentation.relevance import PROMPTS, summarize_scores


def test_skin_ranking_cannot_enable_measurement():
    scores = dict.fromkeys(PROMPTS, -5.0)
    scores["skin_closeup"] = 2.0
    result = summarize_scores(scores)
    assert result["ranked_domain"] == "skin"
    assert result["measurement_eligible"] is False
    assert result["calibrated"] is False and result["clinical_accuracy"] is None
    assert result["modality_validated"] is False


def test_tied_scores_are_ambiguous_not_accepted_by_prompt_order():
    assert summarize_scores(dict.fromkeys(PROMPTS, 0.0))["ranked_domain"] == "ambiguous"


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_model_output_is_rejected(invalid):
    scores = dict.fromkeys(PROMPTS, -1.0)
    scores["surface"] = invalid
    with pytest.raises(ValueError): summarize_scores(scores)


def test_incomplete_prompt_bank_cannot_produce_a_margin():
    with pytest.raises(ValueError): summarize_scores({"skin_closeup": 5.0})
