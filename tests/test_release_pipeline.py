"""Contract tests for the release pipeline (specs/010-release-pipeline/contracts/).

Each test checks one rule of contracts/ci-gate.md (C1-C8) or
contracts/release-workflow.md (W1-W10, P1-P8, G2) by reading the workflow
files and pyproject.toml. They need no network and no GitHub.
"""

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def load_workflow(name: str) -> dict:
    """Parse a workflow file. PyYAML reads the key ``on`` as ``True``, so map it back."""
    data = yaml.safe_load((WORKFLOWS / name).read_text())
    if True in data:
        data["on"] = data.pop(True)
    return data


def load_pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def all_steps(workflow: dict) -> list[dict]:
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


# --- pyproject.toml (contracts/release-workflow.md, P1-P8) ------------------


def test_p1_project_name_is_comfydv():
    """P1: the Comfy Registry node ID is `comfydv` and cannot change."""
    assert load_pyproject()["project"]["name"] == "comfydv"


def test_p2_version_is_static():
    """P2: the Comfy Registry reads a literal `version`, so it is not dynamic."""
    project = load_pyproject()["project"]
    assert isinstance(project.get("version"), str)
    assert "version" not in project.get("dynamic", [])
