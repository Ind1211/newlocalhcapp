"""
Seeds the database with realistic dummy data across all 9 tables.

Safe to re-run: Programs are inserted only if they don't already exist (keyed on
`key`), so running this multiple times won't duplicate the foundational rows —
everything else (patients, cases, results) is illustrative test data and just adds
more sample rows each run, which is fine for local development.

Run from the project root, with the venv activated:
    python -m app.seed
"""

from datetime import date, datetime, timezone

from app.database import SessionLocal
from app.kidney_seed_data import KIDNEY_SEED_DATA
from app.cardio_seed_data import CARDIO_SEED_DATA
from app.qlib_seed_data import QLIB_KIDNEY, QLIB_CARDIOLOGY, QLIB_GENERAL
from app.calculators.registry import CALCULATOR_REGISTRY
from app.models import (
    AssessmentDefinition,
    AssessmentResult,
    AssessmentVersion,
    AuditLogEntry,
    Case,
    ClinicalReview,
    Patient,
    PatientProgram,
    Program,
    QuestionLibraryItem,
)


def get_or_create_program(db, key, label, icon):
    existing = db.query(Program).filter_by(key=key).first()
    if existing:
        return existing
    program = Program(key=key, label=label, icon=icon)
    db.add(program)
    db.commit()
    return program


def get_or_create_definition(db, key, **fields):
    existing = db.query(AssessmentDefinition).filter_by(key=key).first()
    if existing:
        return existing
    definition = AssessmentDefinition(key=key, **fields)
    db.add(definition)
    db.commit()
    return definition


