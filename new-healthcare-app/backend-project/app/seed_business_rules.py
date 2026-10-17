"""
Seeds a comprehensive starting rule library for a kidney/cardiology care
program — the 6-rule patient lifecycle pack adapted from the reference
prototype (business-rules-dsl-engine.html), plus new rules purpose-built for
this app's actual clinical domain and its real, wired trigger points
(patient.imported, patient.enrolled, assessment.completed,
care_plan.review_due — confirmed live against real endpoints, not just
theoretical).

lab.result.received and task.overdue are included as manually-testable
examples only — this app has no lab-results-received or automatic overdue-
detection endpoint wired to fire them yet, matching how the reference itself
treats them (testable via "fire event," not automatically triggered).

Run with: python3 -m app.seed_business_rules
Idempotent — running it again will not create duplicates; it skips any rule
whose name already exists in the library.
"""

from app.database import SessionLocal
from app.models import BusinessRule
from app.rules_engine import parse_rule


RULES = [
    # =========================================================================
    # Patient lifecycle pack (adapted from the reference's 6-rule default set)
    # =========================================================================
    {
        "governance": "operational",
        "dsl": '''RULE "Imported patient needs consent & enrollment outreach"
WHEN patient.imported
IF event.source == "tenant_admin_import"
THEN
  CREATE_TASK "Outreach - obtain consent and enroll patient" ASSIGN "Care Admin" DUE "24h"
  TRANSITION care_plan TO "Draft"
END''',
    },
    {
        "governance": "operational",
        "dsl": '''RULE "Newly enrolled patient needs intake assessment scheduled"
WHEN patient.enrolled
IF 1 == 1
THEN
  CREATE_TASK "Schedule and complete intake assessment" ASSIGN "Care Admin" DUE "24h"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Completed intake assessment activates the care plan"
WHEN assessment.completed
IF event.mode == "manual_intake"
THEN
  TRANSITION care_plan TO "Active"
  CREATE_TASK "Review AI-recommended care plan changes" ASSIGN "Care Admin" DUE "same_day"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Recovery confirmed halts the care plan cycle"
WHEN care_plan.review_due
IF event.outcome == "Recovered"
THEN
  TRANSITION care_plan TO "Recovered"
  SEND_NOTIFICATION "recovery_confirmed" TO "assigned_care_team"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Unresolved case transitions to a new care plan"
WHEN care_plan.review_due
IF event.outcome == "Not recovered"
THEN
  TRANSITION care_plan TO "Under Review"
  CREATE_TASK "Select and activate next care plan template" ASSIGN "Care Admin" DUE "next_visit"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Patient deceased halts the care plan cycle"
WHEN care_plan.review_due
IF event.outcome == "Deceased"
THEN
  TRANSITION care_plan TO "Deceased"
  SEND_NOTIFICATION "patient_deceased" TO "assigned_care_team"
END''',
    },

    # =========================================================================
    # Generic assessment-severity escalation — applies across any assessment,
    # not just a specific one, since a "critical" or "warning" headline means
    # the same thing regardless of which calculator produced it.
    # =========================================================================
    {
        "governance": "clinical",
        "dsl": '''RULE "Critical assessment result triggers urgent risk escalation"
WHEN assessment.completed
IF event.severity == "critical"
THEN
  ESCALATE_RISK "critical"
  CREATE_TASK "Urgent review of critical assessment result" ASSIGN "Nurse" DUE "24h"
END''',
    },
    {
        "governance": "operational",
        "dsl": '''RULE "Warning-severity result prompts a follow-up check"
WHEN assessment.completed
IF event.severity == "warning"
THEN
  CREATE_TASK "Follow up on warning-level assessment result" ASSIGN "Nurse" DUE "24h"
END''',
    },

    # =========================================================================
    # Kidney-specific
    # =========================================================================
    {
        "governance": "clinical",
        "dsl": '''RULE "Critical CKD staging result triggers nephrology referral"
WHEN assessment.completed
IF event.assessment_key == "ckd_staging" AND event.severity == "critical"
THEN
  TRANSITION care_plan TO "Under Review"
  CREATE_TASK "Nephrology referral - critical CKD staging result" ASSIGN "Care Admin" DUE "24h"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Peritoneal dialysis adequacy concern flagged for provider review"
WHEN assessment.completed
IF event.assessment_key == "pd_adequacy" AND event.severity == "warning"
THEN
  CREATE_TASK "Review dialysis adequacy result" ASSIGN "Care Admin" DUE "same_day"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Post-transplant BK viremia concern flagged for follow-up"
WHEN assessment.completed
IF event.assessment_key == "bk_virus_nephropathy" AND event.severity == "warning"
THEN
  CREATE_TASK "Follow up on post-transplant BK viremia result" ASSIGN "Care Admin" DUE "24h"
END''',
    },

    # =========================================================================
    # Cardiology-specific
    # =========================================================================
    {
        "governance": "clinical",
        "dsl": '''RULE "Critical NYHA class triggers urgent cardiology review"
WHEN assessment.completed
IF event.assessment_key == "nyha" AND event.severity == "critical"
THEN
  CREATE_TASK "Urgent cardiology review - NYHA Class IV" ASSIGN "Care Admin" DUE "24h"
  ADD_GOAL "Reassess guideline-directed medical therapy; consider advanced therapies referral"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Critical Killip class signals acute cardiac risk"
WHEN assessment.completed
IF event.assessment_key == "killip" AND event.severity == "critical"
THEN
  ESCALATE_RISK "critical"
  SEND_NOTIFICATION "urgent_cardiac_alert" TO "assigned_care_team"
  CREATE_TASK "Urgent review - Killip Class IV result" ASSIGN "Care Admin" DUE "24h"
END''',
    },

    # =========================================================================
    # Dementia-specific escalation rules. Two paths genuinely reach "critical"
    # severity for this program: the real, deterministic Cognitive Screening
    # Index calculator (>=70% impairment), and the AI-interpreted dementia
    # assessments, whose interpretation_prompt already instructs the model to
    # flag severe findings (potential delirium, elopement risk, physical
    # aggression, hallucinations) as critical. The mandatory Basic Patient
    # Intake's own calculator never produces "critical" severity by design —
    # a rule conditioned on basic_intake + critical would never fire, so none
    # of these target that assessment.
    # =========================================================================
    {
        "governance": "clinical",
        "dsl": '''RULE "Critical cognitive screening result triggers urgent dementia review"
WHEN assessment.completed
IF event.assessment_key == "dementia_cognitive_screening_index" AND event.severity == "critical"
THEN
  ESCALATE_RISK "critical"
  CREATE_TASK "Urgent review - severe cognitive impairment on screening index" ASSIGN "Nurse" DUE "24h"
  SEND_NOTIFICATION "severe_cognitive_impairment" TO "assigned_care_team"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Improved cognitive screening result de-escalates risk and prompts follow-up"
WHEN assessment.completed
IF event.assessment_key == "dementia_cognitive_screening_index" AND event.severity == "warning"
THEN
  ESCALATE_RISK "medium"
  CREATE_TASK "Follow up on moderate cognitive impairment finding" ASSIGN "Nurse" DUE "24h"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Substantially improved cognitive screening result de-escalates risk"
WHEN assessment.completed
IF event.assessment_key == "dementia_cognitive_screening_index" AND (event.severity == "caution" OR event.severity == "good")
THEN
  ESCALATE_RISK "low"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Critical dementia diagnostic result may indicate delirium"
WHEN assessment.completed
IF event.assessment_key == "dementia_diagnostic___clinical_assessment" AND event.severity == "critical"
THEN
  ESCALATE_RISK "critical"
  CREATE_TASK "Urgent review - rule out delirium or acute medical cause before attributing to baseline dementia" ASSIGN "Nurse" DUE "24h"
  SEND_NOTIFICATION "possible_delirium_alert" TO "assigned_care_team"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Critical dementia risk and safety result triggers urgent review"
WHEN assessment.completed
IF event.assessment_key == "dementia_risk___safety_assessment" AND event.severity == "critical"
THEN
  ESCALATE_RISK "critical"
  CREATE_TASK "Urgent safety review - critical finding on Risk & Safety Assessment" ASSIGN "Nurse" DUE "24h"
  SEND_NOTIFICATION "critical_safety_finding" TO "assigned_care_team"
END''',
    },
    {
        "governance": "operational",
        "dsl": '''RULE "Warning-level dementia risk and safety result prompts follow-up"
WHEN assessment.completed
IF event.assessment_key == "dementia_risk___safety_assessment" AND event.severity == "warning"
THEN
  CREATE_TASK "Follow up on warning-level Risk & Safety Assessment finding" ASSIGN "Nurse" DUE "24h"
END''',
    },
    {
        "governance": "clinical",
        "dsl": '''RULE "Critical behavioral finding requires immediate escalation"
WHEN assessment.completed
IF event.assessment_key == "dementia_functional___behavioral_assessment" AND event.severity == "critical"
THEN
  ESCALATE_RISK "critical"
  CREATE_TASK "Urgent behavioral and safety review - critical BPSD finding" ASSIGN "Nurse" DUE "24h"
  SEND_NOTIFICATION "critical_behavioral_finding" TO "assigned_care_team"
END''',
    },
    {
        "governance": "operational",
        "dsl": '''RULE "High caregiver strain flagged for respite care referral"
WHEN assessment.completed
IF event.assessment_key == "dementia_psychosocial___caregiver_assessment" AND event.severity == "critical"
THEN
  CREATE_TASK "Respite care and caregiver support referral - high caregiver strain identified" ASSIGN "Care Admin" DUE "24h"
END''',
    },

    # automatically yet (this app has no lab-result-received integration or
    # automatic overdue-scan trigger point wired to the rules engine), but
    # they're valid, useful examples for "test in isolation" / "fire event."
    # =========================================================================
    {
        "governance": "clinical",
        "dsl": '''RULE "Kidney - eGFR below threshold"
WHEN lab.result.received
IF event.code == "eGFR" AND event.value < tenant.egfr_threshold
THEN
  CREATE_TASK "Review renal function" ASSIGN "Nephrologist" DUE "next_visit"
  TRANSITION escalation TO "Escalated"
  TRANSITION care_plan TO "Under Review"
END''',
    },
    {
        "governance": "operational",
        "dsl": '''RULE "Escalated case with overdue task needs a visit requested"
WHEN task.overdue
IF state.escalation.current == "Escalated" AND event.overdue_days > 1
THEN
  SEND_NOTIFICATION "care_team_alert" TO "assigned_care_team"
  CREATE_TASK "Follow-up call" ASSIGN "Nurse" DUE "24h"
  TRANSITION visit TO "Requested"
END''',
    },
]


def seed_business_rules():
    db = SessionLocal()
    created = 0
    skipped = 0
    try:
        for spec in RULES:
            parsed = parse_rule(spec["dsl"])
            existing = db.query(BusinessRule).filter_by(name=parsed.name).first()
            if existing:
                skipped += 1
                continue
            rule = BusinessRule(
                name=parsed.name, trigger=parsed.trigger, dsl_text=spec["dsl"],
                condition_tree=parsed.condition_tree, actions=parsed.actions,
                governance=spec["governance"], enabled=False, created_by="system (seed)",
            )
            db.add(rule)
            created += 1
        db.commit()
        print(f"  Business rules seeded: {created} created, {skipped} already existed and were skipped.")
        print("  All seeded as disabled drafts — review and enable each one deliberately, especially the clinical-tier ones.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_business_rules()
