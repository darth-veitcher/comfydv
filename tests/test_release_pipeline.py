"""Contract tests for the release pipeline (specs/010-release-pipeline/contracts/).

Each test checks one rule of contracts/ci-gate.md (C1-C8) or
contracts/release-workflow.md (W1-W10, P1-P8, G2) by reading the workflow
files and pyproject.toml. They need no network and no GitHub.
"""

import re
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


# --- test dependencies in CI (research R11) ----------------------------------


def test_torch_comes_from_the_cpu_index():
    """R11: the CUDA build of torch costs ~6 GB for three tests; CI uses the CPU build."""
    uv = load_pyproject()["tool"]["uv"]
    indexes = {i["name"]: i for i in uv["index"]}
    assert indexes["pytorch-cpu"]["url"] == "https://download.pytorch.org/whl/cpu"
    assert indexes["pytorch-cpu"]["explicit"] is True
    sources = uv["sources"]["torch"]
    sources = sources if isinstance(sources, list) else [sources]
    assert any(s.get("index") == "pytorch-cpu" for s in sources)


def test_torchvision_is_not_a_dependency():
    """R11: no code or test imports torchvision."""
    dev = load_pyproject()["dependency-groups"]["dev"]
    assert not any(d.startswith("torchvision") for d in dev)


# --- CI quality gate (contracts/ci-gate.md, C1-C8) ----------------------------


def _ci() -> dict:
    return load_workflow("ci.yml")


def test_c1_runs_on_pull_requests_to_develop_and_main():
    on = _ci()["on"]
    assert sorted(on["pull_request"]["branches"]) == ["develop", "main"]


def test_c2_never_uses_pull_request_target():
    """C2: pull_request_target runs fork code with the base repository's secrets."""
    assert "pull_request_target" not in _ci()["on"]


def test_c3_permissions_are_read_only():
    ci = _ci()
    assert ci["permissions"] == {"contents": "read"}
    for job in ci["jobs"].values():
        assert job.get("permissions", {"contents": "read"}) == {"contents": "read"}


def test_c4_no_step_uses_secrets():
    """C4: no ``${{ secrets.* }}`` expression (comments may mention secrets)."""
    text = (WORKFLOWS / "ci.yml").read_text()
    assert not re.search(r"\$\{\{[^}]*\bsecrets\.", text)


def test_c5_matrix_covers_python_3_11_to_3_13():
    matrix = _ci()["jobs"]["checks"]["strategy"]["matrix"]
    assert [str(v) for v in matrix["python-version"]] == ["3.11", "3.12", "3.13"]


def test_c6_installs_the_locked_versions():
    runs = [s.get("run", "") for s in _ci()["jobs"]["checks"]["steps"]]
    assert any("uv sync --frozen" in r for r in runs)


def test_c7_runs_every_quality_gate():
    runs = "\n".join(s.get("run", "") for s in _ci()["jobs"]["checks"]["steps"])
    for command in (
        "ruff check",
        "ruff format --check",
        "ty check",
        'pytest -m "not integration and not system"',
    ):
        assert command in runs, command


def test_c8_one_quality_gate_job_summarises_the_matrix():
    """C8: rulesets require one stable check name, whatever the matrix holds."""
    gate = _ci()["jobs"]["quality-gate"]
    assert gate["needs"] == "checks" or gate["needs"] == ["checks"]
    assert gate["if"] == "always()"
    runs = "\n".join(s.get("run", "") for s in gate["steps"])
    assert "needs.checks.result" in runs
