---
description: Enforce strict TDD workflow - write test first, see it fail, then implement
allowed-tools: AskUserQuestion, Bash, Read, Glob, Grep, Edit, Write
argument-hint: <feature-description> [--unit|--integration] [--file <test_file.py>]
---

# TDD TDD TDD - Strict Test-Driven Development

Enforce the classic **Red -> Green -> Refactor** cycle. Tests are written FIRST, implementation comes SECOND.

> "TDD TDD TDD" - the repetition is intentional. This skill enforces discipline.

## Arguments

- `$ARGUMENTS` - Feature description and options:
  - First part: Feature description in quotes or as text
  - `--unit` - Write unit test (default)
  - `--integration` - Write integration test
  - `--file <path>` - Explicit test file path

## The Three Laws of TDD

1. **You may not write production code until you have written a failing test**
2. **You may not write more test than is sufficient to fail**
3. **You may not write more production code than is sufficient to pass the test**

---

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at decision points.**

- **Before** writing the test -- confirm what behavior to test and test type
- **After** RED phase -- validate that the failure is the right kind before implementing
- **After** GREEN phase -- ask if the implementation approach is acceptable
- **After** each cycle -- ask whether to iterate or stop

## Workflow

### Phase 0: Understand the Feature

Before writing anything:

1. **Parse `$ARGUMENTS`** to extract feature description and flags
2. **Analyze the feature** - what behavior needs to be tested?
3. **Identify the test location** based on feature area:

| Feature Area | Test Path | Implementation Path |
|--------------|-----------|---------------------|
| Recipe client | `tests/test_client_*.py` | `scripts/recipe_client.py` |
| Draft store | `tests/test_draft_store.py` | `scripts/draft_store.py` |
| Recipe validation | `tests/test_validate_recipes.py` | `scripts/validate_recipes.py` |
| Recipes | `tests/test_recipes/test_<recipe>.py` | `recipes/<recipe>.py` |
| Rust commands | (manual) | `gui/src-tauri/src/*_commands.rs` |

4. **Confirm test approach with user**
5. **Check existing tests** for patterns and fixtures:
   ```bash
   ls tests/
   cat tests/conftest.py 2>/dev/null || echo "No conftest.py"
   ```

---

### Phase 1: RED - Write Failing Test

**CRITICAL**: Write the test FIRST. No implementation code yet.

#### Step 1.1: Create Test Function

```python
import pytest

class TestFeatureName:
    """Tests for [feature description]."""

    def test_feature_does_expected_thing(self):
        """[Feature] should [expected behavior]."""
        # Arrange
        # ... setup test data

        # Act
        result = function_under_test(input_data)

        # Assert
        assert result["status"] == "expected"
```

#### Step 1.2: Run Test and VERIFY IT FAILS

```bash
pytest tests/test_<file>.py -v -k "test_function_name"
```

**STOP AND CHECK**:
- Does the test fail for the RIGHT reason? (e.g., `ImportError`, `AttributeError`)

**If test PASSES without implementation**: The test is invalid. REWRITE IT.

---

### Phase 2: GREEN - Minimal Implementation

**RULE**: Write the MINIMUM code to make the test pass. Nothing more.

#### Step 2.1: Implement Just Enough
#### Step 2.2: Run Test and VERIFY IT PASSES

```bash
pytest tests/test_<file>.py -v -k "test_function_name"
```

---

### Phase 3: REFACTOR - Clean Up

**RULE**: Improve code quality while keeping tests GREEN.

#### Step 3.1: Check for Code Smells
#### Step 3.2: Refactor If Needed
#### Step 3.3: Run Tests After Each Change

```bash
pytest tests/test_<file>.py -v
```

#### Step 3.4: Run Linting

```bash
ruff check scripts/ recipes/ tests/ --fix
ruff format scripts/ recipes/ tests/
```

#### Step 3.5: Run Full Test Suite

```bash
pytest -v --tb=short
```

---

## Iteration

After completing one Red-Green-Refactor cycle, ask the user about continuing.

Common progression:
1. Happy path test
2. Edge case tests
3. Error handling tests
4. Integration tests (if needed)

---

## Anti-Patterns to AVOID

### DON'T: Write Implementation First
### DON'T: Write Tests That Can't Fail
### DON'T: Over-Engineer in GREEN Phase
### DON'T: Add try/except in Tests (Let It Crash)

---

## CCP-Specific Patterns

### Mocking Composio Tools

```python
from unittest.mock import patch, MagicMock

def test_recipe_execution():
    """Mock run_composio_tool for recipe testing."""
    with patch("scripts.recipe_client.ComposioRecipeClient") as mock:
        mock.return_value.execute_recipe.return_value = {
            "status": "DONE", "results": {"twitter": "posted"}
        }
        # Test the function that uses the client
```

### Mocking invoke_llm

```python
def test_llm_content_generation():
    """Mock invoke_llm for recipe testing."""
    # In recipe context, invoke_llm is a global
    with patch("builtins.invoke_llm", return_value="Generated content"):
        # Execute recipe logic
```

### Testing Pure Functions (Preferred)

```python
from scripts.draft_store import slugify, build_draft, validate_draft_for_publish

def test_slugify_basic():
    assert slugify("Hello World! 2025") == "hello-world-2025"

def test_build_draft_creates_valid_structure():
    draft = build_draft(
        title="Test", date="2025-01-01", time="6 PM",
        location="Philly", description="Desc", url="https://example.com",
        copies={"twitter": "Tweet"}, image_url="https://img.png"
    )
    assert draft["status"] == "draft"
    assert draft["version"] == 1
```

### Testing Recipe Validation

```python
def test_validate_recipes_passes():
    """Ensure validate_recipes.py passes on all recipe files."""
    import subprocess
    result = subprocess.run(
        ["python", "scripts/validate_recipes.py"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
```

---

## Quick Reference

| Phase | Action | Verify |
|-------|--------|--------|
| RED | Write test | Test FAILS |
| GREEN | Write minimal impl | Test PASSES |
| REFACTOR | Clean up | Tests still PASS |

```bash
pytest tests/test_<file>.py -v -k "test_name"  # Run specific test
pytest -v --tb=short                             # Run all tests
ruff check scripts/ recipes/ tests/ --fix && ruff format scripts/ recipes/ tests/
```

## Notes

- Always check `tests/conftest.py` for available fixtures
- Do NOT add `try/except` in tests (Let It Crash principle)
- Recipe files are self-contained -- test helpers by importing them directly or via subprocess
- Rust code in `gui/src-tauri/src/` is tested via `cargo test` (separate workflow)
