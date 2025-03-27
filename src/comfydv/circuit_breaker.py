"""
This node is designed in a hacky way to allow you to break a render run semi-gracefully.
"""

import torchvision.transforms as T
from comfy.model_management import InterruptProcessingException

from .utils import any_type


class CircuitBreaker:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        """
        Return a dictionary which contains config for all input fields.
        Some types (string): "MODEL", "VAE", "CLIP", "CONDITIONING", "LATENT", "IMAGE", "INT", "STRING", "FLOAT".
        Input types "INT", "STRING" or "FLOAT" are special values for fields on the node.
        The type can be a list for selection.

        Returns: `dict`:
            - Key input_fields_group (`string`): Can be either required, hidden or optional. A node class must have property `required`
            - Value input_fields (`dict`): Contains input fields config:
                * Key field_name (`string`): Name of a entry-point method's argument
                * Value field_config (`tuple`):
                    + First value is a string indicate the type of field or a list for selection.
                    + Secound value is a config for type "INT", "STRING" or "FLOAT".
        """
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
        if kwargs.get("status"):
            print(f"Circuit Breaker triggered")
            raise InterruptProcessingException()
        else:
            return (trigger,)
