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


def _psr() -> dict:
    return load_pyproject()["tool"]["semantic_release"]


def test_p4_psr_writes_the_project_version():
    """P4: PSR increments the static version in pyproject.toml."""
    assert _psr()["version_toml"] == ["pyproject.toml:project.version"]


def test_p5_breaking_change_is_minor_while_zero():
    """P5: while the major version is 0, a breaking change is a minor bump."""
    psr = _psr()
    assert psr["major_on_zero"] is False
    assert psr["allow_zero_version"] is True


def test_p6_commit_types_map_to_bumps():
    """P6: feat is minor; fix and perf are patch; other types release nothing."""
    options = _psr()["commit_parser_options"]
    assert options["minor_tags"] == ["feat"]
    assert options["patch_tags"] == ["fix", "perf"]


def test_p7_develop_makes_dev_prereleases():
    """P7: develop publishes X.Y.Z-dev.N, which PEP 440 makes X.Y.Z.devN."""
    develop = _psr()["branches"]["develop"]
    assert develop["match"] == "^develop$"
    assert develop["prerelease"] is True
    assert develop["prerelease_token"] == "dev"
    main = _psr()["branches"]["main"]
    assert main["match"] == "^main$"
    assert main["prerelease"] is False


def test_p8_changelog_is_updated_not_rewritten():
    """P8: 'update' keeps the hand-written history; PSR 9's default 'init' rewrites the file."""
    assert _psr()["changelog"]["mode"] == "update"
