"""
Pytest configuration and fixtures for comfydv tests.

This file sets up mocks for ComfyUI dependencies before any test imports.
"""

import os
import sys

import pytest

# Add src directory to Python path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def pytest_configure(config):
    """
    Pytest hook that runs before test collection.
    Install all ComfyUI mocks here before any imports happen.
    """

    # Mock comfy module
    class MockInterruptProcessingException(Exception):
        pass

    class MockModelManagement:
        InterruptProcessingException = MockInterruptProcessingException

    comfy_module = type(sys)("comfy")
    comfy_module.model_management = MockModelManagement
    sys.modules["comfy"] = comfy_module
    sys.modules["comfy.model_management"] = MockModelManagement

    # Mock server module
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

    # Mock folder_paths module
    class MockFolderPaths:
        @staticmethod
        def get_output_directory():
            return "/tmp/comfydv_test"

    sys.modules["folder_paths"] = MockFolderPaths

    # Mock aiohttp module
    class MockWeb:
        @staticmethod
        def json_response(data):
            return data

    aiohttp_module = type(sys)("aiohttp")
    aiohttp_module.web = MockWeb
    sys.modules["aiohttp"] = aiohttp_module


# Keep these classes for type hints/documentation
class MockRoutes:
    """Mock ComfyUI routes for testing."""

    @staticmethod
    def post(path):
        """Mock POST route decorator."""

        def decorator(func):
            return func

        return decorator

    @staticmethod
    def get(path):
        """Mock GET route decorator."""

        def decorator(func):
            return func

        return decorator


class MockPromptServer:
    """Mock ComfyUI PromptServer for testing."""

    def __init__(self):
        self.routes = MockRoutes()

    instance = None


MockPromptServer.instance = MockPromptServer()


class MockFolderPaths:
    """Mock ComfyUI folder_paths module for testing."""

    @staticmethod
    def get_output_directory():
        """Return temporary directory for testing."""
        return "/tmp/comfydv_test"


class MockWeb:
    """Mock aiohttp.web for testing."""

    @staticmethod
    def json_response(data):
        """Mock json_response method."""
        return data


class MockInterruptProcessingException(Exception):
    """Mock ComfyUI InterruptProcessingException."""

    pass


class MockModelManagement:
    """Mock ComfyUI model_management module."""

    InterruptProcessingException = MockInterruptProcessingException


# Install mocks in sys.modules FIRST, before any other imports
# This is critical to prevent ImportErrors from comfydv modules
comfy_module = type(sys)("comfy")
comfy_module.model_management = MockModelManagement
sys.modules["comfy"] = comfy_module
sys.modules["comfy.model_management"] = MockModelManagement

server_module = type(sys)("server")
server_module.PromptServer = MockPromptServer
sys.modules["server"] = server_module

sys.modules["folder_paths"] = MockFolderPaths

aiohttp_module = type(sys)("aiohttp")
aiohttp_module.web = MockWeb
sys.modules["aiohttp"] = aiohttp_module


@pytest.fixture
def format_string_class():
    """Fixture to provide a fresh FormatString class for each test."""
    # Import the module directly, bypassing __init__.py which has ComfyUI dependencies
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

    # Reset class state before each test
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
