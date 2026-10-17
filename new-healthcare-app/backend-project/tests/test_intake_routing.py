"""
Tests for the dementia-related additions to the intake routing engine
(compute_intake_pathway, derive_clinical_programs) — pure functions, no
database needed. Verifies the same behaviors confirmed live against a real
server during development: acute confusion gets urgent priority, known and
suspected dementia both route to the diagnostic assessment, and overlapping
signals merge rather than duplicate.
"""

from app.calculators.intake import compute_intake_pathway, derive_clinical_programs


def _base_answers(**overrides) -> dict:
    base = {
        "knownCkd": "no", "onDialysis": "no", "kidneyTransplant": "no",
        "knownHf": "no", "knownCad": "no", "knownArrhythmia": "no", "hasDevice": "no", "knownValveDisease": "no",
        "diabetes": "no", "pregnant": "no", "knownDementia": "no", "memoryConcerns": "no",
        "symptomChestPain": "no", "symptomSob": "no", "symptomSwelling": "no", "symptomSyncope": "no",
        "symptomPalpitations": "no", "symptomUrineChange": "no", "symptomConfusion": "no",
        "recentHospitalization": "no", "knownHtn": "no", "smokingStatus": "never", "regularNsaidUse": "no",
        "familyHistoryKidneyDisease": "no", "familyHistoryHeartDisease": "no",
        "functionalDecline": "no", "wanderingHistory": "no", "livesAlone": "no",
    }
    base.update(overrides)
    return base


def test_memory_concerns_suggests_diagnostic_assessment_and_tags_dementia_program():
    answers = _base_answers(memoryConcerns="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"]: p for p in pathway}

    assert "dementia_diagnostic___clinical_assessment" in module_ids
    assert module_ids["dementia_diagnostic___clinical_assessment"]["mandatory"] is True
    assert "dementia_functional___behavioral_assessment" in module_ids
    assert module_ids["dementia_functional___behavioral_assessment"]["mandatory"] is False
    assert "dementia_psychosocial___caregiver_assessment" in module_ids

    assert derive_clinical_programs(answers) == ["dementia"]


def test_acute_confusion_gets_urgent_mandatory_priority():
    """Distinct from memoryConcerns — an acute, today-focused symptom that can
    indicate delirium, matching the same urgency tier as chest pain/syncope."""
    answers = _base_answers(symptomConfusion="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"]: p for p in pathway}

    assert "dementia_risk___safety_assessment" in module_ids
    entry = module_ids["dementia_risk___safety_assessment"]
    assert entry["mandatory"] is True
    assert entry["priority"] == 2
    assert "delirium" in entry["reasons"][0].lower()


def test_known_dementia_suggests_diagnostic_not_onboarding():
    """The Onboarding & Intake dementia assessment was removed as redundant
    with the mandatory Basic Patient Intake — this confirms it's genuinely
    gone from suggestions, not just that the diagnostic one is present."""
    answers = _base_answers(knownDementia="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"] for p in pathway}

    assert "dementia_onboarding___intake" not in module_ids
    assert "dementia_diagnostic___clinical_assessment" in module_ids
    assert derive_clinical_programs(answers) == ["dementia"]


def test_overlapping_dementia_signals_merge_not_duplicate():
    """The real property that matters — known diagnosis AND suspected/reported
    changes both target the diagnostic assessment; this must appear once with
    combined reasons, not twice."""
    answers = _base_answers(knownDementia="yes", memoryConcerns="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = [p["moduleId"] for p in pathway]

    assert len(module_ids) == len(set(module_ids))  # no duplicates at all

    diagnostic = next(p for p in pathway if p["moduleId"] == "dementia_diagnostic___clinical_assessment")
    assert len(diagnostic["reasons"]) == 2
    assert diagnostic["mandatory"] is True


def test_no_dementia_signals_suggests_nothing_dementia_related():
    answers = _base_answers()
    pathway = compute_intake_pathway(answers)
    dementia_modules = [p for p in pathway if p["moduleId"].startswith("dementia_")]
    assert dementia_modules == []
    assert "dementia" not in derive_clinical_programs(answers)


def test_dementia_signals_do_not_disturb_existing_cardiology_routing():
    """A real regression check — confirms adding dementia rules didn't
    accidentally change unrelated existing behavior for a cardiology-only
    patient."""
    answers = _base_answers(symptomChestPain="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"] for p in pathway}
    assert "heart_score" in module_ids
    assert "timi_unstable" in module_ids
    assert not any(m.startswith("dementia_") for m in module_ids)


