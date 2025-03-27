from .circuit_breaker import CircuitBreaker
from .format_string import FormatString
from .model_unload import ModelUnloader
from .random_choice import RandomChoice

# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "ModelUnloader": ModelUnloader,
    "RandomChoice": RandomChoice,
    "CircuitBreaker": CircuitBreaker,
    "FormatString": FormatString,
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelUnloader": "Model Unloader (clear cache)",
    "RandomChoice": "Random Choice",
    "CircuitBreaker": "Circuit Breaker",
    "FormatString": "Format String (Python f-strings)",
}

WEB_DIRECTORY = "../js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
