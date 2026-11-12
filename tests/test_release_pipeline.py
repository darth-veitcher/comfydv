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


# --- release workflow (contracts/release-workflow.md, W1-W10) ---------------


def _release() -> dict:
    return load_workflow("release.yml")


def _release_job() -> dict:
    return _release()["jobs"]["release"]


def _step(name_part: str) -> dict:
    matches = [s for s in _release_job()["steps"] if name_part in s.get("name", "")]
    assert len(matches) == 1, f"expected one step named like {name_part!r}"
    return matches[0]


def test_w1_runs_on_pushes_to_main_and_develop_and_on_demand():
    on = _release()["on"]
    assert sorted(on["push"]["branches"]) == ["develop", "main"]
    assert "workflow_dispatch" in on


def test_w2_one_run_per_branch_at_a_time():
    concurrency = _release()["concurrency"]
    assert "github.ref" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is False


def test_w3_uses_the_pypi_environment_on_both_branches():
    environment = _release_job()["environment"]
    name = environment["name"] if isinstance(environment, dict) else environment
    assert name == "pypi"


def test_w4_permissions_are_minimal():
    assert _release()["permissions"] == {"contents": "write", "id-token": "write"}


def test_w6_pypi_publish_is_trusted_and_idempotent():
    """W6: Trusted Publishing (no password input) and skip-existing for re-runs."""
    publish = [
        s
        for s in _release_job()["steps"]
        if s.get("uses", "").startswith("pypa/gh-action-pypi-publish")
    ]
    assert publish, "no PyPI publish step"
    for step in publish:
        inputs = step.get("with", {})
        assert "password" not in inputs
        assert inputs.get("skip-existing") is True
        assert "repository-url" not in inputs  # PyPI, not TestPyPI (research R5)


def test_w8_third_party_actions_are_pinned_to_a_commit():
    """W8: actions outside actions/* and pypa/* run with secrets, so pin a SHA."""
    for workflow in ("release.yml", "ci.yml"):
        for step in all_steps(load_workflow(workflow)):
            uses = step.get("uses", "")
            if not uses or uses.startswith(("actions/", "pypa/")):
                continue
            ref = uses.split("@", 1)[1]
            assert re.fullmatch(r"[0-9a-f]{40}", ref), (
                f"{workflow}: {uses} is not pinned"
            )


def test_w7_registry_publish_only_for_stable_releases():
    """W7: main only, only when PSR released, with the Registry key secret."""
    step = _step("Publish to the Comfy Registry")
    assert step["uses"].startswith("Comfy-Org/publish-node-action@")
    # The action checks out the triggering commit by default, which is the
    # commit before PSR's version bump: it would publish the old version.
    assert step["with"]["skip_checkout"] == "true"
    condition = step["if"]
    assert "github.ref_name == 'main'" in condition
    assert "steps.psr.outputs.released == 'true'" in condition
    assert (
        step["with"]["personal_access_token"] == "${{ secrets.REGISTRY_ACCESS_TOKEN }}"
    )


def test_w10_registry_version_is_verified():
    """W10: read the Registry API and fail if the new version is missing (SC-002)."""
    step = _step("Verify the Comfy Registry")
    assert "github.ref_name == 'main'" in step["if"]
    assert "https://api.comfy.org/nodes/comfydv/versions" in step["run"]
    # The version comes in through env, not inline in `run`: an expression in
    # a shell script is an injection risk.
    assert "steps.psr.outputs.version" in str(step.get("env", {})) + step["run"]
    steps = _release_job()["steps"]
    assert steps.index(step) > steps.index(_step("Publish to the Comfy Registry"))


def test_p3_registry_publisher_id():
    """P3: the Registry publisher that owns node `comfydv` (claimed 2026-11-12)."""
    assert load_pyproject()["tool"]["comfy"]["PublisherId"] == "darth-veitcher"


def test_w9_develop_is_synced_after_a_stable_release():
    """W9: merge main into develop, so the next release PR has no version conflicts."""
    step = _step("Sync develop")
    assert "github.ref_name == 'main'" in step["if"]
    assert "steps.psr.outputs.released == 'true'" in step["if"]
    assert "git merge" in step["run"]
    assert "git push origin develop" in step["run"]


def test_g2_registry_archive_leaves_out_development_files():
    """G2: the Registry archive holds only what ComfyUI loads."""
    ignored = {
        line.strip().rstrip("/")
        for line in (ROOT / ".comfyignore").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert {"tests", "specs", "project-management", "docs"} <= ignored


def test_changelog_has_the_insertion_flag_above_the_history():
    """P8 / R12: PSR's 'update' mode inserts each release at the flag, so the
    flag must sit above the hand-written entries, and the flag must match the
    one in pyproject.toml."""
    flag = _psr()["changelog"]["insertion_flag"]
    text = (ROOT / "CHANGELOG.md").read_text()
    assert text.count(flag) == 1
    assert text.index(flag) < text.index("## [0.1.0]")
    assert "## [Unreleased]" not in text  # renamed in the bootstrap (research R12)


def test_changelog_template_renders_only_commit_summaries():
    """T029: PSR's default template appends each commit's full body. For this
    project that gave about 1,500 lines for 0.2.0, in the changelog and in the
    GitHub Release notes. The project template renders the summary line only."""
    template_dir = ROOT / _psr()["changelog"]["template_dir"]
    changes = (template_dir / ".components" / "changes.md.j2").read_text()
    assert "format_commit_summary_line(commit)" in changes
    assert "commit.descriptions[1:]" not in changes
    for name in ("CHANGELOG.md.j2", ".release_notes.md.j2"):
        assert (template_dir / name).is_file(), name


def test_w5_prereleases_do_not_commit_to_develop():
    """W5 / FR-020: on develop PSR tags and publishes, but writes no commit, so
    pyproject.toml and CHANGELOG.md on develop never conflict with main."""
    run = _step("Python Semantic Release")["run"]
    assert "--no-commit" in run
    # The flag is set only off main: a stable release must commit its version.
    assert re.search(r'if \[ "\$\{\{ github\.ref_name \}\}" != "main" \]', run)
