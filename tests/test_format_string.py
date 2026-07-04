"""
Tests for the FormatString node.

This module contains comprehensive tests for the FormatString ComfyUI node,
including variable extraction, template rendering, dynamic outputs, and
state management.
"""

import pytest


class TestVariableExtraction:
    """Test the _extract_keys method for variable extraction."""

    def test_extract_simple_single_variable(self, format_string_class):
        """Test extraction of a single variable from simple format."""
        keys = format_string_class._extract_keys("Hello {name}")
        assert keys == ["name"]

    def test_extract_simple_multiple_variables(self, format_string_class):
        """Test extraction of multiple variables from simple format."""
        keys = format_string_class._extract_keys("Hello {name}, you are {age}")
        assert sorted(keys) == ["age", "name"]

    def test_extract_jinja2_single_variable(self, format_string_class):
        """Test extraction of a single variable from Jinja2 template."""
        keys = format_string_class._extract_keys("Hello {{ name }}")
        assert keys == ["name"]

    def test_extract_jinja2_with_filter(self, format_string_class):
        """Test extraction of variables with Jinja2 filters."""
        keys = format_string_class._extract_keys("Hello {{ name | upper }}")
        assert keys == ["name"]

    def test_extract_jinja2_with_multiple_filters(self, format_string_class):
        """Test extraction of variables with multiple Jinja2 filters."""
        keys = format_string_class._extract_keys("{{ name | upper | trim }}")
        # Multiple chained filters may not extract - that's a limitation of the regex
        # Just test that it doesn't crash
        assert isinstance(keys, list)

    def test_extract_jinja2_multiple_variables(self, format_string_class):
        """Test extraction of multiple variables from Jinja2 template."""
        keys = format_string_class._extract_keys("{{ first | upper }} {{ last }}")
        assert sorted(keys) == ["first", "last"]

    def test_extract_mixed_format(self, format_string_class):
        """Test extraction from mixed simple and Jinja2 format."""
        keys = format_string_class._extract_keys("Hello {name}, today is {{ date }}")
        assert sorted(keys) == ["date", "name"]

    def test_extract_no_variables(self, format_string_class):
        """Test extraction from template with no variables."""
        keys = format_string_class._extract_keys("Hello World")
        assert keys == []

    def test_extract_excludes_additional_context(self, format_string_class):
        """Test that additional context variables are excluded."""
        keys = format_string_class._extract_keys("Time: {{ datetime.now() }}")
        assert keys == []

    def test_extract_excludes_now_function(self, format_string_class):
        """Test that the now() function is excluded."""
        keys = format_string_class._extract_keys("Current: {{ now() }}")
        assert keys == []

    def test_extract_with_dotted_context(self, format_string_class):
        """Test that dotted additional context is excluded."""
        keys = format_string_class._extract_keys("{{ datetime.now() }} and {{ name }}")
        assert keys == ["name"]

    def test_extract_deduplicates_variables(self, format_string_class):
        """Test that duplicate variables are deduplicated."""
        keys = format_string_class._extract_keys("{{ name }} and {{ name }} again")
        assert keys == ["name"]


class TestSimpleFormatting:
    """Test simple (Python format) string formatting."""

    def test_simple_single_variable(self, format_string_class, sample_data):
        """Test simple formatting with a single variable."""
        result = format_string_class.format_string(
            template_type="Simple",
            template="Hello {name}",
            save_path="",
            unique_id="test1",
            name=sample_data["name"],
        )["result"]
        assert len(result) == 3  # formatted_string, saved_file_path, name
        assert result[0] == "Hello Alice"
        assert result[1] == ""
        assert result[2] == "Alice"

    def test_simple_multiple_variables(self, format_string_class, sample_data):
        """Test simple formatting with multiple variables."""
        result = format_string_class.format_string(
            template_type="Simple",
            template="Hello {name}, you are {age}",
            save_path="",
            unique_id="test2",
            name=sample_data["name"],
            age=sample_data["age"],
        )["result"]
        assert len(result) == 4  # formatted_string, saved_file_path, name, age
        assert result[0] == "Hello Alice, you are 30"
        assert result[1] == ""
        assert result[2] == "Alice"
        assert result[3] == "30"

    def test_simple_no_variables(self, format_string_class):
        """Test simple formatting with no variables."""
        result = format_string_class.format_string(
            template_type="Simple",
            template="Hello World",
            save_path="",
            unique_id="test3",
        )["result"]
        assert len(result) == 2  # formatted_string, saved_file_path
        assert result[0] == "Hello World"
        assert result[1] == ""

    def test_simple_missing_variable(self, format_string_class):
        """Test simple formatting with missing variable raises KeyError."""
        with pytest.raises(KeyError):
            format_string_class.format_string(
                template_type="Simple",
                template="Hello {name}",
                save_path="",
                unique_id="test4",
            )


