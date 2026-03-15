---
description: Update unit tests and integration tests for full coverage
allowed-tools: AskUserQuestion, Bash, Read, Glob, Grep, Edit, Write
argument-hint: [--target=80] [--module=scripts.draft_store] [--dry-run]
---

# Test Coverage Updater

Analyze current test coverage, identify gaps, and write missing tests to reach the target coverage threshold.

## Arguments

- `$ARGUMENTS` - Options to control scope and behavior:
  - `--target=N` - Coverage percentage target (default: `80`)
  - `--module=<path>` - Restrict to a specific module (e.g., `scripts.draft_store`)
  - `--dry-run` - Analyze gaps and report plan without writing tests
  - `--fix` - Fix failing existing tests before writing new ones

---

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at decision points.** Test coverage involves tradeoffs between speed and thoroughness. Validate priorities rather than guessing.

- **Before** writing tests -- confirm which modules to prioritize
- **When** gaps are large -- ask where to focus effort first
- **After** coverage run -- ask about iteration vs stopping

## Workflow

### Phase 1: Coverage Baseline

#### 1.1 Run Current Coverage Report

```bash
pip install -r scripts/requirements.txt -q 2>/dev/null
pip install -r requirements-test.txt -q 2>/dev/null
pytest --cov=scripts --cov=recipes --cov-report=term-missing --cov-report=json:coverage.json -q --tb=no 2>&1 | tail -80
```

#### 1.2 Parse Coverage Gaps

Read `coverage.json` to extract per-file coverage and uncovered lines.

#### 1.3 Build Gap Report

Create a ranked list of files by coverage gap:

| File | Coverage | Missing Lines | Priority |
|------|----------|---------------|----------|
| scripts/recipe_client.py | ??% | ... | CRITICAL/HIGH/MEDIUM/LOW |
| scripts/draft_store.py | ??% | ... | ... |
| recipes/*.py | ??% | ... | ... |

**Priority rules:**
- CRITICAL: 0% coverage
- HIGH: < 30% coverage
- MEDIUM: 30-60% coverage
- LOW: > 60% but below target

#### 1.4 Confirm Coverage Priorities with User

**Skip these files** (recipe runtime dependencies not available locally):
- `recipes/*.py` functions that call `run_composio_tool()` or `invoke_llm()` (mock boundaries)
- Any `__init__.py` files with no logic

---

### Phase 2: Analyze Existing Test Patterns

Before writing ANY tests, study the project's conventions.

#### 2.1 Read Test Infrastructure

```bash
ls tests/
cat tests/conftest.py 2>/dev/null
cat requirements-test.txt
```

#### 2.2 Module-to-Test Mapping Reference

| Source Module | Test Location | Fixtures Needed |
|---------------|---------------|-----------------|
| `scripts/recipe_client.py` | `tests/test_client_*.py` | mock ComposioRecipeClient |
| `scripts/draft_store.py` | `tests/test_draft_store.py` | tmp_path for draft files |
| `scripts/validate_recipes.py` | `tests/test_validate_recipes.py` | none |
| `recipes/social_promotion.py` | `tests/test_recipes/test_social_promotion.py` | mock run_composio_tool, invoke_llm |
| `recipes/social_post.py` | `tests/test_recipes/test_social_post.py` | mock run_composio_tool, invoke_llm |
| `recipes/email_reply.py` | `tests/test_recipes/test_email_reply.py` | mock run_composio_tool, invoke_llm |

---

### Phase 3: Generate Tests

Process gaps in priority order (CRITICAL first). For each file:

#### 3.1 Read the Source Module
#### 3.2 Determine What to Test

| Function Characteristic | Test Type |
|------------------------|-----------|
| Pure function (slugify, build_draft, validate_draft_for_publish) | Unit test (no mocks) |
| Function with Composio API calls | Unit test with mock |
| CLI entry point | Integration test with subprocess |
| Recipe file | Test pure helpers; mock Composio/LLM boundaries |

#### 3.3 Write Tests

Follow these conventions:

```python
"""Tests for scripts.<module>."""
import pytest
from scripts.<module> import function_under_test


class TestFunctionName:
    """Tests for function_name."""

    def test_returns_expected_result(self):
        """function_name returns correct output for valid input."""
        # Arrange
        input_data = ...

        # Act
        result = function_under_test(input_data)

        # Assert
        assert result == expected_value

    def test_handles_edge_case(self):
        """function_name handles edge case correctly."""
        ...
```

**Rules:**
- Use `class Test*` grouping per function under test
- Use AAA pattern (Arrange/Act/Assert)
- Do NOT add `try/except` in tests (Let It Crash principle)
- Mock only external dependencies (Composio API, network)
- Do NOT modify source code to make tests pass (unless genuine bug)

---

### Phase 4: Validate Tests

```bash
# Run new tests
pytest tests/test_<module>.py -v --tb=short

# Full suite
pytest -v --tb=short

# Lint test files
ruff check tests/ --fix
ruff format tests/
```

---

### Phase 5: Coverage Verification

```bash
pytest --cov=scripts --cov=recipes --cov-report=term-missing -q --tb=no 2>&1 | tail -80
```

Report coverage delta (before/after table).

---

## Anti-Patterns to Avoid

### DO NOT:
- Test private/internal methods directly (test via public API)
- Duplicate existing test coverage
- Add `try/except` in tests (Let It Crash)
- Modify source code to make it "more testable"
- Create test utility frameworks or base classes (KISS)
- Write parameterized tests for < 3 cases

---

## Example Usage

```
/test-coverage
/test-coverage --target=70
/test-coverage --module=scripts.draft_store
/test-coverage --dry-run
/test-coverage --fix --target=75
```

## Notes

- Pure functions in `scripts/draft_store.py` are quick wins for coverage
- Recipe helpers (sanitize_input, extract_data) can be tested by importing them
- Rust code in `gui/src-tauri/src/` is tested via `cargo test` (separate workflow)
- Never mock Pydantic/dataclass validation -- let errors propagate per Let It Crash
