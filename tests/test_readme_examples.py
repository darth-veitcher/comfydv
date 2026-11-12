"""The README's code examples run as written (docs/WRITING.md, rule 10).

Each fenced code block in README.md is either run by a test here, or listed in
``NOT_RUN`` with the reason no test can run it. A new block that is in neither
place fails ``test_every_readme_block_is_run_or_explained``.
"""

import json
import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"

_FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.MULTILINE | re.DOTALL)

# First line of each block -> why no test runs it.
NOT_RUN: dict[str, str] = {
    "cd /path/to/ComfyUI/custom_nodes": "needs a ComfyUI install and network access to clone from GitHub",
    "llama-server --models-dir ./models -c 8192": "needs a llama-server binary and model files",
    "pip install -r custom_nodes/comfydv/requirements.txt": "needs a ComfyUI install and network access to PyPI",
    "uv sync": "runs this test suite itself",
}


def _blocks() -> list[tuple[str, str]]:
    return [(lang, body) for lang, body in _FENCE.findall(README.read_text())]


def _first_line(body: str) -> str:
    return body.strip().splitlines()[0].strip()


@pytest.mark.unit
def test_every_readme_block_is_run_or_explained():
    run_here = {_first_line(b) for lang, b in _blocks() if lang == "json"}
    unexplained = [
        _first_line(b)
        for _, b in _blocks()
        if _first_line(b) not in NOT_RUN and _first_line(b) not in run_here
    ]
    assert not unexplained, (
        f"README blocks with no test and no NOT_RUN reason: {unexplained}"
    )


@pytest.mark.unit
def test_not_run_list_has_no_stale_entries():
    present = {_first_line(b) for _, b in _blocks()}
    stale = sorted(set(NOT_RUN) - present)
    assert not stale, f"NOT_RUN names blocks that are no longer in README.md: {stale}"


@pytest.mark.unit
def test_structured_output_schema_example_gives_typed_outputs():
    """The README's `output_schema` example is valid, and gives the output
    types and required-field behaviour that the README describes."""
    from comfydv.ollama import (
        _build_structured_model,
        _comfy_types_for_schema,
        _parse_output_schema,
    )

    (example,) = [b for lang, b in _blocks() if lang == "json"]
    schema = _parse_output_schema(example)

    assert _comfy_types_for_schema(schema) == ("STRING", "INT")

    model = _build_structured_model(schema)
    assert model.model_validate_json(json.dumps({"subject": "fox"})).count is None
    with pytest.raises(ValueError):
        model.model_validate_json(json.dumps({"count": 3}))  # required field missing
