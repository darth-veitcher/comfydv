import json
import logging
import random
import sys

from .utils import any_type

logger = logging.getLogger(__name__)


def _preview_text(value) -> str:
    """Best-effort text preview for RandomChoice's arbitrary-typed output.

    Mirrors ComfyUI core's own ``PreviewAny`` node's value handling (str/
    number passthrough, else JSON, else ``str()``) rather than inventing a
    new convention — RandomChoice's output can be anything (an IMAGE
    tensor, a LATENT, a plain string), so this only needs to be "good
    enough to glance at," not a faithful repr of every type.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, default=str, indent=2)
    except Exception:
        try:
            return str(value)
        except Exception:
            return "<value could not be serialized>"


class RandomChoice:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {"input1": (any_type,)},
            "optional": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF})
            },
        }

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("choice",)

    FUNCTION = "random_choice"

    OUTPUT_NODE = True

    CATEGORY = "dv/utils"

    @classmethod
    def IS_CHANGED(s, **kwargs):
        # Unchanged from before the UI-preview addition: returns the raw
        # picked value (not the ui-wrapped dict random_choice() now returns)
        # so ComfyUI's change-detection comparison keeps working exactly as
        # it did previously.
        return s._pick(**kwargs)

    @staticmethod
    def _pick(**kwargs):
        (
            random.seed(kwargs.get("seed"))
            if kwargs.get("seed")
            else random.seed(random.randrange(sys.maxsize))
        )
        input = [i for i in kwargs.items() if i[0] != "seed"]
        logger.debug("RandomChoice inputs: %s", input)
        return random.choice(input)[1]

    def random_choice(self, **kwargs):
        try:
            choice = self._pick(**kwargs)
            logger.debug("RandomChoice chose: %s", choice)
            return {"ui": {"text": [_preview_text(choice)]}, "result": (choice,)}
        except Exception as e:
            logger.error("RandomChoice: unexpected error: %s", e)
            raise
