"""
Generates the AI interpretation for a custom (user-built) assessment — this is the
core mechanism that makes custom assessments actually computable: unlike built-in
assessments, there's no Python calculator behind them, only the plain-language
"interpretation instructions" the person who built it wrote.
"""

import json
import os

import anthropic

MODEL = "claude-sonnet-5"


class InterpretationError(Exception):
    pass


RESULT_SCHEMA = (
    '{"headline":"one short sentence summarizing the result",'
    '"headlineSeverity":"good|caution|warning|critical",'
    '"metrics":[{"label":"short label","value":"value","unit":"optional unit"}],'
    '"flags":[{"text":"short actionable phrase","severity":"good|caution|warning|critical"}],'
    '"notes":"one short sentence of caveats or context, or empty string"}'
)


def build_prompt(title: str, sections: list[dict], answers: dict, interpretation_prompt: str) -> str:
    field_meta = []
    for section in sections:
        for f in section.get("fields", []):
            field_meta.append({"name": f["name"], "label": f["label"], "type": f["type"]})

    return f"""You are helping interpret the answers to a custom clinical assessment that a care team member built themselves. This assessment was NOT independently reviewed or clinically validated — it is the care team's own tool, built on their own judgment. Interpret the answers strictly according to the instructions they wrote; do not substitute your own clinical judgment for theirs, and do not add clinical claims beyond what their instructions specify.

Respond with ONLY a single minified JSON object, no markdown fences, no commentary, matching exactly this schema:
{RESULT_SCHEMA}

ASSESSMENT TITLE: {title}

QUESTIONS ASKED (name, label, type):
{json.dumps(field_meta)}

THE PERSON WHO BUILT THIS WROTE THESE INTERPRETATION INSTRUCTIONS — follow them exactly:
\"\"\"{interpretation_prompt}\"\"\"

PATIENT'S ANSWERS:
{json.dumps(answers)}"""


def generate_interpretation(title: str, sections: list[dict], answers: dict, interpretation_prompt: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise InterpretationError(
            "ANTHROPIC_API_KEY is not set. Add it to your backend .env to enable custom assessment "
            "interpretation — this requires your own Anthropic API key and account."
        )

    prompt = build_prompt(title, sections, answers, interpretation_prompt)
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise InterpretationError(f"Could not generate an interpretation right now: {e}") from e

    text = "".join(block.text for block in response.content if block.type == "text")
    cleaned = text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise InterpretationError(f"Could not parse the AI response as JSON: {e}") from e

    parsed.setdefault("metrics", [])
    parsed.setdefault("flags", [])
    parsed.setdefault("notes", "")
    return parsed
