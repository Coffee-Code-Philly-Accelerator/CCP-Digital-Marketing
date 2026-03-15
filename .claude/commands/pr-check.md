---
description: Run all local CI checks before creating a PR
allowed-tools: AskUserQuestion, Bash, Read, Edit, Write, Glob, Grep
argument-hint: (no arguments)
---

# PR Check Skill

Run all local CI checks before creating a PR. On failure, offer to fix issues interactively.

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at decision points.** CI check failures require judgment about whether to auto-fix, skip, or investigate.

- **When** a check fails -- ask how to handle before auto-fixing
- **When** multiple checks fail -- let the user prioritize which to fix first
- **After** all checks pass -- ask about next steps

## Checks Overview

Display to user before running:

> **Running 6 PR checks:**
> 1. **Ruff linter** -- `ruff check scripts/ recipes/`
> 2. **Ruff formatter** -- `ruff format --check scripts/ recipes/`
> 3. **Recipe validation** -- `python scripts/validate_recipes.py`
> 4. **Security scan** -- `bandit -r scripts/ recipes/ -ll`
> 5. **Cargo check** -- `cargo clippy -- -D warnings && cargo fmt -- --check` (in `gui/src-tauri/`)
> 6. **Pytest** -- `pytest tests/ -v --tb=short`

## Execute Checks

Run each check sequentially, stopping on first failure:

```bash
# 1. Ruff lint
echo "[1/6] Ruff linter..."
ruff check scripts/ recipes/ --output-format=github

# 2. Ruff format
echo "[2/6] Ruff formatter..."
ruff format --check scripts/ recipes/

# 3. Recipe validation
echo "[3/6] Recipe validation..."
python scripts/validate_recipes.py

# 4. Security scan
echo "[4/6] Security scan..."
pip install bandit -q 2>/dev/null
bandit -r scripts/ recipes/ -ll

# 5. Cargo check (if Rust toolchain available)
echo "[5/6] Cargo check..."
if command -v cargo &>/dev/null; then
  cd gui/src-tauri && cargo clippy -- -D warnings && cargo fmt -- --check && cd ../..
else
  echo "Skipping: Rust toolchain not installed"
fi

# 6. Pytest
echo "[6/6] Pytest..."
pytest tests/ -v --tb=short
```

## On Success

If all checks pass:

```
AskUserQuestion:
  question: "All PR checks passed! What would you like to do next?"
  header: "Next"
  multiSelect: false
  options:
    - label: "Create PR"
      description: "Run /pr to create a pull request with these changes"
    - label: "Run code review"
      description: "Run /code-review before creating the PR"
    - label: "Done"
      description: "Checks passed -- I'll handle the rest manually"
```

## On Failure - Interactive Fix Loop

### 1. Identify Which Check Failed

Parse the output to determine which step failed:
- `[1/6]` = Ruff lint
- `[2/6]` = Ruff format
- `[3/6]` = Recipe validation
- `[4/6]` = Security scan
- `[5/6]` = Cargo check
- `[6/6]` = Pytest

### 2. Ask User How to Handle Each Failure

**Fix strategies by check type:**

| Check | Auto-Fix Strategy |
|-------|------------------|
| **[1/6] Ruff lint** | Run `ruff check scripts/ recipes/ --fix`, then manually fix remaining |
| **[2/6] Ruff format** | Run `ruff format scripts/ recipes/` |
| **[3/6] Recipe validation** | Read error, fix recipe structure issues |
| **[4/6] Security scan** | Explain each Bandit finding, remediate with targeted code changes |
| **[5/6] Cargo check** | Run `cargo clippy --fix` and `cargo fmt`, then fix remaining |
| **[6/6] Pytest** | Read failing tests and source code, fix the root cause |

### 3. After Fix - Re-run All Checks

Continue the fix loop until all checks pass or user stops.

### 4. Track Fixes Applied

On final success, summarize all fixes applied during the session.

## Notes

- Always run full mode -- no shortcuts
- Cargo check is skipped if Rust toolchain is not installed locally
- Never skip or bypass checks -- always fix the underlying issue
- Times out after 10 failed check fix attempts (asks for user guidance)
