"""
Tests for the pure DSL parser/evaluator (rules_engine.py) — no database
dependency at all, matching the module's own design. These are the same
behaviors verified by hand against the reference prototype's own example
rules during development; formalized here so they can't silently regress.
"""

import pytest

from app.rules_engine import RuleParseError, evaluate_condition, parse_action, parse_rule, validate_action


def test_parses_a_basic_rule():
    dsl = '''RULE "Kidney - eGFR below threshold"
WHEN lab.result.received
IF event.code == "eGFR" AND event.value < tenant.egfr_threshold
THEN
  CREATE_TASK "Review renal function" ASSIGN "Nephrologist" DUE "next_visit"
  TRANSITION escalation TO "Escalated"
END'''
    rule = parse_rule(dsl)
    assert rule.name == "Kidney - eGFR below threshold"
    assert rule.trigger == "lab.result.received"
    assert len(rule.actions) == 2
    assert rule.actions[0] == {"type": "CREATE_TASK", "label": "Review renal function", "assignee": "Nephrologist", "due": "next_visit"}
    assert rule.actions[1] == {"type": "TRANSITION", "workflow": "escalation", "target": "Escalated"}


def test_condition_evaluates_correctly_against_real_values():
    dsl = '''RULE "test"
WHEN x
IF event.code == "eGFR" AND event.value < tenant.egfr_threshold
THEN
  ESCALATE_RISK "high"
END'''
    rule = parse_rule(dsl)
    ctx_matches = {"event": {"code": "eGFR", "value": 26}, "tenant": {"egfr_threshold": 30}, "state": {}}
    assert evaluate_condition(rule.condition_tree, ctx_matches) is True

    ctx_no_match = {"event": {"code": "eGFR", "value": 35}, "tenant": {"egfr_threshold": 30}, "state": {}}
    assert evaluate_condition(rule.condition_tree, ctx_no_match) is False


def test_or_not_and_parentheses_operator_precedence():
    rule = parse_rule('''RULE "test"
WHEN x
IF NOT (event.a == "1" OR event.b == "2")
THEN
  ESCALATE_RISK "high"
END''')
    assert evaluate_condition(rule.condition_tree, {"event": {"a": "1", "b": "9"}, "tenant": {}, "state": {}}) is False
    assert evaluate_condition(rule.condition_tree, {"event": {"a": "9", "b": "9"}, "tenant": {}, "state": {}}) is True


def test_state_dot_workflow_dot_current_lookup():
    """The reference's state.<workflow>.current field reference — this is what
    lets a rule condition on the patient's current escalation/care_plan/visit
    stage, not just the incoming event."""
    rule = parse_rule('''RULE "test"
WHEN task.overdue
IF state.escalation.current == "Escalated" AND event.overdue_days > 1
THEN
  ESCALATE_RISK "high"
END''')
    ctx = {"event": {"overdue_days": 2}, "tenant": {}, "state": {"escalation": {"current": "Escalated"}}}
    assert evaluate_condition(rule.condition_tree, ctx) is True

    ctx_wrong_state = {"event": {"overdue_days": 2}, "tenant": {}, "state": {"escalation": {"current": "Normal"}}}
    assert evaluate_condition(rule.condition_tree, ctx_wrong_state) is False


@pytest.mark.parametrize("bad_dsl,expected_fragment", [
    ('WHEN x\nIF 1 == 1\nTHEN\nEND', "RULE"),
    ('RULE "x"\nIF 1 == 1\nTHEN\nEND', "WHEN"),
    ('RULE "x"\nWHEN y\nTHEN\nEND', "IF"),
    ('RULE "x"\nWHEN y\nIF 1 == 1\nEND', "THEN"),
])
def test_malformed_rules_raise_clear_errors(bad_dsl, expected_fragment):
    with pytest.raises(RuleParseError) as exc_info:
        parse_rule(bad_dsl)
    assert any(expected_fragment in e for e in exc_info.value.errors)


def test_unrecognized_action_line_raises():
    with pytest.raises(RuleParseError) as exc_info:
        parse_rule('RULE "x"\nWHEN y\nIF 1 == 1\nTHEN\n  NOT_A_REAL_ACTION "x"\nEND')
    assert "Unrecognized action" in exc_info.value.errors[0]


def test_parse_action_recognizes_all_six_action_types():
    assert parse_action('CREATE_TASK "a" ASSIGN "b" DUE "c"') == {"type": "CREATE_TASK", "label": "a", "assignee": "b", "due": "c"}
    assert parse_action('UPDATE_STATUS "a"') == {"type": "UPDATE_STATUS", "value": "a"}
    assert parse_action('ADD_GOAL "a"') == {"type": "ADD_GOAL", "goal": "a"}
    assert parse_action('SEND_NOTIFICATION "a" TO "b"') == {"type": "SEND_NOTIFICATION", "template": "a", "to": "b"}
    assert parse_action('TRANSITION care_plan TO "Active"') == {"type": "TRANSITION", "workflow": "care_plan", "target": "Active"}
    assert parse_action('ESCALATE_RISK "high"') == {"type": "ESCALATE_RISK", "level": "high"}


def test_validate_action_rejects_unknown_workflow():
    error = validate_action({"type": "TRANSITION", "workflow": "not_a_real_workflow", "target": "Active"})
    assert error is not None
    assert "not_a_real_workflow" in error


def test_validate_action_rejects_invalid_state_for_a_real_workflow():
    error = validate_action({"type": "TRANSITION", "workflow": "care_plan", "target": "Not A Real State"})
    assert error is not None


def test_validate_action_accepts_a_real_transition():
    assert validate_action({"type": "TRANSITION", "workflow": "care_plan", "target": "Active"}) is None
