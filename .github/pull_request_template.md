## Summary

<!-- What does this PR do? 1-3 bullet points. -->

## Design Principles Checklist

Before submitting, verify your changes follow the project's design philosophy:

- [ ] **Let It Crash**: No `try/except` blocks (unless annotated with `# LET-IT-CRASH-EXCEPTION`)
- [ ] **KISS**: No premature abstractions, no clever one-liners, functions under 30 lines
- [ ] **Pure Functions**: Business logic is side-effect-free; I/O pushed to boundaries
- [ ] **SOLID**: Each function/module has a single responsibility
- [ ] **Recipe Pattern**: Recipes use `os.environ.get()` for inputs, `run_composio_tool()` for APIs, bare variable output

## Test Plan

<!-- How did you verify this works? -->
