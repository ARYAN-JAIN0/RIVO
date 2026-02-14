"""Canonical state transition helpers for pipeline entities."""

from __future__ import annotations


class InvalidTransitionError(ValueError):
    """Raised when a disallowed state transition is attempted."""


class StateMachine:
    """Simple in-memory state machine used by orchestration scaffolding."""

    def __init__(self, transitions: dict[str, set[str]]) -> None:
        self._transitions = transitions

    def can_transition(self, current: str, target: str) -> bool:
        return target in self._transitions.get(current, set())

    def assert_transition(self, current: str, target: str) -> None:
        if not self.can_transition(current=current, target=target):
            raise InvalidTransitionError(f"Transition not allowed: {current} -> {target}")

