"""
Voice notes — the transcription itself happens client-side (the browser's Web
Speech API), so this endpoint only ever receives already-transcribed text and
persists it. The one thing genuinely worth protecting here is that a voice
note becomes a REAL PatientDocument row with extraction_status='ok' — which is
what makes it automatically participate in auto-fill and integrated-care-plan
grounding, since both of those simply query every document with
extraction_status='ok' for a patient without caring where the text came from.
"""

from unittest.mock import patch

from app.models import Patient, PatientDocument


def test_create_voice_note_becomes_a_real_document_with_source_set(client, staff_factory, auth_headers, db):
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)

    patient = Patient(name="Voice Note Test Patient", mrn="VOICE-001")
    db.add(patient)
    db.commit()

    with patch("app.routers.documents.upload_document", return_value="fake-storage-key-1"):
        resp = client.post(
            f"/api/patients/{patient.id}/voice-notes",
            json={"text": "Patient reports mild swelling in ankles. Weight 82 kilograms."},
            headers=headers,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "voice_note"
    assert body["extraction_status"] == "ok"
    assert body["extracted_text"] == "Patient reports mild swelling in ankles. Weight 82 kilograms."
    assert body["uploaded_by"] == staff.name


def test_empty_voice_note_text_is_rejected(client, staff_factory, auth_headers, db):
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)
    patient = Patient(name="Empty Voice Note Patient", mrn="VOICE-002")
    db.add(patient)
    db.commit()

    resp = client.post(f"/api/patients/{patient.id}/voice-notes", json={"text": "   "}, headers=headers)
    assert resp.status_code == 400


def test_voice_note_is_included_in_the_same_query_autofill_and_care_plan_use(client, staff_factory, auth_headers, db):
    """The real behavior this feature depends on: neither auto-fill nor
    integrated-care-plan generation filters by source at all — both just query
    every document with extraction_status='ok' for a patient. This confirms a
    voice note genuinely satisfies that exact query, not just that the
    create endpoint returns a plausible-looking response."""
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)
    patient = Patient(name="Query Test Patient", mrn="VOICE-003")
    db.add(patient)
    db.commit()

    with patch("app.routers.documents.upload_document", return_value="fake-storage-key-2"):
        client.post(f"/api/patients/{patient.id}/voice-notes", json={"text": "Blood pressure 140 over 88."}, headers=headers)

    matching_docs = db.query(PatientDocument).filter_by(patient_id=patient.id, extraction_status="ok").all()
    assert len(matching_docs) == 1
    assert matching_docs[0].source == "voice_note"
    assert matching_docs[0].extracted_text == "Blood pressure 140 over 88."


def test_voice_note_appears_in_the_regular_documents_list(client, staff_factory, auth_headers, db):
    """Confirms a voice note shows up through the same GET .../documents
    endpoint a regular upload does, with source correctly distinguishing it —
    what the frontend's mic-icon display and Voice Notes tab both depend on."""
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)
    patient = Patient(name="List Test Patient", mrn="VOICE-004")
    db.add(patient)
    db.commit()

    with patch("app.routers.documents.upload_document", return_value="fake-storage-key-3"):
        client.post(f"/api/patients/{patient.id}/voice-notes", json={"text": "Patient ambulatory without assistance."}, headers=headers)

    docs = client.get(f"/api/patients/{patient.id}/documents", headers=headers).json()
    voice_docs = [d for d in docs if d["source"] == "voice_note"]
    assert len(voice_docs) == 1


def test_editing_a_voice_note_updates_its_text(client, staff_factory, auth_headers, db):
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)
    patient = Patient(name="Edit Voice Note Patient", mrn="VOICE-005")
    db.add(patient)
    db.commit()

    with patch("app.routers.documents.upload_document", return_value="fake-storage-key-4"):
        create_resp = client.post(f"/api/patients/{patient.id}/voice-notes", json={"text": "pateint has fever"}, headers=headers)
    doc_id = create_resp.json()["id"]

    with patch("app.routers.documents.upload_document", return_value="fake-storage-key-4-edited"), \
         patch("app.routers.documents.delete_document"):
        edit_resp = client.patch(f"/api/patients/{patient.id}/voice-notes/{doc_id}", json={"text": "patient has fever"}, headers=headers)

    assert edit_resp.status_code == 200
    assert edit_resp.json()["extracted_text"] == "patient has fever"


def test_editing_a_regular_uploaded_document_as_a_voice_note_is_rejected(client, staff_factory, auth_headers, db):
    """The real safety property this restriction protects: a regular document's
    extracted_text is derived FROM its original file, so allowing this edit
    path on one would create a permanent, confusing mismatch the moment
    someone next clicks retry-extraction."""
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)
    patient = Patient(name="Reject Edit Patient", mrn="VOICE-006")
    db.add(patient)
    db.commit()

    doc = PatientDocument(
        patient_id=patient.id, filename="referral.pdf", content_type="application/pdf",
        storage_key="real-upload-key", size_bytes=100, extraction_status="ok",
        extracted_text="Real extracted text from a real file.", source="upload",
    )
    db.add(doc)
    db.commit()

    resp = client.patch(f"/api/patients/{patient.id}/voice-notes/{doc.id}", json={"text": "trying to edit a regular upload"}, headers=headers)
    assert resp.status_code == 400
