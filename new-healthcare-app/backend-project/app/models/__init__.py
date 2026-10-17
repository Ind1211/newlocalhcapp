import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Program(Base):
    """kidney / cardiology / diabetes — a row, not a fork in the code. Assessments and
    question-library items point here via program_id, matching the 'program is a tag,
    never a hard partition' principle established for the cardiorenal integration."""

    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(10), nullable=True)


class PatientProgram(Base):
    """The real fix for 'a patient can have both kidney and heart issues' — this is
    a genuine many-to-many relationship to the existing Program table, not a
    free-text label. care_pathway (below) stays as a legacy display field for
    patients created before this existed; new code should read/write through
    this table, not that column."""

    __tablename__ = "patient_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="programs")
    program: Mapped["Program"] = relationship()


class PatientDocument(Base):
    """A document uploaded for a patient — a referral letter, lab report, discharge
    summary, etc. The raw file itself lives in Azure Blob Storage (object storage),
    not in
    Postgres — this row is metadata plus the extracted text, which is what
    auto-fill and care-plan generation actually read. Keeping the raw file and its
    extracted text as two separate things matters: extraction can be re-run later
    (a better extraction method, a fix to a parsing bug) without needing to
    re-upload anything, since the original file is still sitting in object storage."""

    __tablename__ = "patient_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|ok|failed
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 'upload'|'voice_note' — purely a UI-display distinction (mic icon vs file
    # icon). Functionally identical either way: a voice note IS a real stored
    # text file with its transcript as extracted_text, going through the exact
    # same auto-fill and care-plan-grounding logic as any uploaded document,
    # since both just read extracted_text without caring where it came from.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="upload")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    patient: Mapped["Patient"] = relationship()


class Patient(Base):
    """Extended for the patient roster flow — name, DOB, MRN are real fields, not
    just an internal_label. This is a deliberate reversal of this model's earlier
    de-identification stance (see git history / prior comment: 'never a real name,
    MRN, or other identifier'). That stance was right for a prototype where cases
    were anonymous case labels; it doesn't fit a patient roster, which is the whole
    point of this flow. Appropriate for prototype/demo data — a real deployment
    handling genuine PHI needs its own access-control and compliance review, which
    is outside what this migration does.

    care_pathway is now legacy — a single free-text field literally cannot
    represent a patient with both kidney and cardiac involvement, which is exactly
    the gap that motivated adding PatientProgram. Kept only so patients created
    before this existed still display something; new code reads programs, not this."""

    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    internal_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    mrn: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    care_pathway: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Payor / eligibility — real administrative fields, not previously tracked at all.
    payor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    member_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    group_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    eligibility_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # active|inactive|pending|unverified
    eligibility_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Onboarding stepper support. care_plan_created_at is set the first time an
    # integrated care plan is successfully generated for this patient — the care
    # plan itself was never persisted anywhere before this (it's generated fresh
    # on demand each time), so without this single timestamp there would be no
    # way to answer "has a care plan ever existed for this patient" at all.
    # program_status is a simple, explicit lifecycle flag a staff member sets
    # directly — nothing computes "completed" from other data, since only a
    # person can meaningfully decide a patient's program is actually finished.
    care_plan_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    program_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active|completed

    # Deliberately distinct from program_status above — that tracks whether a
    # patient's CARE PROGRAM is finished (a clinical concept; they might still be
    # an active patient in a maintenance phase). This tracks whether the patient
    # RECORD ITSELF should still appear in the active roster at all (discharged,
    # transferred, deceased, duplicate entry, etc.) — an administrative concept.
    # A soft delete, never a real one: the row and all its history (assessments,
    # documents, notes, tasks) stay intact, matching the same block-don't-delete
    # philosophy already used for Staff.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deactivated_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Contact information — genuinely absent before this; there was no way to
    # actually reach a patient from this app at all, despite tasks routinely
    # implying "call patient to follow up."
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_contact_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # phone|email|portal|mail
    preferred_language: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Deliberately nullable with no default — "no risk level assigned yet" is a
    # real, valid state for a patient who hasn't been triaged, and is NOT the
    # same thing as "low risk." Defaulting this to 'low' would make an
    # un-assessed patient look like a clinical judgment was actually made about
    # them, which would be actively misleading rather than just incomplete data.
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # low|medium|high|critical

    # Distinct from program_status (active|completed, too coarse for this) —
    # this specifically models the business-rules engine's "care_plan"
    # workflow state machine: draft|active|under_review|recovered|deceased.
    # Set by TRANSITION care_plan actions, or left null for patients never
    # touched by any rule.
    care_plan_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Deliberately distinct from any assessment-completion or task-activity
    # timestamp — this specifically answers "when did a person last actually
    # reach this patient," which is its own real event a staff member records,
    # not something inferable from other activity in the system.
    last_contact_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # onupdate=utcnow means every UPDATE to this row bumps this automatically —
    # no endpoint has to remember to set it by hand, which matters because a
    # forgotten manual update would silently break optimistic locking rather
    # than raise an obvious error. This IS the version token update_patient
    # checks against to detect two people editing the same patient at once.
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    cases: Mapped[list["Case"]] = relationship(back_populates="patient")
    programs: Mapped[list["PatientProgram"]] = relationship(back_populates="patient")

    @property
    def clinical_programs(self) -> list["Program"]:
        return [pp.program for pp in self.programs]


class Case(Base):
    """One case can hold assessments from any program at once — a patient with both
    kidney and heart involvement is one case, not split across two."""

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # The shared patient snapshot (age, sex, eGFR, ACR, vitals, key labs) — filled once,
    # used to prefill matching fields across any assessment in this case. Mirrors the
    # original app's state.patientContext, which persisted as part of the saved case.
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="cases")
    results: Mapped[list["AssessmentResult"]] = relationship(back_populates="case")


