import os
import random
import sys
from enum import Enum
from typing import Optional

import requests
import torch
from comfy import model_management  # Adjust based on actual module location
from rich import print
from rich.pretty import pprint

from .utils import any_type


class DEVICE_TYPE(Enum):
    CUDA = "cuda"
    MPS = "mps"
    ROCm = "cuda"  # ROCm behaves like CUDA
    CPU = "cpu"


class ModelUnloader:
    """
    A custom node that handles unloading models, clearing GPU/CPU memory, and calling
    the ComfyUI /free API endpoint to release memory resources. The API endpoint can
    be configured by the user.
    """

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("passthrough",)
    FUNCTION = "unload_model"
    OUTPUT_NODE = True
    CATEGORY = "dv/experimental"

    def __init__(self):
        """Initializes the ModelUnloader class."""
        pass

    @classmethod
    def INPUT_TYPES(cls):
        """
        Defines the input types for the node, including a required API URL to specify where
        the /free API call should be made.

        Returns:
            dict: A dictionary with input field configurations.
        """
        return {
            "required": {
                "trigger": (any_type,),
                "api_url": ("STRING", {"default": "http://localhost:8188"}),
            },
            "optional": {"model": ("MODEL", {})},
        }

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return random.randrange(sys.maxsize)  # force to always recalc

    def unload_model(self, trigger, api_url: str, **kwargs):
        """
        Unloads models, clears backend-specific memory caches, and calls the /free API to release memory.

        Args:
            api_url (str): The API URL where the /free endpoint can be accessed.
            kwargs: Optional arguments to specify which model to unload.
        """
        # Unload models via ComfyUI model management
        print("Attempting to unload models...")
        model_to_unload = kwargs.get("model")
        print(f"Unloading {model_to_unload}") if model_to_unload else None
        loaded_models = model_management.current_loaded_models
        [
            pprint(
                {
                    "model": m.model,
                    "device": m.device,
                    "weights_loaded": m.weights_loaded,
                    "currently_used": m.currently_used,
                    "real_model": str(m.real_model)[:100],
                },
                max_depth=1,
                max_length=5,
            )
            for m in loaded_models
        ]

        if model_to_unload:
            for m in loaded_models:
                if m.model == model_to_unload:
                    print(f"Unloading model: {m.model}")
                    m.model_unload()
        else:
            print("No specific model provided, unloading all models.")
            for m in loaded_models:
                m.model_unload()

        # Clear CUDA/MPS/CPU memory and call /free API
        self.clear_memory(api_url)

        # Call soft_empty_cache to clear ComfyUI's internal model cache
        print("Calling soft_empty_cache from ComfyUI model_management.")
        model_management.soft_empty_cache()

        return (trigger,)

    def clear_memory(self, api_url: str):
        """
        Clears memory based on the detected device backend (CUDA, MPS, CPU) and sends a /free API request.

        Args:
            api_url (str): The API URL where the /free endpoint can be accessed.
        """
        device = get_best_pytorch_device()

        # CUDA backend
        if device.type == "cuda":
            print("Clearing CUDA memory cache...")
            torch.cuda.empty_cache()

        # Call model_management's soft_empty_cache for ComfyUI
        print("Calling soft_empty_cache from ComfyUI model_management...")
        model_management.soft_empty_cache()

        # Make the /free API call to ensure models are unloaded and memory is freed
        try:
            print(f"Calling /free API at {api_url} to unload models and free memory...")
            response = requests.post(
                f"{api_url}/free",  # Use the user-configured API URL
                json={"unload_models": True, "free_memory": True},
            )
            if response.status_code == 200:
                print("/free API call successful.")
            else:
                print(f"/free API call failed with status code {response.status_code}.")
        except Exception as e:
            print(f"Failed to call /free API: {e}")


def get_best_pytorch_device(
    device_type: Optional[DEVICE_TYPE] = None, device_number: int = 0
) -> torch.device:
    """
    Determines the best available PyTorch device, using CUDA, MPS, or CPU.

    Args:
        device_type (Optional[DEVICE_TYPE]): Manually specify the device type.
        device_number (int): The device number to select.

    Returns:
        torch.device: The best available device for PyTorch operations.
    """
    dev: torch.device = None

    # Override if device_type is specified
    if device_type:
        dev = torch.device(
            f"{device_type.value}{':' & device_number if device_number else ''}"
        )

    # Detect CUDA devices
    elif torch.cuda.is_available():
        print(f"CUDA detected. Using device {device_number}.")
        dev = torch.device(f"{DEVICE_TYPE.CUDA.value}:{device_number}")

    # Detect MPS backend (Apple Silicon)
    elif torch.backends.mps.is_available():
        dev = torch.device(DEVICE_TYPE.MPS.value)
        print("MPS device detected. Setting environment for MPS fallback.")
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

    # Default to CPU
    else:
        dev = torch.device(DEVICE_TYPE.CPU.value)
        print("No GPU devices found, using CPU.")

    print(f"Set device to: {dev}")
    return dev


# Example usage:
if __name__ == "__main__":
    # Example of calling the node and passing the API URL
    unloader = ModelUnloader()
    unloader.unload_model(api_url="http://localhost:8188")
