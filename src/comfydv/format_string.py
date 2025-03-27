"""
FormatString module for ComfyUI.

This module provides a custom node for ComfyUI that allows formatting strings
using either simple Python formatting or Jinja2 templates. It can also save
formatted templates to disk for later reuse.

The node dynamically updates its inputs and outputs based on the variables
detected in the template, making it highly flexible for various text generation
and parameter formatting needs in ComfyUI workflows.
"""

import re
import json
import os
from typing import Any, Dict, List, Tuple
from aiohttp import web
from server import PromptServer  # from comfyui
import folder_paths  # from comfyui - gives access to `get_temp_directory()` and `get_output_directory()`
from jinja2 import Environment, sandbox, exceptions
import datetime
import random
import math
import sys
from rich import print
from rich.pretty import pprint


class FormatString:
    """
    A ComfyUI node for string formatting using Python's format syntax or Jinja2 templates.

    This node dynamically adapts its inputs and outputs based on the variables detected
    in the provided template. It supports saving template state to disk and loading it back.
    The node can operate in two modes:
    1. Simple: Uses Python's str.format() method
    2. Jinja2: Uses Jinja2 templating engine with sandbox protection

    Additional context variables like datetime, random, and math functions are available
    in Jinja2 mode.

    Attributes:
        CATEGORY (str): The category of the node in ComfyUI's node menu.
        FUNCTION (str): The main function to be called when the node is executed.
        RETURN_TYPES (tuple): Types of the returned outputs.
        RETURN_NAMES (tuple): Names of the returned outputs.
        node_configs (dict): Storage for configurations of node instances.
        jinja_env (SandboxedEnvironment): Sandboxed Jinja2 environment for secure template rendering.
        additional_context (dict): Extra context variables available in Jinja2 templates.
    """

    CATEGORY = "dv/string_operations"
    FUNCTION = "format_string"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("formatted_string", "saved_file_path")

    # Store configurations for each node instance
    node_configs = {}

    # Create a sandboxed Jinja2 environment for security
    jinja_env = sandbox.SandboxedEnvironment()

    # Define additional context
    def time_now() -> str:
        """
        Get the current time in a formatted string.

        Returns:
            str: Current time formatted as 'YYYYMMDD-HHMMSS'.

        Example:
            ```python
            from format_string import FormatString

            timestamp = FormatString.time_now()
            print(timestamp)  # Outputs something like: '20240327-153045'
            ```

        <!-- Example Test:
        >>> from datetime import datetime
        >>> timestamp = FormatString.time_now()
        >>> assert len(timestamp) == 15  # Format YYYYMMDD-HHMMSS is 15 chars
        >>> assert timestamp[8] == '-'  # Check format separator
        >>> # Verify it's roughly the current time (allowing some seconds of delay)
        >>> current = datetime.now().strftime("%Y%m%d-%H%M")
        >>> assert timestamp.startswith(current)
        -->
        """
        return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    additional_context = {
        "datetime": datetime,
        "now": time_now,
        "random": random,
        "math": math,
        # Add more modules or functions as needed
    }

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        """
        Define the input types for the FormatString node.

        This method is called by ComfyUI to determine what inputs the node should have.

        Returns:
            Dict[str, Any]: Dictionary defining the node's inputs, including template_type,
                           template, save_path, and a hidden unique_id.

        Example:
            ```python
            from format_string import FormatString

            input_types = FormatString.INPUT_TYPES()
            print(input_types["required"]["template_type"])  # Outputs: (["Simple", "Jinja2"],)
            ```

        <!-- Example Test:
        >>> input_types = FormatString.INPUT_TYPES()
        >>> assert "required" in input_types
        >>> assert "template_type" in input_types["required"]
        >>> assert "template" in input_types["required"]
        >>> assert "save_path" in input_types["required"]
        >>> assert "hidden" in input_types
        >>> assert "unique_id" in input_types["hidden"]
        >>> assert input_types["required"]["template_type"] == (["Simple", "Jinja2"],)
        -->
        """
        return {
            "required": {
                "template_type": (["Simple", "Jinja2"],),
                "template": ("STRING", {"multiline": True}),
                "save_path": ("STRING", {"default": ""}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID"
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """
        Determine if the node should be re-executed based on input changes.

        This method is called by ComfyUI to check if the node needs to be re-calculated
        due to changes in its inputs. It forces recalculation when Jinja2 templates
        contain time-dependent functions.

        Args:
            **kwargs: Keyword arguments containing the node's current inputs.

        Returns:
            Any: Either the kwargs if no time-dependent functions are detected, or a random
                 number to force recalculation.

        Example:
            ```python
            from format_string import FormatString

            # This would typically be called by ComfyUI
            result = FormatString.IS_CHANGED(template="Hello {name}", template_type="Simple")
            # If no time functions detected, returns the kwargs
            ```

        <!-- Example Test:
        >>> # Test with Simple template
        >>> result = FormatString.IS_CHANGED(template="Hello {name}", template_type="Simple")
        >>> assert isinstance(result, dict)
        >>> # Test with Jinja2 template containing datetime
        >>> result = FormatString.IS_CHANGED(template="Time: {{ datetime.now() }}", template_type="Jinja2")
        >>> assert isinstance(result, int)  # Should return a random int to force recalculation
        -->
        """
        print("\n[bold red]IS_CHANGED:")
        pprint(kwargs)
        keys = cls._extract_keys(kwargs.get('template'))
        print("Keys:")
        pprint(keys)
        if kwargs.get('template_type', "simple") == "Jinja2":
            for k in cls.additional_context.keys():
                if k in kwargs.get('template'):
                    # assume that our additional context items are functions returning
                    # changing data such as datetime.now()
                    print(f"Detected: {k}")
                    return random.randrange(sys.maxsize)  # force to always recalc
        return kwargs

    @staticmethod
    def _extract_keys(template: str) -> List[str]:
        """
        Extract variable names from a template string.

        This method parses a template string to find all variable names used in it,
        supporting both Python's format style {var} and Jinja2's {{ var }} syntax.

        Args:
            template (str): The template string to parse.

        Returns:
            List[str]: A list of unique variable names found in the template.

        Example:
            ```python
            from format_string import FormatString

            template = "Hello {name}, today is {{ datetime.now() }}"
            keys = FormatString._extract_keys(template)
            print(keys)  # Outputs: ['name']
            ```

        <!-- Example Test:
        >>> # Test simple format
        >>> keys = FormatString._extract_keys("Hello {name}, your age is {age}")
        >>> assert sorted(keys) == ['age', 'name']
        >>> # Test Jinja2 format
        >>> keys = FormatString._extract_keys("Hello {{ name }}, {{ greeting | upper }}")
        >>> assert sorted(keys) == ['greeting', 'name']
        >>> # Test mixed format
        >>> keys = FormatString._extract_keys("Hello {name}, today is {{ date }}")
        >>> assert sorted(keys) == ['date', 'name']
        >>> # Test with additional context (should be excluded)
        >>> keys = FormatString._extract_keys("Time: {{ datetime.now() }}")
        >>> assert keys == []
        -->
        """
        variables = []
        seen = set()

        def add_var(var):
            var = var.split('|')[0].split('.')[0].strip()
            if var not in seen and var not in FormatString.additional_context:
                seen.add(var)
                variables.append(var)

        # Extract variables from Jinja2 expressions {{ }}
        for match in re.finditer(r'\{\{\s*([\w.]+)(?:\|[\w\s]+)?(?:\.[^\(\)]+\(\))?\s*\}\}', template):
            add_var(match.group(1))

        # Extract variables from f-string style { }
        for match in re.finditer(r'\{(\w+)\}', template):
            add_var(match.group(1))

        # Extract variables from Jinja2 control structures {% %}
        for structure in re.finditer(r'\{%.*?%\}', template):
            for var in re.findall(r'\b(\w+)\|\b', structure.group(0)):
                if not var.startswith('end') and var not in {'if', 'else', 'elif', 'for', 'in'}:
                    add_var(var)

        return variables

    @classmethod
    def format_string(cls, template_type: str, template: str, save_path: str, **kwargs) -> Tuple[str, ...]:
        """
        Format a string using the specified template type and variables.

        This is the main method executed by the node. It formats the template using either
        Python's str.format() or Jinja2 templating, and optionally saves the state to disk.

        Args:
            template_type (str): Either "Simple" or "Jinja2" to specify the template engine.
            template (str): The template string to format.
            save_path (str): Optional path to save the node state. If empty, state is not saved.
            **kwargs: Variable keyword arguments that provide values for template variables.

        Returns:
            Tuple[str, ...]: A tuple containing the values of input variables, followed by
                           the formatted string and the save path (if any).

        Example:
            ```python
            from format_string import FormatString

            # Simple template example
            result = FormatString.format_string(
                template_type="Simple",
                template="Hello {name}, you are {age} years old",
                save_path="",
                name="Alice",
                age="30"
            )
            print(result)  # Outputs: ('Alice', '30', 'Hello Alice, you are 30 years old', '')

            # Jinja2 template example
            result = FormatString.format_string(
                template_type="Jinja2",
                template="Hello {{ name }}, today is {{ datetime.now().strftime('%A') }}",
                save_path="",
                name="Bob"
            )
            print(result[2])  # Outputs: 'Hello Bob, today is Wednesday' (or current day)
            ```

        <!-- Example Test:
        >>> # Test simple format
        >>> result = FormatString.format_string(
        ...     template_type="Simple",
        ...     template="Hello {name}, you are {age} years old",
        ...     save_path="",
        ...     name="Alice",
        ...     age="30"
        ... )
        >>> assert result[0] == "Alice"
        >>> assert result[1] == "30"
        >>> assert result[2] == "Hello Alice, you are 30 years old"
        >>> assert result[3] == ""
        >>>
        >>> # Test Jinja2 format with datetime (can't test exact output due to time dependency)
        >>> result = FormatString.format_string(
        ...     template_type="Jinja2",
        ...     template="Name: {{ name }}",
        ...     save_path="",
        ...     name="Bob"
        ... )
        >>> assert result[0] == "Bob"
        >>> assert result[1] == "Name: Bob"
        >>> assert result[2] == ""
        -->
        """
        keys = cls._extract_keys(template)

        if template_type == "Simple":
            formatted_string = template.format(**kwargs)
        else:  # Jinja2
            try:
                jinja_template = cls.jinja_env.from_string(template)
                # Combine user-provided kwargs with additional_context
                context = {**cls.additional_context, **kwargs}
                formatted_string = jinja_template.render(**context)
            except exceptions.TemplateSyntaxError as e:
                formatted_string = f"Error in Jinja2 template: {str(e)}"

        # Save the state
        save_data = {
            "template_type": template_type,
            "template": template,
            "inputs": {k: kwargs.get(k, "") for k in keys}
        }

        if save_path:
            save_path = os.path.join(folder_paths.get_output_directory(), save_path)
            try:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "w") as f:
                    json.dump(save_data, f, indent=2, sort_keys=True)
                print(f"Node state saved to: {save_path}")
            except Exception as e:
                print(f"Error saving node state: {str(e)}")
                save_path = ""  # Reset save_path if saving failed
        else:
            print("No save_path provided, node state not saved.")

        # Return all input values first, then formatted_string and saved_file_path
        return tuple(str(kwargs.get(key, "")) for key in keys) + (formatted_string, save_path)

    @classmethod
    def update_widget(cls, node_id: str, template_type: str, template: str) -> Dict[str, Any]:
        """
        Update a node's widget configuration based on the template.

        This method is called when a template is changed to dynamically update the
        node's inputs and outputs based on the variables detected in the template.

        Args:
            node_id (str): The unique identifier of the node instance.
            template_type (str): The template type ("Simple" or "Jinja2").
            template (str): The template string.

        Returns:
            Dict[str, Any]: Updated configuration for the node.

        Example:
            ```python
            from format_string import FormatString

            # Called via ComfyUI's web API when template changes
            config = FormatString.update_widget(
                node_id="node_123",
                template_type="Simple",
                template="Hello {name}, you are {age} years old"
            )
            print(config["inputs"])  # Shows inputs including 'name' and 'age'
            print(config["outputs"])  # Shows outputs including extracted variables
            ```

        <!-- Example Test:
        >>> config = FormatString.update_widget(
        ...     node_id="test_node",
        ...     template_type="Simple",
        ...     template="Hello {name}, you are {age} years old"
        ... )
        >>> assert "name" in config["inputs"]
        >>> assert "age" in config["inputs"]
        >>> assert len(config["outputs"]) == 4  # name, age, formatted_string, saved_file_path
        >>> assert config["outputs"][0]["name"] == "name"
        >>> assert config["outputs"][1]["name"] == "age"
        >>> assert config["outputs"][2]["name"] == "formatted_string"
        >>> assert config["outputs"][3]["name"] == "saved_file_path"
        >>> # Check that RETURN_TYPES and RETURN_NAMES are updated
        >>> assert len(FormatString.RETURN_TYPES) == 4
        >>> assert len(FormatString.RETURN_NAMES) == 4
        >>> assert FormatString.RETURN_NAMES[0] == "name"
        >>> assert FormatString.RETURN_NAMES[1] == "age"
        >>> assert FormatString.RETURN_NAMES[2] == "formatted_string"
        >>> assert FormatString.RETURN_NAMES[3] == "saved_file_path"
        >>> # Check that node config is stored
        >>> assert "test_node" in FormatString.node_configs
        >>> assert FormatString.node_configs["test_node"] == config
        -->
        """
        keys = cls._extract_keys(template)
        config = {
            "inputs": {
                "template_type": (["Simple", "Jinja2"],),
                "template": ("STRING", {"multiline": True}),
                "save_path": ("STRING", {"default": ""}),
            },
            "outputs": [],
        }
        for key in keys:
            config["inputs"][key] = ("STRING", {"default": ""})
            config["outputs"].append({"name": key, "type": "STRING"})

        # Add formatted_string and saved_file_path at the end of outputs
        config["outputs"].extend([
            {"name": "formatted_string", "type": "STRING"},
            {"name": "saved_file_path", "type": "STRING"},
        ])

        # Update RETURN_TYPES and RETURN_NAMES
        cls.RETURN_TYPES = ("STRING",) * len(keys) + ("STRING", "STRING")
        cls.RETURN_NAMES = tuple(keys) + ("formatted_string", "saved_file_path")

        # Store the configuration for this specific node
        cls.node_configs[node_id] = config

        return config

    @classmethod
    def get_node_config(cls, node_id: str) -> Dict[str, Any]:
        """
        Get the configuration for a specific node instance.

        Args:
            node_id (str): The unique identifier of the node instance.

        Returns:
            Dict[str, Any]: The configuration for the specified node, or an empty dict if not found.

        Example:
            ```python
            from format_string import FormatString

            # After updating a node's configuration
            config = FormatString.get_node_config("node_123")
            print(config)  # Shows the stored configuration for node_123
            ```

        <!-- Example Test:
        >>> # First create a config
        >>> _ = FormatString.update_widget(
        ...     node_id="test_node_2",
        ...     template_type="Simple",
        ...     template="Hello {name}"
        ... )
        >>> # Then retrieve it
        >>> config = FormatString.get_node_config("test_node_2")
        >>> assert "inputs" in config
        >>> assert "outputs" in config
        >>> assert "name" in config["inputs"]
        >>> assert len(config["outputs"]) == 3  # name, formatted_string, saved_file_path
        >>> # Test non-existent node
        >>> empty_config = FormatString.get_node_config("non_existent_node")
        >>> assert empty_config == {}
        -->
        """
        return cls.node_configs.get(node_id, {})

    @classmethod
    def load_node_state(cls, file_path: str) -> Dict[str, Any]:
        """
        Load a previously saved node state from disk.

        Args:
            file_path (str): Path to the saved node state JSON file.

        Returns:
            Dict[str, Any]: The loaded node state, or an empty dict if loading failed.

        Example:
            ```python
            from format_string import FormatString

            # Load a previously saved state
            state = FormatString.load_node_state("/path/to/saved_state.json")
            print(state["template"])  # Shows the saved template
            print(state["inputs"])    # Shows the saved input values
            ```

        <!-- Example Test:
        >>> import tempfile
        >>> import json
        >>> import os
        >>> # Create a temporary file with test data
        >>> test_data = {
        ...     "template_type": "Simple",
        ...     "template": "Hello {name}",
        ...     "inputs": {"name": "Alice"}
        ... }
        >>> with tempfile.NamedTemporaryFile(delete=False, mode="w") as temp:
        ...     json.dump(test_data, temp)
        ...     temp_path = temp.name
        >>> # Test loading the file
        >>> state = FormatString.load_node_state(temp_path)
        >>> assert state["template_type"] == "Simple"
        >>> assert state["template"] == "Hello {name}"
        >>> assert state["inputs"]["name"] == "Alice"
        >>> # Clean up
        >>> os.unlink(temp_path)
        >>> # Test loading non-existent file
        >>> empty_state = FormatString.load_node_state("non_existent_file.json")
        >>> assert empty_state == {}
        -->
        """
        try:
            with open(file_path, "r") as f:
                load_data = json.load(f)
            return load_data
        except FileNotFoundError:
            return {}
        except Exception as e:
            print(f"Error loading node state: {e}")
            return {}


# Custom route for updating node configuration
@PromptServer.instance.routes.post("/update_format_string_node")
async def update_format_string_node(request):
    """
    AIOHTTP route handler for updating a FormatString node's configuration.

    This endpoint receives JSON data containing a node ID, template type, and template,
    then updates the node's configuration based on the template.

    Args:
        request (web.Request): The HTTP request object containing JSON data.

    Returns:
        web.Response: JSON response with the updated node configuration.

    Example:
        This would typically be called by the frontend JavaScript via a POST request:

        ```javascript
        // In ComfyUI frontend
        fetch("/update_format_string_node", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                nodeId: "node_123",
                template_type: "Simple",
                template: "Hello {name}"
            })
        }).then(response => response.json())
          .then(data => console.log(data));
        ```
    """
    data = await request.json()
    node_id = data.get('nodeId', '')
    template_type = data.get('template_type', '')
    template = data.get('template', '')
    updated_config = FormatString.update_widget(node_id, template_type, template)
    return web.json_response(updated_config)


# Custom route for loading node state
@PromptServer.instance.routes.post("/load_format_string_node")
async def load_format_string_node(request):
    """
    AIOHTTP route handler for loading a FormatString node's state from disk.

    This endpoint receives JSON data containing a file path, then loads and returns
    the node state from that file.

    Args:
        request (web.Request): The HTTP request object containing JSON data.

    Returns:
        web.Response: JSON response with the loaded node state.

    Example:
        This would typically be called by the frontend JavaScript via a POST request:

        ```javascript
        // In ComfyUI frontend
        fetch("/load_format_string_node", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file_path: "/path/to/saved_state.json"
            })
        }).then(response => response.json())
          .then(data => console.log(data));
        ```
    """
    data = await request.json()
    file_path = data.get('file_path', '')
    state = FormatString.load_node_state(file_path)
    return web.json_response(state)


# Custom route for getting node-specific configuration
@PromptServer.instance.routes.get("/get_format_string_node_config/{node_id}")
async def get_format_string_node_config(request):
    """
    AIOHTTP route handler for retrieving a FormatString node's configuration.

    This endpoint retrieves the stored configuration for a specific node instance.

    Args:
        request (web.Request): The HTTP request object containing the node ID in the URL.

    Returns:
        web.Response: JSON response with the node's configuration.

    Example:
        This would typically be called by the frontend JavaScript via a GET request:

        ```javascript
        // In ComfyUI frontend
        fetch("/get_format_string_node_config/node_123")
          .then(response => response.json())
          .then(data => console.log(data));
        ```
    """
    node_id = request.match_info['node_id']
    config = FormatString.get_node_config(node_id)
    return web.json_response(config)


# Node registration for ComfyUI
NODE_CLASS_MAPPINGS = {
    "FormatString": FormatString
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FormatString": "Format String"
}
