"""Packaging correctness tests for specs/002-manager-compatible-install."""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
REQUIREMENTS = REPO_ROOT / "requirements.txt"
PYPROJECT = REPO_ROOT / "pyproject.toml"

BANNED_PACKAGES = {"colorama", "termcolor", "rich"}


def _requirements_lines() -> list[str]:
    return [
        line.strip()
        for line in REQUIREMENTS.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _pyproject_runtime_deps() -> list[str]:
    data = tomllib.loads(PYPROJECT.read_text())
    return data.get("project", {}).get("dependencies", [])


class TestRequirementsTxt:
    """US1 — Clean dependency install from a fresh clone."""

    def test_requirements_txt_exists(self):
        assert REQUIREMENTS.exists(), "requirements.txt not found at repo root"

    def test_requirements_txt_contains_jinja2(self):
        lines = _requirements_lines()
        assert any("jinja2" in line.lower() for line in lines), (
            f"jinja2 not found in requirements.txt; got: {lines}"
        )

    def test_requirements_txt_has_no_removed_packages(self):
        lines = _requirements_lines()
        for line in lines:
            pkg = line.split("=")[0].split(">")[0].split("<")[0].split("[")[0].lower()
            assert pkg not in BANNED_PACKAGES, (
                f"Removed package {pkg!r} still in requirements.txt"
            )

    def test_requirements_txt_has_no_bare_dot(self):
        lines = _requirements_lines()
        assert "." not in lines, (
            "requirements.txt contains bare '.' (editable install marker) — remove it"
        )

    def test_requirements_txt_packages_in_pyproject_dependencies(self):
        req_lines = _requirements_lines()
        runtime_deps = [d.split(">=")[0].split("==")[0].split("!=")[0].lower() for d in _pyproject_runtime_deps()]
        for line in req_lines:
            pkg = line.split("=")[0].split(">")[0].split("<")[0].split("[")[0].lower()
            assert pkg in runtime_deps, (
                f"Package {pkg!r} is in requirements.txt but not in pyproject.toml [project.dependencies]"
            )

    def test_aiohttp_in_project_dependencies(self):
        runtime_deps = [d.split(">=")[0].split("==")[0].lower() for d in _pyproject_runtime_deps()]
        assert "aiohttp" in runtime_deps, (
            "aiohttp must be in pyproject.toml [project.dependencies], not only in [dependency-groups]"
        )


MANAGER_ENTRY = REPO_ROOT / "comfy-manager-entry.json"
MANAGER_REQUIRED_FIELDS = {"author", "title", "reference", "files", "install_type", "description", "nodename"}
EXPECTED_INSTALL_TYPE = "git-clone"
EXPECTED_NODENAMES = {"Format String (Python f-strings)", "Random Choice", "Circuit Breaker"}


class TestManagerEntry:
    """US2 — ComfyUI Manager registration."""

    def test_manager_entry_json_exists(self):
        assert MANAGER_ENTRY.exists(), (
            "comfy-manager-entry.json not found at repo root — run T020-I to create it"
        )

    def test_manager_entry_json_is_valid(self):
        import json
        data = json.loads(MANAGER_ENTRY.read_text())
        assert isinstance(data, dict), "comfy-manager-entry.json must be a JSON object"

    def test_manager_entry_has_required_fields(self):
        import json
        data = json.loads(MANAGER_ENTRY.read_text())
        missing = MANAGER_REQUIRED_FIELDS - set(data.keys())
        assert not missing, f"Manager entry is missing required fields: {missing}"
        assert data.get("install_type") == EXPECTED_INSTALL_TYPE, (
            f"install_type must be {EXPECTED_INSTALL_TYPE!r}, got {data.get('install_type')!r}"
        )

    def test_manager_entry_nodenames_match_node_class_mappings(self):
        import json
        data = json.loads(MANAGER_ENTRY.read_text())
        nodenames = set(data.get("nodename", []))
        assert nodenames == EXPECTED_NODENAMES, (
            f"nodename list mismatch.\nExpected: {EXPECTED_NODENAMES}\nGot: {nodenames}"
        )


ROOT_INIT = REPO_ROOT / "__init__.py"
STALE_PHRASES = ["model memory", "model unloader", "Model Unloader", "Model Memory"]
EXPECTED_NODE_MENTIONS = ["format", "random", "circuit"]


def _root_description() -> str:
    text = ROOT_INIT.read_text()
    for line in text.splitlines():
        if "@description" in line:
            return line
    return ""


class TestMetadata:
    """US3 — Accurate package metadata."""

    def test_description_does_not_mention_model_unloader(self):
        desc = _root_description().lower()
        assert "model unloader" not in desc, (
            "root __init__.py @description references non-existent 'Model Unloader' node"
        )

    def test_description_does_not_mention_model_memory_management(self):
        desc = _root_description().lower()
        assert "model memory" not in desc, (
            "root __init__.py @description references non-existent 'model memory management'"
        )

    def test_description_mentions_existing_nodes(self):
        desc = _root_description().lower()
        for keyword in EXPECTED_NODE_MENTIONS:
            assert keyword in desc, (
                f"@description should mention the {keyword!r} node but doesn't: {desc!r}"
            )


COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"


class TestDockerCompose:
    """US4 — Docker Compose local test harness."""

    def test_docker_compose_yml_exists(self):
        assert COMPOSE_FILE.exists(), (
            "docker-compose.yml not found at repo root — run T040-I to create it"
        )

    def test_docker_compose_has_comfyui_service(self):
        import yaml
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        services = data.get("services", {})
        assert "comfyui" in services, (
            f"docker-compose.yml must define a 'comfyui' service; found: {list(services.keys())}"
        )

    def test_docker_compose_exposes_port_8188(self):
        import yaml
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        ports = data.get("services", {}).get("comfyui", {}).get("ports", [])
        port_strings = [str(p) for p in ports]
        assert any("8188" in p for p in port_strings), (
            f"comfyui service must expose port 8188; found ports: {port_strings}"
        )

    def test_dockerfile_exists(self):
        assert DOCKERFILE.exists(), (
            "docker/Dockerfile not found — run T041-I to create it"
        )

    def test_dockerfile_uses_python_311_base(self):
        text = DOCKERFILE.read_text()
        assert "FROM python:3.11" in text, (
            "Dockerfile must use python:3.11 base image (CPU-only, no CUDA)"
        )
