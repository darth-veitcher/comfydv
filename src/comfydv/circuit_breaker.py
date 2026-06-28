"""
This node is designed in a hacky way to allow you to break a render run semi-gracefully.
"""

import logging
import sys

logger = logging.getLogger(__name__)

if "comfy" in sys.modules:
    from comfy.model_management import InterruptProcessingException  # noqa
else:
    logger.warning(
        "ComfyUI not detected, CircuitBreaker node will not function properly outside of ComfyUI."
    )


class CircuitBreaker:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {"trigger": ("IMAGE", {})},
            "optional": {"status": ("BOOLEAN", {"default": True})},
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("passthrough",)

    FUNCTION = "doit"

    OUTPUT_NODE = True

    CATEGORY = "dv/utils"

    def doit(self, trigger, **kwargs):
        if not kwargs.get("status", True):
            logger.debug("CircuitBreaker: interrupt triggered")
            raise InterruptProcessingException()
        return (trigger,)
