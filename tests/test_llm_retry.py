"""Tests for comfydv._llm.retry — shared retry-on-blank-output helpers used
by both providers' chat() and the shared chat_structured() helper.
"""

from comfydv._llm.retry import next_seed


def test_next_seed_attempt_one_is_zero_by_default():
    assert next_seed(None, 1) == 0


def test_next_seed_increments_from_zero_when_unset():
    assert next_seed(None, 2) == 1
    assert next_seed({}, 3) == 2


def test_next_seed_starts_from_pinned_base():
    assert next_seed({"seed": 42}, 1) == 42
    assert next_seed({"seed": 42}, 2) == 43
    assert next_seed({"seed": 42}, 3) == 44


def test_next_seed_ignores_non_int_seed():
    assert next_seed({"seed": "not-an-int"}, 2) == 1
