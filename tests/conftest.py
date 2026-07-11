"""
Pytest configuration and fixtures for comfydv tests.

This file sets up mocks for ComfyUI dependencies before any test imports.
"""

import os
import socket
import sys

import pytest

# Add src directory to Python path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def pytest_configure(config):
    """Install ComfyUI mocks into sys.modules before any test collection."""

    class MockInterruptProcessingException(Exception):
        pass

    class MockModelManagement:
        InterruptProcessingException = MockInterruptProcessingException

    comfy_module = type(sys)("comfy")
    comfy_module.model_management = MockModelManagement
    sys.modules["comfy"] = comfy_module
    sys.modules["comfy.model_management"] = MockModelManagement

    class MockRoutes:
        @staticmethod
        def post(path):
            def decorator(func):
                return func

            return decorator

        @staticmethod
        def get(path):
            def decorator(func):
                return func

            return decorator

    class MockPromptServer:
        def __init__(self):
            self.routes = MockRoutes()

    MockPromptServer.instance = MockPromptServer()

    server_module = type(sys)("server")
    server_module.PromptServer = MockPromptServer
    sys.modules["server"] = server_module

    class MockFolderPaths:
        @staticmethod
        def get_output_directory():
            return "/tmp/comfydv_test"

    sys.modules["folder_paths"] = MockFolderPaths


# ---------------------------------------------------------------------------
# Ollama fixtures (used by @pytest.mark.integration tests)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_ollama_caches():
    """Reset the shared LLM provider caches and ChatCompletion's dynamic
    RETURN_TYPES/RETURN_NAMES around every test.

    Several tests reuse identical client/model/prompt inputs across cases
    with different monkeypatched responses — without this, a later test would
    silently get an earlier test's cached result instead of exercising its
    own fake. RETURN_TYPES/RETURN_NAMES are class-level mutable state (set by
    ChatCompletion.update_outputs for structured_output mode) shared across
    every test in the module — without resetting them, a structured-output
    test would leak its dynamic outputs into unrelated tests that assert the
    fixed 3-tuple.

    Caches live in comfydv._llm.ollama_provider (ADR-007's single source of
    truth) — comfydv.ollama's combo-widget helpers (_fetch_models) share the
    same cache instance, not a separate copy.
    """
    from comfydv._llm.ollama_provider import _CHAT_RESPONSE_CACHE, _MODEL_LIST_CACHE
    from comfydv.ollama import ChatCompletion

    def _reset():
        _MODEL_LIST_CACHE.clear()
        _CHAT_RESPONSE_CACHE.clear()
        ChatCompletion.RETURN_TYPES = ChatCompletion._BASE_RETURN_TYPES
        ChatCompletion.RETURN_NAMES = ChatCompletion._BASE_RETURN_NAMES
        ChatCompletion.node_configs.clear()

    _reset()
    yield
    _reset()


@pytest.fixture(scope="session")
def ollama_host():
    return "http://localhost:11434"


@pytest.fixture(scope="session")
def ollama_available():
    try:
        sock = socket.create_connection(("localhost", 11434), timeout=2.0)
        sock.close()
        return True
    except OSError:
        return False


@pytest.fixture
def skip_if_no_ollama(ollama_available):
    if not ollama_available:
        pytest.skip(
            "Ollama not reachable at localhost:11434 — start Ollama to run integration tests"
        )


@pytest.fixture(scope="session")
def first_generative_model(ollama_host, ollama_available):
    """Return the first model available from Ollama, skipping embedding-only models.

    Used by lifecycle tests that call /api/generate — embedding models like
    embeddinggemma reject that endpoint with HTTP 400.
    """
    if not ollama_available:
        pytest.skip("Ollama not reachable at localhost:11434")
    import asyncio

    from comfydv.ollama import _fetch_models

    models = asyncio.run(_fetch_models(ollama_host))
    if not models:
        pytest.skip("No models installed in Ollama")
    return models[0]


# ---------------------------------------------------------------------------
# Existing ComfyUI node fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def format_string_class():
    """Provide a fresh FormatString class for each test."""
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "format_string",
        os.path.join(
            os.path.dirname(__file__), "..", "src", "comfydv", "format_string.py"
        ),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    FormatString = module.FormatString

    FormatString.node_configs = {}
    FormatString.RETURN_TYPES = ("STRING", "STRING")
    FormatString.RETURN_NAMES = ("formatted_string", "saved_file_path")
    FormatString.OUTPUT_IS_LIST = (False, False)

    return FormatString


@pytest.fixture
def sample_templates():
    """Fixture providing sample templates for testing."""
    return {
        "simple_one_var": "Hello {name}",
        "simple_two_vars": "Hello {name}, you are {age} years old",
        "simple_three_vars": "{greeting} {name}, you are {age}",
        "jinja2_simple": "Hello {{ name }}",
        "jinja2_filter": "Hello {{ name | upper }}",
        "jinja2_multiple_filters": "{{ first | upper }} {{ last | lower }}",
        "jinja2_datetime": "Current time: {{ now() }}",
        "jinja2_with_math": "Result: {{ value * 2 }}",
        "mixed": "Hello {name}, today is {{ date }}",
        "no_vars": "Hello World",
    }


@pytest.fixture
def sample_data():
    """Fixture providing sample data for template rendering."""
    return {
        "name": "Alice",
        "age": "30",
        "greeting": "Hi",
        "first": "John",
        "last": "Doe",
        "date": "2025-11-05",
        "value": 5,
    }
