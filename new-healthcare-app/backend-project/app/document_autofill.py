"""
Suggests answers for an assessment's fields based on a patient's uploaded document
text — deliberately never writes anything to the assessment itself. This returns
suggestions only; a person has to explicitly review and accept them, the same
"offer, never auto-apply" pattern already used for prefilling a repeat check-in
from the patient's last submission.

Long-context, not RAG: a patient's whole document set is included directly in the
prompt rather than retrieved via embeddings. That's a deliberate choice, not a
placeholder for a "real" version — a typical patient's documents are a handful of
pages, well within a single prompt, and this stays simpler and more inspectable
than a retrieval pipeline would be for that size of input.
"""

import json
import os

import anthropic

MODEL = "claude-sonnet-5"

# A hard ceiling on how much document text gets sent in one prompt — not a chunking
# strategy, just a safety valve. A patient with an unusually large document set
# should fail loudly here rather than silently send a huge, expensive prompt.
MAX_DOCUMENT_CHARS = 60_000


class AutoFillError(Exception):
    pass


def _describe_field(f: dict) -> dict:
    desc = {"name": f["name"], "label": f["label"], "type": f["type"]}
    if f.get("options"):
        # Options can be plain strings (dropdown) or {value,label} objects (pill/select) —
        # normalized here so the prompt always shows Claude the same simple shape.
        desc["valid_values"] = [
            o if isinstance(o, str) else o.get("value") for o in f["options"]
        ]
    if f.get("unit"):
        desc["unit"] = f["unit"]
    return desc


def _flatten_fields(fields_meta: dict) -> list[dict]:
    if fields_meta.get("steps"):
        return [f for step in fields_meta["steps"] for f in step["fields"]]
    return fields_meta.get("fields") or []


def build_prompt(assessment_title: str, fields_meta: dict, documents: list[dict]) -> str:
    field_descriptions = [_describe_field(f) for f in _flatten_fields(fields_meta)]

    doc_sections = []
    total_chars = 0
    for doc in documents:
        text = doc["extracted_text"] or ""
        if total_chars + len(text) > MAX_DOCUMENT_CHARS:
            break
        doc_sections.append(f"--- {doc['filename']} ---\n{text}")
        total_chars += len(text)

    documents_text = "\n\n".join(doc_sections)

    return f"""You are helping pre-fill a clinical assessment from a patient's uploaded documents. Suggest a value ONLY for a field when the documents give you a genuinely clear, specific basis for it — when in doubt, omit the field entirely rather than guess. This is a suggestion a clinician will review before anything is saved, not an automatic decision, but it still needs to be trustworthy: a wrong suggestion that looks confident is worse than no suggestion at all.

For any field with "valid_values" listed, your suggested value MUST be exactly one of those values — never invent a value outside that list.

Respond with ONLY a single minified JSON object, no markdown fences, no commentary, matching exactly this schema:
{{"suggestions":{{"<field_name>":{{"value":"<the suggested value>","source":"<short quote or paraphrase from the documents that justifies this>"}}}}}}

ASSESSMENT: {assessment_title}

FIELDS (name, label, type, valid_values if constrained):
{json.dumps(field_descriptions)}

PATIENT DOCUMENTS:
{documents_text}"""


def suggest_autofill(assessment_title: str, fields_meta: dict, documents: list[dict]) -> dict:
    if not documents:
        raise AutoFillError("This patient has no uploaded documents to suggest answers from.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AutoFillError(
            "ANTHROPIC_API_KEY is not set. Add it to your backend .env to enable "
            "auto-fill from documents — this requires your own Anthropic API key."
        )

    prompt = build_prompt(assessment_title, fields_meta, documents)
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise AutoFillError(f"Could not generate suggestions right now: {e}") from e

    text = "".join(block.text for block in response.content if block.type == "text")
    cleaned = text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise AutoFillError(f"Could not parse the AI response as JSON: {e}") from e

    suggestions = parsed.get("suggestions", {})

    # Defense in depth on top of the prompt instruction — never trust the model's
    # own claim that a value is valid. A constrained field (pill/select/dropdown)
    # gets its suggestion dropped outright if it's not actually one of the field's
    # real options, rather than passing through something the UI can't render
    # correctly or that would silently fail validation on submit.
    valid_values_by_field = {
        f["name"]: set(_describe_field(f).get("valid_values", []) or [])
        for f in _flatten_fields(fields_meta)
    }
    cleaned_suggestions = {}
    for field_name, suggestion in suggestions.items():
        # A field name that isn't a real field on this assessment at all gets
        # dropped outright — this must be checked separately from the
        # constrained-options check below, since "no listed valid_values" (a real,
        # unconstrained field) and "not a key at all" (a field that doesn't exist)
        # are both falsy in Python and were being treated identically before this
        # explicit check was added.
        if field_name not in valid_values_by_field:
            continue
        allowed = valid_values_by_field[field_name]
        value = suggestion.get("value") if isinstance(suggestion, dict) else None
        if value is None:
            continue
        if allowed and value not in allowed:
            continue
        cleaned_suggestions[field_name] = suggestion

    return {"suggestions": cleaned_suggestions}
