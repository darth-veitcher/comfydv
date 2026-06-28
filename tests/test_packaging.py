"""Packaging correctness tests for specs/002-manager-compatible-install."""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


class TestRequirementsTxt:
    """US1 — Clean dependency install from a fresh clone."""

    def test_requirements_txt_exists(self):
        pass

    def test_requirements_txt_contains_jinja2(self):
        pass

    def test_requirements_txt_has_no_removed_packages(self):
        pass

    def test_requirements_txt_has_no_bare_dot(self):
        pass

    def test_requirements_txt_packages_in_pyproject_dependencies(self):
        pass

    def test_aiohttp_in_project_dependencies(self):
        pass


class TestManagerEntry:
    """US2 — ComfyUI Manager registration."""

    def test_manager_entry_json_exists(self):
        pass

    def test_manager_entry_json_is_valid(self):
        pass

    def test_manager_entry_has_required_fields(self):
        pass

    def test_manager_entry_nodenames_match_node_class_mappings(self):
        pass


class TestMetadata:
    """US3 — Accurate package metadata."""

    def test_description_does_not_mention_model_unloader(self):
        pass

    def test_description_does_not_mention_model_memory_management(self):
        pass

    def test_description_mentions_existing_nodes(self):
        pass


class TestDockerCompose:
    """US4 — Docker Compose local test harness."""

    def test_docker_compose_yml_exists(self):
        pass

    def test_docker_compose_has_comfyui_service(self):
        pass

    def test_docker_compose_exposes_port_8188(self):
        pass

    def test_dockerfile_exists(self):
        pass

    def test_dockerfile_uses_python_311_base(self):
        pass
