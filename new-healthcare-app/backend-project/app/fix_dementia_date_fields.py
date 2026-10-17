"""
One-time fix for anyone who already ran app.seed_dementia before this
correction: "Date" question-bank fields (date of last eye examination, date
of last hearing examination, and two others) were mapped to a plain text
field, a deliberate simplification from before this app's assessment builder
had a real date field type. Updates the already-created assessment versions
in place to use the real "date" type instead.

Field-level safety, not all-or-nothing at the whole-assessment level: an
assessment merely being assigned to a patient poses no risk at all if
nothing has actually been answered yet for the specific date field being
changed. This mutates the CURRENT, live fields JSON in place, converting
each individual date-type-candidate field to "date" one at a time — a field
with no real conflicting stored answer gets updated regardless of whether a
completely different field in the very same assessment does have one. Only
the specific field(s) with a real, non-empty, non-YYYY-MM-DD stored answer
(in AssignedAssessment.draft_answers or AssessmentResult.answers) are left
as "text" for manual review — the rest of that same assessment still gets
fixed.

Run with: python3 -m app.fix_dementia_date_fields
Safe to run more than once — reports "already correct" if nothing changed.
"""

import re

from sqlalchemy.orm.attributes import flag_modified

from app.database import SessionLocal
from app.dementia_seed_data import DEMENTIA_ASSESSMENTS
from app.models import AssessmentDefinition, AssessmentResult, AssignedAssessment, AssessmentVersion

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _real_conflicting_value(db, definition_id, field_name: str) -> str | None:
    """The first real, stored, non-ISO-format value found for this exact
    field name — or None if nothing conflicts. Checked by field name
    specifically, not "does any answer dict exist at all" — a draft with
    other fields filled in but not this one is not a conflict."""
    assignments = db.query(AssignedAssessment).filter_by(assessment_definition_id=definition_id).all()
    for a in assignments:
        if a.draft_answers and field_name in a.draft_answers:
            value = a.draft_answers[field_name]
            if value and not _ISO_DATE_RE.match(str(value)):
                return str(value)

    results = db.query(AssessmentResult).filter_by(assessment_definition_id=definition_id).all()
    for r in results:
        if r.answers and field_name in r.answers:
            value = r.answers[field_name]
            if value and not _ISO_DATE_RE.match(str(value)):
                return str(value)

    return None


def fix_dementia_date_fields():
    db = SessionLocal()
    try:
        fields_updated, fields_already_correct, fields_skipped = 0, 0, 0
        for a in DEMENTIA_ASSESSMENTS:
            title = f"Dementia — {a['phase_label']}"
            definition = db.query(AssessmentDefinition).filter_by(title=title).first()
            if not definition:
                continue

            version = db.query(AssessmentVersion).filter_by(assessment_definition_id=definition.id, version_number=definition.active_version).first()
            if not version or not version.fields:
                continue

            # The set of field names this phase's source data says should be
            # "date" — used to find the matching field(s) inside whatever the
            # CURRENT, live fields JSON actually is right now, not to
            # overwrite the whole structure wholesale.
            intended_date_names = {f["name"] for step in a["steps"] for f in step["fields"] if f["type"] == "date"}
            if not intended_date_names:
                continue

            current_fields = version.fields
            sections = current_fields.get("steps") or [{"fields": current_fields.get("fields") or []}]

            any_change = False
            for section in sections:
                for field in section.get("fields", []):
                    if field.get("name") not in intended_date_names:
                        continue
                    if field.get("type") == "date":
                        fields_already_correct += 1
                        continue

                    conflict = _real_conflicting_value(db, definition.id, field["name"])
                    if conflict:
                        print(f"  SKIPPING field '{field['label']}' on '{title}': a real stored answer "
                              f"(\"{conflict}\") isn't in YYYY-MM-DD format. Review this specific answer "
                              f"manually rather than changing the field type out from under it.")
                        fields_skipped += 1
                        continue

                    field["type"] = "date"
                    any_change = True
                    fields_updated += 1
                    print(f"  Updated field '{field['label']}' on '{title}' — now uses the real date picker.")

            if any_change:
                # Reassigning version.fields to the very same object we just
                # mutated does NOT register as a change to SQLAlchemy's dirty
                # checking for a JSONB column — it compares object identity,
                # not content, and the reference never changed. flag_modified
                # is the correct, explicit way to mark it dirty so db.commit()
                # actually writes it, rather than silently doing nothing.
                flag_modified(version, "fields")
                db.commit()

        print(f"\n  {fields_updated} field(s) updated, {fields_already_correct} already correct, "
              f"{fields_skipped} field(s) skipped for safety.")
    finally:
        db.close()


if __name__ == "__main__":
    fix_dementia_date_fields()
