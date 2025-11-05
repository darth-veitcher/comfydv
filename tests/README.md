# Tests

This directory contains comprehensive pytest tests for the comfydv package.

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run with coverage report
uv run pytest --cov=src/comfydv --cov-report=html

# Run specific test file
uv run pytest tests/test_format_string.py

# Run specific test class
uv run pytest tests/test_format_string.py::TestVariableExtraction

# Run specific test
uv run pytest tests/test_format_string.py::TestVariableExtraction::test_extract_simple_single_variable

# Run tests matching a pattern
uv run pytest -k "jinja2"
```

Coverage reports are available in `htmlcov/index.html` after running with `--cov-report=html`.

## Test Coverage

**Current: 75%** (203 statements total, 51 missed)

- `format_string.py`: 78% coverage
- `__init__.py`: 100% coverage
- `circuit_breaker.py`: 68% coverage
- `random_choice.py`: 60% coverage
- `utils.py`: 75% coverage

## Test Structure

### `conftest.py`

Contains pytest configuration, fixtures, and mocks for ComfyUI dependencies:
- Mock ComfyUI modules (`comfy`, `server`, `folder_paths`, `aiohttp`)
- Uses `pytest_configure` hook to install mocks before test collection
- Provides `format_string_class` fixture using `importlib` to directly load module
- Fixtures for test data and class instances
- Pytest hooks for early mock installation

### `test_format_string.py`

Comprehensive test suite for the FormatString node with **47 tests** organized into classes:

- **TestVariableExtraction** (12 tests): Variable extraction from templates
- **TestSimpleFormatting** (4 tests): Python format string rendering
- **TestJinja2Formatting** (5 tests): Jinja2 template rendering
- **TestDynamicOutputs** (6 tests): Dynamic output configuration
- **TestOutputConsistency** (3 tests): Outputs match RETURN_TYPES/RETURN_NAMES
- **TestInputTypes** (4 tests): INPUT_TYPES method validation
- **TestIsChanged** (5 tests): Cache invalidation logic
- **TestStatePersistence** (2 tests): State saving/loading
- **TestEdgeCases** (4 tests): Error handling and edge cases
- **TestTimeNowFunction** (2 tests): time_now utility function

## Mocking Strategy

The tests use `importlib.util` to directly load the `format_string.py` module, bypassing the package `__init__.py` which has ComfyUI dependencies. This allows testing without ComfyUI installation while maintaining the root `__init__.py` for ComfyUI extension discovery.

## Writing Tests

### Example test

```python
def test_new_feature(self, format_string_class, sample_data):
    """Test that new feature works correctly."""
    result = format_string_class.some_method(sample_data["name"])
    assert result == expected_value
```

### Available fixtures

- `format_string_class`: Fresh FormatString class with reset state
- `sample_templates`: Dictionary of sample template strings
- `sample_data`: Dictionary of sample data for templates

### Test naming convention

Use descriptive names: `test_<what>_<condition>_<expected>`

## Troubleshooting

### Debugging failed tests

```bash
# Run with verbose output
uv run pytest -vv --tb=long

# Run with pdb debugger
uv run pytest --pdb
```

### Test isolation

Each test is independent. The `format_string_class` fixture provides a fresh instance with reset state.

## Future Improvements

- Add integration tests with actual ComfyUI installation
- Add JavaScript tests for frontend functionality
- Increase coverage for circuit_breaker and random_choice nodes
- Add property-based testing with Hypothesis
