"""
Cleanup for anyone who already ran the earlier version of app.seed_dementia,
which created a "Dementia — Onboarding & Intake" assessment template that
duplicated what this app's mandatory Basic Patient Intake already covers for
every patient. Removing the template only — its 41 questions remain in the
question library, still individually reusable via "Choose from library".

Distinguishes two very different situations:
- A real, COMPLETED result exists — genuine clinical data. This still
  refuses to delete anything, exactly as before. Review manually.
- The assessment is merely SCHEDULED/assigned to one or more patients but
  never actually answered — no real clinical data exists yet, just a
  pending task. This is now treated as safe to remove: both the pending
  assignment(s) and the assessment definition itself are deleted together,
  rather than leaving a dangling assignment pointing at a now-deleted
  definition. It's a scheduled task disappearing, not any deletion of a
  patient's actual answers.

Running app.seed_dementia again after this will NOT recreate the removed
template — it was deleted from DEMENTIA_ASSESSMENTS in the source data, not
just from the database.

Run with: python3 -m app.remove_dementia_onboarding_intake
Safe to run more than once — reports "nothing to do" if already removed.
"""

from app.database import SessionLocal
from app.models import AssessmentDefinition, AssessmentResult, AssignedAssessment, AssessmentVersion, AuditLogEntry

TARGET_KEY = "dementia_onboarding___intake"


def remove_dementia_onboarding_intake():
    db = SessionLocal()
    try:
        definition = db.query(AssessmentDefinition).filter_by(key=TARGET_KEY).first()
        if not definition:
            print(f"  Nothing to do — no assessment with key '{TARGET_KEY}' exists in this database.")
            return

        n_results = db.query(AssessmentResult).filter_by(assessment_definition_id=definition.id).count()
        n_assigned = db.query(AssignedAssessment).filter_by(assessment_definition_id=definition.id).count()

        if n_results > 0:
            print(f"  REFUSING TO DELETE: '{definition.title}' has {n_results} completed result(s) — real "
                  f"clinical data from actual patient answers. Deleting it would destroy that data. Review "
                  f"this manually rather than running this script.")
            return

        if n_assigned > 0:
            db.query(AssignedAssessment).filter_by(assessment_definition_id=definition.id).delete()
            print(f"  Removed {n_assigned} pending/scheduled assignment(s) for '{definition.title}' — none of "
                  f"them had actually been answered, so no real patient data was lost, just a pending task.")

        db.query(AuditLogEntry).filter_by(assessment_definition_id=definition.id).delete()
        db.query(AssessmentVersion).filter_by(assessment_definition_id=definition.id).delete()
        db.delete(definition)
        db.commit()
        print(f"  Removed '{definition.title}' (key={TARGET_KEY}) entirely. Its 41 questions remain in the "
              f"question library under their original categories.")
    finally:
        db.close()


if __name__ == "__main__":
    remove_dementia_onboarding_intake()
