"""
AST-based function extractor for recipe files.

Recipes execute code at module level (os.environ.get, run_composio_tool, etc.)
so they cannot be imported directly. This module uses Python's ast module to
extract only function definitions, compiling them into callable objects without
executing any module-level code.
"""

import ast
import textwrap
from pathlib import Path


def extract_functions_from_file(filepath, function_names):
    """
    Extract function definitions from a Python file without executing module-level code.

    Args:
        filepath: Path to the Python source file
        function_names: List of function names to extract

    Returns:
        Dict mapping function names to callable objects.
        Missing functions are omitted from the result.
    """
    source = Path(filepath).read_text()
    tree = ast.parse(source)

    functions = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in function_names:
            # Extract the source lines for this function
            func_source = ast.get_source_segment(source, node)
            if func_source is None:
                continue

            # Dedent in case it's nested (shouldn't be for recipe top-level funcs)
            func_source = textwrap.dedent(func_source)

            # Compile and execute just this function definition
            code = compile(func_source, filepath, "exec")
            namespace = {}
            exec(code, namespace)
            if node.name in namespace:
                functions[node.name] = namespace[node.name]

    return functions


def extract_functions_with_imports(filepath, function_names):
    """
    Extract functions along with their required imports.

    Same as extract_functions_from_file but also executes import statements
    so that functions referencing stdlib modules (e.g., json) work correctly.
    """
    source = Path(filepath).read_text()
    tree = ast.parse(source)

    # Collect import statements
    import_lines = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.append(ast.get_source_segment(source, node))

    # Build namespace with imports
    namespace = {}
    for imp in import_lines:
        if imp:
            exec(compile(imp, filepath, "exec"), namespace)

    # Extract and compile each function into the namespace
    functions = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in function_names:
            func_source = ast.get_source_segment(source, node)
            if func_source is None:
                continue
            func_source = textwrap.dedent(func_source)
            code = compile(func_source, filepath, "exec")
            exec(code, namespace)
            if node.name in namespace:
                functions[node.name] = namespace[node.name]

    return functions
