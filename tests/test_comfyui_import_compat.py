"""Guards against the exact bug found while validating spec 008 against a
real ComfyUI dev harness (docker-compose): every `from comfydv._llm.X
import Y`-style absolute self-import inside src/comfydv/ silently broke the
*entire* plugin (every node, not just LLM ones) as soon as ComfyUI actually
loaded it.

ComfyUI's custom_nodes loader imports the plugin via a *relative* chain —
the repo-root __init__.py does `from .src.comfydv import ...`, nesting
comfydv under whatever top-level name the folder has (never `comfydv`
itself). An absolute `from comfydv...` self-import only resolves if `src/`
has separately been placed on sys.path — which conftest.py does for every
other test file in this suite, masking the bug completely. This file
deliberately does NOT rely on that sys.path insertion: it reproduces
ComfyUI's actual nested-relative-import shape in a subprocess.

Confirmed via git history: this predates spec 008 entirely — it was already
broken immediately after PR #17 merged (spec 007), well before llamacpp.py
existed. No test caught it because none exercised this exact loading shape
until the docker harness was run by hand.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def _clear_ollama_caches():
    """Shadow conftest.py's autouse fixture of the same name for this module
    only. That fixture's own setup does `from comfydv._llm.ollama_provider
    import ...` — this file's tests are the exact reproduction of an
    environment where `comfydv` resolving correctly can't be assumed (that's
    the point of the file), so depending on it for an unrelated cache-reset
    would make these tests order-dependent on whichever other test file
    happens to import `comfydv` "the normal way" first in the session. These
    tests touch no OllamaProvider/ChatCompletion state, so there is nothing
    to reset."""
    yield


_SUBPROCESS_SCRIPT = textwrap.dedent(
    """
    import sys
    import types

    # Minimal ComfyUI stubs — same shape as conftest.py's pytest_configure,
    # but this script intentionally runs outside pytest so it isn't reusing
    # (or accidentally validated by) that fixture's sys.path setup.
    class _InterruptProcessingException(Exception):
        pass

    comfy_module = types.ModuleType("comfy")
    comfy_module.model_management = types.SimpleNamespace(
        InterruptProcessingException=_InterruptProcessingException
    )
    sys.modules["comfy"] = comfy_module
    sys.modules["comfy.model_management"] = comfy_module.model_management

    class _Routes:
        def post(self, path):
            return lambda fn: fn

        def get(self, path):
            return lambda fn: fn

    class _PromptServer:
        pass

    _PromptServer.instance = _PromptServer()
    _PromptServer.instance.routes = _Routes()
    server_module = types.ModuleType("server")
    server_module.PromptServer = _PromptServer
    sys.modules["server"] = server_module

    folder_paths_module = types.ModuleType("folder_paths")
    folder_paths_module.get_output_directory = lambda: "/tmp/comfydv_test"
    sys.modules["folder_paths"] = folder_paths_module

    # The critical part: put the repo's *parent* directory on sys.path, so
    # `import comfydv` resolves to the repo-root __init__.py — exactly how
    # ComfyUI resolves a folder under custom_nodes/ — NOT to src/comfydv
    # directly (that's what conftest.py's sys.path.insert(0, ".../src")
    # does for the rest of this test suite, and why it never caught this).
    sys.path.insert(0, sys.argv[1])

    import comfydv

    required = {"FormatString", "RandomChoice", "CircuitBreaker",
                "OllamaClient", "LlamaCppClient", "ChatCompletion"}
    missing = required - set(comfydv.NODE_CLASS_MAPPINGS)
    if missing:
        print(f"MISSING_NODES:{missing}")
        sys.exit(1)
    print("OK")
    """
)


def test_package_imports_under_comfyui_style_relative_nesting():
    """Reproduces ComfyUI's real loading shape and fails loudly — with the
    actual traceback — if any internal module reverts to an absolute
    `from comfydv...` self-import."""
    result = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT, str(REPO_ROOT.parent)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        "comfydv failed to import the way ComfyUI actually loads it "
        "(relative nesting, not a top-level `comfydv` on sys.path). "
        f"This means every node in the plugin would fail to register.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "OK" in result.stdout


def test_no_absolute_self_imports_in_package():
    """Cheap, fast static guard alongside the dynamic test above: no file
    under src/comfydv/ should import itself as `comfydv.X` — internal
    imports must be relative (`.X` / `..X`) so they resolve regardless of
    what the outer package happens to be named at load time."""
    import ast

    offenders = []
    for path in (REPO_ROOT / "src" / "comfydv").rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "comfydv" or node.module.startswith("comfydv.")
                ):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "comfydv" or alias.name.startswith("comfydv."):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")

    assert not offenders, (
        "Absolute self-imports found — use relative imports instead "
        f"(they break under ComfyUI's actual loader): {offenders}"
    )