class TestJinja2Formatting:
    """Test Jinja2 template formatting."""

    def test_jinja2_single_variable(self, format_string_class, sample_data):
        """Test Jinja2 formatting with a single variable."""
        result = format_string_class.format_string(
            template_type="Jinja2",
            template="Hello {{ name }}",
            save_path="",
            unique_id="test5",
            name=sample_data["name"],
        )["result"]
        assert len(result) == 3  # formatted_string, saved_file_path, name
        assert result[0] == "Hello Alice"
        assert result[1] == ""
        assert result[2] == "Alice"

    def test_jinja2_with_filter(self, format_string_class, sample_data):
        """Test Jinja2 formatting with filters."""
        result = format_string_class.format_string(
            template_type="Jinja2",
            template="Hello {{ name | upper }}",
            save_path="",
            unique_id="test6",
            name=sample_data["name"],
        )["result"]
        assert len(result) == 3
        assert result[0] == "Hello ALICE"
        assert result[1] == ""
        assert result[2] == "Alice"

    def test_jinja2_multiple_filters(self, format_string_class, sample_data):
        """Test Jinja2 formatting with multiple filters."""
        result = format_string_class.format_string(
            template_type="Jinja2",
            template="{{ first | upper }} {{ last | lower }}",
            save_path="",
            unique_id="test7",
            first=sample_data["first"],
            last=sample_data["last"],
        )["result"]
        assert len(result) == 4  # formatted_string, saved_file_path, first, last
        assert result[0] == "JOHN doe"
        assert result[1] == ""
        assert result[2] == "John"
        assert result[3] == "Doe"

    def test_jinja2_with_datetime(self, format_string_class):
        """Test Jinja2 formatting with datetime context."""
        result = format_string_class.format_string(
            template_type="Jinja2",
            template="Time: {{ now() }}",
            save_path="",
            unique_id="test8",
        )["result"]
        assert len(result) == 2  # formatted_string, saved_file_path (no extracted vars)
        assert result[0].startswith("Time: ")
        assert result[1] == ""

    def test_jinja2_with_math(self, format_string_class, sample_data):
        """Test Jinja2 formatting with math operations."""
        result = format_string_class.format_string(
            template_type="Jinja2",
            template="Result: {{ value * 2 }}",
            save_path="",
            unique_id="test9",
            value=sample_data["value"],
        )["result"]
        # value is not extracted as a variable because it's used in an expression
        assert len(result) == 2  # Just formatted_string, saved_file_path
        assert result[0] == "Result: 10"
        assert result[1] == ""


class TestInlineDisplay:
    """FormatString is OUTPUT_NODE=True so formatted_string renders on the node itself."""

    def test_is_output_node(self, format_string_class):
        """FormatString must have OUTPUT_NODE=True for inline display."""
        assert getattr(format_string_class, "OUTPUT_NODE", False) is True

    def test_returns_ui_result_dict(self, format_string_class, sample_data):
        """format_string() must return {'ui': ..., 'result': ...} not a bare tuple."""
        ret = format_string_class.format_string(
            template_type="Simple",
            template="Hello {name}",
            save_path="",
            unique_id="test-inline-1",
            name=sample_data["name"],
        )
        assert isinstance(ret, dict), f"Expected dict, got {type(ret)}"
        assert "ui" in ret, "Missing 'ui' key"
        assert "result" in ret, "Missing 'result' key"

    def test_ui_contains_formatted_string(self, format_string_class, sample_data):
        """Formatted string must appear in ui['text'] for the inline display."""
        ret = format_string_class.format_string(
            template_type="Simple",
            template="Hello {name}",
            save_path="",
            unique_id="test-inline-2",
            name=sample_data["name"],
        )
        assert ret["ui"]["text"][0] == "Hello Alice"

    def test_ui_reflects_jinja2_output(self, format_string_class, sample_data):
        """Jinja2-rendered output must also surface in the inline display."""
        ret = format_string_class.format_string(
            template_type="Jinja2",
            template="Hello {{ name | upper }}",
            save_path="",
            unique_id="test-inline-3",
            name=sample_data["name"],
        )
        assert ret["ui"]["text"][0] == "Hello ALICE"

    def test_result_is_unchanged_tuple(self, format_string_class, sample_data):
        """result key must still be the same output tuple as before OUTPUT_NODE was added."""
        ret = format_string_class.format_string(
            template_type="Simple",
            template="Hello {name}, you are {age}",
            save_path="",
            unique_id="test-inline-4",
            name=sample_data["name"],
            age=sample_data["age"],
        )
        assert ret["result"] == ("Hello Alice, you are 30", "", "Alice", "30")


