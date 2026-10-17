from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import require_staff
from app.database import get_db
from app.models import Patient, Staff, Task
from app.notifications import create_notification
from app.schemas import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api/patients", tags=["tasks"])

VALID_STATUSES = {"pending", "in_progress", "completed"}


@router.get("/{patient_id}/tasks", response_model=list[TaskOut])
def list_tasks(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    # Incomplete work first, most-recently-created within each group — a
    # completed task has nothing more to act on, so it's more useful sorted out
    # of the way rather than mixed in by date alone.
    tasks = db.query(Task).filter_by(patient_id=patient_id).order_by(Task.created_at.desc()).all()
    return sorted(tasks, key=lambda t: t.status == "completed")


@router.post("/{patient_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(
    patient_id: str, payload: TaskCreate,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Task title cannot be empty")
    task = Task(
        patient_id=patient_id, title=payload.title.strip(), description=payload.description,
        assigned_to_id=str(payload.assigned_to_id) if payload.assigned_to_id else None,
        due_date=payload.due_date, created_by_id=staff.id,
    )
    db.add(task)
    db.commit()
    log_audit(db, "task", task.id, "created", staff, details={"title": task.title}, related_patient_id=patient_id)

    # Notify the assignee — but not if they assigned it to themselves, since
    # that's not really "someone telling you about a new task," it's just you
    # making a note for yourself.
    if task.assigned_to_id and str(task.assigned_to_id) != str(staff.id):
        assignee = db.query(Staff).filter_by(id=task.assigned_to_id).first()
        if assignee:
            create_notification(
                db, assignee,
                "task_assigned",
                f"New task: {task.title}",
                f"{staff.name} assigned you a task for {patient.name}: \"{task.title}\"" + (f" (due {task.due_date})" if task.due_date else ""),
                related_patient_id=patient_id, related_entity_id=str(task.id),
            )
    return task


@router.patch("/{patient_id}/tasks/{task_id}", response_model=TaskOut)
def update_task_status(
    patient_id: str, task_id: str, payload: TaskUpdate,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(VALID_STATUSES)}")
    task = db.query(Task).filter_by(id=task_id, patient_id=patient_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    old_status = task.status
    task.status = payload.status
    db.commit()
    if old_status != payload.status:
        log_audit(db, "task", task.id, "status_changed", staff, details={"from": old_status, "to": payload.status}, related_patient_id=patient_id)
    return task


@router.delete("/{patient_id}/tasks/{task_id}", status_code=204)
def delete_task(
    patient_id: str, task_id: str,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    task = db.query(Task).filter_by(id=task_id, patient_id=patient_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task_title = task.title
    db.delete(task)
    db.commit()
    log_audit(db, "task", task_id, "deleted", staff, details={"title": task_title}, related_patient_id=patient_id)
