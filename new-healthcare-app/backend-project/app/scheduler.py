"""
The real background scheduler this app never had — until now, task_due_soon
and assessment_overdue notifications (and, before this change, nothing at
all for task.overdue) only ever got checked when the frontend happened to
call /api/notifications/check-due on page load. That's a real, working
mechanism for a demo, but it means an overdue item can go uncaught
indefinitely if no one has the app open.

Uses APScheduler's BackgroundScheduler (a real background thread, not an
async job) since the rest of this app's database access is synchronous
SQLAlchemy — an async scheduler would need its own, separate async DB path
for no real benefit here.

The interval is deliberately configurable via an env var rather than
hardcoded, since "how often" is a real operational tradeoff (more frequent
= faster detection, more DB load) that shouldn't require a code change to
adjust.
"""

import os

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.scheduled_checks import run_due_checks

SCHEDULER_INTERVAL_MINUTES = int(os.environ.get("SCHEDULER_INTERVAL_MINUTES", "15"))

_scheduler: BackgroundScheduler | None = None


def _run_due_checks_job():
    """Each run gets its own, fresh DB session — this runs on the
    scheduler's own background thread, entirely outside any request's own
    get_db dependency, so it can't reuse a request-scoped session even if it
    wanted to."""
    db = SessionLocal()
    try:
        result = run_due_checks(db)
        if result["notifications_created"] or result["overdue_events_fired"]:
            print(f"[scheduler] due-checks run: {result['notifications_created']} notification(s) created, "
                  f"{result['overdue_events_fired']} task.overdue event(s) fired.", flush=True)
    except Exception as e:
        # A single failed run must never crash the scheduler itself — the
        # next scheduled run should still happen. Logged loudly so a real
        # failure doesn't go unnoticed either.
        print(f"[scheduler] due-checks run FAILED: {e!r}", flush=True)
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return  # already running — avoid accidentally starting a second one
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_run_due_checks_job, "interval", minutes=SCHEDULER_INTERVAL_MINUTES, id="due_checks")
    _scheduler.start()
    print(f"[scheduler] started — due-checks job runs every {SCHEDULER_INTERVAL_MINUTES} minute(s).", flush=True)


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
