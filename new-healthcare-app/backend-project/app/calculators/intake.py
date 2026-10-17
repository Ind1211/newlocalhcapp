"""
The mandatory basic patient intake and its routing engine — ported directly from
the checkpoint's INTAKE_ROUTING_RULES and computeIntakePathway(). The one change
from the original: 'ckd' is renamed to 'ckd_staging' throughout, matching the key
this backend actually uses for the flagship CKD wizard.
"""

from app.calculators.base import Calculator


def _yes(a: dict, key: str) -> bool:
    return a.get(key) == "yes"


# Each rule: (id, condition(answers) -> bool, [(module_id, mandatory, priority, reason), ...])
# Priorities and mandatory/optional flags are copied exactly from the verified
# original — these aren't arbitrary, they encode real clinical urgency ordering
# (e.g. chest pain triage at priority 1-2, ASCVD risk-enhancer notes at 22-23).
INTAKE_ROUTING_RULES = [
    ("chest_pain", lambda a: _yes(a, "symptomChestPain"), [
        ("heart_score", True, 1, "Chest pain today requires immediate risk stratification"),
        ("timi_unstable", True, 2, "Further risk stratification for suspected acute coronary syndrome"),
    ]),
    ("sob", lambda a: _yes(a, "symptomSob"), [
        ("ef_classification", True, 3, "Shortness of breath warrants assessment of cardiac function"),
        ("hf_staging", True, 4, "Shortness of breath warrants heart failure staging"),
    ]),
    ("swelling", lambda a: _yes(a, "symptomSwelling"), [
        ("hf_staging", True, 4, "Swelling can indicate heart failure"),
        ("ckd_staging", True, 5, "Swelling can indicate kidney dysfunction"),
    ]),
    ("syncope", lambda a: _yes(a, "symptomSyncope"), [
        ("sfsr", True, 1, "Fainting or dizziness requires an immediate safety screen"),
        ("orthostatic_hypotension", True, 2, "Rule out orthostatic causes of fainting or dizziness"),
        ("vasovagal_features", False, 20, "Helps characterize a likely benign cause if the safety screen is negative"),
    ]),
    ("palpitations", lambda a: _yes(a, "symptomPalpitations"), [
        ("afib_type", False, 18, "Characterize the arrhythmia pattern if one is confirmed"),
        ("cha2ds2vasc", False, 19, "Assess stroke risk if an arrhythmia is confirmed"),
    ]),
    ("urine_change", lambda a: _yes(a, "symptomUrineChange"), [
        ("aki_staging", True, 5, "A change in urination today warrants screening for acute kidney injury"),
    ]),
    ("known_ckd", lambda a: _yes(a, "knownCkd"), [
        ("ckd_staging", True, 6, "Baseline staging for known chronic kidney disease"),
    ]),
    ("dialysis_hd", lambda a: _yes(a, "onDialysis") and a.get("dialysisType") != "Peritoneal dialysis", [
        ("hd_adequacy", True, 7, "Routine hemodialysis adequacy check"),
    ]),
    ("dialysis_pd", lambda a: _yes(a, "onDialysis") and a.get("dialysisType") == "Peritoneal dialysis", [
        ("pd_adequacy", True, 7, "Routine peritoneal dialysis adequacy check"),
    ]),
    ("transplant", lambda a: _yes(a, "kidneyTransplant"), [
        ("posttx_monitoring", True, 7, "Routine post-transplant monitoring"),
    ]),
    ("known_hf", lambda a: _yes(a, "knownHf"), [
        ("hf_staging", True, 4, "Baseline staging for known heart failure"),
        ("ef_classification", True, 3, "Baseline ejection fraction classification for known heart failure"),
    ]),
    ("known_arrhythmia", lambda a: _yes(a, "knownArrhythmia"), [
        ("cha2ds2vasc", True, 8, "Stroke risk assessment for known arrhythmia"),
        ("hasbled", True, 9, "Bleeding risk assessment to weigh against stroke risk"),
    ]),
    ("has_device", lambda a: _yes(a, "hasDevice"), [
        ("device_followup", True, 10, "Routine device follow-up given a pacemaker or defibrillator is present"),
    ]),
    ("diabetes", lambda a: _yes(a, "diabetes"), [
        ("ckd_staging", True, 6, "Diabetes is a leading cause of kidney disease and warrants baseline kidney function staging"),
        ("diabetes_med_renal_safety", True, 11, "Check for diabetes medications that need dose adjustment based on kidney function"),
        ("ascvd_risk_enhancers", False, 22, "Diabetes is a recognized ASCVD risk-enhancing factor"),
    ]),
    ("pregnant_cardiac", lambda a: _yes(a, "pregnant") and any(_yes(a, k) for k in ["knownHf", "knownCad", "knownArrhythmia", "knownValveDisease"]), [
        ("mwho_classification", True, 6, "Known cardiac condition in pregnancy requires maternal risk classification"),
    ]),
    ("pregnant_ckd", lambda a: _yes(a, "pregnant") and _yes(a, "knownCkd"), [
        ("ckd_pregnancy_risk", True, 6, "Known kidney disease in pregnancy requires risk stratification"),
    ]),
    ("recent_hosp", lambda a: _yes(a, "recentHospitalization"), [
        ("post_mi_checklist", False, 23, "Confirm secondary prevention measures are in place after a recent hospitalization"),
    ]),
    ("confusion_today", lambda a: _yes(a, "symptomConfusion"), [
        ("dementia_risk___safety_assessment", True, 2, "New or worsening confusion today warrants an urgent risk and safety assessment — this can also indicate delirium, which needs prompt medical evaluation rather than being attributed to baseline dementia"),
    ]),
    ("known_dementia", lambda a: _yes(a, "knownDementia"), [
        ("dementia_diagnostic___clinical_assessment", True, 6, "Baseline diagnostic and clinical assessment for a known dementia/Alzheimer's diagnosis"),
        ("dementia_cognitive_screening_index", True, 6, "A deterministic cognitive impairment score establishes a baseline for a known dementia/Alzheimer's diagnosis"),
        ("dementia_functional___behavioral_assessment", False, 20, "Functional and behavioral status is valuable context alongside a known dementia diagnosis"),
        ("dementia_psychosocial___caregiver_assessment", False, 21, "Caregiver burden screening is valuable context alongside a known dementia diagnosis"),
    ]),
    ("suspected_dementia", lambda a: _yes(a, "memoryConcerns"), [
        ("dementia_diagnostic___clinical_assessment", True, 6, "Family/caregiver-reported memory or thinking changes warrant a formal cognitive assessment"),
        ("dementia_cognitive_screening_index", True, 6, "A deterministic cognitive impairment score helps quantify family/caregiver-reported memory or thinking changes"),
        ("dementia_functional___behavioral_assessment", False, 20, "Functional status helps characterize the impact of reported memory or thinking changes"),
        ("dementia_psychosocial___caregiver_assessment", False, 21, "Caregiver burden screening is valuable when memory or thinking changes have already been noticed at home"),
    ]),
    ("known_htn", lambda a: _yes(a, "knownHtn"), [
        ("ckd_staging", True, 6, "Hypertension is a leading cause of kidney disease and warrants baseline kidney function staging"),
        ("bp_category", True, 12, "Classify current blood pressure category for a known hypertension diagnosis"),
        ("htn_management_checklist", False, 20, "Review hypertension management now that a diagnosis is confirmed"),
        ("ascvd_risk_enhancers", False, 22, "Hypertension is a recognized ASCVD risk-enhancing factor"),
    ]),
    ("smoker", lambda a: a.get("smokingStatus") in ("current", "former"), [
        ("ascvd_risk_enhancers", False, 22, "Current or former smoking is a recognized ASCVD risk-enhancing factor"),
    ]),
    ("nsaid_use", lambda a: _yes(a, "regularNsaidUse"), [
        ("drug_nephrotoxicity_checklist", True, 12, "Regular NSAID use warrants a nephrotoxicity review given the kidney risk"),
    ]),
    ("family_history_kidney", lambda a: _yes(a, "familyHistoryKidneyDisease"), [
        ("adpkd_mayo", False, 22, "Family history of kidney disease warrants screening for a hereditary cause such as ADPKD"),
    ]),
    ("family_history_heart", lambda a: _yes(a, "familyHistoryHeartDisease"), [
        ("ascvd_risk_enhancers", False, 22, "Family history of heart disease or sudden cardiac death is a recognized ASCVD risk-enhancing factor"),
    ]),
    ("functional_decline", lambda a: _yes(a, "functionalDecline"), [
        ("dementia_functional___behavioral_assessment", True, 6, "Reported difficulty with daily activities warrants a formal functional and behavioral assessment"),
    ]),
    ("wandering_history", lambda a: _yes(a, "wanderingHistory"), [
        ("dementia_risk___safety_assessment", True, 2, "A history of wandering or getting lost is a direct, urgent safety concern"),
    ]),
    ("lives_alone_with_dementia_signal", lambda a: _yes(a, "livesAlone") and any(_yes(a, k) for k in ["knownDementia", "memoryConcerns", "functionalDecline", "wanderingHistory"]), [
        ("dementia_risk___safety_assessment", True, 3, "Living alone alongside a dementia-related signal raises the safety stakes and warrants a risk and safety assessment"),
        ("dementia_psychosocial___caregiver_assessment", False, 20, "Living alone with a dementia-related signal makes support-system and caregiver context especially relevant"),
    ]),
]


