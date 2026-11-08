from collections.abc import Callable
from typing import Literal

from app.models import Run

Severity = Literal["low", "medium", "high"]


class Finding:
    def __init__(self, type: str, step_index: int, severity: Severity, explanation: str) -> None:
        self.type = type
        self.step_index = step_index
        self.severity = severity
        self.explanation = explanation


Rule = Callable[[Run], list[Finding]]

_RULES: list[Rule] = []


def rule(func: Rule) -> Rule:
    if func not in _RULES:
        _RULES.append(func)
    return func


def registered_rules() -> tuple[Rule, ...]:
    return tuple(_RULES)
