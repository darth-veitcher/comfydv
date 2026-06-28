"""
@author: Darth Veitcher
@title: Comfy DV Nodes
@nickname: DV Nodes
@description: Quality of life ComfyUI nodes: dynamic string formatting, random selection, circuit-breaker.
"""

if "comfy" in __import__("sys").modules:
    from .src.comfydv import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
else:
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

WEB_DIRECTORY = "./src/js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
