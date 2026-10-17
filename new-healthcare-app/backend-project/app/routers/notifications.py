from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_staff
from app.database import get_db
from app.models import Notification, Staff
from app.scheduled_checks import run_due_checks
from app.schemas import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_my_notifications(unread_only: bool = False, staff: Staff = Depends(require_staff), db: Session = Depends(get_db)):
    query = db.query(Notification).filter_by(recipient_staff_id=staff.id)
    if unread_only:
        query = query.filter_by(is_read=False)
    return query.order_by(Notification.created_at.desc()).limit(100).all()


@router.get("/unread-count")
def get_unread_count(staff: Staff = Depends(require_staff), db: Session = Depends(get_db)):
    count = db.query(Notification).filter_by(recipient_staff_id=staff.id, is_read=False).count()
    return {"count": count}


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(notification_id: str, staff: Staff = Depends(require_staff), db: Session = Depends(get_db)):
    notification = db.query(Notification).filter_by(id=notification_id, recipient_staff_id=staff.id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    return notification


@router.post("/mark-all-read")
def mark_all_read(staff: Staff = Depends(require_staff), db: Session = Depends(get_db)):
    db.query(Notification).filter_by(recipient_staff_id=staff.id, is_read=False).update({"is_read": True})
    db.commit()
    return {"status": "ok"}


@router.post("/check-due")
def check_due_notifications(db: Session = Depends(get_db)):
    """The on-demand path — the frontend calls this on load. The real logic
    now lives in app.scheduled_checks.run_due_checks, shared with the actual
    background scheduler (app.scheduler), so the two can never quietly drift
    apart. This on-demand call keeps working exactly as it always has —
    running the scheduler doesn't replace it, it just means overdue items
    also get caught even when nobody has the app open."""
    result = run_due_checks(db)
    return {"notifications_created": result["notifications_created"]}