class AssessmentDefinition(Base):
    """Built-in AND custom assessments live in the same table — is_builtin just
    distinguishes them. This mirrors the JS app's single MODULES registry, which was
    kept deliberately unified rather than forked, to avoid the two-parallel-systems bug
    class that regressed there twice."""

    __tablename__ = "assessment_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # 'calculator' | 'structured'
    interaction: Mapped[str] = mapped_column(String(20), default="flat")  # 'flat' | 'wizard'
    blurb: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True)
    active_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    program: Mapped["Program"] = relationship()
    versions: Mapped[list["AssessmentVersion"]] = relationship(back_populates="definition")
    reviews: Mapped[list["ClinicalReview"]] = relationship(back_populates="definition")
    audit_log: Mapped[list["AuditLogEntry"]] = relationship(back_populates="definition")


class AssessmentVersion(Base):
    """Every saved version of an assessment's field definitions, kept indefinitely —
    a case remembers which version it used even if the assessment is edited later."""

    __tablename__ = "assessment_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_definitions.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    blurb: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    interpretation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(200), default="Unspecified")  # self-reported, not verified identity
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    definition: Mapped["AssessmentDefinition"] = relationship(back_populates="versions")


class AssessmentResult(Base):
    """One completed assessment, for one case."""

    __tablename__ = "assessment_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), index=True, nullable=False)
    assessment_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_definitions.id"), nullable=False
    )
    version_used: Mapped[int] = mapped_column(Integer, nullable=False)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {headline, metrics, flags, notes}
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped["Case"] = relationship(back_populates="results")


class AssignedAssessment(Base):
    """An assessment added to a patient's plan. Status is derived from two things,
    not stored directly: Scheduled if there's no draft and no result; In Progress if
    draft_answers has at least one real answer but no AssessmentResult exists yet;
    Completed once a matching AssessmentResult exists. draft_answers is intentionally
    separate from the final answers on AssessmentResult — saving progress never
    computes or stores a result, only Mark Complete does."""

    __tablename__ = "assigned_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), index=True, nullable=False)
    assessment_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_definitions.id"), nullable=False
    )
    draft_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title_override: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # 'template' | 'custom'
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    definition: Mapped["AssessmentDefinition"] = relationship()


