"""
FormatString module for ComfyUI.

This module provides a custom node for ComfyUI that allows formatting strings
using either simple Python formatting or Jinja2 templates. It can also save
formatted templates to disk for later reuse.

The node dynamically updates its inputs and outputs based on the variables
detected in the template, making it highly flexible for various text generation
and parameter formatting needs in ComfyUI workflows.
"""

import datetime
import json
import logging
import math
import os
import random
import re
import sys
from typing import Any, Dict, List, Tuple

from aiohttp import web
from jinja2 import exceptions, sandbox
from rich import print

# Set up logger for this module
logger = logging.getLogger(__name__)

if "comfy" in sys.modules:
    import folder_paths  # from comfyui - gives access to `get_temp_directory()` and `get_output_directory()`
    from server import PromptServer  # noqa: from comfyui
else:
    print(
        "ComfyUI not detected, FormatString node will not function properly outside of ComfyUI."
    )


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

    Outputs:
        The node always returns formatted_string and saved_file_path as the first two outputs
        (positions 0 and 1), followed by any variable values extracted from the template in
        subsequent positions. This ensures the primary outputs are in fixed, predictable positions.

    Attributes:
        CATEGORY (str): The category of the node in ComfyUI's node menu.
        FUNCTION (str): The main function to be called when the node is executed.
        RETURN_TYPES (tuple): Types of the returned outputs (dynamically updated).
        RETURN_NAMES (tuple): Names of the returned outputs (dynamically updated).
        node_configs (dict): Storage for configurations of node instances.
        jinja_env (SandboxedEnvironment): Sandboxed Jinja2 environment for secure template rendering.
        additional_context (dict): Extra context variables available in Jinja2 templates.
    """

    CATEGORY = "dv/string_operations"
    FUNCTION = "format_string"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("formatted_string", "saved_file_path")
    OUTPUT_IS_LIST = (False, False)

    # Store configurations for each node instance
    node_configs: Dict[str, Dict[str, Any]] = {}

    # Create a sandboxed Jinja2 environment for security
    jinja_env = sandbox.SandboxedEnvironment()

    # Define additional context
    @staticmethod
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
        "now": time_now,  # we name our custom function `time_now` as `now` so inside jinja it's `{{ now() }}`
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
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """
        Determine if the node should be re-executed based on input changes.

        This method is called by ComfyUI to check if the node needs to be re-calculated
        due to changes in its inputs. It forces recalculation when Jinja2 templates
        contain time-dependent function calls (e.g., datetime.now(), time_now()).

        Args:
            **kwargs: Keyword arguments containing the node's current inputs.

        Returns:
            Any: A hash of inputs for caching, or a random number to force recalculation
                 when time-dependent functions are detected.

        Example:
            ```python
            from format_string import FormatString

            # This would typically be called by ComfyUI
            result = FormatString.IS_CHANGED(template="Hello {name}", template_type="Simple")
            # Returns hash of inputs for proper caching
            ```

        <!-- Example Test:
        >>> # Test with Simple template
        >>> result = FormatString.IS_CHANGED(template="Hello {name}", template_type="Simple")
        >>> assert isinstance(result, dict)
        >>> # Test with Jinja2 template containing datetime function call
        >>> result = FormatString.IS_CHANGED(template="Time: {{ datetime.now() }}", template_type="Jinja2")
        >>> assert isinstance(result, int)  # Should return a random int to force recalculation
        -->
        """
        template = kwargs.get("template", "")
        template_type = kwargs.get("template_type", "Simple")

        if not template:
            logger.debug("Empty template, returning kwargs for caching")
            return kwargs

        template_preview = template[:50] if len(template) > 50 else template
        logger.debug(
            f"IS_CHANGED called - template_type: {template_type}, template: {template_preview}..."
        )

        # Check for time-dependent function calls in Jinja2 templates
        if template_type == "Jinja2":
            # Look for actual function calls like datetime.now(), now(), or time_now()
            # These are time-dependent and should force recalculation each time
            time_function_pattern = r"\b(datetime\.now|now|time_now)\s*\("
            if re.search(time_function_pattern, template):
                # Force recalculation for time-dependent templates
                logger.debug(
                    "Time-dependent function detected in Jinja2 template, forcing recalculation"
                )
                return random.randrange(sys.maxsize)

        # Return kwargs for proper caching - ComfyUI will hash this
        logger.debug(
            "No time-dependent functions, using cached result if inputs unchanged"
        )
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
            var = var.split("|")[0].split(".")[0].strip()
            if var not in seen and var not in FormatString.additional_context:
                seen.add(var)
                variables.append(var)

        # Extract variables from Jinja2 expressions {{ }}
        for match in re.finditer(
            r"\{\{\s*([\w.]+)(?:\s*\|[\w\s]+)?(?:\.[^\(\)]+\(\))?\s*\}\}", template
        ):
            add_var(match.group(1))

        # Extract variables from f-string style { }
        for match in re.finditer(r"\{(\w+)\}", template):
            add_var(match.group(1))

        # Extract variables from Jinja2 control structures {% %}
        for structure in re.finditer(r"\{%.*?%\}", template):
            for var in re.findall(r"\b(\w+)\|\b", structure.group(0)):
                if not var.startswith("end") and var not in {
                    "if",
                    "else",
                    "elif",
                    "for",
                    "in",
                }:
                    add_var(var)

        return variables

    @classmethod
    def format_string(
        cls,
        template_type: str,
        template: str,
        save_path: str,
        unique_id: str = "",
        **kwargs,
    ) -> Tuple[str, ...]:
        """
        Format a string using the specified template type and variables.

        This is the main method executed by the node. It formats the template using either
        Python's str.format() or Jinja2 templating, and optionally saves the state to disk.

        Args:
            template_type (str): Either "Simple" or "Jinja2" to specify the template engine.
            template (str): The template string to format.
            save_path (str): Optional path to save the node state. If empty, state is not saved.
            unique_id (str): The unique identifier for this node instance (passed by ComfyUI).
            **kwargs: Variable keyword arguments that provide values for template variables.

        Returns:
            Tuple[str, ...]: A tuple containing the formatted string, the save path,
                           followed by the values of input variables (in order).

        Example:
            ```python
            from format_string import FormatString

            # Simple template example
            result = FormatString.format_string(
                template_type="Simple",
                template="Hello {name}, you are {age} years old",
                save_path="",
                unique_id="123",
                name="Alice",
                age="30"
            )
            print(result)  # Outputs: ('Hello Alice, you are 30 years old', '', 'Alice', '30')

            # Jinja2 template example
            result = FormatString.format_string(
                template_type="Jinja2",
                template="Hello {{ name }}, today is {{ datetime.now().strftime('%A') }}",
                save_path="",
                unique_id="124",
                name="Bob"
            )
            print(result)  # Outputs: ('Hello Bob, today is Wednesday', '', 'Bob')
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
        >>> assert result[0] == "Hello Alice, you are 30 years old"
        >>> assert result[1] == ""
        >>> assert result[2] == "Alice"
        >>> assert result[3] == "30"
        >>>
        >>> # Test Jinja2 format with datetime (can't test exact output due to time dependency)
        >>> result = FormatString.format_string(
        ...     template_type="Jinja2",
        ...     template="Name: {{ name }}",
        ...     save_path="",
        ...     name="Bob"
        ... )
        >>> assert result[0] == "Name: Bob"
        >>> assert result[1] == ""
        >>> assert result[2] == "Bob"
        -->
        """
        logger.info(
            f"Formatting string - type: {template_type}, unique_id: {unique_id}"
        )
        logger.debug(f"Template: {template[:100]}...")

        keys = cls._extract_keys(template)
        logger.debug(f"Extracted variables: {keys}")
        input_vals = ", ".join(f'{k}={kwargs.get(k, "")}' for k in keys)
        logger.debug(f"Input values: {input_vals}")

        # CRITICAL: Update RETURN_TYPES/RETURN_NAMES before execution to ensure they match our return tuple
        # This is necessary because update_widget might not have been called yet (e.g., on workflow load)
        if unique_id:
            cls.update_widget(unique_id, template_type, template)
            logger.debug(
                f"Updated RETURN_TYPES for node {unique_id}: {cls.RETURN_TYPES}"
            )

        if template_type == "Simple":
            try:
                formatted_string = template.format(**kwargs)
                if logger.level < logging.DEBUG:
                    logger.info(
                        f"Simple format successful, result length: {len(formatted_string)}"
                    )
                elif logger.level == logging.DEBUG:
                    logger.debug(f"Simple format successful: {formatted_string}")
            except KeyError as e:
                error_msg = f"Missing variable in Simple template: {str(e)}"
                logger.error(error_msg)
                raise  # Re-raise for proper error handling
            except Exception as e:
                error_msg = f"Error in Simple template: {str(e)}"
                logger.error(error_msg)
                formatted_string = f"Error: {error_msg}"
        else:  # Jinja2
            try:
                jinja_template = cls.jinja_env.from_string(template)
                # Combine user-provided kwargs with additional_context
                context = {**cls.additional_context, **kwargs}
                formatted_string = jinja_template.render(**context)
                logger.info(
                    f"Jinja2 format successful, result length: {len(formatted_string)}"
                )
            except exceptions.TemplateSyntaxError as e:
                error_msg = f"Error in Jinja2 template: {str(e)}"
                logger.error(error_msg)
                formatted_string = error_msg
            except Exception as e:
                error_msg = f"Error rendering Jinja2 template: {str(e)}"
                logger.error(error_msg)
                formatted_string = error_msg

        # Save the state
        save_data = {
            "template_type": template_type,
            "template": template,
            "inputs": {k: kwargs.get(k, "") for k in keys},
        }

        actual_save_path = ""
        if save_path:
            actual_save_path = os.path.join(
                folder_paths.get_output_directory(), save_path
            )
            try:
                os.makedirs(os.path.dirname(actual_save_path), exist_ok=True)
                with open(actual_save_path, "w") as f:
                    json.dump(save_data, f, indent=2, sort_keys=True)
                logger.info(f"Node state saved to: {actual_save_path}")
            except Exception as e:
                logger.error(f"Error saving node state: {str(e)}")
                actual_save_path = ""  # Reset save_path if saving failed
        else:
            logger.debug("No save_path provided, skipping state save")

        # Log the final formatted string to stdout for visibility
        print(f"\n[FormatString Node {unique_id}] Output:")
        print(f"  formatted_string: {formatted_string}")
        print(f"  Variables extracted: {keys}")
        print(f"  Variable values: {[kwargs.get(key, '') for key in keys]}")
        print(f"  Class RETURN_TYPES: {cls.RETURN_TYPES}")
        print(f"  Class RETURN_NAMES: {cls.RETURN_NAMES}")
        print(
            f"  Expected outputs: {len(keys)} vars + formatted_string + saved_file_path = {len(keys) + 2} total"
        )
        print()

        # Return formatted_string and saved_file_path FIRST (fixed positions 0,1),
        # then all input values (for chaining)
        # The order must match what was set in update_widget's RETURN_TYPES/RETURN_NAMES
        result = (
            formatted_string,
            actual_save_path,
        ) + tuple(str(kwargs.get(key, "")) for key in keys)

        print(f"[FormatString Node {unique_id}] Actual return tuple:")
        for i, (name, value) in enumerate(zip(cls.RETURN_NAMES, result)):
            value_preview = value[:50] if len(value) > 50 else value
            print(f"  Output {i}: {name} = {value_preview}")
        print()

        logger.debug(
            f"Returning {len(result)} outputs: keys={keys}, formatted_string={formatted_string[:50]}..., save_path={actual_save_path}"
        )
        logger.debug(
            f"Full result tuple length: {len(result)}, expected: {len(keys) + 2}"
        )
        return result

    @classmethod
    def update_widget(
        cls, node_id: str, template_type: str, template: str
    ) -> Dict[str, Any]:
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
        >>> assert len(config["outputs"]) == 4  # formatted_string, saved_file_path, name, age
        >>> assert config["outputs"][0]["name"] == "formatted_string"
        >>> assert config["outputs"][1]["name"] == "saved_file_path"
        >>> assert config["outputs"][2]["name"] == "name"
        >>> assert config["outputs"][3]["name"] == "age"
        >>> # Check that RETURN_TYPES and RETURN_NAMES are updated
        >>> assert len(FormatString.RETURN_TYPES) == 4
        >>> assert len(FormatString.RETURN_NAMES) == 4
        >>> assert FormatString.RETURN_NAMES[0] == "formatted_string"
        >>> assert FormatString.RETURN_NAMES[1] == "saved_file_path"
        >>> assert FormatString.RETURN_NAMES[2] == "name"
        >>> assert FormatString.RETURN_NAMES[3] == "age"
        >>> # Check that node config is stored
        >>> assert "test_node" in FormatString.node_configs
        >>> assert FormatString.node_configs["test_node"] == config
        -->
        """
        logger.info(
            f"Updating widget config - node_id: {node_id}, template_type: {template_type}"
        )
        logger.debug(f"Template: {template[:100]}...")

        keys = cls._extract_keys(template)
        logger.info(f"Extracted {len(keys)} variables from template: {keys}")

        config: Dict[str, Any] = {
            "inputs": {
                "template_type": (["Simple", "Jinja2"],),
                "template": ("STRING", {"multiline": True}),
                "save_path": ("STRING", {"default": ""}),
            },
            "outputs": [],
        }
        for key in keys:
            config["inputs"][key] = ("STRING", {"default": ""})  # type: ignore
            config["outputs"].append({"name": key, "type": "STRING"})  # type: ignore

        # Add formatted_string and saved_file_path at the START of outputs (fixed positions)
        config["outputs"] = [
            {"name": "formatted_string", "type": "STRING"},
            {"name": "saved_file_path", "type": "STRING"},
        ] + config["outputs"]

        # Update RETURN_TYPES and RETURN_NAMES dynamically
        # formatted_string and saved_file_path are ALWAYS first two outputs (positions 0,1)
        # This allows passing through variable values for chaining
        cls.RETURN_TYPES = ("STRING", "STRING") + ("STRING",) * len(keys)
        cls.RETURN_NAMES = ("formatted_string", "saved_file_path") + tuple(keys)
        cls.OUTPUT_IS_LIST = (False,) * (len(keys) + 2)

        logger.debug(
            f"Updated RETURN_TYPES to {len(cls.RETURN_TYPES)} outputs: {cls.RETURN_NAMES}"
        )

        # Store the configuration for this specific node
        cls.node_configs[node_id] = config
        logger.debug(f"Stored config for node {node_id}")

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
    node_id = data.get("nodeId", "")
    template_type = data.get("template_type", "")
    template = data.get("template", "")

    logger.info(
        f"Web API: update_format_string_node - node_id: {node_id}, template_type: {template_type}"
    )

    try:
        updated_config = FormatString.update_widget(node_id, template_type, template)
        logger.debug(f"Successfully updated config for node {node_id}")
        return web.json_response(updated_config)
    except Exception as e:
        logger.error(f"Error updating node config: {str(e)}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


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
    file_path = data.get("file_path", "")
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
    node_id = request.match_info["node_id"]
    config = FormatString.get_node_config(node_id)
    return web.json_response(config)


# Node registration for ComfyUI
NODE_CLASS_MAPPINGS = {"FormatString": FormatString}

NODE_DISPLAY_NAME_MAPPINGS = {"FormatString": "Format String"}
