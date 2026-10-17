"""
The calculator-plugin pattern discussed throughout this project's architecture: one
shared interface, one implementation per assessment, registered by key. This is what
keeps kidney, cardiology, and future programs from becoming parallel, drifting code
paths — the exact anti-pattern that caused the dropdown/checkbox bug to regress twice
in the original JS build.
"""

from abc import ABC, abstractmethod
from typing import Any


class Calculator(ABC):
    key: str

    @abstractmethod
    def compute(self, answers: dict[str, Any]) -> dict[str, Any]:
        """Returns {headline, headlineSeverity, metrics, flags, notes} —
        the same result shape used throughout the original JS build."""
        raise NotImplementedError