def test_known_htn_suggests_kidney_and_cardiology_assessments():
    answers = _base_answers(knownHtn="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"] for p in pathway}
    assert "ckd_staging" in module_ids
    assert "bp_category" in module_ids
    assert "htn_management_checklist" in module_ids
    assert "ascvd_risk_enhancers" in module_ids
    # Matches the existing diabetes precedent — a risk factor, not a
    # diagnosed condition, so it should not auto-enroll either program.
    assert derive_clinical_programs(answers) == []


def test_current_or_former_smoker_suggests_ascvd_risk_enhancers():
    for status in ("current", "former"):
        answers = _base_answers(smokingStatus=status)
        pathway = compute_intake_pathway(answers)
        module_ids = {p["moduleId"] for p in pathway}
        assert "ascvd_risk_enhancers" in module_ids, f"failed for status={status}"

    never_answers = _base_answers(smokingStatus="never")
    never_pathway = compute_intake_pathway(never_answers)
    assert "ascvd_risk_enhancers" not in {p["moduleId"] for p in never_pathway}


def test_nsaid_use_suggests_nephrotoxicity_checklist():
    answers = _base_answers(regularNsaidUse="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"] for p in pathway}
    assert "drug_nephrotoxicity_checklist" in module_ids


def test_family_history_kidney_suggests_adpkd_screening():
    answers = _base_answers(familyHistoryKidneyDisease="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"] for p in pathway}
    assert "adpkd_mayo" in module_ids


def test_family_history_heart_suggests_ascvd_risk_enhancers():
    answers = _base_answers(familyHistoryHeartDisease="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"] for p in pathway}
    assert "ascvd_risk_enhancers" in module_ids


def test_functional_decline_suggests_functional_assessment_and_tags_dementia():
    answers = _base_answers(functionalDecline="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"]: p for p in pathway}
    assert "dementia_functional___behavioral_assessment" in module_ids
    assert module_ids["dementia_functional___behavioral_assessment"]["mandatory"] is True
    assert derive_clinical_programs(answers) == ["dementia"]


def test_wandering_history_gets_urgent_safety_suggestion():
    answers = _base_answers(wanderingHistory="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"]: p for p in pathway}
    assert "dementia_risk___safety_assessment" in module_ids
    assert module_ids["dementia_risk___safety_assessment"]["mandatory"] is True
    assert derive_clinical_programs(answers) == ["dementia"]


def test_lives_alone_alone_triggers_nothing_without_a_dementia_signal():
    """The real property that matters — living alone by itself, with no
    cognitive or safety signal present, should not trigger dementia-specific
    suggestions or auto-enrollment."""
    answers = _base_answers(livesAlone="yes")
    pathway = compute_intake_pathway(answers)
    assert not any(p["moduleId"].startswith("dementia_") for p in pathway)
    assert derive_clinical_programs(answers) == []


def test_lives_alone_combined_with_dementia_signal_raises_urgency():
    answers = _base_answers(livesAlone="yes", memoryConcerns="yes")
    pathway = compute_intake_pathway(answers)
    module_ids = {p["moduleId"] for p in pathway}
    assert "dementia_risk___safety_assessment" in module_ids
    assert "dementia_psychosocial___caregiver_assessment" in module_ids


def test_memory_concerns_and_known_dementia_both_suggest_cognitive_screening_index():
    """The deterministic Cognitive Screening Index calculator was previously
    never suggested by intake routing at all — only the AI-interpreted
    Diagnostic & Clinical assessment was. Both a suspected (memoryConcerns)
    and a known (knownDementia) dementia signal should now also suggest the
    calculator-backed screening specifically, as a mandatory item."""
    for answer_key in ("memoryConcerns", "knownDementia"):
        answers = _base_answers(**{answer_key: "yes"})
        pathway = compute_intake_pathway(answers)
        module_ids = {p["moduleId"]: p for p in pathway}
        assert "dementia_cognitive_screening_index" in module_ids, f"failed for {answer_key}"
        assert module_ids["dementia_cognitive_screening_index"]["mandatory"] is True