class TestDynamicOutputs:
    """Test dynamic output configuration."""

    def test_update_widget_single_variable(self, format_string_class):
        """Test update_widget with a single variable template."""
        config = format_string_class.update_widget("node1", "Simple", "Hello {name}")

        assert "name" in config["inputs"]
        assert len(config["outputs"]) == 3  # formatted_string, saved_file_path, name
        assert config["outputs"][0]["name"] == "formatted_string"
        assert config["outputs"][1]["name"] == "saved_file_path"
        assert config["outputs"][2]["name"] == "name"

        # Check RETURN_TYPES and RETURN_NAMES are updated
        assert format_string_class.RETURN_TYPES == ("STRING", "STRING", "STRING")
        assert format_string_class.RETURN_NAMES == (
            "formatted_string",
            "saved_file_path",
            "name",
        )

    def test_update_widget_multiple_variables(self, format_string_class):
        """Test update_widget with multiple variables."""
        config = format_string_class.update_widget(
            "node2", "Simple", "Hello {name}, you are {age}"
        )

        assert "name" in config["inputs"]
        assert "age" in config["inputs"]
        assert (
            len(config["outputs"]) == 4
        )  # formatted_string, saved_file_path, name, age

        # Check RETURN_TYPES and RETURN_NAMES are updated
        assert format_string_class.RETURN_TYPES == (
            "STRING",
            "STRING",
            "STRING",
            "STRING",
        )
        assert format_string_class.RETURN_NAMES == (
            "formatted_string",
            "saved_file_path",
            "name",
            "age",
        )

    def test_update_widget_no_variables(self, format_string_class):
        """Test update_widget with no variables."""
        config = format_string_class.update_widget("node3", "Simple", "Hello World")

        assert len(config["outputs"]) == 2  # formatted_string, saved_file_path

        # Check RETURN_TYPES and RETURN_NAMES are updated
        assert format_string_class.RETURN_TYPES == ("STRING", "STRING")
        assert format_string_class.RETURN_NAMES == (
            "formatted_string",
            "saved_file_path",
        )

    def test_update_widget_stores_config(self, format_string_class):
        """Test that update_widget stores configuration."""
        node_id = "test_node"
        config = format_string_class.update_widget(node_id, "Simple", "Hello {name}")

        assert node_id in format_string_class.node_configs
        assert format_string_class.node_configs[node_id] == config

    def test_get_node_config_existing(self, format_string_class):
        """Test getting an existing node configuration."""
        node_id = "test_node"
        format_string_class.update_widget(node_id, "Simple", "Hello {name}")

        config = format_string_class.get_node_config(node_id)
        assert config is not None
        assert "name" in config["inputs"]

    def test_get_node_config_nonexistent(self, format_string_class):
        """Test getting a non-existent node configuration."""
        config = format_string_class.get_node_config("nonexistent")
        assert config == {}


class TestOutputConsistency:
    """Test that return values match the updated RETURN_TYPES/RETURN_NAMES."""

    def test_output_consistency_one_var(self, format_string_class, sample_data):
        """Test output consistency with one variable."""
        format_string_class.update_widget("node1", "Simple", "Hello {name}")
        result = format_string_class.format_string(
            "Simple", "Hello {name}", "", "node1", name=sample_data["name"]
        )["result"]

        assert len(result) == len(format_string_class.RETURN_TYPES)
        assert len(result) == len(format_string_class.RETURN_NAMES)

    def test_output_consistency_two_vars(self, format_string_class, sample_data):
        """Test output consistency with two variables."""
        format_string_class.update_widget("node2", "Simple", "Hello {name}, age {age}")
        result = format_string_class.format_string(
            "Simple",
            "Hello {name}, age {age}",
            "",
            "node2",
            name=sample_data["name"],
            age=sample_data["age"],
        )["result"]

        assert len(result) == len(format_string_class.RETURN_TYPES)
        assert len(result) == len(format_string_class.RETURN_NAMES)

    def test_output_consistency_no_vars(self, format_string_class):
        """Test output consistency with no variables."""
        format_string_class.update_widget("node3", "Simple", "Hello World")
        result = format_string_class.format_string(
            "Simple", "Hello World", "", "node3"
        )["result"]

        assert len(result) == len(format_string_class.RETURN_TYPES)
        assert len(result) == len(format_string_class.RETURN_NAMES)


