"""
Fix-up for anyone who already had "Dementia — Risk & Safety Assessment"
seeded before the "Abuse, Neglect & Financial Exploitation Screening"
section was added to it. app.seed_dementia's own idempotency check is by
title — it only CREATES an assessment that doesn't exist yet, it never
refreshes an already-existing one's fields. That's correct for most cases
(it protects hand-edited content from being silently overwritten), but it
also means adding a new section to an existing template's source data has
no effect on a database that already has that template.

This adds the new section only if it's genuinely missing, and does nothing
if it's already there or the assessment doesn't exist at all — safe to run
regardless of your current state.

Run with: python3 -m app.add_elder_abuse_screening_section
"""

from app.database import SessionLocal
from app.dementia_seed_data import DEMENTIA_ASSESSMENTS
from app.models import AssessmentDefinition, AssessmentVersion
from sqlalchemy.orm.attributes import flag_modified


def add_elder_abuse_screening_section():
    db = SessionLocal()
    try:
        definition = db.query(AssessmentDefinition).filter_by(title="Dementia — Risk & Safety Assessment").first()
        if not definition:
            print("  Nothing to do — 'Dementia — Risk & Safety Assessment' doesn't exist in this database yet. "
                  "Run app.seed_dementia first, which will create it with the section already included.")
            return

        version = db.query(AssessmentVersion).filter_by(assessment_definition_id=definition.id, version_number=definition.active_version).first()
        if not version or not version.fields:
            print("  ERROR: found the assessment but it has no fields — this shouldn't happen, review manually.")
            return

        current_sections = version.fields.get("steps") or []
        already_has_it = any("Abuse" in (s.get("title") or "") for s in current_sections)
        if already_has_it:
            print("  Already present — nothing to do.")
            return

        source = next(a for a in DEMENTIA_ASSESSMENTS if "Risk & Safety" in a["phase_label"])
        new_section_source = next(s for s in source["steps"] if "Abuse" in s["title"])

        # Purely additive — appends a new section, doesn't touch any existing
        # field's name, type, or position, so no existing patient answer for
        # any other field on this assessment is affected in any way.
        current_sections.append({
            "id": f"section-{len(current_sections)}",
            "title": new_section_source["title"],
            "fields": new_section_source["fields"],
        })
        flag_modified(version, "fields")
        db.commit()
        print(f"  Added 'Abuse, Neglect & Financial Exploitation Screening' ({len(new_section_source['fields'])} "
              f"questions) to 'Dementia — Risk & Safety Assessment'.")
    finally:
        db.close()


if __name__ == "__main__":
    add_elder_abuse_screening_section()