class ClinicalReview(Base):
    """A real, durable version of the review-tracking feature — previously stored only
    in browser localStorage, meaning it vanished if the browser cache was cleared."""

    __tablename__ = "clinical_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_definitions.id"), nullable=False
    )
    reviewer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    definition: Mapped["AssessmentDefinition"] = relationship(back_populates="reviews")


class QuestionLibraryItem(Base):
    """program_id is nullable — null means 'general', matching the cross-cutting
    categories that show under every program filter, same as the JS question library."""

    __tablename__ = "question_library_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(150), nullable=False)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    program: Mapped["Program | None"] = relationship()


class AuditLogEntry(Base):
    """Append-only. created / edited / restored — mirrors the JS app's family.auditLog."""

    __tablename__ = "audit_log_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_definitions.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # created | edited | restored
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    performed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    definition: Mapped["AssessmentDefinition"] = relationship(back_populates="audit_log")


class Staff(Base):
    """A real staff record, distinct from Auth0's own user account — Auth0 proves
    someone is a genuine, authenticated person; this table is what makes that
    person a known member of this care team, with a real name and role the rest
    of the app can display and reason about.

    auth0_sub is Auth0's own permanent, stable user identifier (the JWT's "sub"
    claim — e.g. "auth0|507f1f77bcf86cd799439011") — never the email, since email
    can change but sub never does for a given Auth0 account. This is the join key
    between "a validly-signed token arrived" (Kong's job) and "here's who that
    actually is" (this table's job) — a distinction the backend had no way to make
    at all before this."""

    __tablename__ = "staff"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth0_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # care_manager|nurse|provider|admin
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active|inactive
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PatientStaffAssignment(Base):
    """Links a patient to a staff member with a specific role ON THIS PATIENT —
    deliberately separate from Staff.role, since the same nurse could reasonably
    be the primary contact for one patient and a secondary contact for another;
    the role in that relationship isn't always identical to their general job
    title, even though it usually is."""

    __tablename__ = "patient_staff_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id"), index=True, nullable=False)
    role_on_patient: Mapped[str] = mapped_column(String(50), nullable=False)  # care_manager|nurse|provider
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    patient: Mapped["Patient"] = relationship()
    staff: Mapped["Staff"] = relationship()


class CareNote(Base):
    """Free-text clinical notes, distinct from assessments — an assessment is
    structured data feeding a calculator or an AI interpretation; a care note is
    just what a staff member observed or decided, in their own words, with no
    computed result attached. author_id is nullable only for pre-existing rows
    from before this table required one; every new note always has a real author."""

    __tablename__ = "care_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    patient: Mapped["Patient"] = relationship()
    author: Mapped["Staff | None"] = relationship()


