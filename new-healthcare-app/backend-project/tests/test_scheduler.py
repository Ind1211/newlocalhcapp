"""
Tests for the real background scheduler (app.scheduler) — it needs to start
and stop cleanly, never start a second instance if called twice, and never
let one failed run crash the whole scheduler and silently stop all future
runs.
"""

from unittest.mock import patch

import app.scheduler as scheduler_module


def teardown_function():
    """Every test in this file starts/stops the real module-level scheduler
    — always leave it stopped afterward so one test's scheduler state can
    never bleed into the next test."""
    scheduler_module.stop_scheduler()


def test_start_and_stop_scheduler_cleanly():
    scheduler_module.start_scheduler()
    assert scheduler_module._scheduler is not None
    assert scheduler_module._scheduler.running is True

    scheduler_module.stop_scheduler()
    assert scheduler_module._scheduler is None


def test_starting_twice_does_not_create_a_second_scheduler():
    scheduler_module.start_scheduler()
    first_instance = scheduler_module._scheduler

    scheduler_module.start_scheduler()
    second_instance = scheduler_module._scheduler

    assert first_instance is second_instance


def test_stopping_when_never_started_does_not_raise():
    scheduler_module.stop_scheduler()  # should be a no-op, not an error


def test_a_failed_run_does_not_raise_and_is_swallowed():
    """The scheduled job function itself must never let a real exception
    escape — that would crash the background thread and silently stop all
    future scheduled runs with no obvious symptom anywhere in the app."""
    with patch("app.scheduler.run_due_checks", side_effect=RuntimeError("simulated failure")):
        scheduler_module._run_due_checks_job()  # must not raise
