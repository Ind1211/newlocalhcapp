"""
Generates one combined narrative + action list across ALL of a patient's completed
assessments — distinct from ai_care_plan.py, which is specific to the CKD staging
wizard's own deterministic staging output. This one takes whatever's actually been
completed (any mix of the 132 real calculators or custom assessments) and asks
Claude to synthesize a single cross-assessment picture, since no individual
assessment's own logic has visibility into what else has been recorded for the
same patient.

Also grounds the plan in the patient's uploaded documents where available — a
clinical document almost always contains context beyond what maps to any
assessment's fixed fields (e.g. "recently referred" vs. "long-established"),
which would otherwise be silently discarded once auto-fill's structured answers
are accepted.

suggest_pgi_from_care_plan() is a second, separate AI call that structures the
generated plan's findings into a Problems/Goals/Interventions hierarchy — a real
head start on PGI, not a replacement for someone reviewing it. Nothing from
either function is ever written to the database directly; the frontend is
responsible for treating both as reviewable suggestions, the same pattern
already used for document auto-fill.
"""

import json
import os

import anthropic

MODEL = "claude-sonnet-5"

# Same safety valve as document_autofill.py — a hard ceiling on how much document
# text gets included, not a chunking strategy. A patient with an unusually large
# document set should fail loudly here rather than silently send a huge prompt.
MAX_DOCUMENT_CHARS = 40_000


class IntegratedCarePlanError(Exception):
    pass


RESULT_SCHEMA = (
    '{"summary":"one short paragraph synthesizing the overall picture across all completed assessments",'
    '"keyFindings":["short phrase naming one notable finding, referencing which assessment or document it came from"],'
    '"actionItems":[{"text":"short actionable recommendation","priority":"high|medium|low"}],'
    '"caveats":"one short sentence noting that this synthesizes separately-completed assessments and does not replace integrated clinical judgment"}'
)

PGI_SCHEMA = (
    '{"problems":[{"description":"a specific clinical or care problem this plan identifies",'
    '"goals":[{"description":"a concrete, specific goal addressing this problem",'
    '"interventions":["a specific, doable action toward this goal"]}]}]}'
)


def _format_documents(document_texts: list[dict]) -> str:
    if not document_texts:
        return ""
    sections = []
    total_chars = 0
    for doc in document_texts:
        text = doc.get("extracted_text") or ""
        if total_chars + len(text) > MAX_DOCUMENT_CHARS:
            break
        sections.append(f"--- {doc['filename']} ---\n{text}")
        total_chars += len(text)
    if not sections:
        return ""
    return "\n\nPATIENT DOCUMENTS (referral letters, labs, discharge summaries, etc.):\n" + "\n\n".join(sections)


def build_prompt(patient_name: str, completed: list[dict], document_texts: list[dict] | None = None) -> str:
    """completed: [{"title": ..., "headline": ..., "severity": ..., "flags": [...], "notes": ...}, ...]"""
    documents_section = _format_documents(document_texts or [])
    return f"""You are a clinical decision-support assistant helping synthesize multiple, separately-completed patient assessments{" and uploaded documents" if documents_section else ""} into one combined picture. You support clinical judgment; you do not replace it. Each assessment's own headline, severity, and flags below are already correctly computed by that assessment's own logic — use them as given, do not recompute or contradict any individual assessment's result. Documents are supporting context, not another assessment result — draw on them for nuance (e.g. how recently a condition was diagnosed, what a referral was actually for) that the structured assessment answers alone wouldn't capture.

Respond with ONLY a single minified JSON object, no markdown fences, no commentary, matching exactly this schema:
{RESULT_SCHEMA}

Look across all the assessments together for patterns a single assessment wouldn't surface on its own — e.g. two assessments both flagging a related concern, or a finding in one assessment that changes how urgently another's recommendation should be acted on. Keep every string concise.

PATIENT: {patient_name}

COMPLETED ASSESSMENTS:
{json.dumps(completed)}{documents_section}"""


def generate_integrated_care_plan(patient_name: str, completed: list[dict], document_texts: list[dict] | None = None) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise IntegratedCarePlanError(
            "ANTHROPIC_API_KEY is not set. Add it to your backend .env to enable the integrated "
            "care plan — this requires your own Anthropic API key and account."
        )
    if not completed:
        raise IntegratedCarePlanError("No completed assessments to synthesize yet.")

    prompt = build_prompt(patient_name, completed, document_texts)
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise IntegratedCarePlanError(f"Could not generate the integrated care plan right now: {e}") from e

    text = "".join(block.text for block in response.content if block.type == "text")
    cleaned = text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise IntegratedCarePlanError(f"Could not parse the AI response as JSON: {e}") from e

    parsed.setdefault("keyFindings", [])
    parsed.setdefault("actionItems", [])
    parsed.setdefault("caveats", "")
    return parsed


def suggest_pgi_from_care_plan(patient_name: str, care_plan: dict) -> dict:
    """Structures an already-generated care plan's findings into a
    Problems/Goals/Interventions hierarchy. Deliberately a second, separate call
    rather than folding this into the same prompt as generate_integrated_care_plan
    — asking for two structurally different outputs (a narrative synthesis vs. a
    nested action hierarchy) in one call tends to produce a worse result at either
    task than two focused calls each doing one job well."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise IntegratedCarePlanError("ANTHROPIC_API_KEY is not set.")

    prompt = f"""You are structuring an already-generated clinical care plan synthesis into a Problems/Goals/Interventions (PGI) hierarchy — a standard clinical care-planning framework. Group related findings under the same problem rather than creating a separate problem for every single finding; a good PGI structure is specific and actionable, not an exhaustive restatement of everything in the plan. Only include problems with a genuine basis in the plan below — do not invent problems the plan doesn't actually support.

Respond with ONLY a single minified JSON object, no markdown fences, no commentary, matching exactly this schema:
{PGI_SCHEMA}

PATIENT: {patient_name}

CARE PLAN SUMMARY: {care_plan.get("summary", "")}

KEY FINDINGS: {json.dumps(care_plan.get("keyFindings", []))}

ACTION ITEMS: {json.dumps(care_plan.get("actionItems", []))}"""

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise IntegratedCarePlanError(f"Could not generate PGI suggestions right now: {e}") from e

    text = "".join(block.text for block in response.content if block.type == "text")
    cleaned = text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise IntegratedCarePlanError(f"Could not parse the AI response as JSON: {e}") from e

    parsed.setdefault("problems", [])
    return parsed
