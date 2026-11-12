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
