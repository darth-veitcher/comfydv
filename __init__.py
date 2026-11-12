"""
@author: Darth Veitcher
@title: Comfy DV Nodes
@nickname: DV Nodes
@description: Quality of life ComfyUI nodes: dynamic string formatting, random selection, circuit-breaker.
"""

if "comfy" in __import__("sys").modules:
    # Resolvable only when ComfyUI loads this repo root as a package.
    from .src.comfydv import (  # ty: ignore[import-not-found]
        NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS,
    )
else:
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

WEB_DIRECTORY = "./src/js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
