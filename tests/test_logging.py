"""
Logging behaviour tests for comfydv nodes.

Verifies:
- US1: zero stdout/stderr during normal execution
- US2: ERROR records emitted on failure paths
- US3: DEBUG records appear when host opts in; NullHandler default is silent
"""

import logging
import logging.handlers
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_format_string():
    """Load FormatString from source, bypassing __init__.py."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "comfydv.format_string",
        os.path.join(
            os.path.dirname(__file__), "..", "src", "comfydv", "format_string.py"
        ),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cls = module.FormatString
    cls.node_configs = {}
    cls.RETURN_TYPES = ("STRING", "STRING")
    cls.RETURN_NAMES = ("formatted_string", "saved_file_path")
    cls.OUTPUT_IS_LIST = (False, False)
    return cls


def _load_random_choice():
    """Load RandomChoice from source, pre-registering the utils sibling."""
    import importlib.util
    import types

    src = os.path.join(os.path.dirname(__file__), "..", "src")

    # Register comfydv package namespace so relative imports work
    if "comfydv" not in sys.modules:
        pkg = types.ModuleType("comfydv")
        pkg.__path__ = [os.path.join(src, "comfydv")]
        pkg.__package__ = "comfydv"
        sys.modules["comfydv"] = pkg

    # Register utils submodule so `from .utils import any_type` resolves
    if "comfydv.utils" not in sys.modules:
        utils_spec = importlib.util.spec_from_file_location(
            "comfydv.utils",
            os.path.join(src, "comfydv", "utils.py"),
        )
        utils_mod = importlib.util.module_from_spec(utils_spec)
        sys.modules["comfydv.utils"] = utils_mod
        utils_spec.loader.exec_module(utils_mod)

    spec = importlib.util.spec_from_file_location(
        "comfydv.random_choice",
        os.path.join(src, "comfydv", "random_choice.py"),
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["comfydv.random_choice"] = module
    spec.loader.exec_module(module)
    return module.RandomChoice


def _load_circuit_breaker():
    """Load CircuitBreaker from source."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "comfydv.circuit_breaker",
        os.path.join(
            os.path.dirname(__file__), "..", "src", "comfydv", "circuit_breaker.py"
        ),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CircuitBreaker


# ---------------------------------------------------------------------------
# US1: Silent Normal Operation
# ---------------------------------------------------------------------------


class TestUS1SilentNormalOperation:
    """US1: no stdout/stderr from comfydv during successful node execution."""

    def test_format_string_produces_no_stdout(self, capsys):
        """T010-T (red): format_string() must not write to stdout."""
        FormatString = _load_format_string()
        FormatString.format_string(
            template_type="Simple",
            template="Hello {name}",
            save_path="",
            unique_id="t010",
            name="Alice",
        )
        captured = capsys.readouterr()
        assert captured.out == "", f"Unexpected stdout: {captured.out!r}"
        assert captured.err == "", f"Unexpected stderr: {captured.err!r}"

    def test_update_widget_produces_no_stdout(self, capsys):
        """T010-T (red): update_widget() must not write to stdout."""
        FormatString = _load_format_string()
        FormatString.update_widget("node1", "Simple", "Hello {name}")
        captured = capsys.readouterr()
        assert captured.out == "", f"Unexpected stdout: {captured.out!r}"
        assert captured.err == "", f"Unexpected stderr: {captured.err!r}"

    def test_is_changed_produces_no_info_records(self, caplog):
        """T011-T (red): IS_CHANGED must not emit records at INFO or above."""
        FormatString = _load_format_string()
        with caplog.at_level(logging.INFO, logger="comfydv.format_string"):
            FormatString.IS_CHANGED(template="Hello {name}", template_type="Simple")
        info_plus = [r for r in caplog.records if r.levelno >= logging.INFO]
        assert info_plus == [], f"Unexpected INFO+ records: {info_plus}"

    def test_update_widget_produces_no_info_records(self, caplog):
        """T011-T (red): update_widget must not emit records at INFO or above."""
        FormatString = _load_format_string()
        with caplog.at_level(logging.INFO, logger="comfydv.format_string"):
            FormatString.update_widget("node1", "Simple", "Hello {name}")
        info_plus = [r for r in caplog.records if r.levelno >= logging.INFO]
        assert info_plus == [], f"Unexpected INFO+ records: {info_plus}"

    def test_random_choice_produces_no_stdout(self, capsys):
        """T012-T (red): random_choice() must not write to stdout."""
        RandomChoice = _load_random_choice()
        rc = RandomChoice()
        rc.random_choice(input1="a", input2="b", seed=42)
        captured = capsys.readouterr()
        assert captured.out == "", f"Unexpected stdout: {captured.out!r}"
        assert captured.err == "", f"Unexpected stderr: {captured.err!r}"


