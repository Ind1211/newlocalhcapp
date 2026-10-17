from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import require_staff
from app.database import get_db
from app.models import Goal, Intervention, Patient, Problem, Staff
from app.schemas import GoalCreate, GoalOut, InterventionCreate, InterventionOut, ProblemCreate, ProblemOut

router = APIRouter(tags=["pgi"])


@router.get("/api/patients/{patient_id}/pgi", response_model=list[ProblemOut])
def list_problems(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return db.query(Problem).filter_by(patient_id=patient_id).order_by(Problem.created_at.desc()).all()


@router.post("/api/patients/{patient_id}/pgi", response_model=ProblemOut, status_code=201)
def create_problem(
    patient_id: str, payload: ProblemCreate,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="Problem description cannot be empty")
    problem = Problem(patient_id=patient_id, description=payload.description.strip())
    db.add(problem)
    db.commit()
    log_audit(db, "pgi_problem", problem.id, "created", staff, details={"description": problem.description}, related_patient_id=patient_id)
    return problem


@router.patch("/api/pgi/problems/{problem_id}/resolve", response_model=ProblemOut)
def resolve_problem(problem_id: str, db: Session = Depends(get_db), staff: Staff = Depends(require_staff)):
    problem = db.query(Problem).filter_by(id=problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    problem.status = "resolved"
    db.commit()
    log_audit(db, "pgi_problem", problem.id, "resolved", staff, related_patient_id=problem.patient_id)
    return problem


@router.post("/api/pgi/problems/{problem_id}/goals", response_model=GoalOut, status_code=201)
def create_goal(
    problem_id: str, payload: GoalCreate,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    problem = db.query(Problem).filter_by(id=problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="Goal description cannot be empty")
    goal = Goal(problem_id=problem_id, description=payload.description.strip(), target_date=payload.target_date)
    db.add(goal)
    db.commit()
    log_audit(db, "pgi_goal", goal.id, "created", staff, details={"description": goal.description}, related_patient_id=problem.patient_id)
    return goal


@router.patch("/api/pgi/goals/{goal_id}/status", response_model=GoalOut)
def update_goal_status(
    goal_id: str, status: str,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    if status not in {"active", "met", "not_met"}:
        raise HTTPException(status_code=400, detail="status must be one of active|met|not_met")
    goal = db.query(Goal).filter_by(id=goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    old_status = goal.status
    goal.status = status
    db.commit()
    if old_status != status:
        problem = db.query(Problem).filter_by(id=goal.problem_id).first()
        log_audit(db, "pgi_goal", goal.id, "status_changed", staff, details={"from": old_status, "to": status}, related_patient_id=problem.patient_id if problem else None)
    return goal


@router.post("/api/pgi/goals/{goal_id}/interventions", response_model=InterventionOut, status_code=201)
def create_intervention(
    goal_id: str, payload: InterventionCreate,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    goal = db.query(Goal).filter_by(id=goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="Intervention description cannot be empty")
    intervention = Intervention(goal_id=goal_id, description=payload.description.strip())
    db.add(intervention)
    db.commit()
    problem_for_goal = db.query(Problem).filter_by(id=goal.problem_id).first()
    log_audit(db, "pgi_intervention", intervention.id, "created", staff, details={"description": intervention.description}, related_patient_id=problem_for_goal.patient_id if problem_for_goal else None)
    return intervention


@router.patch("/api/pgi/interventions/{intervention_id}/status", response_model=InterventionOut)
def update_intervention_status(
    intervention_id: str, status: str,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    if status not in {"planned", "in_progress", "done"}:
        raise HTTPException(status_code=400, detail="status must be one of planned|in_progress|done")
    intervention = db.query(Intervention).filter_by(id=intervention_id).first()
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention not found")
    old_status = intervention.status
    intervention.status = status
    db.commit()
    if old_status != status:
        goal_for_intervention = db.query(Goal).filter_by(id=intervention.goal_id).first()
        problem_for_intervention = db.query(Problem).filter_by(id=goal_for_intervention.problem_id).first() if goal_for_intervention else None
        log_audit(
            db, "pgi_intervention", intervention.id, "status_changed", staff,
            details={"from": old_status, "to": status},
            related_patient_id=problem_for_intervention.patient_id if problem_for_intervention else None,
        )
    return intervention
