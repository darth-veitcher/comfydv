"""
@author: Darth Veitcher
@title: Comfy DV Nodes
@nickname: DV Nodes
@description: This collection of nodes provides string formatting, random choices, model memory management, and other quality of life improvements.
"""

import sys

# Only import when not running pytest (to avoid ComfyUI dependency issues during testing)
if "pytest" not in sys.modules:
    from .src.comfydv import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

    WEB_DIRECTORY = "./src/js"
    __all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
else:
    # When running tests, provide empty exports
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}
    WEB_DIRECTORY = "./src/js"
    __all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
