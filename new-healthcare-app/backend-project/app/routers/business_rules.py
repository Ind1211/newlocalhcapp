"""
Business rules engine API — save/enable/disable/delete rules, test a rule in
isolation (dry-run, no real side effects), manually fire an event against the
saved library for a specific patient, and read the execution log.

Real, automatic firing from actual app events (a patient being created, an
assessment completed, etc.) lives in each of those endpoints' own routers,
calling fire_event() from this module — not here. This router is only the
authoring/management surface plus the manual test/fire tools, mirroring the
reference prototype's own split between "author & test" and the events the
rest of the real app fires on its own.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import get_current_staff
from app.database import get_db
from app.models import BusinessRule, Patient, RuleExecutionLog, Staff
from app.permissions import require_role
from app.rules_actions import execute_actions
from app.rules_engine import RuleParseError, evaluate_condition, parse_rule, validate_action
from app.schemas import (
    BusinessRuleOut,
    BusinessRuleCreate,
    RuleEnableRequest,
    RuleExecutionLogOut,
    RuleFireEventRequest,
    RuleTestRequest,
)

router = APIRouter(prefix="/api/business-rules", tags=["business-rules"])


def _build_context(tenant: dict, event: dict, state: dict) -> dict:
    return {"event": event, "tenant": tenant, "state": state}


@router.get("", response_model=list[BusinessRuleOut])
def list_rules(db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    """Deliberately open to any registered staff member for reading — seeing
    what automation exists is not the sensitive action here; authoring,
    enabling, and deleting it is (all admin-only below)."""
    return db.query(BusinessRule).order_by(BusinessRule.created_at.desc()).all()


@router.post("", response_model=BusinessRuleOut, status_code=201)
def create_rule(payload: BusinessRuleCreate, db: Session = Depends(get_db), staff: Staff = Depends(require_role("admin"))):
    """Parses and validates the DSL, then saves it as a disabled draft —
    matching the reference's lifecycle exactly: saving is never the same
    action as making a rule live."""
    if payload.governance not in ("clinical", "operational"):
        raise HTTPException(status_code=400, detail="governance must be 'clinical' or 'operational'")
    try:
        parsed = parse_rule(payload.dsl_text)
    except RuleParseError as e:
        raise HTTPException(status_code=400, detail={"errors": e.errors})

    for action in parsed.actions:
        error = validate_action(action)
        if error:
            raise HTTPException(status_code=400, detail={"errors": [error]})

    rule = BusinessRule(
        name=parsed.name, trigger=parsed.trigger, dsl_text=payload.dsl_text,
        condition_tree=parsed.condition_tree, actions=parsed.actions,
        governance=payload.governance, enabled=False, created_by=staff.name,
    )
    db.add(rule)
    db.commit()
    log_audit(db, "business_rule", rule.id, "created", staff, details={"name": rule.name, "trigger": rule.trigger})
    return rule


@router.patch("/{rule_id}", response_model=BusinessRuleOut)
def edit_rule(rule_id: str, payload: BusinessRuleCreate, db: Session = Depends(get_db), staff: Staff = Depends(require_role("admin"))):
    """Updates an existing rule's DSL in place, preserving its id — so
    execution-log history (rule_id) stays correctly linked, unlike the old
    delete-and-recreate workaround which orphaned it. Requires the rule be
    disabled first: editing a currently-enabled rule's actual logic is at
    least as consequential as enabling a new one, and this app's own
    clinical-tier confirmation gate on enabling would mean nothing if an
    enabled rule's behavior could just be silently swapped out from under it
    while live. Re-enabling after an edit goes through that same gate again,
    deliberately."""
    rule = db.query(BusinessRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if rule.enabled:
        raise HTTPException(status_code=409, detail="This rule is currently enabled. Disable it before editing, then re-enable once you're ready.")

    if payload.governance not in ("clinical", "operational"):
        raise HTTPException(status_code=400, detail="governance must be 'clinical' or 'operational'")
    try:
        parsed = parse_rule(payload.dsl_text)
    except RuleParseError as e:
        raise HTTPException(status_code=400, detail={"errors": e.errors})

    for action in parsed.actions:
        error = validate_action(action)
        if error:
            raise HTTPException(status_code=400, detail={"errors": [error]})

    old_name = rule.name
    rule.name = parsed.name
    rule.trigger = parsed.trigger
    rule.dsl_text = payload.dsl_text
    rule.condition_tree = parsed.condition_tree
    rule.actions = parsed.actions
    rule.governance = payload.governance
    db.commit()
    log_audit(db, "business_rule", rule.id, "edited", staff, details={"old_name": old_name, "new_name": rule.name, "trigger": rule.trigger})
    return rule


@router.patch("/{rule_id}/enable", response_model=BusinessRuleOut)
def enable_rule(rule_id: str, payload: RuleEnableRequest, db: Session = Depends(get_db), staff: Staff = Depends(require_role("admin"))):
    """Clinical-tier rules (thresholds, risk scoring, care plan transitions)
    require confirmed=true — the frontend is expected to show a real
    confirmation dialog before sending that, matching the reference's own
    governance gate. The backend enforces this itself rather than trusting
    the frontend to have asked, since a direct API call could otherwise
    bypass it entirely."""
    rule = db.query(BusinessRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if rule.governance == "clinical" and not payload.confirmed:
        raise HTTPException(status_code=409, detail="This is a clinical-tier rule — enabling it requires an explicit sign-off confirmation.")
    rule.enabled = True
    db.commit()
    log_audit(db, "business_rule", rule.id, "enabled", staff, details={"name": rule.name, "governance": rule.governance})
    return rule


@router.patch("/{rule_id}/disable", response_model=BusinessRuleOut)
def disable_rule(rule_id: str, db: Session = Depends(get_db), staff: Staff = Depends(require_role("admin"))):
    rule = db.query(BusinessRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.enabled = False
    db.commit()
    log_audit(db, "business_rule", rule.id, "disabled", staff, details={"name": rule.name})
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str, db: Session = Depends(get_db), staff: Staff = Depends(require_role("admin"))):
    rule = db.query(BusinessRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    log_audit(db, "business_rule", rule_id, "deleted", staff, details={"name": rule.name})


@router.post("/test")
def test_rule_in_isolation(payload: RuleTestRequest, db: Session = Depends(get_db), staff: Staff = Depends(require_role("admin"))):
    """Parses the DSL text directly (not a saved rule) and evaluates it
    against the supplied context — always a dry run, never a real write,
    since testing a rule in progress should never be able to mutate a real
    patient's record."""
    try:
        parsed = parse_rule(payload.dsl_text)
    except RuleParseError as e:
        raise HTTPException(status_code=400, detail={"errors": e.errors})

    for action in parsed.actions:
        error = validate_action(action)
        if error:
            raise HTTPException(status_code=400, detail={"errors": [error]})

    ctx = _build_context(payload.tenant, payload.event, payload.state)
    condition_result = evaluate_condition(parsed.condition_tree, ctx)

    action_results = []
    if condition_result:
        patient = None
        if payload.patient_id:
            patient = db.query(Patient).filter_by(id=payload.patient_id).first()
            if not patient:
                raise HTTPException(status_code=404, detail="patient_id given but no such patient exists")
        if patient:
            action_results = execute_actions(parsed.actions, patient, db, staff, dry_run=True)
        else:
            action_results = [{"action": a, "summary": "(no patient_id given — action not evaluated against real data)"} for a in parsed.actions]

    return {
        "name": parsed.name,
        "trigger": parsed.trigger,
        "condition_result": condition_result,
        "actions": action_results,
    }


