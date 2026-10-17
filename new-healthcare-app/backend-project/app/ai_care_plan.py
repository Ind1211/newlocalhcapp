"""
Generates the AI narrative care plan for a completed CKD staging assessment — the one
piece deliberately left out when the deterministic staging/referral logic was ported,
since it's a network call and prompt design, not clinical calculation.

Requires a real Anthropic API key (ANTHROPIC_API_KEY in .env) — this calls the actual
Messages API from this backend server, which is a different mechanism entirely from an
artifact's embedded fetch() call. There is no key baked in; you need your own.
"""

import json
import os

import anthropic

# The original tool used claude-sonnet-4-6. Updated here to claude-sonnet-5, the
# current model at time of writing — using an older, possibly-retired model string
# in new code would be a disservice.
MODEL = "claude-sonnet-5"


class CarePlanError(Exception):
    pass


def build_prompt(staging: dict, answers: dict, available_assessments: list[dict]) -> str:
    """staging: the dict returned by CKDStagingCalculator.compute() for this case.
    answers: the same answers dict submitted for staging.
    available_assessments: [{"id": ..., "title": ...}, ...] not yet completed for this case."""

    metrics = {m["label"]: m["value"] for m in staging.get("metrics", [])}
    payload = {
        "demographics": {"age": answers.get("age"), "sex": answers.get("sex"), "reason": answers.get("reason")},
        "riskFactors": answers.get("riskFactors") or [],
        "computedStaging": {
            "eGFR": metrics.get("eGFR"),
            "gCategory": metrics.get("G-stage"),
            "ACR": metrics.get("ACR"),
            "aCategory": metrics.get("A-stage"),
            "riskLevel": staging.get("headline"),
        },
        "ruleBasedReferralFlags": [f["text"] for f in staging.get("flags", [])],
        "vitals": {
            "sbp": answers.get("sbp"), "dbp": answers.get("dbp"),
            "antihypertensiveClasses": answers.get("antihtnCount"),
            "weightTrend": answers.get("weightTrend"), "edemaOnExam": answers.get("edemaExam"),
        },
        "diabetesDetail": {"hba1c": answers.get("hba1c"), "sglt2i": answers.get("sglt2i"), "insulin": answers.get("insulin")},
        "cvDetail": {"statin": answers.get("statin"), "priorMiStroke": answers.get("priorMiStroke")},
        "symptoms": answers.get("symptoms") or [],
        "medicationSafety": {
            "nsaidUse": answers.get("nsaidUse"), "recentContrast": answers.get("recentContrast"),
            "metforminUse": answers.get("metforminUse"), "otherNephrotoxic": answers.get("otherNephrotoxic"),
        },
        "complicationLabs": {
            "hemoglobin": answers.get("hemoglobin"), "potassium": answers.get("potassium"),
            "bicarbonate": answers.get("bicarbonate"), "calcium": answers.get("calcium"),
            "phosphate": answers.get("phosphate"), "pth": answers.get("pth"),
        },
        "advancedCarePlanning": {
            "activeReferral": answers.get("activeReferral"), "transplantDiscussed": answers.get("transplantDiscussed"),
            "dialysisPlanning": answers.get("dialysisPlanning"), "advanceCarePlanning": answers.get("advanceCarePlanning"),
        },
    }

    schema = (
        '{"stageSummary":"1-2 sentence plain-language clinical summary of this patient\'s kidney status",'
        '"redFlags":["short phrase describing a concerning finding worth flagging", "..."],'
        '"referral":{"needed":true,"urgency":"routine|soon|urgent","reason":"one short sentence"},'
        '"monitoring":{"frequency":"e.g. every 6 months","labsToTrend":["eGFR","ACR"]},'
        '"medications":["short actionable recommendation, e.g. drug class and rationale"],'
        '"lifestyle":["short recommendation"],'
        '"patientEducation":["short point to discuss with patient"],'
        '"caveats":"one short sentence noting any data limitations, estimates, or missing values that affect confidence",'
        '"suggestedAssessments":["exact id string, 0-4 items"]}'
    )

    return f"""You are a nephrology clinical decision-support assistant helping a clinician interpret a structured CKD risk assessment for one patient. You support clinical judgment; you do not replace it. The GFR category, albuminuria category, and risk level below are already computed correctly from CKD-EPI 2021 and KDIGO thresholds — use them as given, do not recompute or contradict them.

Respond with ONLY a single minified JSON object, no markdown fences, no commentary, matching exactly this schema:
{schema}

Keep every string concise (roughly one sentence). Ground recommendations in KDIGO CKD guideline principles (e.g. ACEi/ARB and SGLT2i use, blood pressure targets, sodium/protein guidance, anemia and mineral-bone-disease workup thresholds, referral thresholds). If data was estimated (e.g. dipstick instead of ACR, or eGFR calculated rather than lab-reported), reflect that in caveats.

For "suggestedAssessments": pick 0-4 items ONLY from the list below of other available assessments not yet completed for this patient — choose whichever would most directly close a gap you named in caveats. Use the exact "id" string. Return an empty array if none would meaningfully help. Do not invent ids.

OTHER ASSESSMENTS AVAILABLE TO SUGGEST (id, title):
{json.dumps(available_assessments)}

PATIENT DATA:
{json.dumps(payload)}"""


def generate_care_plan(staging: dict, answers: dict, available_assessments: list[dict]) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise CarePlanError(
            "ANTHROPIC_API_KEY is not set. Add it to your backend .env to enable care plan generation — "
            "this requires your own Anthropic API key and account; it is not provided automatically."
        )

    prompt = build_prompt(staging, answers, available_assessments)
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise CarePlanError(f"Anthropic API call failed: {e}") from e

    text = "".join(block.text for block in response.content if block.type == "text")
    cleaned = text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise CarePlanError(f"Could not parse the AI response as JSON: {e}") from e

    return parsed
