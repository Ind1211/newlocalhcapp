"""
Business rules engine — a faithful port of the DSL grammar, tokenizer, and
recursive-descent parser from the reference prototype (business-rules-dsl-
engine.html), rewired to actually execute against this app's real data
instead of a localStorage sandbox.

DSL grammar (unchanged from the reference):
    RULE "<name>"
    WHEN <trigger.event>
    IF <condition>
    THEN
      <action>
      <action>
    END

Condition operators: == != < > <= >=  AND  OR  NOT  ( )
Value references: event.<field>, tenant.<key>, state.<workflow>.current
Actions: CREATE_TASK "label" ASSIGN "role" DUE "due"
         UPDATE_STATUS "value"
         ADD_GOAL "goal"
         SEND_NOTIFICATION "template" TO "role"
         TRANSITION <workflow> TO "state"
         ESCALATE_RISK "level"

The three fixed "workflows" (care_plan, escalation, visit) are the same
concept as the reference's state machines, mapped onto this app's real
fields where a real field exists:
  - care_plan  → Patient.care_plan_stage (a dedicated field added specifically
                 for this — program_status alone is too coarse, just
                 active/completed)
  - escalation → Patient.risk_level (a direct, natural mapping — no new field
                 needed)
  - visit      → deliberately NOT backed by any real field. This app has no
                 visit-scheduling concept yet. TRANSITION visit actions are
                 still parsed, validated, and recorded in the execution log
                 (so they're visible and auditable), but they do not persist
                 anywhere — an honest limitation, not a silently faked one.
"""

import re
from dataclasses import dataclass, field
from typing import Any


