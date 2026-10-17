"""
Ingests the Dementia & Alzheimer's Patient Assessment Question Bank into two
places, matching the two real, distinct systems this app already has:

1. Question library items — one QuestionLibraryItem per question, grouped by
   the workbook's own "Assessment Category" column, tagged to the Dementia
   program. These become individually reusable via "Choose from library" in
   the custom assessment builder, the same way kidney/cardiology library
   questions already work.

2. Six real, program-tagged assessment templates — one per workbook "Phase"
   (Onboarding & Intake, Diagnostic & Clinical Assessment, Functional &
   Behavioral Assessment, Risk & Safety Assessment, Psychosocial & Caregiver
   Assessment, Care Planning & Follow-Up), each a multi-step wizard with one
   step per Assessment Category within that phase.

Deliberately created with is_builtin=False, unlike this app's other 132
built-in clinical calculators. The source workbook is explicit that it's a
"structural/content starting point" requiring review by a licensed clinician
before real patient use — is_builtin=True would lock these from editing
entirely, which is the wrong default for content that's meant to be reviewed
and adjusted, not treated as an already-validated instrument.

Also deliberately does NOT reproduce any of the well-known, copyrighted
dementia instruments the source workbook's own Licensing Notes sheet names
(MMSE, MoCA, GDS, Cornell Scale, Zarit Burden Interview, Katz ADL, Lawton-
Brody IADL, FAST, CDR) — the workbook confirms its content is original
questions covering the same clinical domains, not reproductions.

Run with: python3 -m app.seed_dementia
Idempotent — checks by exact name before creating anything.
"""

from app.database import SessionLocal
from app.dementia_seed_data import DEMENTIA_ASSESSMENTS, QLIB_DEMENTIA
from app.models import AssessmentDefinition, AssessmentVersion, AuditLogEntry, Program, QuestionLibraryItem

INTERPRETATION_PROMPTS = {
    "Diagnostic & Clinical Assessment": (
        "Summarize diagnostic status (formally diagnosed vs. suspected vs. unknown, type and stage if known), "
        "medication safety concerns (missed/duplicate doses, psychotropic medications and their indication, "
        "cognitive-enhancing medication use), and the pattern of cognitive findings across orientation, memory, "
        "attention/executive function, language, and visuospatial domains. Flag as needing urgent follow-up if "
        "there are signs of new or acutely worsening disorientation — this can indicate delirium from an acute "
        "medical cause rather than baseline dementia progression, and should prompt medical evaluation rather "
        "than being attributed to dementia by default. Also flag any history of missed doses, duplicate doses, "
        "or medication errors as a medication-safety concern warranting a pharmacist consult or management "
        "intervention."
    ),
    "Functional & Behavioral Assessment": (
        "Summarize the overall level of assistance needed for basic ADLs and instrumental ADLs, and highlight "
        "any behavioral or psychological symptoms (BPSD), mood, or anxiety findings that suggest a need for "
        "psychiatric or behavioral-health follow-up. The overall ADL assistance level should be treated as a "
        "primary driver of the level-of-care recommendation. Nonverbal or severely limited expressive "
        "communication status should be flagged clearly, since it means standard self-report tools (like verbal "
        "pain scales) won't be reliable and an alternate assessment approach is needed."
    ),
    "Risk & Safety Assessment": (
        "This section covers fall risk, home safety, pain, nutrition/hydration, sleep, sensory function, and "
        "continence — flag any combination of findings that compounds risk (e.g., a fall-risk finding "
        "combined with a home-safety hazard, or unaddressed pain combined with agitation-type behavioral "
        "symptoms elsewhere in the record) rather than treating each domain in isolation. Untreated pain in "
        "particular can present as agitation or behavioral change in dementia rather than a direct pain "
        "complaint, so a positive pain finding alongside behavioral symptoms noted elsewhere deserves specific "
        "mention as a possible connection, not two unrelated flags."
    ),
    "Psychosocial & Caregiver Assessment": (
        "Summarize caregiver burden and support needs as their own, distinct concern from the patient's own "
        "clinical status — caregiver strain is a real predictor of placement and crisis events in dementia "
        "care, not a secondary detail. Note advance care planning documentation status (or its absence) "
        "clearly, since this affects future decision-making. Reflect any cultural, spiritual, or personal "
        "preferences noted, since these should shape how the rest of the care plan gets delivered, not just "
        "be recorded for their own sake."
    ),
    "Care Planning & Follow-Up": (
        "Synthesize the overall risk stratification and level-of-care recommendation from this section as the "
        "headline finding, supported by the specific goals and reassessment triggers identified. Call out any "
        "reassessment trigger conditions explicitly, since these define when this assessment should be "
        "repeated rather than left as a one-time snapshot."
    ),
}