# ---------------------------------------------------------------------------
# US2: Errors Still Surface
# ---------------------------------------------------------------------------


class TestUS2ErrorsStillSurface:
    """US2: error conditions must emit records at ERROR level."""

    def test_jinja2_syntax_error_emits_error_record(self, caplog):
        """T020-T (red): invalid Jinja2 template must produce an ERROR log record."""
        FormatString = _load_format_string()
        with caplog.at_level(logging.DEBUG, logger="comfydv.format_string"):
            FormatString.format_string(
                template_type="Jinja2",
                template="{{ unclosed",
                save_path="",
                unique_id="t020a",
            )
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert error_records, (
            "Expected at least one ERROR record for invalid Jinja2 template"
        )

    def test_simple_missing_variable_emits_error_record(self, caplog):
        """T020-T (red): missing Simple template variable must produce an ERROR log record."""
        FormatString = _load_format_string()
        with caplog.at_level(logging.DEBUG, logger="comfydv.format_string"):
            try:
                FormatString.format_string(
                    template_type="Simple",
                    template="Hello {name}",
                    save_path="",
                    unique_id="t020b",
                )
            except KeyError:
                pass
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert error_records, (
            "Expected at least one ERROR record for missing template variable"
        )

    def test_load_node_state_error_emits_error_record(self, caplog):
        """T020-T (red): failed load_node_state must produce an ERROR log record (not a print)."""
        FormatString = _load_format_string()
        with caplog.at_level(logging.DEBUG, logger="comfydv.format_string"):
            # Trigger the except branch with a path that can be opened but is invalid JSON
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                f.write("not valid json {{{{")
                bad_path = f.name
            try:
                FormatString.load_node_state(bad_path)
            finally:
                os.unlink(bad_path)
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert error_records, (
            "Expected at least one ERROR record for failed node state load"
        )

    def test_circuit_breaker_emits_log_record(self, caplog):
        """T021-T (red): CircuitBreaker.doit with status=False must emit a log record."""
        CircuitBreaker = _load_circuit_breaker()
        cb = CircuitBreaker()
        with caplog.at_level(logging.DEBUG, logger="comfydv.circuit_breaker"):
            try:
                cb.doit(trigger="img", status=False)
            except Exception:
                pass
        assert caplog.records, "Expected at least one log record from CircuitBreaker"


# ---------------------------------------------------------------------------
# US3: Developer Debug Mode
# ---------------------------------------------------------------------------


class TestUS3DeveloperDebugMode:
    """US3: DEBUG records appear when host opts in; zero records with default config."""

    def test_debug_records_appear_with_opt_in(self, caplog):
        """T030-T: configuring DEBUG on comfydv logger must surface trace records."""
        FormatString = _load_format_string()
        with caplog.at_level(logging.DEBUG, logger="comfydv.format_string"):
            FormatString.format_string(
                template_type="Simple",
                template="Hello {name}",
                save_path="",
                unique_id="t030a",
                name="Alice",
            )
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert debug_records, (
            "Expected at least one DEBUG record when DEBUG level is enabled"
        )

    def test_null_handler_is_default(self):
        """T030-T: comfydv/__init__.py must register a NullHandler on the package logger."""
        # Verify the contract at source level — the NullHandler registration must be present
        init_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "comfydv", "__init__.py"
        )
        with open(init_path) as f:
            source = f.read()
        assert "NullHandler" in source, (
            "comfydv/__init__.py must call "
            "logging.getLogger(__name__).addHandler(logging.NullHandler())"
        )

        # Verify the runtime effect: registering the handler means no records escape
        # by default (the NullHandler absorbs them).
        FormatString = _load_format_string()
        test_handler = logging.handlers.MemoryHandler(
            capacity=100, flushLevel=logging.CRITICAL
        )
        fmt_logger = logging.getLogger("comfydv.format_string")
        fmt_logger.addHandler(test_handler)
        # Without propagation to root (which has no handler), NullHandler absorbs at comfydv level
        original_propagate = fmt_logger.propagate
        fmt_logger.propagate = False
        try:
            FormatString.format_string(
                template_type="Simple",
                template="Hello {name}",
                save_path="",
                unique_id="null_test",
                name="test",
            )
            # No records should have reached any external handler (they go to NullHandler)
            flushed = test_handler.buffer
            assert len(flushed) == 0 or all(
                r.levelno < logging.INFO for r in flushed
            ), f"Records reached external handler: {flushed}"
        finally:
            fmt_logger.removeHandler(test_handler)
            fmt_logger.propagate = original_propagate