class RuleParseError(Exception):
    """Raised with a list of human-readable errors, mirroring the reference's
    errors array — callers show these directly to whoever is authoring the rule."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


WORKFLOWS = {
    "care_plan": {"label": "Care plan status", "states": ["Draft", "Active", "Under Review", "Recovered", "Deceased"]},
    "escalation": {"label": "Escalation level", "states": ["Normal", "Elevated", "Escalated", "Crisis"]},
    "visit": {"label": "Visit scheduling", "states": ["None scheduled", "Requested", "Confirmed", "Completed"]},
}

VALID_ACTION_TYPES = {"CREATE_TASK", "UPDATE_STATUS", "ADD_GOAL", "SEND_NOTIFICATION", "TRANSITION", "ESCALATE_RISK"}


# =============================================================================
# Tokenizer + recursive-descent condition parser
# =============================================================================

_TOKEN_RE = re.compile(r'"[^"]*"|\(|\)|<=|>=|==|!=|<|>|[^\s()]+')


def tokenize_condition(text: str) -> list[str]:
    """A faithful port of the reference's tokenizer, including its real
    limitation: operators need surrounding whitespace. "1 == 1" tokenizes
    correctly into three tokens; "1==1" does not — the catch-all pattern for
    identifiers/numbers greedily consumes right through adjacent operator
    characters when nothing separates them. Every real rule (the reference's
    own examples and this app's seeded library) already writes conditions
    with spaces around operators, so this has never actually been a practical
    problem — but it's worth knowing if a hand-written rule mysteriously
    fails to parse."""
    return _TOKEN_RE.findall(text)


class _ConditionParser:
    """Mirrors the reference's parseOr/parseAnd/parseNot/parseComparison
    exactly, including operator precedence (OR lowest, AND next, NOT next,
    comparison/parens tightest) — a straight port, not a reinterpretation."""

    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def parse(self) -> dict:
        tree = self._parse_or()
        if self.pos < len(self.tokens):
            raise ValueError(f'unexpected token "{self.tokens[self.pos]}"')
        return tree

    def _parse_or(self) -> dict:
        node = self._parse_and()
        while self.peek() and self.peek().upper() == "OR":
            self.pos += 1
            node = {"type": "or", "left": node, "right": self._parse_and()}
        return node

    def _parse_and(self) -> dict:
        node = self._parse_not()
        while self.peek() and self.peek().upper() == "AND":
            self.pos += 1
            node = {"type": "and", "left": node, "right": self._parse_not()}
        return node

    def _parse_not(self) -> dict:
        if self.peek() and self.peek().upper() == "NOT":
            self.pos += 1
            return {"type": "not", "child": self._parse_not()}
        return self._parse_comparison()

    def _parse_comparison(self) -> dict:
        if self.peek() == "(":
            self.pos += 1
            node = self._parse_or()
            if self.peek() != ")":
                raise ValueError("missing closing parenthesis")
            self.pos += 1
            return node
        left = self._consume_token("left operand")
        op = self._consume_operator()
        right = self._consume_token("right operand")
        return {"type": "cmp", "left": left, "op": op, "right": right}

    def _consume_token(self, label: str) -> str:
        t = self.peek()
        if t is None:
            raise ValueError(f"unexpected end of condition, expected {label}")
        self.pos += 1
        return t

    def _consume_operator(self) -> str:
        t = self.peek()
        if t not in ("==", "!=", "<", ">", "<=", ">="):
            raise ValueError(f'expected a comparison operator, got "{t}"')
        self.pos += 1
        return t


def parse_condition(text: str) -> dict:
    return _ConditionParser(tokenize_condition(text)).parse()


def resolve_value(token: str, ctx: dict) -> Any:
    """Mirrors the reference's resolveValue exactly: quoted strings, true/
    false, numbers, then a dotted-path lookup into the context (event.*,
    tenant.*, state.*.current) — in that priority order."""
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    if token.lower() == "true":
        return True
    if token.lower() == "false":
        return False
    try:
        if token.strip() != "":
            return float(token) if "." in token else int(token)
    except ValueError:
        pass
    cur: Any = ctx
    for part in token.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def evaluate_condition(node: dict, ctx: dict) -> bool:
    node_type = node["type"]
    if node_type == "and":
        return evaluate_condition(node["left"], ctx) and evaluate_condition(node["right"], ctx)
    if node_type == "or":
        return evaluate_condition(node["left"], ctx) or evaluate_condition(node["right"], ctx)
    if node_type == "not":
        return not evaluate_condition(node["child"], ctx)
    if node_type == "cmp":
        l = resolve_value(node["left"], ctx)
        r = resolve_value(node["right"], ctx)
        op = node["op"]
        # Loose, JS-style equality on purpose — the reference uses == / !=
        # (not === ), and rules written there (e.g. comparing a numeric event
        # field against a quoted "26") are expected to keep working the same
        # way when ported here.
        try:
            if op == "==":
                return l == r or str(l) == str(r)
            if op == "!=":
                return not (l == r or str(l) == str(r))
            if op in ("<", ">", "<=", ">="):
                if l is None or r is None:
                    return False
                if op == "<":
                    return l < r
                if op == ">":
                    return l > r
                if op == "<=":
                    return l <= r
                if op == ">=":
                    return l >= r
        except TypeError:
            return False
    return False


# =============================================================================
# Action parsing
# =============================================================================

_ACTION_PATTERNS = [
    (re.compile(r'^CREATE_TASK\s+"([^"]*)"\s+ASSIGN\s+"([^"]*)"\s+DUE\s+"([^"]*)"$', re.I),
     lambda m: {"type": "CREATE_TASK", "label": m.group(1), "assignee": m.group(2), "due": m.group(3)}),
    (re.compile(r'^UPDATE_STATUS\s+"([^"]*)"$', re.I),
     lambda m: {"type": "UPDATE_STATUS", "value": m.group(1)}),
    (re.compile(r'^ADD_GOAL\s+"([^"]*)"$', re.I),
     lambda m: {"type": "ADD_GOAL", "goal": m.group(1)}),
    (re.compile(r'^SEND_NOTIFICATION\s+"([^"]*)"\s+TO\s+"([^"]*)"$', re.I),
     lambda m: {"type": "SEND_NOTIFICATION", "template": m.group(1), "to": m.group(2)}),
    (re.compile(r'^TRANSITION\s+(\S+)\s+TO\s+"([^"]*)"$', re.I),
     lambda m: {"type": "TRANSITION", "workflow": m.group(1), "target": m.group(2)}),
    (re.compile(r'^ESCALATE_RISK\s+"([^"]*)"$', re.I),
     lambda m: {"type": "ESCALATE_RISK", "level": m.group(1)}),
]


def parse_action(line: str) -> dict | None:
    for pattern, builder in _ACTION_PATTERNS:
        m = pattern.match(line)
        if m:
            return builder(m)
    return None


# =============================================================================
# Full rule parser
# =============================================================================

@dataclass
class ParsedRule:
    name: str
    trigger: str
    condition_str: str
    condition_tree: dict
    actions: list[dict] = field(default_factory=list)


def parse_rule(text: str) -> ParsedRule:
    """A direct port of the reference's parseRule — same line-by-line
    RULE/WHEN/IF/THEN/END grammar, same error messages where practical, so
    anyone already familiar with the reference DSL editor sees the same
    validation behavior here."""
    errors: list[str] = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    i = 0

    if not lines or not re.match(r"^RULE\b", lines[0], re.I):
        raise RuleParseError(["Expected a line starting with RULE."])
    name = re.sub(r'^RULE\s+', '', lines[i], flags=re.I).strip('"')
    i += 1

    if i >= len(lines) or not re.match(r"^WHEN\b", lines[i], re.I):
        raise RuleParseError(["Expected a WHEN line after RULE."])
    trigger = re.sub(r'^WHEN\s+', '', lines[i], flags=re.I)
    i += 1

    if i >= len(lines) or not re.match(r"^IF\b", lines[i], re.I):
        raise RuleParseError(["Expected an IF line after WHEN."])
    cond_parts = [re.sub(r'^IF\s+', '', lines[i], flags=re.I)]
    i += 1
    while i < len(lines) and not re.match(r"^THEN$", lines[i], re.I):
        cond_parts.append(lines[i])
        i += 1
    condition_str = " ".join(cond_parts)

    if i >= len(lines) or not re.match(r"^THEN$", lines[i], re.I):
        raise RuleParseError(["Expected a THEN line after the condition."])
    i += 1

    actions_raw = []
    while i < len(lines) and not re.match(r"^END$", lines[i], re.I):
        actions_raw.append(lines[i])
        i += 1
    if i >= len(lines) or not re.match(r"^END$", lines[i], re.I):
        raise RuleParseError(["Expected a closing END line."])

    if not condition_str.strip():
        errors.append("IF condition cannot be empty.")

    condition_tree = None
    if not errors:
        try:
            condition_tree = parse_condition(condition_str)
        except ValueError as e:
            errors.append(f"Could not parse condition: {e}")

    actions = []
    for line in actions_raw:
        parsed = parse_action(line)
        if parsed:
            actions.append(parsed)
        else:
            errors.append(f'Unrecognized action: "{line}"')

    if errors:
        raise RuleParseError(errors)

    return ParsedRule(name=name, trigger=trigger, condition_str=condition_str, condition_tree=condition_tree, actions=actions)


def validate_action(action: dict) -> str | None:
    """Returns an error string if this action would fail at execution time
    (an unknown workflow, or a target state that workflow doesn't have) — used
    at save/enable time so a bad TRANSITION is caught before it ever fires
    against a real patient, not discovered only when it silently no-ops."""
    if action["type"] == "TRANSITION":
        workflow = action.get("workflow")
        if workflow not in WORKFLOWS:
            return f'Unknown workflow "{workflow}" — must be one of {", ".join(WORKFLOWS)}.'
        if action.get("target") not in WORKFLOWS[workflow]["states"]:
            return f'"{action.get("target")}" is not a valid state for {WORKFLOWS[workflow]["label"]}.'
    return None
