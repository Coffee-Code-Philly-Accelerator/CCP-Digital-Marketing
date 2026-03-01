#!/usr/bin/env python3
"""
Recipe Validation Script

Validates that all Rube MCP recipe files in recipes/ follow the required patterns:
1. Must parse as valid Python (AST)
2. Must have a module-level docstring with RECIPE ID
3. Must import os
4. Must define sanitize_input() and extract_data()
5. Must have a mock guard for run_composio_tool (try/except NameError)
6. Must have a bare `output` expression as the last statement
7. Must NOT have a bare `return` at module level
8. Must NOT have `if __name__` guard (recipes are not standalone scripts)
9. Must reference os.environ.get for inputs
10. Must NOT use try/except beyond the mock guard pattern

Exit codes:
  0 - All recipes valid
  1 - Validation errors found
"""

import ast
import sys
from pathlib import Path

RECIPES_DIR = Path(__file__).parent.parent / "recipes"

# auth_setup.py is NOT a Rube recipe (it's a standalone script)
SKIP_FILES = {"auth_setup.py"}

# Required function definitions in every recipe
REQUIRED_FUNCTIONS = {"sanitize_input", "extract_data"}


def validate_recipe(filepath):
    """Validate a single recipe file. Returns list of error strings."""
    errors = []
    source = filepath.read_text()
    filename = filepath.name

    # Check 1: Valid Python AST
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        return [f"Syntax error at line {e.lineno}: {e.msg}"]

    # Check 2: Module docstring with RECIPE ID
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        docstring = tree.body[0].value.value
        if "RECIPE ID" not in docstring:
            errors.append("Module docstring missing 'RECIPE ID'")
    else:
        errors.append("Missing module-level docstring")

    # Check 3: Must import os
    os_imported = False
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    os_imported = True
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            os_imported = True
    if not os_imported:
        errors.append("Missing 'import os'")

    # Check 4: Required function definitions
    defined_functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defined_functions.add(node.name)

    for fn in REQUIRED_FUNCTIONS:
        if fn not in defined_functions:
            errors.append(f"Missing required function: {fn}()")

    # Check 5: Mock guard for run_composio_tool
    has_mock_guard = False
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Try):
            # Look for: try: run_composio_tool except NameError: def run_composio_tool
            for handler in node.handlers:
                if handler.type and isinstance(handler.type, ast.Name) and handler.type.id == "NameError":
                    has_mock_guard = True
                    break
    if not has_mock_guard:
        errors.append("Missing mock guard: try/except NameError for run_composio_tool")

    # Check 6: Last statement must be bare `output` expression
    if tree.body:
        last_stmt = tree.body[-1]
        if isinstance(last_stmt, ast.Expr) and isinstance(last_stmt.value, ast.Name) and last_stmt.value.id == "output":
            pass  # Correct
        else:
            errors.append("Last statement must be bare 'output' expression (no return)")

    # Check 7: No bare return at module level
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Return):
            errors.append(f"Module-level 'return' found at line {node.lineno} (recipes use bare 'output')")

    # Check 8: No if __name__ guard
    for node in ast.iter_child_nodes(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ):
            errors.append("Recipes must not use 'if __name__' guard")

    # Check 9: Must use os.environ.get
    has_environ_get = "os.environ.get" in source
    if not has_environ_get:
        errors.append("No os.environ.get() calls found (recipes must read inputs from env)")

    # Check 10: No try/except beyond mock guards
    try_except_count = 0
    mock_guard_count = 0
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Try):
            try_except_count += 1
            is_mock_guard = False
            for handler in node.handlers:
                if handler.type and isinstance(handler.type, ast.Name) and handler.type.id == "NameError":
                    is_mock_guard = True
            if is_mock_guard:
                mock_guard_count += 1

    non_guard_try = try_except_count - mock_guard_count
    if non_guard_try > 0:
        errors.append(
            f"Found {non_guard_try} try/except block(s) beyond mock guards "
            f"(Let It Crash principle: no try/except in recipes)"
        )

    # Check 11: Must have a ValueError for missing required inputs
    has_value_error = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Raise)
            and node.exc
            and isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Name)
            and node.exc.func.id == "ValueError"
        ):
            has_value_error = True
    if not has_value_error:
        errors.append("Missing input validation: no ValueError raised for missing required inputs")

    # Check 12: Must assign output variable
    has_output_assignment = False
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "output":
                    has_output_assignment = True
    if not has_output_assignment:
        errors.append("Missing 'output = ...' assignment")

    return errors


def main():
    recipe_files = sorted(RECIPES_DIR.glob("*.py"))
    if not recipe_files:
        print("ERROR: No recipe files found in recipes/")
        return 1

    total_errors = 0
    validated = 0
    skipped = 0

    for filepath in recipe_files:
        if filepath.name in SKIP_FILES:
            print(f"  SKIP  {filepath.name} (not a Rube recipe)")
            skipped += 1
            continue

        errors = validate_recipe(filepath)
        validated += 1

        if errors:
            print(f"  FAIL  {filepath.name}")
            for error in errors:
                print(f"         - {error}")
            total_errors += len(errors)
        else:
            print(f"  OK    {filepath.name}")

    print(f"\n{validated} recipes validated, {skipped} skipped, {total_errors} errors")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
