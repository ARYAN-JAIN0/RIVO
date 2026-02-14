from __future__ import annotations

import pytest

from app.orchestration.state_machine import InvalidTransitionError, StateMachine


def test_state_machine_allows_valid_transition():
    sm = StateMachine({"new": {"running"}, "running": {"completed"}})
    assert sm.can_transition("new", "running") is True
    sm.assert_transition("new", "running")


def test_state_machine_rejects_invalid_transition():
    sm = StateMachine({"new": {"running"}})
    with pytest.raises(InvalidTransitionError):
        sm.assert_transition("new", "completed")
