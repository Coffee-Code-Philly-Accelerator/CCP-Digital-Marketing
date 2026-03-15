---
description: Run recipe validation and pattern compliance checks across the CCP codebase
allowed-tools: AskUserQuestion, Bash, Read, Glob, Grep, Edit, Write
argument-hint: [--scope recipes|scripts|rust|all] [--fix] [--dry-run]
---

# Recipe & Code Validation

Run structural validation, pattern compliance, and design principle checks across the CCP codebase. Identifies recipe pattern violations, Let It Crash compliance, KISS metrics, and cross-file consistency issues.

## Arguments

- `$ARGUMENTS` - Options:
  - `--scope <scope>` - What to validate: `recipes`, `scripts`, `rust`, `all` (default: `all`)
  - `--fix` - Auto-fix issues where possible
  - `--dry-run` - Report issues without fixing

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at decision points.** Validation can surface many issues -- let the user prioritize which to address.

- **Before** running -- confirm scope
- **After** results -- ask which issues to fix
- **Before** fixing -- present proposed changes for approval

## Checks

### 1. Recipe Validation (scripts/validate_recipes.py)

```bash
python scripts/validate_recipes.py
```

This runs AST-based checks on all recipe files. If it fails, report the specific violations.

### 2. Recipe Pattern Compliance

For each file in `recipes/*.py`, verify:

| Check | Rule | Severity |
|-------|------|----------|
| Docstring format | First line: `"""RECIPE: Name \| RECIPE ID: rcp_xxxxx"""` | ERROR |
| Self-contained | No imports from `scripts/` or `gui/` | ERROR |
| Output pattern | Ends with bare variable assignment (no `return`) | ERROR |
| Mock guards | Has `# LET-IT-CRASH-EXCEPTION` on `except NameError` for mocks | WARNING |
| Helper sync | `sanitize_input()`, `extract_data()`, `extract_json_from_text()` match across files | WARNING |
| Apostrophe escaping | Browser recipes (luma, meetup, partiful) include `' -> \u2019`; non-browser recipes don't | WARNING |
| Input pattern | Uses `os.environ.get()` for inputs | ERROR |

### 3. Let It Crash Compliance

For each `.py` file in `scripts/` and `recipes/`:

```bash
# Check for unauthorized try/except
for f in recipes/*.py; do
  VIOLATIONS=$(grep -n '^\s*except ' "$f" | grep -v 'except NameError' | grep -v '# LET-IT-CRASH-EXCEPTION')
  if [ -n "$VIOLATIONS" ]; then
    echo "ERROR: $f has unauthorized try/except"
    echo "$VIOLATIONS"
  fi
done

for f in scripts/*.py; do
  BARE=$(grep -n '^\s*except\s*:' "$f")
  if [ -n "$BARE" ]; then
    echo "ERROR: $f has bare 'except:' clause"
  fi
done
```

### 4. KISS Metrics

For each `.py` file in `scripts/` and `recipes/`:

| Metric | Threshold | Action |
|--------|-----------|--------|
| File length | > 500 lines | WARNING |
| Deep nesting | > 3 levels (16+ spaces indent) | WARNING |
| Function length | > 30 lines | WARNING |
| Parameters | > 8 | WARNING |

### 5. Pure Functions Check

```bash
# Check for global state mutation
for f in $(find scripts recipes -name "*.py"); do
  GLOBALS=$(grep -n '^\s\+global ' "$f")
  if [ -n "$GLOBALS" ]; then
    echo "ERROR: $f uses 'global' keyword"
  fi
done
```

### 6. Rust Checks (if toolchain available)

```bash
if command -v cargo &>/dev/null; then
  cd gui/src-tauri
  cargo clippy -- -D warnings 2>&1
  cargo fmt -- --check 2>&1
  cd ../..
fi
```

### 7. Ruff Lint & Format

```bash
ruff check scripts/ recipes/ --output-format=github
ruff format --check scripts/ recipes/
```

### 8. Cross-File Consistency

- **Recipe helper sync**: Compare `sanitize_input()` across all recipe files
- **Draft schema sync**: Compare `scripts/draft_store.py` `build_draft()` with `gui/src-tauri/src/draft.rs` draft types
- **Config sync**: Compare env var defaults in `gui/src-tauri/src/config.rs` with CLAUDE.md table

---

## Output Format

```markdown
## Validation Report

**Scope**: <scope>
**Files Checked**: N

### Errors (must fix)

| # | File | Line | Check | Issue |
|---|------|------|-------|-------|
| 1 | recipes/foo.py | 42 | Recipe Pattern | Missing RECIPE docstring |

### Warnings (should fix)

| # | File | Line | Check | Issue |
|---|------|------|-------|-------|

### Passed
- Recipe validation: PASS
- Let It Crash: PASS (N files)
- KISS metrics: PASS
- Ruff lint: PASS
- Cargo clippy: PASS

### Summary
- Errors: N
- Warnings: M
- Files clean: K
```

## Fix Mode

If `--fix` is specified, attempt auto-fixes:

| Check | Auto-Fix |
|-------|----------|
| Ruff lint | `ruff check scripts/ recipes/ --fix` |
| Ruff format | `ruff format scripts/ recipes/` |
| Cargo fmt | `cargo fmt` |
| Helper sync | Copy canonical helper to other files (ask which is canonical) |

Manual fixes required for:
- Recipe pattern violations
- Let It Crash violations (requires design decision)
- KISS metric violations (requires refactoring)

## Example Usage

```
/evaluate
/evaluate --scope recipes
/evaluate --scope rust
/evaluate --fix
/evaluate --dry-run --scope scripts
```

## Notes

- `validate_recipes.py` is the primary recipe validation tool -- always run it first
- Rust checks require the Rust toolchain to be installed
- Helper sync checks compare function bodies, not just names
- The apostrophe escaping divergence between browser/non-browser recipes is intentional
