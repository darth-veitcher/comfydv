"""Tests for comfydv.random_choice.RandomChoice.

Covers the UI-preview addition (OUTPUT_NODE=True + a "ui": {"text": [...]}
return, mirroring ChatCompletion/FormatString so all three get a visible
text preview via src/js/preview_text.js) without changing IS_CHANGED's
change-detection semantics.
"""

import json

from comfydv.random_choice import RandomChoice, _preview_text


def test_output_node_is_true():
    assert RandomChoice.OUTPUT_NODE is True


def test_random_choice_returns_ui_result_dict():
    ret = RandomChoice().random_choice(input1="a", seed=42)
    assert isinstance(ret, dict)
    assert "ui" in ret
    assert "result" in ret
    assert ret["result"] == ("a",)


def test_ui_text_matches_the_chosen_value_for_a_string():
    ret = RandomChoice().random_choice(input1="hello", seed=42)
    assert ret["ui"]["text"] == ["hello"]


def test_ui_text_for_a_number_is_stringified():
    ret = RandomChoice().random_choice(input1=7, seed=42)
    assert ret["ui"]["text"] == ["7"]
    assert ret["result"] == (7,)


def test_seed_pins_the_choice_deterministically():
    ret1 = RandomChoice().random_choice(input1="a", input2="b", input3="c", seed=42)
    ret2 = RandomChoice().random_choice(input1="a", input2="b", input3="c", seed=42)
    assert ret1["result"] == ret2["result"]


def test_is_changed_returns_raw_pick_not_ui_wrapped_dict():
    """Regression guard: IS_CHANGED must keep returning the same shape it
    did before the ui-preview addition (the raw picked value), not the new
    {"ui": ..., "result": ...} dict random_choice() now returns — otherwise
    ComfyUI's change-detection comparison would be comparing dicts full of
    UI-only text noise instead of the actual output value."""
    result = RandomChoice.IS_CHANGED(input1="only-choice", seed=42)
    assert result == "only-choice"


class TestPreviewText:
    def test_string_passthrough(self):
        assert _preview_text("hello") == "hello"

    def test_number_stringified(self):
        assert _preview_text(42) == "42"
        assert _preview_text(3.14) == "3.14"
        assert _preview_text(True) == "True"

    def test_list_json_dumped(self):
        assert json.loads(_preview_text([1, 2, 3])) == [1, 2, 3]

    def test_unserializable_falls_back_to_str(self):
        class Weird:
            def __repr__(self):
                return "<Weird thing>"

        # json.dumps(default=str) actually succeeds here (falls back to
        # str() per-value), so this exercises the "else JSON" branch
        # rather than the outer except — confirms it never raises either
        # way.
        assert "<Weird thing>" in _preview_text(Weird())
