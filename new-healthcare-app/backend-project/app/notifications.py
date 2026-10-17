"""
A single, shared helper for creating a notification — mirrors app/audit.py's own
design: one function every trigger point calls, rather than each place
constructing its own Notification(...) row and its own email-sending logic
slightly differently.

Creates the in-app row FIRST, then attempts email — matching the same ordering
principle used for staff invites (app/auth0_management.py): the real, durable
thing (the in-app notification existing at all) should never be lost just
because a secondary delivery channel (email) happened to fail. email_sent on the
row itself is what lets the frontend or a future admin view distinguish "this
person was truly never told" from "they were told in-app, but the email hiccuped."
"""

from sqlalchemy.orm import Session

from app.email_service import EmailError, send_email
from app.models import Notification, Staff


def create_notification(
    db: Session,
    recipient: Staff,
    notification_type: str,
    title: str,
    body: str,
    related_patient_id: str | None = None,
    related_entity_id: str | None = None,
    source_rule_name: str | None = None,
) -> Notification:
    notification = Notification(
        recipient_staff_id=recipient.id,
        type=notification_type,
        title=title,
        body=body,
        related_patient_id=related_patient_id,
        related_entity_id=related_entity_id,
        source_rule_name=source_rule_name,
    )
    db.add(notification)
    db.commit()

    if recipient.email:
        try:
            send_email(recipient.email, title, body)
            notification.email_sent = True
            db.commit()
        except EmailError:
            # Deliberately swallowed, not re-raised — the action that triggered
            # this notification (assigning a task, say) already fully succeeded
            # by this point, and a flaky mail server is never a good enough
            # reason to make that whole request fail. email_sent staying False
            # is itself the honest record that this specific delivery path
            # didn't work, without blocking anything else.
            pass

    return notification
