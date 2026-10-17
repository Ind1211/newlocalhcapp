"""
An original, deterministic cognitive-screening scoring calculator for the
"Dementia — Diagnostic & Clinical Assessment" template's 5 cognitive
sub-domains (Orientation, Memory, Attention & Executive Function, Language &
Communication, Visuospatial & Functional Reasoning).

This is NOT the MMSE, MoCA, or any other validated, copyrighted cognitive
instrument — it does not reproduce their items or their actual scoring
rubric, matching this whole question bank's own deliberate approach. It is
an original impairment index built from this app's own original questions,
intended as a structured screening aid, not a diagnostic or validated
clinical score. This should be read alongside the AI-generated narrative
interpretation this same assessment also produces, not in place of it.

Missing/unanswered questions are excluded from both the numerator and the
denominator, rather than treated as either "answered normally" or "maximally
impaired" — an assessment with 40 of 46 cognitive items answered is scored
against the 40 that were actually answered, not penalized or inflated by the
6 that weren't.
"""

from app.calculators.base import Calculator


def _pill(answers: dict, name: str, impaired_values: dict[str, float]) -> float | None:
    """Returns the impairment point value for a pill/select answer, or None
    if unanswered — impaired_values maps each real answer value to its point
    weight (0 = no impairment)."""
    value = answers.get(name)
    if value is None or value == "":
        return None
    return impaired_values.get(value)


def _number(answers: dict, name: str, worst_at: float, best_at: float, max_points: float) -> float | None:
    """Linearly scales a numeric answer between best_at (0 impairment points)
    and worst_at (max_points), clamped to that range."""
    value = answers.get(name)
    if value is None or value == "":
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if worst_at == best_at:
        return 0.0
    fraction = (value - best_at) / (worst_at - best_at)
    return max(0.0, min(1.0, fraction)) * max_points


# Each entry: (field_name, scorer_function, max_points_for_this_item)
_ORIENTATION_ITEMS = [
    ("can_the_patient_correctly_state_the_current_year", lambda a: _pill(a, "can_the_patient_correctly_state_the_current_year", {"no": 1, "yes": 0}), 1),
    ("can_the_patient_correctly_state_the_current_season", lambda a: _pill(a, "can_the_patient_correctly_state_the_current_season", {"no": 1, "yes": 0}), 1),
    ("can_the_patient_correctly_state_the_current_month_and_approximate_date", lambda a: _pill(a, "can_the_patient_correctly_state_the_current_month_and_approximate_date", {"no": 1, "yes": 0}), 1),
    ("can_the_patient_correctly_state_the_day_of_the_week", lambda a: _pill(a, "can_the_patient_correctly_state_the_day_of_the_week", {"no": 1, "yes": 0}), 1),
    ("can_the_patient_correctly_identify_their_current_location_building_city_state", lambda a: _pill(a, "can_the_patient_correctly_identify_their_current_location_building_city_state", {"no": 1, "yes": 0}), 1),
    ("does_the_patient_recognize_familiar_people_family_members_regular_caregivers", lambda a: _pill(a, "does_the_patient_recognize_familiar_people_family_members_regular_caregivers", {"always": 0, "usually": 0, "sometimes": 1, "rarely": 2, "never": 3}), 3),
    ("does_the_patient_know_their_own_current_age", lambda a: _pill(a, "does_the_patient_know_their_own_current_age", {"no": 1, "yes": 0}), 1),
    ("does_the_patient_know_their_own_date_of_birth", lambda a: _pill(a, "does_the_patient_know_their_own_date_of_birth", {"no": 1, "yes": 0}), 1),
]

