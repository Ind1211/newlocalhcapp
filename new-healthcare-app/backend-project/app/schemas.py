import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    internal_label: str | None = None
    name: str
    dob: date | None = None
    mrn: str | None = None  # auto-generated (REN-XXXXX) if not supplied
    care_pathway: str | None = None  # legacy — new code should use clinical_program_keys
    clinical_program_keys: list[str] = []  # e.g. ["kidney", "cardiology"] — a patient can be in more than one
    payor_name: str | None = None
    member_id: str | None = None
    group_number: str | None = None
    eligibility_status: str | None = None  # active|inactive|pending|unverified
    phone_number: str | None = None
    email: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    preferred_contact_method: str | None = None  # phone|email|portal|mail
    preferred_language: str | None = None
    risk_level: str | None = None  # low|medium|high|critical


class PatientUpdate(BaseModel):
    """Deliberately has no mrn field — the MRN is this patient's primary
    identifier and isn't exposed as an editable field here. Every other field a
    patient might legitimately need corrected or updated over time (name typos,
    insurance changes, eligibility re-verification, program membership) is
    included. clinical_program_keys, when provided, REPLACES the patient's
    current program set entirely — a deliberate difference from how intake
    completion adds programs (additive-only, never removing one). This is an
    explicit, deliberate edit through a form; the person filling it out should be
    able to remove a program that was added in error, which intake's own logic
    intentionally can't do."""
    name: str | None = None
    dob: date | None = None
    clinical_program_keys: list[str] | None = None
    payor_name: str | None = None
    member_id: str | None = None
    group_number: str | None = None
    eligibility_status: str | None = None
    phone_number: str | None = None
    email: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    preferred_contact_method: str | None = None  # phone|email|portal|mail
    preferred_language: str | None = None
    risk_level: str | None = None  # low|medium|high|critical
    # The version token for optimistic locking — the frontend captures a
    # patient's updated_at when it loads the edit form, and sends that exact
    # value back here. If it doesn't match the CURRENT value in the database,
    # someone else changed this patient in between, and the request is rejected
    # rather than silently overwriting their edit. None means "don't check" —
    # kept optional so this doesn't become a required field for every caller
    # that has no reason to know about locking (e.g. a script, or an older client).
    expected_updated_at: datetime | None = None



class ProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    label: str
    icon: str | None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    internal_label: str | None
    name: str | None
    dob: date | None
    mrn: str | None
    care_pathway: str | None
    clinical_programs: list[ProgramOut] = []
    payor_name: str | None
    member_id: str | None
    group_number: str | None
    eligibility_status: str | None
    eligibility_verified_at: datetime | None
    phone_number: str | None
    email: str | None
    address_line1: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    preferred_contact_method: str | None
    preferred_language: str | None
    risk_level: str | None
    last_contact_date: datetime | None
    is_active: bool
    deactivated_reason: str | None
    created_at: datetime
    updated_at: datetime


class AssignAssessmentRequest(BaseModel):
    assessment_definition_key: str
    title_override: str | None = None
    source: str = "template"  # 'template' | 'custom'
    scheduled_date: date | None = None
    mandatory: bool = False


class ConfirmPathwayItem(BaseModel):
    module_id: str
    mandatory: bool


class ConfirmPathwayRequest(BaseModel):
    items: list[ConfirmPathwayItem]


class SaveDraftRequest(BaseModel):
    answers: dict[str, Any]


class PatientAssessmentSummary(BaseModel):
    """One row in a patient's assessment list. status is derived from draft_answers
    and AssessmentResult, not stored directly — deliberately doesn't include an 'X
    of Y answered' count, since that wouldn't be meaningful or comparable across the
    wide range of field structures the 132 real assessments actually use (a wizard's
    steps, a checkboxgroup representing several sub-answers, etc.)."""
    assigned_assessment_id: uuid.UUID
    assessment_definition_key: str
    title: str
    source: str
    mandatory: bool
    scheduled_date: date | None
    status: str  # 'Scheduled' | 'In Progress' | 'Completed'
    draft_answers: dict[str, Any] | None
    result_id: uuid.UUID | None
    result_headline: str | None
    result_severity: str | None


class CaseCreate(BaseModel):
    patient_id: uuid.UUID
    label: str | None = None


class CaseContextUpdate(BaseModel):
    context: dict[str, Any]


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    label: str | None
    context: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class CustomFieldInput(BaseModel):
    name: str
    label: str
    type: str
    options: list[dict] | list[str] | None = None
    unit: str | None = None
    placeholder: str | None = None
    required: bool = False
    show_only_if: dict[str, str] | None = None  # {"field": "name", "equals": "value"}


class CustomSectionInput(BaseModel):
    title: str
    description: str | None = None
    fields: list[CustomFieldInput]


class CustomAssessmentCreate(BaseModel):
    title: str
    blurb: str | None = None
    sections: list[CustomSectionInput]
    interpretation_prompt: str
    created_by: str


class CustomAssessmentEdit(BaseModel):
    title: str
    blurb: str | None = None
    sections: list[CustomSectionInput]
    interpretation_prompt: str
    created_by: str


