"""Internal package: shared LLM provider abstraction (ADR-007).

Not a ComfyUI node module — nothing here is registered in
``NODE_CLASS_MAPPINGS``. ``comfydv.ollama`` and ``comfydv.llamacpp``
import from here.

Telemetry and phone-home defaults (ADR-014) are applied on import, before
any submodule can import pydantic-ai or FastMCP.
"""

from . import _telemetry

_telemetry.apply()
