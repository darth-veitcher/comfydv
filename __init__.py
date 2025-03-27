"""
@author: Darth Veitcher
@title: Comfy DV Nodes
@nickname: DV Nodes
@description: This collection of nodes provides string formatting, random choices, model memory management, and other quality of life improvements.
"""
from .src.comfydv import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
WEB_DIRECTORY = "./src/js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
