"""
Fix-up for anyone who already had "Dementia — Diagnostic & Clinical
Assessment" seeded before two of its Medical History questions were
improved from vague free-text to structured inputs:

1. "Primary diagnosis prompting referral for nurse care services" —
   plain text -> a real dropdown (with an Other + conditional free-text
   follow-up, since no fixed list covers every possible diagnosis).

2. "Reason(s) for and approximate date(s) of recent hospitalizations" — one
   vague textarea asking for both a reason AND a date at once, split into a
   real date picker, a reason dropdown (with its own Other follow-up), and a
   narrower textarea reserved specifically for any additional
   hospitalizations beyond the one most recent event.

Field-level safety: change #1 only proceeds if no real, stored answer
already exists for that exact field name — an existing free-text answer
like "vascular dementia with HTN" wouldn't match any of the new dropdown's
option values, and switching the type out from under it would make that
real answer effectively disappear from view. Change #2 only proceeds if no
real, stored answer exists under the OLD combined field name — removing
that field while a real answer exists there would orphan it. Each change is
independent: one can apply while the other is skipped, depending on what
real data actually exists.

Run with: python3 -m app.improve_medical_history_questions
Safe to run more than once — reports "already correct" if nothing changed.
"""

from sqlalchemy.orm.attributes import flag_modified

from app.database import SessionLocal
from app.dementia_seed_data import DEMENTIA_ASSESSMENTS
from app.models import AssessmentDefinition, AssessmentResult, AssignedAssessment, AssessmentVersion

TARGET_TITLE = "Dementia — Diagnostic & Clinical Assessment"


def _has_real_stored_answer(db, definition_id, field_name: str) -> bool:
    for a in db.query(AssignedAssessment).filter_by(assessment_definition_id=definition_id).all():
        if a.draft_answers and a.draft_answers.get(field_name):
            return True
    for r in db.query(AssessmentResult).filter_by(assessment_definition_id=definition_id).all():
        if r.answers and r.answers.get(field_name):
            return True
    return False


def improve_medical_history_questions():
    db = SessionLocal()
    try:
        definition = db.query(AssessmentDefinition).filter_by(title=TARGET_TITLE).first()
        if not definition:
            print(f"  Nothing to do — '{TARGET_TITLE}' doesn't exist in this database yet. Run "
                  f"app.seed_dementia first, which will create it with both improvements already included.")
            return

        version = db.query(AssessmentVersion).filter_by(assessment_definition_id=definition.id, version_number=definition.active_version).first()
        if not version or not version.fields:
            print("  ERROR: found the assessment but it has no fields — review manually.")
            return

        source = next(a for a in DEMENTIA_ASSESSMENTS if "Diagnostic" in a["phase_label"])
        source_medhist = next(s for s in source["steps"] if s["title"] == "Medical History")

        current_sections = version.fields.get("steps") or []
        current_medhist = next((s for s in current_sections if s.get("title") == "Medical History"), None)
        if not current_medhist:
            print("  ERROR: 'Medical History' section not found on the existing assessment — review manually.")
            return

        any_change = False

        # --- Change 1: diagnosis field text -> select ---
        diagnosis_name = "primary_diagnosis_prompting_referral_for_nurse_care_services"
        current_diag_field = next((f for f in current_medhist["fields"] if f["name"] == diagnosis_name), None)
        if current_diag_field and current_diag_field.get("type") == "select":
            print(f"  '{diagnosis_name}' already updated — skipping.")
        elif current_diag_field and _has_real_stored_answer(db, definition.id, diagnosis_name):
            print(f"  SKIPPING '{diagnosis_name}': a real stored free-text answer already exists for this "
                  f"field. Changing it to a dropdown would make that existing answer invisible. Review manually.")
        elif current_diag_field:
            source_field = next(f for f in source_medhist["fields"] if f["name"] == diagnosis_name)
            current_diag_field["type"] = source_field["type"]
            current_diag_field["options"] = source_field["options"]
            follow_up_name = "primary_diagnosis_other_please_specify"
            if not any(f["name"] == follow_up_name for f in current_medhist["fields"]):
                idx = current_medhist["fields"].index(current_diag_field)
                follow_up = next(f for f in source_medhist["fields"] if f["name"] == follow_up_name)
                current_medhist["fields"].insert(idx + 1, follow_up)
            any_change = True
            print(f"  Updated '{diagnosis_name}' to a real dropdown with an Other follow-up.")

        # --- Change 2: split the hospitalization field ---
        old_hosp_name = "reason_s_for_and_approximate_date_s_of_recent_hospitalizations"
        old_hosp_field = next((f for f in current_medhist["fields"] if f["name"] == old_hosp_name), None)
        if not old_hosp_field:
            print(f"  Hospitalization question already updated — skipping.")
        elif _has_real_stored_answer(db, definition.id, old_hosp_name):
            print(f"  SKIPPING hospitalization question split: a real stored answer already exists under "
                  f"the old combined field name. Removing it would orphan that real answer. Review manually.")
        else:
            old_idx = current_medhist["fields"].index(old_hosp_field)
            current_medhist["fields"].remove(old_hosp_field)
            new_names = [
                "approximate_date_of_most_recent_hospitalization",
                "reason_for_most_recent_hospitalization",
                "hospitalization_reason_other_please_specify",
                "details_of_any_additional_hospitalizations_in_the_past_12_months",
            ]
            for offset, name in enumerate(new_names):
                new_field = next(f for f in source_medhist["fields"] if f["name"] == name)
                current_medhist["fields"].insert(old_idx + offset, new_field)
            any_change = True
            print(f"  Split the hospitalization question into 4 structured fields (date, reason dropdown, "
                  f"Other follow-up, additional-hospitalizations textarea).")

        if any_change:
            flag_modified(version, "fields")
            db.commit()
        else:
            print("  No changes made.")
    finally:
        db.close()


if __name__ == "__main__":
    improve_medical_history_questions()