def seed():
    db = SessionLocal()

    # --- Programs ---
    kidney = get_or_create_program(db, "kidney", "Kidney", "🫘")
    cardiology = get_or_create_program(db, "cardiology", "Cardiology", "❤️")
    diabetes = get_or_create_program(db, "diabetes", "Diabetes", "🩸")
    dementia = get_or_create_program(db, "dementia", "Dementia", "🧠")

    # --- Assessment definitions (real, verified logic from earlier in this build) ---
    # Keys match app/calculators/registry.py exactly — this is what lets a submitted
    # result actually get computed, not just stored as static data.
    cha2ds2vasc = get_or_create_definition(
        db, "cha2ds2vasc",
        title="CHA2DS2-VASc Score", category="Arrhythmia & anticoagulation",
        program_id=cardiology.id, kind="calculator", is_builtin=True,
    )
    hasbled = get_or_create_definition(
        db, "hasbled",
        title="HAS-BLED Score", category="Arrhythmia & anticoagulation",
        program_id=cardiology.id, kind="calculator", is_builtin=True,
    )
    ckd_staging = get_or_create_definition(
        db, "ckd_staging",
        title="CKD Staging (KDIGO)", category="Screening & staging",
        program_id=kidney.id, kind="calculator", interaction="wizard", is_builtin=True,
    )
    existing_ckd_version = db.query(AssessmentVersion).filter_by(assessment_definition_id=ckd_staging.id).first()
    if not existing_ckd_version:
        db.add(AssessmentVersion(
            assessment_definition_id=ckd_staging.id,
            version_number=1,
            title="CKD Staging (KDIGO)",
            blurb="Adaptive intake computing CKD-EPI 2021 staging and KDIGO risk, with steps that branch based on your answers.",
            fields={
                "steps": [
                    {"id": "demographics", "title": "Patient demographics", "fields": [
                        {"name": "age", "label": "Patient age", "type": "number", "unit": "years", "placeholder": "e.g. 64"},
                        {"name": "sex", "label": "Sex", "type": "pill", "options": [{"value": "female", "label": "Female"}, {"value": "male", "label": "Male"}]},
                        {"name": "reason", "label": "Reason for assessment", "type": "select", "options": [
                            {"value": "screening", "label": "Routine risk-based screening"}, {"value": "incidental", "label": "Incidental abnormal labs"},
                            {"value": "aki_ckd", "label": "Suspected AKI-on-CKD"}, {"value": "referral", "label": "Referral for CKD management"}, {"value": "followup", "label": "Follow-up of known CKD"},
                        ]},
                    ]},
                    {"id": "risk_factors", "title": "Risk factors", "fields": [
                        {"name": "riskFactors", "label": "Select all known risk factors", "type": "checkboxgroup", "options": [
                            {"value": "diabetes", "label": "Diabetes"}, {"value": "hypertension", "label": "Hypertension"}, {"value": "cvd", "label": "Cardiovascular disease"},
                            {"value": "familyHistory", "label": "Family history of kidney failure"}, {"value": "akiHistory", "label": "Prior episode of AKI"},
                            {"value": "stonesRecurrentUTI", "label": "Recurrent UTI / kidney stones"}, {"value": "autoimmune", "label": "Autoimmune disease (e.g. lupus)"},
                            {"value": "nephrotoxicMeds", "label": "Chronic nephrotoxic medication use"}, {"value": "obesity", "label": "Obesity"}, {"value": "smoking", "label": "Current smoker"},
                            {"value": "none", "label": "No known risk factors"},
                        ]},
                    ]},
                    {"id": "labs_egfr", "title": "Kidney function \u2014 eGFR", "fields": [
                        {"name": "knownEgfr", "label": "Do you have a recent eGFR result?", "type": "pill", "options": [{"value": "yes", "label": "Yes, I have a value"}, {"value": "no", "label": "No, calculate from creatinine"}]},
                        {"name": "egfrValue", "label": "Reported eGFR", "type": "number", "unit": "mL/min/1.73m\u00b2", "placeholder": "e.g. 52"},
                        {"name": "scrValue", "label": "Serum creatinine", "type": "number", "unit": "mg/dL", "placeholder": "e.g. 1.4"},
                        {"name": "priorEgfr", "label": "Prior eGFR (>90 days ago, optional)", "type": "number", "unit": "mL/min/1.73m\u00b2", "placeholder": "e.g. 68"},
                        {"name": "priorEgfrMonthsAgo", "label": "Months ago", "type": "number", "placeholder": "months ago"},
                    ]},
                    {"id": "labs_acr", "title": "Albuminuria \u2014 urine ACR", "fields": [
                        {"name": "knownAcr", "label": "Recent urine ACR available?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No, use dipstick instead"}]},
                        {"name": "acrValue", "label": "Urine ACR", "type": "number", "unit": "mg/g", "placeholder": "e.g. 45"},
                        {"name": "dipstickProtein", "label": "Urine dipstick protein (surrogate)", "type": "select", "options": [
                            {"value": "negative", "label": "Negative"}, {"value": "trace", "label": "Trace"}, {"value": "1+", "label": "1+"}, {"value": "2+", "label": "2+"}, {"value": "3+", "label": "3+"},
                        ]},
                    ]},
                    {"id": "vitals", "title": "Vitals & blood pressure", "fields": [
                        {"name": "sbp", "label": "Systolic BP", "type": "number", "unit": "mmHg"},
                        {"name": "dbp", "label": "Diastolic BP", "type": "number", "unit": "mmHg"},
                        {"name": "antihtnCount", "label": "Antihypertensive medication classes used", "type": "number", "placeholder": "0\u20136"},
                        {"name": "weightTrend", "label": "Recent weight trend", "type": "select", "options": [{"value": "stable", "label": "Stable"}, {"value": "gain", "label": "Gaining"}, {"value": "loss", "label": "Losing"}]},
                        {"name": "edemaExam", "label": "Peripheral edema present on exam?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                    ]},
                    {"id": "diabetes_detail", "title": "Diabetes detail (shown if diabetes selected)", "fields": [
                        {"name": "hba1c", "label": "Most recent HbA1c", "type": "number", "unit": "%", "placeholder": "e.g. 7.8"},
                        {"name": "sglt2i", "label": "Currently on an SGLT2 inhibitor?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                        {"name": "insulin", "label": "On insulin?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                    ]},
                    {"id": "cv_detail", "title": "Cardiovascular detail (shown if CVD or older with HTN)", "fields": [
                        {"name": "statin", "label": "Currently on a statin?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                        {"name": "priorMiStroke", "label": "Prior MI or stroke?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                    ]},
                    {"id": "symptoms", "title": "Symptoms (shown if CKD suspected)", "fields": [
                        {"name": "symptoms", "label": "Select any reported symptoms", "type": "checkboxgroup", "options": [
                            {"value": "fatigue", "label": "Fatigue"}, {"value": "pruritus", "label": "Itching (pruritus)"}, {"value": "nauseaAppetite", "label": "Nausea / poor appetite"},
                            {"value": "edemaSymptom", "label": "Swelling reported by patient"}, {"value": "nocturia", "label": "Nocturia"}, {"value": "foamyUrine", "label": "Foamy urine"},
                            {"value": "decreasedUrineOutput", "label": "Decreased urine output"}, {"value": "muscleCramps", "label": "Muscle cramps"}, {"value": "none", "label": "No symptoms reported"},
                        ]},
                    ]},
                    {"id": "medication_safety", "title": "Medication safety", "fields": [
                        {"name": "nsaidUse", "label": "Regular NSAID use?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                        {"name": "recentContrast", "label": "Recent IV contrast exposure?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                        {"name": "metforminUse", "label": "On metformin?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                        {"name": "otherNephrotoxic", "label": "Other nephrotoxic exposure (optional)", "type": "text", "placeholder": "e.g. aminoglycoside course, lithium"},
                    ]},
                    {"id": "labs_complications", "title": "Complication labs (shown if G3b or worse)", "fields": [
                        {"name": "hemoglobin", "label": "Hemoglobin", "type": "number", "unit": "g/dL", "placeholder": "e.g. 11.2"},
                        {"name": "potassium", "label": "Potassium", "type": "number", "unit": "mmol/L", "placeholder": "e.g. 4.8"},
                        {"name": "bicarbonate", "label": "Bicarbonate", "type": "number", "unit": "mmol/L", "placeholder": "e.g. 22"},
                        {"name": "calcium", "label": "Calcium", "type": "number", "unit": "mg/dL", "placeholder": "e.g. 9.1"},
                        {"name": "phosphate", "label": "Phosphate", "type": "number", "unit": "mg/dL", "placeholder": "e.g. 4.2"},
                        {"name": "pth", "label": "PTH", "type": "number", "unit": "pg/mL", "placeholder": "e.g. 65"},
                    ]},
                    {"id": "advanced_care", "title": "Advanced CKD planning (shown if G4\u2013G5)", "fields": [
                        {"name": "activeReferral", "label": "Nephrology referral currently active?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                        {"name": "transplantDiscussed", "label": "Transplant candidacy discussed?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                        {"name": "dialysisPlanning", "label": "Dialysis / vascular access planning stage", "type": "select", "options": [
                            {"value": "none", "label": "Not yet started"}, {"value": "education", "label": "Patient education started"}, {"value": "access", "label": "Access placement underway/complete"}, {"value": "active", "label": "Currently on dialysis"},
                        ]},
                        {"name": "advanceCarePlanning", "label": "Advance care planning discussed?", "type": "pill", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                    ]},
                ],
                "fields": None,
            },
            interpretation_prompt="AI-generated narrative care plan — not yet implemented; the deterministic KDIGO staging and referral-flag logic is fully computed by the backend calculator.",
            created_by="Built with the KDIGO 2012 CKD classification grid and CKD-EPI 2021 eGFR formula",
        ))
        db.commit()

    # --- All 75 real kidney assessments from the JS checkpoint ---
    # Only the 11 with a real Python calculator (see app/calculators/kidney.py, each
    # cross-verified against the original JS logic) will actually compute a result if
    # submitted — the rest are genuinely browsable with real fields, but submitting
    # against them correctly returns a clean 501 until their logic is ported too.
    kidney_definitions_created = 0
    for key, info in KIDNEY_SEED_DATA.items():
        definition = get_or_create_definition(
            db, key,
            title=info["title"], category=info["category"],
            program_id=kidney.id, kind=info["kind"], interaction=info["interaction"],
            blurb=info["blurb"], is_builtin=True,
        )
        existing_version = db.query(AssessmentVersion).filter_by(assessment_definition_id=definition.id).first()
        if not existing_version:
            version = AssessmentVersion(
                assessment_definition_id=definition.id,
                version_number=1,
                title=info["title"],
                blurb=info["blurb"],
                fields={"fields": info["fields"], "steps": info["steps"]},
                created_by="Ported from JS checkpoint",
            )
            db.add(version)
            db.commit()
        kidney_definitions_created += 1

    # --- All 56 real cardiology assessments from the JS checkpoint ---
    # cha2ds2vasc, hasbled, and map_calc were already seeded individually above with
    # their own get_or_create_definition calls — this loop safely no-ops for those 3
    # (get_or_create_definition returns the existing row rather than duplicating) and
    # creates the remaining 53, all with real, cross-verified calculator logic.
    cardio_definitions_created = 0
    for key, info in CARDIO_SEED_DATA.items():
        definition = get_or_create_definition(
            db, key,
            title=info["title"], category=info["category"],
            program_id=cardiology.id, kind=info["kind"], interaction=info["interaction"],
            blurb=info["blurb"], is_builtin=True,
        )
        existing_version = db.query(AssessmentVersion).filter_by(assessment_definition_id=definition.id).first()
        if not existing_version:
            version = AssessmentVersion(
                assessment_definition_id=definition.id,
                version_number=1,
                title=info["title"],
                blurb=info["blurb"],
                fields={"fields": info["fields"], "steps": info["steps"]},
                created_by="Ported from JS checkpoint",
            )
            db.add(version)
            db.commit()
        cardio_definitions_created += 1

    # --- Versions, with real field definitions matching the actual field shapes ---
    cha_v1 = AssessmentVersion(
        assessment_definition_id=cha2ds2vasc.id,
        version_number=1,
        title="CHA2DS2-VASc Score",
        fields={
            "chf": {"type": "pill", "options": ["yes", "no"]},
            "htn": {"type": "pill", "options": ["yes", "no"]},
            "age": {"type": "number"},
            "sex": {"type": "pill", "options": ["male", "female"]},
        },
        created_by="Dr. Chen, cardiology",
    )
    db.add(cha_v1)
    db.commit()

    # --- Patients & cases — a fifth and sixth example distinct from the four in the
    # main roster below: this one demonstrates a patient with BOTH kidney and
    # cardiology involvement on a single case, which none of the four single-pathway
    # examples show. Previously created with only internal_label and no name — the
    # exact cause of two blank "?" tiles appearing in the patient list, since name
    # is required for a patient to display correctly. ---
    patient1 = db.query(Patient).filter_by(mrn="REN-29102").first()
    if not patient1:
        patient1 = Patient(name="Diane Okafor", dob=date(1958, 4, 12), mrn="REN-29102", care_pathway="Cardiorenal (CKD + AFib)")
        db.add(patient1)
        db.commit()
        # The real fix, demonstrated: two actual program associations, not one
        # hacky combined label — this patient is genuinely in both.
        for key in ["kidney", "cardiology"]:
            program = db.query(Program).filter_by(key=key).first()
            if program:
                db.add(PatientProgram(patient_id=patient1.id, program_id=program.id))
        db.commit()
    patient2 = db.query(Patient).filter_by(mrn="REN-30044").first()
    if not patient2:
        patient2 = Patient(name="Harold Vance", dob=date(1970, 12, 3), mrn="REN-30044", care_pathway="CKD Stage 3")
        db.add(patient2)
        db.commit()
        kidney_program = db.query(Program).filter_by(key="kidney").first()
        if kidney_program:
            db.add(PatientProgram(patient_id=patient2.id, program_id=kidney_program.id))
        db.commit()
    case1 = db.query(Case).filter_by(patient_id=patient1.id).first()
    if not case1:
        case1 = Case(patient_id=patient1.id, label=f"{patient1.name} — primary")
        db.add(case1)
        db.commit()
    case2 = db.query(Case).filter_by(patient_id=patient2.id).first()
    if not case2:
        case2 = Case(patient_id=patient2.id, label=f"{patient2.name} — primary")
        db.add(case2)
        db.commit()

    # --- Results — using the ACTUAL verified CHA2DS2-VASc scoring from earlier testing ---
    # 78-year-old woman with hypertension: HTN(1) + age>=75(2) + female(1) = 4
    result1 = AssessmentResult(
        case_id=case1.id,
        assessment_definition_id=cha2ds2vasc.id,
        version_used=1,
        answers={"chf": "no", "htn": "yes", "age": "78", "sex": "female"},
        result={
            "headline": "CHA2DS2-VASc = 4 - anticoagulation typically recommended",
            "headlineSeverity": "warning",
            "metrics": [{"label": "CHA2DS2-VASc score", "value": 4, "unit": "/ 9"}],
            "flags": [{"text": "Consider oral anticoagulation", "severity": "warning"}],
            "notes": "Weigh alongside bleeding risk (e.g. HAS-BLED).",
        },
    )
    db.add(result1)
    db.commit()

    # --- Clinical review — a real, durable record, unlike the old localStorage version ---
    review1 = ClinicalReview(
        assessment_definition_id=cha2ds2vasc.id,
        reviewer_name="Dr. Chen, cardiology",
        notes="Confirmed scoring against 2023 ESC AF guidelines.",
    )
    db.add(review1)

    # --- Audit log — created + edited, mirroring the JS app's audit trail ---
    audit1 = AuditLogEntry(
        assessment_definition_id=cha2ds2vasc.id,
        action="created",
        version_number=1,
        performed_by="Dr. Chen, cardiology",
    )
    db.add(audit1)

    # --- Question library — the real kidney and cardiology sets from the checkpoint ---
    # Safe to re-run: checks for an existing item with the same category+label before
    # inserting, so this won't duplicate on a second seed run.
    qlib_created = 0
    for category_block, program in [(QLIB_KIDNEY, kidney), (QLIB_CARDIOLOGY, cardiology), (QLIB_GENERAL, None)]:
        for cat in category_block:
            for q in cat["questions"]:
                existing = (
                    db.query(QuestionLibraryItem)
                    .filter_by(category=cat["category"], label=q["label"])
                    .first()
                )
                if existing:
                    continue
                db.add(QuestionLibraryItem(
                    category=cat["category"],
                    program_id=program.id if program else None,
                    label=q["label"],
                    field_type=q["type"],
                    options=q.get("options"),
                ))
                qlib_created += 1
    db.commit()

    print("Seed complete:")
    print(f"  Programs: kidney={kidney.id}, cardiology={cardiology.id}, diabetes={diabetes.id}, dementia={dementia.id}")
    print(f"  Assessment definitions: {cha2ds2vasc.id}, {hasbled.id}, {ckd_staging.id}")
    print(f"  Patients/cases: {patient1.id}/{case1.id}, {patient2.id}/{case2.id}")
    print(f"  Result: {result1.id} (headline: {result1.result['headline']})")
    print(f"  Kidney assessments seeded: {kidney_definitions_created} (of 75 real definitions)")
    calc_covered = [k for k in KIDNEY_SEED_DATA if k in CALCULATOR_REGISTRY]
    print(f"  Of those, {len(calc_covered)} have a real, verified calculator")
    print(f"  Cardiology assessments seeded: {cardio_definitions_created} (of 56 real definitions)")
    cardio_calc_covered = [k for k in CARDIO_SEED_DATA if k in CALCULATOR_REGISTRY]
    print(f"  Of those, {len(cardio_calc_covered)} have a real, verified calculator")
    print(f"  TOTAL migrated assessments with real calculator logic: {len(calc_covered) + len(cardio_calc_covered) + 1}")  # +1 for ckd_staging, not in KIDNEY_SEED_DATA

    # --- Dummy patient roster, matching the wireframe's four example patients ---
    # Uses real built-in calculators relevant to each patient's stated care pathway,
    # rather than porting the wireframe's own fictional 4-point symptom-scale system
    # — these produce genuinely correct clinical results, not placeholder text.
    from app.calculators.registry import get_calculator
    from app.models import AssignedAssessment
    from app.routers.patients import get_or_create_primary_case

    def get_or_create_patient(mrn, name, dob, care_pathway, program_keys=()):
        patient = db.query(Patient).filter_by(mrn=mrn).first()
        if patient:
            return patient
        patient = Patient(name=name, dob=dob, mrn=mrn, care_pathway=care_pathway)
        db.add(patient)
        db.commit()
        for key in program_keys:
            program = db.query(Program).filter_by(key=key).first()
            if program:
                db.add(PatientProgram(patient_id=patient.id, program_id=program.id))
        db.commit()
        return patient

    def assign_and_maybe_complete(patient, key, title_override, source, scheduled_date, answers=None, draft_answers=None):
        case = get_or_create_primary_case(db, patient)
        definition = db.query(AssessmentDefinition).filter_by(key=key).first()
        if not definition:
            return
        existing = db.query(AssignedAssessment).filter_by(case_id=case.id, assessment_definition_id=definition.id).first()
        if existing:
            return
        assigned = AssignedAssessment(
            case_id=case.id, assessment_definition_id=definition.id,
            title_override=title_override, source=source, scheduled_date=scheduled_date,
            draft_answers=draft_answers,
        )
        db.add(assigned)
        db.commit()
        if answers is not None:
            calculator = get_calculator(key)
            if calculator:
                result = calculator.compute(answers)
                db.add(AssessmentResult(
                    case_id=case.id, assessment_definition_id=definition.id,
                    version_used=definition.active_version, answers=answers, result=result,
                ))
                db.commit()

    # One sample custom assessment, matching the wireframe's own "Custom Check-in —
    # Symptom Burden" example, created through the same pathway a real user would use.
    # --- Basic Patient Intake — mandatory, general/cross-cutting, ported directly
    # from the checkpoint's 4-step wizard. Every new patient gets this auto-assigned
    # at creation (see patients.py's create_patient), and completing it drives the
    # suggested-pathway auto-assignment logic in results.py. ---
    intake_def = db.query(AssessmentDefinition).filter_by(key="basic_intake").first()
    if not intake_def:
        intake_def = AssessmentDefinition(
            key="basic_intake", title="Basic Patient Intake", category="Basic Intake",
            program_id=None, kind="structured", interaction="wizard",
            blurb="Start here — a quick intake that suggests which assessments to complete next, in order.",
            is_builtin=True, active_version=1,
        )
        db.add(intake_def)
        db.commit()

    yn = [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]
    intake_fields = {"fields": None, "steps": [
        {"id": "reason", "title": "Reason for visit", "fields": [
            # No "programs" tag — always relevant regardless of clinical program.
            {"name": "chiefComplaint", "label": "What is the main reason for this visit today?", "type": "textarea", "required": True},
        ]},
        {"id": "conditions", "title": "Known conditions", "fields": [
            {"name": "knownCkd", "label": "Known chronic kidney disease?", "type": "pill", "options": yn, "required": True, "programs": ["kidney"]},
            {"name": "onDialysis", "label": "Currently on dialysis?", "type": "pill", "options": yn, "required": True, "programs": ["kidney"]},
            {"name": "dialysisType", "label": "Which type of dialysis?", "type": "pill",
             "options": [{"value": "Hemodialysis", "label": "Hemodialysis"}, {"value": "Peritoneal dialysis", "label": "Peritoneal dialysis"}],
             "required": False, "show_only_if": {"field": "onDialysis", "equals": "yes"}, "programs": ["kidney"]},
            {"name": "kidneyTransplant", "label": "Kidney transplant recipient?", "type": "pill", "options": yn, "required": True, "programs": ["kidney"]},
            {"name": "knownHf", "label": "Known heart failure?", "type": "pill", "options": yn, "required": True, "programs": ["cardiology"]},
            {"name": "knownCad", "label": "Known coronary artery disease or prior heart attack?", "type": "pill", "options": yn, "required": True, "programs": ["cardiology"]},
            {"name": "knownArrhythmia", "label": "Known arrhythmia (irregular heartbeat)?", "type": "pill", "options": yn, "required": True, "programs": ["cardiology"]},
            {"name": "hasDevice", "label": "Has a pacemaker or implantable defibrillator?", "type": "pill", "options": yn, "required": True, "programs": ["cardiology"]},
            {"name": "knownValveDisease", "label": "Known heart valve disease?", "type": "pill", "options": yn, "required": True, "programs": ["cardiology"]},
            # Diabetes is a leading cause of both CKD and cardiovascular disease —
            # the routing engine itself treats it as triggering both kidney and
            # cardiology suggestions, so it stays visible for either program.
            {"name": "diabetes", "label": "Diabetes?", "type": "pill", "options": yn, "required": True, "programs": ["kidney", "cardiology"]},
            {"name": "pregnant", "label": "Currently pregnant?", "type": "pill", "options": yn, "required": True, "programs": ["kidney", "cardiology"]},
            {"name": "knownDementia", "label": "Known dementia or Alzheimer's diagnosis?", "type": "pill", "options": yn, "required": True, "programs": ["dementia"]},
            # Deliberately separate from knownDementia — this catches suspected-but-
            # not-yet-diagnosed cognitive decline, which the source question bank's
            # own diagnostic-status question treats as a distinct category from a
            # formal diagnosis. Family/caregiver-reported changes are often the
            # first real signal, before any clinical diagnosis exists at all.
            {"name": "memoryConcerns", "label": "Have family or caregivers noticed memory or thinking changes?", "type": "pill", "options": yn, "required": True, "programs": ["dementia"]},
            # Hypertension is a leading cause of both CKD and cardiovascular disease
            # — same shared-program pattern as diabetes above — yet had no intake
            # screening question at all despite diabetes already having one.
            {"name": "knownHtn", "label": "Known high blood pressure (hypertension)?", "type": "pill", "options": yn, "required": True, "programs": ["kidney", "cardiology"]},
            {"name": "smokingStatus", "label": "Smoking status", "type": "pill",
             "options": [{"value": "never", "label": "Never smoked"}, {"value": "former", "label": "Former smoker"}, {"value": "current", "label": "Current smoker"}],
             "required": True, "programs": ["cardiology"]},
            {"name": "regularNsaidUse", "label": "Regular use of NSAIDs (ibuprofen, naproxen, etc.)?", "type": "pill", "options": yn, "required": True, "programs": ["kidney"]},
            {"name": "familyHistoryKidneyDisease", "label": "Family history of kidney disease?", "type": "pill", "options": yn, "required": True, "programs": ["kidney"]},
            {"name": "familyHistoryHeartDisease", "label": "Family history of heart disease or sudden cardiac death?", "type": "pill", "options": yn, "required": True, "programs": ["cardiology"]},
            {"name": "functionalDecline", "label": "Difficulty with daily activities such as bathing, dressing, or managing medications?", "type": "pill", "options": yn, "required": True, "programs": ["dementia"]},
            {"name": "wanderingHistory", "label": "Any history of wandering or getting lost?", "type": "pill", "options": yn, "required": True, "programs": ["dementia"]},
            {"name": "livesAlone", "label": "Does the patient currently live alone?", "type": "pill", "options": yn, "required": True, "programs": ["dementia"]},
        ]},
        {"id": "symptoms", "title": "Today's symptoms", "fields": [
            {"name": "symptomChestPain", "label": "Chest pain or pressure today?", "type": "pill", "options": yn, "required": True, "programs": ["cardiology"]},
            # Swelling and shortness of breath are genuinely ambiguous between
            # heart failure and kidney disease — the routing engine suggests both
            # hf_staging and ckd_staging from these same answers, so filtering
            # either one out for a single-program patient would silently break
            # that cross-program detection.
            {"name": "symptomSob", "label": "Shortness of breath today?", "type": "pill", "options": yn, "required": True, "programs": ["kidney", "cardiology"]},
            {"name": "symptomSwelling", "label": "Swelling in legs, ankles, or abdomen today?", "type": "pill", "options": yn, "required": True, "programs": ["kidney", "cardiology"]},
            {"name": "symptomSyncope", "label": "Fainting, near-fainting, or dizziness today?", "type": "pill", "options": yn, "required": True, "programs": ["cardiology"]},
            {"name": "symptomPalpitations", "label": "Palpitations (racing or irregular heartbeat) today?", "type": "pill", "options": yn, "required": True, "programs": ["cardiology"]},
            {"name": "symptomUrineChange", "label": "A significant change in urination today?", "type": "pill", "options": yn, "required": True, "programs": ["kidney"]},
            # A today-focused acute-change question, distinct from memoryConcerns
            # above (which asks about a general, ongoing pattern) — new or
            # worsening confusion specifically can signal delirium requiring
            # urgent medical evaluation, not just routine cognitive screening.
            {"name": "symptomConfusion", "label": "New or worsening confusion today?", "type": "pill", "options": yn, "required": True, "programs": ["dementia"]},
        ]},
        {"id": "recent", "title": "Recent care", "fields": [
            # No "programs" tag — always relevant regardless of clinical program.
            {"name": "recentHospitalization", "label": "Any hospitalization in the past 30 days?", "type": "pill", "options": yn, "required": True},
        ]},
    ]}

    intake_version = (
        db.query(AssessmentVersion)
        .filter_by(assessment_definition_id=intake_def.id, version_number=intake_def.active_version)
        .first()
    )
    if intake_version:
        # Refresh in place — never a new version, since basic_intake is built-in
        # infrastructure, not user-editable content someone might want history for.
        # This is exactly what was missing before: without this, a field-tag change
        # (like adding "programs") would sit correctly in this file forever while
        # every real deployment kept serving the version seeded before the change.
        intake_version.fields = intake_fields
    else:
        db.add(AssessmentVersion(
            assessment_definition_id=intake_def.id, version_number=1,
            title="Basic Patient Intake", fields=intake_fields,
            created_by="Ported from JS checkpoint",
        ))
    db.commit()

    custom_key = "custom_symptom_burden_checkin"
    custom_def = db.query(AssessmentDefinition).filter_by(key=custom_key).first()
    if not custom_def:
        custom_def = AssessmentDefinition(
            key=custom_key, title="Symptom Burden Check-in", category="Custom",
            program_id=None, kind="structured", interaction="flat",
            blurb="Weekly symptom burden self-check.", is_builtin=False, active_version=1,
        )
        db.add(custom_def)
        db.commit()
        db.add(AssessmentVersion(
            assessment_definition_id=custom_def.id, version_number=1,
            title="Symptom Burden Check-in",
            fields={"steps": None, "fields": [
                {"name": "fatigue", "label": "Fatigue or lack of energy", "type": "pill",
                 "options": [{"value": "0", "label": "Not at all"}, {"value": "1", "label": "Several days"},
                             {"value": "2", "label": "More than half the days"}, {"value": "3", "label": "Nearly every day"}],
                 "required": True, "show_only_if": None},
                {"name": "itching", "label": "Itching (pruritus)", "type": "pill",
                 "options": [{"value": "0", "label": "Not at all"}, {"value": "1", "label": "Several days"},
                             {"value": "2", "label": "More than half the days"}, {"value": "3", "label": "Nearly every day"}],
                 "required": True, "show_only_if": None},
            ]},
            interpretation_prompt="Flag as elevated symptom burden if either answer is 'More than half the days' or 'Nearly every day'; otherwise routine.",
            created_by="Dr. Renata Osei",
        ))
        db.commit()

    walter = get_or_create_patient("REN-30215", "Walter Higgins", date(1965, 9, 8), "In-Center Hemodialysis", ["kidney"])
    assign_and_maybe_complete(walter, "hd_adequacy", None, "template", date(2026, 7, 28),
        answers={"preBUN": "80", "postBUN": "25", "sessionHours": "3.5", "ufVolume": "2.5", "postWeight": "70"})
    assign_and_maybe_complete(walter, custom_key, "Custom Check-in — Symptom Burden", "custom", date(2026, 8, 1),
        draft_answers={"fatigue": "2"})  # itching left unanswered — a real, genuine In Progress example

    priya = get_or_create_patient("REN-30402", "Priya Nandakumar", date(1975, 11, 2), "Post-Transplant", ["kidney"])
    assign_and_maybe_complete(priya, "bk_virus_nephropathy", "Post-Transplant Recovery Check", "template", date(2026, 7, 30),
        answers={"biopsySv40Positive": "no", "bkViremiaCopiesPerMl": "500", "recentAntirejectionTx": "no", "risingCreatinine": "no"})
    assign_and_maybe_complete(priya, "posttx_monitoring", "Post-Transplant Recovery Check", "template", date(2026, 8, 3))

    elias = get_or_create_patient("REN-29888", "Elias Thornton", date(1960, 2, 27), "Peritoneal Dialysis", ["kidney", "cardiology"])
    assign_and_maybe_complete(elias, "pd_adequacy", "KDQOL Symptom & Burden Screening", "template", date(2026, 7, 25),
        answers={"age": "65", "sex": "male", "heightCm": "175", "weightKg": "78", "peritonealUreaClearance": "50", "residualRenalUreaClearance": "8"})
    assign_and_maybe_complete(elias, "pd_peritonitis", "KDQOL Symptom & Burden Screening", "template", date(2026, 8, 2))

    sofia = get_or_create_patient("REN-30510", "Sofia Brennan", date(2001, 7, 19), "CKD Stage 4", ["kidney"])
    assign_and_maybe_complete(sofia, "ckd_staging", "CKD Diet & Fluid Management", "template", date(2026, 8, 4))

    print(f"  Dummy patients seeded: Walter Higgins, Priya Nandakumar, Elias Thornton, Sofia Brennan")
    print(f"  Question library items seeded this run: {qlib_created} (66 kidney + 117 cardiology + 309 general = 492 total when run fresh)")

    db.close()


if __name__ == "__main__":
    seed()