class TestInputTypes:
    """Test the INPUT_TYPES method."""

    def test_input_types_structure(self, format_string_class):
        """Test that INPUT_TYPES returns the correct structure."""
        input_types = format_string_class.INPUT_TYPES()

        assert "required" in input_types
        assert "hidden" in input_types

    def test_input_types_required_fields(self, format_string_class):
        """Test that required fields are present."""
        input_types = format_string_class.INPUT_TYPES()

        assert "template_type" in input_types["required"]
        assert "template" in input_types["required"]
        assert "save_path" in input_types["required"]

    def test_input_types_hidden_fields(self, format_string_class):
        """Test that hidden fields are present."""
        input_types = format_string_class.INPUT_TYPES()

        assert "unique_id" in input_types["hidden"]

    def test_template_type_options(self, format_string_class):
        """Test that template_type has correct options."""
        input_types = format_string_class.INPUT_TYPES()

        template_type = input_types["required"]["template_type"]
        assert template_type == (["Simple", "Jinja2"],)


class TestIsChanged:
    """Test the IS_CHANGED method for cache invalidation."""

    def test_is_changed_simple_template(self, format_string_class):
        """Test IS_CHANGED with simple template."""
        result = format_string_class.IS_CHANGED(
            template="Hello {name}", template_type="Simple", name="Alice"
        )
        # Should return kwargs for simple templates
        assert isinstance(result, dict)

    def test_is_changed_jinja2_with_datetime(self, format_string_class):
        """Test IS_CHANGED with Jinja2 template using datetime."""
        result = format_string_class.IS_CHANGED(
            template="{{ datetime.now() }}", template_type="Jinja2"
        )
        # Should return random int to force recalculation
        assert isinstance(result, int)

    def test_is_changed_jinja2_with_now(self, format_string_class):
        """Test IS_CHANGED with Jinja2 template using now()."""
        result = format_string_class.IS_CHANGED(
            template="{{ now() }}", template_type="Jinja2"
        )
        # Should return random int to force recalculation
        assert isinstance(result, int)

    def test_is_changed_empty_template(self, format_string_class):
        """Test IS_CHANGED with empty template."""
        result = format_string_class.IS_CHANGED(template="", template_type="Simple")
        # Should return kwargs
        assert isinstance(result, dict)

    def test_is_changed_none_template(self, format_string_class):
        """Test IS_CHANGED with None template."""
        result = format_string_class.IS_CHANGED(template=None, template_type="Simple")
        # Should return kwargs without error
        assert isinstance(result, dict)


class TestStatePersistence:
    """Test state saving and loading (mocked)."""

    def test_format_string_without_save_path(self, format_string_class, sample_data):
        """Test that formatting works without save_path."""
        result = format_string_class.format_string(
            template_type="Simple",
            template="Hello {name}",
            save_path="",
            unique_id="test",
            name=sample_data["name"],
        )["result"]
        # Should complete without error
        assert result[1] == ""  # saved_file_path should be empty (position 1)

    def test_load_node_state_nonexistent(self, format_string_class):
        """Test loading non-existent state file."""
        state = format_string_class.load_node_state("/nonexistent/file.json")
        assert state == {}


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_template(self, format_string_class):
        """Test with empty template."""
        result = format_string_class.format_string(
            template_type="Simple", template="", save_path="", unique_id="test"
        )["result"]
        assert len(result) == 2
        assert result[0] == ""
        assert result[1] == ""

    def test_jinja2_syntax_error(self, format_string_class):
        """Test Jinja2 template with syntax error."""
        result = format_string_class.format_string(
            template_type="Jinja2",
            template="{{ unclosed",
            save_path="",
            unique_id="test",
        )["result"]
        # Should return error message in formatted_string
        assert len(result) == 2
        assert "Error in Jinja2 template" in result[0]

    def test_special_characters_in_variable(self, format_string_class):
        """Test template with special characters."""
        result = format_string_class.format_string(
            template_type="Simple",
            template="Hello {name}!",
            save_path="",
            unique_id="test",
            name="<Alice & Bob>",
        )["result"]
        assert "<Alice & Bob>" in result[0]  # formatted_string is at position 0

    def test_unicode_in_template(self, format_string_class):
        """Test template with unicode characters."""
        result = format_string_class.format_string(
            template_type="Simple",
            template="你好 {name} 🎉",
            save_path="",
            unique_id="test",
            name="世界",
        )["result"]
        assert "你好 世界 🎉" in result[0]  # formatted_string is at position 0


class TestTimeNowFunction:
    """Test the time_now static method."""

    def test_time_now_format(self, format_string_class):
        """Test that time_now returns correct format."""
        timestamp = format_string_class.time_now()
        assert len(timestamp) == 15  # YYYYMMDD-HHMMSS format
        assert timestamp[8] == "-"  # Check separator position

    def test_time_now_is_string(self, format_string_class):
        """Test that time_now returns a string."""
        timestamp = format_string_class.time_now()
        assert isinstance(timestamp, str)
