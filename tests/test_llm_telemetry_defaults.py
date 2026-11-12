"""Telemetry and phone-home behaviour is off by default (ADR-014).

Each test runs in a fresh interpreter: the defaults are applied at import
time through environment variables, so an in-process import would only ever
observe whichever state the first test left behind.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = str(Path(__file__).resolve().parent.parent / "src")

_DEFAULTED = (
    "FASTMCP_TELEMETRY_MODE",
    "FASTMCP_CHECK_FOR_UPDATES",
    "FASTMCP_SHOW_SERVER_BANNER",
    "PYDANTIC_AI_NO_BANNER",
)


# Load ``comfydv._llm`` without running ``comfydv/__init__.py``, which
# registers ComfyUI nodes and needs a real (or mocked) ComfyUI. The defaults
# live in ``_llm/__init__.py``, which always runs before any ``_llm``
# submodule imports pydantic-ai or FastMCP.
_ISOLATE = f"""
import sys, types
_pkg = types.ModuleType("comfydv")
_pkg.__path__ = [{str(Path(SRC) / "comfydv")!r}]
sys.modules["comfydv"] = _pkg
"""


def _run(code: str, extra_env: dict[str, str] | None = None) -> dict:
    code = _ISOLATE + code
    env = {k: v for k, v in os.environ.items() if k not in _DEFAULTED}
    env.update(extra_env or {})
    env["PYTHONPATH"] = SRC
    out = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


_PROBE = f"""
import json, os
import comfydv._llm
print(json.dumps({{k: os.environ.get(k) for k in {_DEFAULTED!r}}}))
"""


@pytest.mark.unit
def test_importing_llm_package_switches_off_telemetry_and_update_checks():
    env = _run(_PROBE)
    assert env == {
        "FASTMCP_TELEMETRY_MODE": "off",
        "FASTMCP_CHECK_FOR_UPDATES": "off",
        "FASTMCP_SHOW_SERVER_BANNER": "false",
        "PYDANTIC_AI_NO_BANNER": "1",
    }


@pytest.mark.unit
def test_explicit_user_settings_win_so_users_can_opt_back_in():
    env = _run(
        _PROBE,
        {"FASTMCP_TELEMETRY_MODE": "native", "FASTMCP_CHECK_FOR_UPDATES": "stable"},
    )
    assert env["FASTMCP_TELEMETRY_MODE"] == "native"
    assert env["FASTMCP_CHECK_FOR_UPDATES"] == "stable"
    assert env["FASTMCP_SHOW_SERVER_BANNER"] == "false"


@pytest.mark.unit
def test_libraries_observe_the_defaults_when_imported_after_comfydv():
    result = _run(
        """
import json
import comfydv._llm
import fastmcp
from pydantic_ai import Agent
s = fastmcp.settings
print(json.dumps({
    "telemetry_mode": s.telemetry_mode,
    "check_for_updates": s.check_for_updates,
    "show_server_banner": s.show_server_banner,
    "pydantic_ai_instrument_default": Agent._instrument_default,
}))
"""
    )
    assert result == {
        "telemetry_mode": "off",
        "check_for_updates": "off",
        "show_server_banner": False,
        "pydantic_ai_instrument_default": False,
    }


@pytest.mark.unit
def test_defaults_module_imports_no_third_party_libraries():
    """Applying the defaults must not eagerly import pydantic-ai or FastMCP:
    the plain Ollama chat path never needs either."""
    loaded = _run(
        """
import json, sys
import comfydv._llm
print(json.dumps(sorted(m for m in ("pydantic_ai", "fastmcp", "pydantic_monty") if m in sys.modules)))
"""
    )
    assert loaded == []