_MEMORY_ITEMS = [
    ("does_the_patient_repeat_questions_or_statements_within_a_short_period_of_time", lambda a: _pill(a, "does_the_patient_repeat_questions_or_statements_within_a_short_period_of_time", {"never": 0, "occasionally": 1, "frequently": 2, "constantly": 3}), 3),
    ("does_the_patient_forget_recent_conversations_or_events", lambda a: _pill(a, "does_the_patient_forget_recent_conversations_or_events", {"never": 0, "occasionally": 1, "frequently": 2, "constantly": 3}), 3),
    ("does_the_patient_forget_scheduled_appointments_or_important_dates", lambda a: _pill(a, "does_the_patient_forget_scheduled_appointments_or_important_dates", {"never": 0, "occasionally": 1, "frequently": 2, "constantly": 3}), 3),
    ("does_the_patient_frequently_misplace_items_keys_glasses_wallet", lambda a: _pill(a, "does_the_patient_frequently_misplace_items_keys_glasses_wallet", {"never": 0, "occasionally": 1, "frequently": 2, "constantly": 3}), 3),
    ("does_the_patient_forget_the_names_of_close_family_members", lambda a: _pill(a, "does_the_patient_forget_the_names_of_close_family_members", {"no": 0, "yes": 1}), 1),
    ("clinician_administered_number_of_3_unrelated_words_correctly_recalled_after_a_short_delay_0_3", lambda a: _number(a, "clinician_administered_number_of_3_unrelated_words_correctly_recalled_after_a_short_delay_0_3", worst_at=0, best_at=3, max_points=3), 3),
    ("does_the_patient_have_difficulty_learning_new_information_or_routines", lambda a: _pill(a, "does_the_patient_have_difficulty_learning_new_information_or_routines", {"never": 0, "occasionally": 1, "frequently": 2, "constantly": 3}), 3),
    ("does_the_patient_retell_the_same_stories_or_ask_the_same_questions_repeatedly", lambda a: _pill(a, "does_the_patient_retell_the_same_stories_or_ask_the_same_questions_repeatedly", {"no": 0, "yes": 1}), 1),
    ("long_term_memory_recall_of_major_life_events_clinician_judgment", lambda a: _pill(a, "long_term_memory_recall_of_major_life_events_clinician_judgment", {"intact": 0, "mildly_impaired": 1, "moderately_impaired": 2, "severely_impaired": 3}), 3),
]

_ATTENTION_ITEMS = [
    ("ability_to_follow_a_3_step_instruction_e_g_pick_up_the_paper_fold_it_place_it_on_the_table", lambda a: _pill(a, "ability_to_follow_a_3_step_instruction_e_g_pick_up_the_paper_fold_it_place_it_on_the_table", {"completes_independently": 0, "completes_with_cues": 1, "unable_to_complete": 2}), 2),
    ("number_of_errors_when_counting_backward_from_20_by_3s_clinician_administered", lambda a: _number(a, "number_of_errors_when_counting_backward_from_20_by_3s_clinician_administered", worst_at=5, best_at=0, max_points=3), 3),
    ("ability_to_maintain_attention_on_a_task_without_redirection", lambda a: _pill(a, "ability_to_maintain_attention_on_a_task_without_redirection", {"more_than_10_minutes": 0, "5_10_minutes": 1, "less_than_5_minutes": 2, "unable_to_sustain_attention": 3}), 3),
    ("does_the_patient_show_impulsivity_or_poor_judgment_in_decision_making", lambda a: _pill(a, "does_the_patient_show_impulsivity_or_poor_judgment_in_decision_making", {"no": 0, "yes": 1}), 1),
    ("ability_to_plan_and_sequence_a_familiar_multi_step_task_e_g_preparing_a_simple_meal", lambda a: _pill(a, "ability_to_plan_and_sequence_a_familiar_multi_step_task_e_g_preparing_a_simple_meal", {"independent": 0, "needs_verbal_cues": 1, "needs_physical_assistance": 2, "unable": 3}), 3),
    ("ability_to_problem_solve_in_a_novel_or_unexpected_situation", lambda a: _pill(a, "ability_to_problem_solve_in_a_novel_or_unexpected_situation", {"intact": 0, "mildly_impaired": 1, "moderately_impaired": 2, "severely_impaired": 3}), 3),
    ("presence_of_perseveration_repeating_the_same_word_question_or_action", lambda a: _pill(a, "presence_of_perseveration_repeating_the_same_word_question_or_action", {"no": 0, "yes": 1}), 1),
]

_LANGUAGE_ITEMS = [
    ("ability_to_name_common_everyday_objects", lambda a: _pill(a, "ability_to_name_common_everyday_objects", {"intact": 0, "occasional_word_finding_difficulty": 1, "frequent_word_finding_difficulty": 2, "unable_to_name_objects": 3}), 3),
    ("ability_to_follow_and_participate_in_a_conversation", lambda a: _pill(a, "ability_to_follow_and_participate_in_a_conversation", {"intact": 0, "mildly_impaired": 1, "moderately_impaired": 2, "severely_impaired": 3}), 3),
    ("ability_to_express_needs_verbally", lambda a: _pill(a, "ability_to_express_needs_verbally", {"fully_able": 0, "partially_able": 1, "unable_relies_on_gestures": 2, "nonverbal": 3}), 3),
    ("presence_of_noticeable_word_finding_difficulty_anomia", lambda a: _pill(a, "presence_of_noticeable_word_finding_difficulty_anomia", {"no": 0, "yes": 1}), 1),
    ("repetition_of_others_words_or_phrases_echolalia", lambda a: _pill(a, "repetition_of_others_words_or_phrases_echolalia", {"no": 0, "yes": 1}), 1),
]

