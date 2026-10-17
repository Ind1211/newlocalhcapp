"""
Real role-based restrictions, layered on top of app/auth.py's require_staff.

require_staff only ever answered "is this a genuinely registered staff member at
all?" — never "is this specific person authorized for this specific action."
That gap meant, until now, any registered staff account — including a
nurse-level one — could invite another admin, deactivate any other staff member,
or delete any care note regardless of who actually wrote it. This module is
what actually closes that gap, not just documents it as a known limitation.

Deliberately narrow in scope: this restricts the small set of actions that are
genuinely administrative or genuinely personal (staff account management,
deleting someone else's note) — it does not attempt a full permissions matrix
across every endpoint in this app. Most clinical work (tasks, PGI, assessments,
care team assignment) stays open to any registered staff member, since
restricting those further wasn't part of what was actually flagged as a gap.
"""

from fastapi import Depends, HTTPException

from app.auth import require_staff
from app.models import Staff


def require_role(*allowed_roles: str):
    """A dependency FACTORY, not a dependency itself — call it with the roles
    allowed for a given endpoint (e.g. Depends(require_role("admin"))). Returns
    the actual Staff object on success, exactly like require_staff does, so an
    endpoint using this doesn't need a second, separate dependency just to get
    the caller's own identity."""
    def _check(staff: Staff = Depends(require_staff)) -> Staff:
        if staff.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"This action requires one of these roles: {', '.join(allowed_roles)}. Your role is '{staff.role}'.",
            )
        return staff
    return _check