class CustomAssessmentVersionOut(BaseModel):
    version_number: int
    title: str
    blurb: str | None
    created_by: str
    created_at: datetime


class AssessmentDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    key: str
    title: str
    category: str
    program_id: int | None
    kind: str
    interaction: str
    blurb: str | None
    is_builtin: bool
    active_version: int
    fields: dict[str, Any] | None = None
    interpretation_prompt: str | None = None


class AssessmentResultCreate(BaseModel):
    assessment_definition_key: str
    answers: dict[str, Any]


class AssessmentResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    case_id: uuid.UUID
    assessment_definition_id: uuid.UUID
    version_used: int
    answers: dict[str, Any]
    result: dict[str, Any]
    completed_at: datetime


class ClinicalReviewCreate(BaseModel):
    reviewer_name: str
    notes: str | None = None


class ClinicalReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    assessment_definition_id: uuid.UUID
    reviewer_name: str
    notes: str | None
    reviewed_at: datetime


class PatientDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    extraction_status: str
    extraction_error: str | None
    uploaded_by: str | None
    source: str
    uploaded_at: datetime


class PatientDocumentDetailOut(PatientDocumentOut):
    extracted_text: str | None


class StaffCreate(BaseModel):
    auth0_sub: str
    name: str
    email: str | None = None
    role: str  # care_manager|nurse|provider|admin


class StaffInviteCreate(BaseModel):
    name: str
    email: str
    role: str  # care_manager|nurse|provider|admin


class StaffUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    email: str | None
    role: str
    status: str
    created_at: datetime


class PatientStaffAssignmentCreate(BaseModel):
    staff_id: uuid.UUID
    role_on_patient: str


class PatientStaffAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    staff: StaffOut
    role_on_patient: str
    assigned_at: datetime


class StaffBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    role: str


class PatientListOut(PatientOut):
    """A separate, richer schema used only by the patient list endpoint — kept
    distinct from the base PatientOut so other endpoints (create, get single
    patient) don't pay for computing these aggregates when they don't need them."""
    care_team: list[StaffBriefOut] = []
    assessments_completed: int = 0
    assessments_total: int = 0
    open_tasks_count: int = 0


class PaginatedPatientsOut(BaseModel):
    items: list[PatientListOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entity_type: str
    entity_id: str
    action: str
    performed_by: str | None
    details: dict | None
    performed_at: datetime


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    title: str
    body: str
    related_patient_id: uuid.UUID | None
    related_entity_id: str | None
    source_rule_name: str | None
    is_read: bool
    email_sent: bool
    created_at: datetime


class CareNoteCreate(BaseModel):
    content: str


class CareNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    author: StaffBriefOut | None
    content: str
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    assigned_to_id: uuid.UUID | None = None
    due_date: date | None = None


class TaskUpdate(BaseModel):
    status: str  # pending|in_progress|completed


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    title: str
    description: str | None
    assigned_to: StaffBriefOut | None
    created_by: StaffBriefOut | None
    due_date: date | None
    status: str
    source_rule_name: str | None
    created_at: datetime


class InterventionCreate(BaseModel):
    description: str


class InterventionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    goal_id: uuid.UUID
    description: str
    status: str
    created_at: datetime


class GoalCreate(BaseModel):
    description: str
    target_date: date | None = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: uuid.UUID
    description: str
    target_date: date | None
    status: str
    source_rule_name: str | None
    created_at: datetime
    interventions: list[InterventionOut] = []


class ProblemCreate(BaseModel):
    description: str


class ProblemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    description: str
    status: str
    created_at: datetime
    goals: list[GoalOut] = []


class OnboardingStepOut(BaseModel):
    key: str
    label: str
    complete: bool


class OnboardingProgressOut(BaseModel):
    steps: list[OnboardingStepOut]
    program_status: str


class QuestionLibraryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    category: str
    program_id: int | None
    label: str
    field_type: str
    options: list[str | dict[str, Any]] | None


class BusinessRuleCreate(BaseModel):
    dsl_text: str
    governance: str  # clinical|operational


class BusinessRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    trigger: str
    dsl_text: str
    condition_tree: dict
    actions: list
    governance: str
    enabled: bool
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class RuleEnableRequest(BaseModel):
    confirmed: bool = False  # required true for clinical-tier rules — the frontend's sign-off gate


class RuleTestRequest(BaseModel):
    dsl_text: str
    tenant: dict = {}
    event: dict = {}
    state: dict = {}  # e.g. {"care_plan": {"current": "Active"}, "escalation": {"current": "Normal"}}
    patient_id: str | None = None  # if provided, actions describe what WOULD happen to this real patient; still a dry run either way


class RuleFireEventRequest(BaseModel):
    trigger: str
    tenant: dict = {}
    event: dict = {}
    state: dict = {}
    patient_id: str
    dry_run: bool = True


class RuleExecutionLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rule_id: uuid.UUID | None
    rule_name: str | None
    trigger: str
    patient_id: uuid.UUID | None
    event_payload: dict
    matched: bool
    actions_executed: list | None
    performed_at: datetime
