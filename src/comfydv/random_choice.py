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
            logger.error("RandomChoice: unexpected error: %s", e)
            raise