_VISUOSPATIAL_ITEMS = [
    ("clinician_administered_ability_to_copy_a_simple_geometric_shape_or_drawing", lambda a: _pill(a, "clinician_administered_ability_to_copy_a_simple_geometric_shape_or_drawing", {"accurate": 0, "mildly_distorted": 1, "severely_distorted": 2, "unable_to_attempt": 3}), 3),
    ("history_of_getting_lost_in_familiar_environments", lambda a: _pill(a, "history_of_getting_lost_in_familiar_environments", {"no": 0, "yes": 1}), 1),
    ("difficulty_judging_distances_depth_or_navigating_stairs_safely", lambda a: _pill(a, "difficulty_judging_distances_depth_or_navigating_stairs_safely", {"no": 0, "yes": 1}), 1),
    ("difficulty_recognizing_familiar_places_home_neighborhood", lambda a: _pill(a, "difficulty_recognizing_familiar_places_home_neighborhood", {"no_difficulty": 0, "occasional_difficulty": 1, "frequent_difficulty": 2}), 2),
]

_DOMAINS = [
    ("Orientation", _ORIENTATION_ITEMS),
    ("Memory", _MEMORY_ITEMS),
    ("Attention & Executive Function", _ATTENTION_ITEMS),
    ("Language & Communication", _LANGUAGE_ITEMS),
    ("Visuospatial & Functional Reasoning", _VISUOSPATIAL_ITEMS),
]


def _score_domain(answers: dict, items: list) -> tuple[float, float, int]:
    """Returns (points_scored, max_possible_for_answered_items, count_answered)."""
    scored, possible, answered = 0.0, 0.0, 0
    for _, scorer, max_points in items:
        result = scorer(answers)
        if result is None:
            continue
        scored += result
        possible += max_points
        answered += 1
    return scored, possible, answered


class DementiaCognitiveScreeningCalculator(Calculator):
    key = "dementia_cognitive_screening_index"

    def compute(self, a: dict) -> dict:
        domain_results = []
        total_scored, total_possible, total_answered, total_items = 0.0, 0.0, 0, 0

        for domain_name, items in _DOMAINS:
            scored, possible, answered = _score_domain(a, items)
            total_items += len(items)
            if answered == 0:
                domain_results.append({"name": domain_name, "pct": None, "answered": 0, "of": len(items)})
                continue
            pct = round((scored / possible) * 100) if possible > 0 else 0
            domain_results.append({"name": domain_name, "pct": pct, "answered": answered, "of": len(items)})
            total_scored += scored
            total_possible += possible
            total_answered += answered

        if total_answered == 0:
            return {
                "headline": "No cognitive screening items answered yet",
                "headlineSeverity": "caution",
                "metrics": [],
                "flags": [],
                "notes": "This index scores the Diagnostic & Clinical Assessment's 5 cognitive screening "
                         "sections (Orientation, Memory, Attention & Executive Function, Language & Communication, "
                         "Visuospatial & Functional Reasoning). Complete at least some of those items to generate a score.",
            }

        overall_pct = round((total_scored / total_possible) * 100) if total_possible > 0 else 0

        if overall_pct < 15:
            band, severity = "Minimal cognitive concern", "good"
        elif overall_pct < 40:
            band, severity = "Mild cognitive impairment indicated", "caution"
        elif overall_pct < 70:
            band, severity = "Moderate cognitive impairment indicated", "warning"
        else:
            band, severity = "Severe cognitive impairment indicated", "critical"

        completeness_note = ""
        if total_answered < total_items:
            completeness_note = f" Based on {total_answered} of {total_items} cognitive screening items answered — score reflects only what was completed."

        metrics = [{"label": "Overall cognitive impairment index", "value": f"{overall_pct}%"}]
        for d in domain_results:
            if d["pct"] is None:
                metrics.append({"label": d["name"], "value": f"not answered (0/{d['of']})"})
            else:
                metrics.append({"label": d["name"], "value": f"{d['pct']}% ({d['answered']}/{d['of']} answered)"})

        flags = []
        for d in domain_results:
            if d["pct"] is not None and d["pct"] >= 70:
                flags.append({"text": f"Severe impairment indicated in {d['name']}", "severity": "critical"})
            elif d["pct"] is not None and d["pct"] >= 40:
                flags.append({"text": f"Moderate impairment indicated in {d['name']}", "severity": "warning"})

        return {
            "headline": f"{band} — Dementia Cognitive Screening Index: {overall_pct}%",
            "headlineSeverity": severity,
            "metrics": metrics,
            "flags": flags,
            "notes": (
                "This is an original screening index built from this app's own questions — it is NOT the MMSE, "
                "MoCA, or any other validated diagnostic instrument, and this score should not be used as a "
                "substitute for formal neuropsychological testing or clinical diagnosis. It's intended as a "
                "structured aid for tracking screening findings over time, alongside — not instead of — the "
                "AI-generated clinical interpretation this same assessment also produces."
                + completeness_note
            ),
        }