def compute_intake_pathway(answers: dict) -> list[dict]:
    merged: dict[str, dict] = {}
    for _rule_id, condition, suggestions in INTAKE_ROUTING_RULES:
        if not condition(answers):
            continue
        for module_id, mandatory, priority, reason in suggestions:
            existing = merged.get(module_id)
            if not existing:
                merged[module_id] = {"mandatory": mandatory, "priority": priority, "reasons": [reason]}
            else:
                existing["mandatory"] = existing["mandatory"] or mandatory
                existing["priority"] = min(existing["priority"], priority)
                if reason not in existing["reasons"]:
                    existing["reasons"].append(reason)

    pathway = [{"moduleId": k, **v} for k, v in merged.items()]
    pathway.sort(key=lambda p: (0 if p["mandatory"] else 1, p["priority"]))
    return pathway


# Derives the patient's care pathway from intake answers — the most specific signal
# wins: active dialysis or transplant status says more than a general CKD flag,
# which in turn says more than isolated cardiac history alone. Deliberately doesn't
# fabricate a specific CKD stage number from intake alone — that requires an actual
# eGFR/ACR result, which intake doesn't collect.
def derive_clinical_programs(answers: dict) -> list[str]:
    """Returns every clinical program this intake's answers actually support —
    deliberately a list, not a single value, since a patient can genuinely have
    both kidney and cardiac involvement (the exact case the old single-string
    care_pathway field couldn't represent at all). Order doesn't imply priority;
    duplicates are never possible since each key can only be added once."""
    programs: list[str] = []
    if (
        _yes(answers, "onDialysis")
        or _yes(answers, "kidneyTransplant")
        or _yes(answers, "knownCkd")
    ):
        programs.append("kidney")
    if any(_yes(answers, k) for k in ["knownHf", "knownCad", "knownArrhythmia", "knownValveDisease", "hasDevice"]):
        programs.append("cardiology")
    if any(_yes(answers, k) for k in ["knownDementia", "memoryConcerns", "functionalDecline", "wanderingHistory"]):
        programs.append("dementia")
    return programs


class IntakeCalculator(Calculator):
    key = "basic_intake"

    def compute(self, a: dict) -> dict:
        pathway = compute_intake_pathway(a)
        mandatory_count = sum(1 for p in pathway if p["mandatory"])
        optional_count = len(pathway) - mandatory_count
        if not pathway:
            headline = "No specific follow-up assessments were triggered by this intake."
            severity = "good"
        else:
            headline = f"{len(pathway)} suggested assessment(s) \u2014 {mandatory_count} mandatory, {optional_count} optional."
            severity = "warning" if mandatory_count > 0 else "caution"
        return {
            "headline": headline,
            "headlineSeverity": severity,
            "metrics": [],
            "flags": [],
            "notes": (
                "This pathway is a starting point based on your answers - use clinical judgment to "
                "add, skip, or reorder items as the case develops."
                if pathway
                else "You can still browse and add any assessment manually."
            ),
            "suggestedPathway": pathway,
        }
