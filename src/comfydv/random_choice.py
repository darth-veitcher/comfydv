import logging
import random
import sys

from .utils import any_type

logger = logging.getLogger(__name__)


class RandomChoice:
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
            "required": {"input1": (any_type,)},
            "optional": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF})
            },
        }

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("choice",)

    FUNCTION = "random_choice"

    OUTPUT_NODE = False

    CATEGORY = "dv/utils"

    """
        The node will always be re executed if any of the inputs change but
        this method can be used to force the node to execute again even when the inputs don't change.
        You can make this node return a number or a string. This value will be compared to the one returned the last time the node was
        executed, if it is different the node will be executed again.
        This method is used in the core repo for the LoadImage node where they return the image hash as a string, if the image hash
        changes between executions the LoadImage node is executed again.
    """

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return s.random_choice(s, **kwargs)

    def random_choice(self, **kwargs):
        (
            random.seed(kwargs.get("seed"))
            if kwargs.get("seed")
            else random.seed(random.randrange(sys.maxsize))
        )
        input = [i for i in kwargs.items() if i[0] != "seed"]
        logger.debug("RandomChoice inputs: %s", input)
        try:
            choice = random.choice(input)[1]
            logger.debug("RandomChoice chose: %s", choice)
            return (choice,)
        except Exception as e:
            raise e