@router.post("/fire-event")
def fire_event_manually(payload: RuleFireEventRequest, db: Session = Depends(get_db), staff: Staff = Depends(require_role("admin"))):
    """Evaluates every ENABLED saved rule listening for this trigger against a
    real patient — the manual equivalent of what a real app event does
    automatically. dry_run defaults to true; set it to false deliberately to
    actually write real changes to this patient's record."""
    patient = db.query(Patient).filter_by(id=payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    result = fire_event(db, payload.trigger, payload.event, patient, staff, dry_run=payload.dry_run, tenant=payload.tenant, state=payload.state)
    return result


@router.get("/execution-log", response_model=list[RuleExecutionLogOut])
def get_execution_log(patient_id: str | None = None, limit: int = 100, db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    query = db.query(RuleExecutionLog)
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    return query.order_by(RuleExecutionLog.performed_at.desc()).limit(min(limit, 300)).all()


def fire_event(
    db: Session, trigger: str, event: dict, patient: Patient, staff: Staff | None,
    dry_run: bool = False, tenant: dict | None = None, state: dict | None = None,
) -> dict:
    """The real entry point every actual app event should call — patient
    creation, assessment completion, program enrollment, and so on. Evaluates
    every enabled rule listening for this trigger, in save order (matching
    the reference's own "evaluated in the order they were saved" behavior),
    logging every rule checked — matched or not — not just the ones that ran.

    This is intentionally the single place both the manual "fire event" tool
    and every real automatic trigger point call through, so there is only
    one execution path to keep correct, not two that could quietly drift
    apart."""
    ctx = _build_context(tenant or {}, event, state or {})
    rules = db.query(BusinessRule).filter_by(trigger=trigger, enabled=True).order_by(BusinessRule.created_at).all()

    fired = []
    for rule in rules:
        matched = evaluate_condition(rule.condition_tree, ctx)
        actions_executed = None
        if matched:
            actions_executed = execute_actions(rule.actions, patient, db, staff, dry_run=dry_run, rule_name=rule.name)
            fired.append({"rule_id": str(rule.id), "rule_name": rule.name, "actions": actions_executed})

        if not dry_run:
            db.add(RuleExecutionLog(
                rule_id=rule.id, rule_name=rule.name, trigger=trigger, patient_id=patient.id,
                event_payload=event, matched=matched,
                actions_executed=[a["summary"] for a in actions_executed] if actions_executed else None,
            ))
    if not dry_run:
        db.commit()

    return {"trigger": trigger, "rules_checked": len(rules), "rules_matched": len(fired), "fired": fired}