def seed_dementia_cognitive_screening_index(db):
    """A second, complementary assessment for the same cognitive screening
    content already collected in 'Dementia — Diagnostic & Clinical
    Assessment' — that one stays AI-interpreted and fully editable
    (is_builtin=False), preserving its rich narrative interpretation.
    This one is a real, deterministic, is_builtin=True calculator (see
    app/calculators/dementia_cognitive_screening.py), giving both a
    structured numeric score AND the existing narrative — not a
    replacement for either."""
    existing = db.query(AssessmentDefinition).filter_by(key="dementia_cognitive_screening_index").first()
    if existing:
        print("  Dementia Cognitive Screening Index: already exists, skipped.")
        return

    dementia_program = db.query(Program).filter_by(key="dementia").first()
    diag = next(a for a in DEMENTIA_ASSESSMENTS if "Diagnostic" in a["phase_label"])
    cognitive_sections = [s for s in diag["steps"] if "Cognitive Screening" in s["title"]]

    fields_json = {
        "steps": [{"id": f"section-{i}", "title": s["title"], "fields": s["fields"]} for i, s in enumerate(cognitive_sections)],
        "fields": None,
    }
    total_q = sum(len(s["fields"]) for s in cognitive_sections)

    definition = AssessmentDefinition(
        key="dementia_cognitive_screening_index",
        title="Dementia Cognitive Screening Index",
        category="Dementia",
        program_id=dementia_program.id,
        kind="calculator",
        interaction="wizard",
        blurb=f"A deterministic, numeric cognitive impairment score across {len(cognitive_sections)} domains "
              f"({total_q} questions) — an original screening aid, not the MMSE, MoCA, or any validated instrument.",
        is_builtin=True,
        active_version=1,
    )
    db.add(definition)
    db.commit()

    version = AssessmentVersion(
        assessment_definition_id=definition.id, version_number=1,
        title=definition.title, blurb=definition.blurb, fields=fields_json,
        interpretation_prompt=None,
        created_by="system (dementia cognitive screening calculator)",
    )
    db.add(version)
    db.add(AuditLogEntry(assessment_definition_id=definition.id, action="created", version_number=1, performed_by="system (import)"))
    db.commit()
    print(f"  Created: Dementia Cognitive Screening Index ({len(cognitive_sections)} sections, {total_q} questions, real calculator)")


def seed_dementia():
    db = SessionLocal()
    try:
        dementia_program = db.query(Program).filter_by(key="dementia").first()
        if not dementia_program:
            print("  ERROR: 'dementia' program does not exist yet — run app.seed first (or the program-adding step) before this script.")
            return

        # --- Question library ---
        qlib_created, qlib_skipped = 0, 0
        for block in QLIB_DEMENTIA:
            for q in block["questions"]:
                existing = db.query(QuestionLibraryItem).filter_by(category=block["category"], label=q["label"]).first()
                if existing:
                    qlib_skipped += 1
                    continue
                db.add(QuestionLibraryItem(
                    category=block["category"],
                    program_id=dementia_program.id,
                    label=q["label"],
                    field_type=q["type"],
                    options=q.get("options"),
                ))
                qlib_created += 1
        db.commit()
        print(f"  Question library: {qlib_created} created, {qlib_skipped} already existed and were skipped.")

        # --- Assessment templates ---
        assess_created, assess_skipped = 0, 0
        for a in DEMENTIA_ASSESSMENTS:
            title = f"Dementia — {a['phase_label']}"
            existing = db.query(AssessmentDefinition).filter_by(title=title).first()
            if existing:
                assess_skipped += 1
                continue

            key = "dementia_" + "".join(c if c.isalnum() else "_" for c in a["phase_label"].lower()).strip("_")
            while db.query(AssessmentDefinition).filter_by(key=key).first():
                key += "_2"

            is_wizard = len(a["steps"]) > 1
            fields_json = (
                {"steps": [{"id": f"section-{i}", "title": s["title"], "fields": s["fields"]} for i, s in enumerate(a["steps"])], "fields": None}
                if is_wizard
                else {"steps": None, "fields": a["steps"][0]["fields"] if a["steps"] else []}
            )
            total_q = sum(len(s["fields"]) for s in a["steps"])
            blurb = f"{a['phase_label']} — {len(a['steps'])} sections, {total_q} questions, from the Dementia & Alzheimer's Patient Assessment Question Bank."

            definition = AssessmentDefinition(
                key=key, title=title, category="Dementia", program_id=dementia_program.id,
                kind="structured", interaction="wizard" if is_wizard else "flat",
                blurb=blurb, is_builtin=False, active_version=1,
            )
            db.add(definition)
            db.commit()

            interpretation_prompt = INTERPRETATION_PROMPTS[a["phase_label"]]
            if a["flag_summary"]:
                interpretation_prompt += f"\n\nSpecific clinical guidance from this section's source material: {a['flag_summary']}"

            version = AssessmentVersion(
                assessment_definition_id=definition.id, version_number=1,
                title=title, blurb=blurb, fields=fields_json,
                interpretation_prompt=interpretation_prompt,
                created_by="system (Dementia & Alzheimer's Patient Assessment Question Bank import)",
            )
            db.add(version)
            db.add(AuditLogEntry(assessment_definition_id=definition.id, action="created", version_number=1, performed_by="system (import)"))
            db.commit()
            assess_created += 1
            print(f"    Created: {title} ({len(a['steps'])} sections, {total_q} questions)")

        print(f"  Assessment templates: {assess_created} created, {assess_skipped} already existed and were skipped.")

        seed_dementia_cognitive_screening_index(db)
    finally:
        db.close()


if __name__ == "__main__":
    seed_dementia()
