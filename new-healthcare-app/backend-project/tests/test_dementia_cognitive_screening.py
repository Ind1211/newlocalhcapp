"""
Tests for the two pieces of real work added to close identified gaps in the
Dementia clinical program:
1. A deterministic cognitive screening calculator (not AI interpretation)
2. An elder abuse / neglect / financial exploitation screening section
"""

from app.calculators.dementia_cognitive_screening import DementiaCognitiveScreeningCalculator
from app.calculators.registry import get_calculator
from app.dementia_seed_data import DEMENTIA_ASSESSMENTS, QLIB_DEMENTIA


def test_calculator_is_registered():
    calc = get_calculator("dementia_cognitive_screening_index")
    assert calc is not None
    assert isinstance(calc, DementiaCognitiveScreeningCalculator)


def test_no_impairment_scores_zero_percent():
    calc = DementiaCognitiveScreeningCalculator()
    answers = {
        "can_the_patient_correctly_state_the_current_year": "yes",
        "can_the_patient_correctly_state_the_current_season": "yes",
        "does_the_patient_know_their_own_current_age": "yes",
        "clinician_administered_number_of_3_unrelated_words_correctly_recalled_after_a_short_delay_0_3": 3,
    }
    result = calc.compute(answers)
    assert "0%" in result["headline"]
    assert result["headlineSeverity"] == "good"


def test_severe_impairment_scores_high_and_flags_domains():
    calc = DementiaCognitiveScreeningCalculator()
    answers = {
        "can_the_patient_correctly_state_the_current_year": "no",
        "can_the_patient_correctly_state_the_current_season": "no",
        "does_the_patient_know_their_own_current_age": "no",
        "clinician_administered_number_of_3_unrelated_words_correctly_recalled_after_a_short_delay_0_3": 0,
    }
    result = calc.compute(answers)
    assert result["headlineSeverity"] == "critical"
    assert "100%" in result["headline"]
    assert len(result["flags"]) > 0


def test_nothing_answered_does_not_crash_or_produce_a_misleading_score():
    calc = DementiaCognitiveScreeningCalculator()
    result = calc.compute({})
    assert "not answered" in result["headline"].lower() or "no cognitive" in result["headline"].lower()
    assert result["metrics"] == []


def test_partial_answers_score_only_what_was_actually_answered():
    """The real property this calculator depends on — an incomplete
    assessment must not be penalized (or artificially inflated) by treating
    unanswered items as either impaired or normal."""
    calc = DementiaCognitiveScreeningCalculator()
    # Only 1 of 8 orientation items answered, with a normal response
    answers = {"can_the_patient_correctly_state_the_current_year": "yes"}
    result = calc.compute(answers)
    orientation_metric = next(m for m in result["metrics"] if m["label"] == "Orientation")
    assert "1/8" in orientation_metric["value"]
    assert "0%" in orientation_metric["value"]  # the one answered item was normal
    assert "1 of" in result["notes"]  # completeness note present


def test_numeric_word_recall_is_correctly_inverted():
    """3 words recalled = best possible (0 impairment); 0 words recalled =
    worst possible — the raw number itself is inverted relative to impairment."""
    calc = DementiaCognitiveScreeningCalculator()
    best = calc.compute({"clinician_administered_number_of_3_unrelated_words_correctly_recalled_after_a_short_delay_0_3": 3})
    worst = calc.compute({"clinician_administered_number_of_3_unrelated_words_correctly_recalled_after_a_short_delay_0_3": 0})
    assert "0%" in best["headline"]
    assert "100%" in worst["headline"]


def test_elder_abuse_section_exists_on_risk_safety_assessment():
    risk_safety = next(a for a in DEMENTIA_ASSESSMENTS if "Risk & Safety" in a["phase_label"])
    section = next((s for s in risk_safety["steps"] if "Abuse" in s["title"]), None)
    assert section is not None
    assert len(section["fields"]) >= 10

    # No duplicate field names across the whole assessment
    all_names = [f["name"] for s in risk_safety["steps"] for f in s["fields"]]
    assert len(all_names) == len(set(all_names))


def test_elder_abuse_questions_also_in_reusable_library():
    abuse_category = next((b for b in QLIB_DEMENTIA if "Abuse" in b["category"]), None)
    assert abuse_category is not None
    assert len(abuse_category["questions"]) >= 10


def test_orientation_option_with_internal_parentheses_and_commas_not_mangled():
    """Regression test for a real parsing bug found during this work — a
    naive comma-split broke "Fully oriented (person, place, time, situation)"
    into malformed fragments like "place" and "situation)"."""
    diag = next(a for a in DEMENTIA_ASSESSMENTS if "Diagnostic" in a["phase_label"])
    orientation = next(s for s in diag["steps"] if "Orientation" in s["title"])
    field = next(f for f in orientation["fields"] if "overall" in f["label"].lower())
    option_labels = [o["label"] for o in field["options"]]
    assert "Fully oriented (person, place, time, situation)" in option_labels
    assert "place" not in option_labels
    assert "situation)" not in option_labels
