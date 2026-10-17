"""
Document auto-fill's safety validation — pure unit tests, no HTTP client or
database needed, since suggest_autofill() is a plain function.

test_fabricated_field_name_is_dropped ports a REAL bug this exact test caught
during manual verification: a field name Claude invented (that doesn't exist on
the assessment at all) was silently passed through, because the original
validation only checked "is this value within the field's allowed options" —
which is falsy-equivalent for both "field has no options" (a real, unconstrained
field) and "field doesn't exist at all" in Python. This test is what makes sure
that specific class of bug can never come back unnoticed.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.document_autofill import AutoFillError, suggest_autofill

FIELDS_META = {
    "fields": [
        {"name": "knownCkd", "label": "Known CKD?", "type": "pill", "options": [
            {"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"},
        ]},
        {"name": "chiefComplaint", "label": "Reason", "type": "textarea"},
    ],
    "steps": None,
}
DOCUMENTS = [{"filename": "referral.docx", "extracted_text": "Patient has known chronic kidney disease."}]


def _mock_claude_response(json_text: str):
    block = MagicMock()
    block.type = "text"
    block.text = json_text
    response = MagicMock()
    response.content = [block]
    return response


def test_valid_suggestions_are_kept():
    fake_response = json.dumps({"suggestions": {
        "knownCkd": {"value": "yes", "source": "known chronic kidney disease"},
        "chiefComplaint": {"value": "CKD follow-up", "source": "referral context"},
    }})
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_claude_response(fake_response)
        result = suggest_autofill("Basic Intake", FIELDS_META, DOCUMENTS)
    assert "knownCkd" in result["suggestions"]
    assert "chiefComplaint" in result["suggestions"]


def test_fabricated_field_name_is_dropped():
    """The exact regression test for the bug caught during manual testing."""
    fake_response = json.dumps({"suggestions": {
        "knownCkd": {"value": "yes", "source": "known chronic kidney disease"},
        "sneaky_invalid_field": {"value": "maybe", "source": "not a real field at all"},
    }})
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_claude_response(fake_response)
        result = suggest_autofill("Basic Intake", FIELDS_META, DOCUMENTS)
    assert "knownCkd" in result["suggestions"]
    assert "sneaky_invalid_field" not in result["suggestions"]


def test_out_of_range_value_for_constrained_field_is_dropped():
    fake_response = json.dumps({"suggestions": {
        "knownCkd": {"value": "definitely-not-yes-or-no", "source": "bad value test"},
    }})
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_claude_response(fake_response)
        result = suggest_autofill("Basic Intake", FIELDS_META, DOCUMENTS)
    assert "knownCkd" not in result["suggestions"]


def test_no_documents_raises_clear_error():
    with pytest.raises(AutoFillError, match="no uploaded documents"):
        suggest_autofill("Basic Intake", FIELDS_META, [])