class Task(Base):
    """An action item — distinct from an assigned_assessment, which is clinical
    work with a computed result. A task is just something someone needs to do
    ("call patient re: missed dialysis session"), with no result to compute at
    all. assigned_to and created_by are both nullable for the same reason as
    CareNote.author_id — legacy-row tolerance, not a real design choice going
    forward."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff.id"), index=True, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|in_progress|completed
    # Set the first time the task.overdue event fires for this task — without
    # this, a scheduler running repeatedly would re-fire the event (and any
    # rule-driven task/notification it causes) every single cycle for the
    # same already-overdue task, not just once when it first became overdue.
    overdue_event_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Snapshot of the rule's name at creation time, not a foreign key — matches
    # RuleExecutionLog.rule_name's own reasoning: stays readable even if the
    # rule is later renamed or deleted. Null means created manually by staff.
    source_rule_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    patient: Mapped["Patient"] = relationship()
    assigned_to: Mapped["Staff | None"] = relationship(foreign_keys=[assigned_to_id])
    created_by: Mapped["Staff | None"] = relationship(foreign_keys=[created_by_id])


class Problem(Base):
    """The 'P' in PGI — a structured, itemized clinical planning framework,
    genuinely distinct from the AI-generated narrative care plans elsewhere in
    this app. Those summarize; PGI is meant to be tracked and updated over time,
    each problem with its own linked goals and each goal its own linked
    interventions."""

    __tablename__ = "pgi_problems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active|resolved
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    patient: Mapped["Patient"] = relationship()
    goals: Mapped[list["Goal"]] = relationship(back_populates="problem", cascade="all, delete-orphan")


class Goal(Base):
    """The 'G' in PGI — always tied to exactly one problem, since a goal without
    a problem it's addressing isn't really a goal in this framework, it's just an
    aspiration."""

    __tablename__ = "pgi_goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pgi_problems.id"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active|met|not_met
    source_rule_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    problem: Mapped["Problem"] = relationship(back_populates="goals")
    interventions: Mapped[list["Intervention"]] = relationship(back_populates="goal", cascade="all, delete-orphan")


class Intervention(Base):
    """The 'I' in PGI — the concrete, doable action taken toward a goal."""

    __tablename__ = "pgi_interventions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pgi_goals.id"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")  # planned|in_progress|done
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    goal: Mapped["Goal"] = relationship(back_populates="interventions")


class AuditLog(Base):
    """A genuinely generic audit log — deliberately separate from the older
    AuditLogEntry above, which is hard-scoped to assessment_definition_id and was
    built narrowly for custom assessment versioning specifically. That model
    can't represent 'a patient was edited' or 'a task was deleted' at all
    without a schema change to something already in use; this one can represent
    any entity in the app without ever needing another one.

    entity_id is stored as a plain string, not a foreign key — deliberately, since
    an audit log needs to keep working even if the entity it describes is later
    deleted, and a single column here needs to reference many different tables."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # patient|staff|task|care_note|pgi_problem|...
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # created|updated|deleted|deactivated|reactivated|...
    performed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # A real column, not something buried inside details — set consistently by
    # log_audit() itself for every child-entity event (tasks, notes, documents,
    # PGI). Without this as its own column, finding "everything that happened to
    # this patient" for a DELETED task, say, would require the task to still
    # exist as a row to look up — which is exactly backwards, since a deleted
    # entity's audit trail matters most right when the entity itself is gone.
    related_patient_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    """In-app notifications, plus a record of whether email delivery for the same
    event succeeded — deliberately tracked as one row per event, not two, since
    an in-app notification and its email are the same real-world event told two
    ways, not two independent things to keep in sync separately.

    related_patient_id is nullable — some notification types (a future
    system-wide announcement, say) might not be about a specific patient at all,
    even though every type built so far is."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # task_assigned|task_due_soon|assessment_overdue
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    related_patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patients.id"), index=True, nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. the task's own id
    source_rule_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    recipient: Mapped["Staff"] = relationship()
    related_patient: Mapped["Patient | None"] = relationship()


class BusinessRule(Base):
    """A rule authored via the DSL editor or form builder, saved as a draft
    (enabled=False) until explicitly activated. Deliberately keeps both the
    raw DSL text (for re-editing/display exactly as written) and the parsed
    condition_tree/actions (for actual evaluation) — re-parsing the DSL on
    every single event fire would be wasteful and would also mean a rule's
    behavior could silently change if the parser itself changes later, which
    a frozen, already-parsed tree avoids.

    governance='clinical' rules (thresholds, risk scoring, care plan stage
    transitions) require an explicit sign-off confirmation from the frontend
    before enabling — matching the same governance gate the reference
    prototype's DSL engine used. This is enforced by the enable endpoint
    requiring a confirmed=true flag for clinical-tier rules; the backend does
    not — and should not — silently skip that gate."""

    __tablename__ = "business_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    trigger: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    dsl_text: Mapped[str] = mapped_column(Text, nullable=False)
    condition_tree: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actions: Mapped[list] = mapped_column(JSONB, nullable=False)
    governance: Mapped[str] = mapped_column(String(20), nullable=False)  # clinical|operational
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RuleExecutionLog(Base):
    """One row per rule evaluated against a fired event — including rules that
    were checked and did NOT match, not just ones that ran. rule_id is nullable
    and rule_name is stored as its own snapshot column specifically so this log
    stays fully readable even after the rule itself is later edited or
    deleted; a foreign key alone would go stale or cascade-null the name away."""

    __tablename__ = "rule_execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_rules.id"), nullable=True, index=True)
    rule_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    trigger: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    event_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actions_executed: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
