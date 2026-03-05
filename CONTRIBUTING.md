# Contributing to CCP Digital Marketing

Thank you for your interest in contributing to CCP Digital Marketing! This project automates event creation and social media promotion for Coffee Code Philly Accelerator.

## Getting Started

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/CCP-Digital-Marketing.git
   cd CCP-Digital-Marketing
   ```
3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/Coffee-Code-Philly-Accelerator/CCP-Digital-Marketing.git
   ```

### Development Setup

Install dependencies:

```bash
# Install runtime dependencies
pip install -r scripts/requirements.txt

# Install test dependencies
pip install -r requirements-test.txt
```

Set up environment variables:

```bash
export COMPOSIO_API_KEY='your-api-key'
export CCP_MEETUP_GROUP_URL='https://www.meetup.com/code-coffee-philly'
```

### Running Tests

```bash
# Run all tests with coverage
pytest tests/ -v --cov=scripts --cov-report=term-missing

# Run specific test file
pytest tests/test_recipe_client.py -v

# Run with verbose output
pytest tests/ -vv
```

### Code Quality

This project uses Ruff for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-format code
ruff format .

# Check and format in one command
ruff check . && ruff format .
```

Configuration is in `pyproject.toml`.

## Developer Certificate of Origin (DCO)

All commits must be signed off to certify you have the right to contribute the code. By signing off, you agree to the [Developer Certificate of Origin](https://developercertificate.org/):

```
Developer Certificate of Origin
Version 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

### How to Sign Off

Add the `-s` flag when committing:

```bash
git commit -s -m "Add feature X"
```

This adds a "Signed-off-by" line to your commit message:

```
Add feature X

Signed-off-by: Your Name <your.email@example.com>
```

**All commits in a PR must be signed off.** If you forgot to sign off, you can amend:

```bash
# Amend the last commit
git commit --amend -s

# Sign off all commits in a branch (rebase)
git rebase --signoff main
```

## Design Principles

This project follows strict design principles documented in `CLAUDE.md`. Please read the full document before contributing. Key principles:

### 1. Let It Crash (CRITICAL)

**Do NOT write `try/except` blocks.** This is the most important principle in the codebase.

- Errors should propagate visibly with full stack traces
- Use error-returning patterns: `result, error = run_composio_tool(...)`
- No defensive programming, no silent failures, no retry loops
- The ONLY exception: third-party library imports that may not be installed, annotated with `# LET-IT-CRASH-EXCEPTION: IMPORT_GUARD`

```python
# GOOD - Let it crash
def create_event(title: str, date: str) -> dict:
    payload = {"title": title, "date": date}
    result, error = run_composio_tool("TOOL_NAME", payload)
    if error:
        return {"status": "FAILED", "error": error}
    return {"status": "DONE", "data": result}

# BAD - Don't add try/except
def create_event(title: str, date: str) -> dict:
    try:
        result, error = run_composio_tool("TOOL_NAME", payload)
        return result
    except Exception as e:
        return None  # NEVER DO THIS
```

### 2. KISS (Keep It Simple, Stupid)

- Readable over clever
- Explicit over implicit
- Avoid premature abstraction (wait for 3+ use cases)
- No over-engineering

### 3. Pure Functions

- Business logic should be pure (deterministic, no side effects)
- Push I/O and state changes to boundaries
- Makes testing easy, code predictable

### 4. SOLID Principles

- Single Responsibility: One purpose per function
- Open-Closed: Extend via configuration, not modification
- Liskov Substitution: Subtypes must honor contracts
- Interface Segregation: Small, focused interfaces
- Dependency Inversion: Depend on abstractions

## Pull Request Process

### 1. Create a Feature Branch

```bash
git checkout -b feature/description
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

- Follow design principles (especially Let It Crash)
- Add tests for new functionality
- Update documentation if needed
- Keep commits focused and atomic

### 3. Run Local Checks

Before pushing, ensure all checks pass:

```bash
# Run tests
pytest tests/ -v

# Check code quality
ruff check .
ruff format .

# Verify all tests pass
pytest tests/ --cov=scripts
```

### 4. Commit with Sign-Off

```bash
git add .
git commit -s -m "Add feature: description"
```

Remember: **All commits must be signed off** (use `-s` flag).

### 5. Push and Open PR

```bash
git push origin feature/description
```

Open a pull request on GitHub and fill out the PR template checklist.

### 6. Respond to Reviews

- **Claude Code Review**: The CI automatically runs Claude Code review on your PR. Respond to feedback and push fixes.
- **Maintainer Review**: Wait for a maintainer to review and approve.
- **CI Checks**: All 9 CI jobs must pass (lint, format, test, coverage, security, design principles, etc.).

### 7. Merge

Once approved and all checks pass, a maintainer will merge your PR. The branch will be automatically deleted after merge.

## Recipe Contributions

Recipes in `recipes/` are self-contained Python scripts for Composio's Rube MCP runtime.

### Recipe Pattern

```python
"""RECIPE: Name | RECIPE ID: rcp_xxxxx"""
import os

# Inputs from environment variables
event_title = os.environ.get("event_title")
event_date = os.environ.get("event_date")

# Call Composio tools
result, error = run_composio_tool("TOOL_NAME", {
    "param1": event_title,
    "param2": event_date,
})

# Use AI for content generation
response, error = invoke_llm("Generate a description for: " + event_title)

# Output as bare variable (no return statement)
output = {
    "status": "DONE" if not error else "FAILED",
    "data": result,
    "error": error,
}
output
```

### Recipe Requirements

- **Header**: Include recipe name and ID in docstring
- **Inputs**: Use `os.environ.get()` for all inputs
- **Tools**: Use `run_composio_tool()` for Composio APIs
- **AI**: Use `invoke_llm()` for LLM calls
- **Output**: Bare variable at end (no `return` statement)
- **Testing**: Include mock implementations for local testing
- **Error Handling**: Follow "Let It Crash" - no try/except

### Recipe Testing

Test recipes locally using the CLI:

```bash
python scripts/recipe_client.py create-event \
  --title "Test Event" \
  --date "January 25, 2025" \
  --time "6:00 PM EST" \
  --location "Test Location" \
  --description "Test description"
```

## What to Contribute

We welcome contributions in these areas:

### Bug Fixes
- Fix broken recipes (form filling, auth issues)
- Fix CLI bugs
- Fix documentation errors

### New Platform Integrations
- Eventbrite support
- Additional Meetup alternatives
- New event platforms

### New Social Media Platforms
- Bluesky integration
- Mastodon support
- Threads integration
- TikTok support

### Recipe Improvements
- Better AI prompts for content generation
- More robust form filling (handle edge cases)
- Image generation enhancements
- Better error messages

### Documentation
- Improve setup guides
- Add troubleshooting tips
- Create video tutorials
- Translate documentation

### Tests
- Increase test coverage
- Add integration tests
- Add end-to-end tests

## Code Review Standards

All PRs must pass these checks:

| Check | Tool | Requirement |
|-------|------|-------------|
| Linting | Ruff | No errors |
| Formatting | Ruff | Auto-formatted |
| Tests | Pytest | All pass |
| Coverage | Pytest-cov | Maintain or improve |
| Security | Bandit | No high/critical issues |
| Design Principles | Claude Code | Follows CLAUDE.md |
| DCO | Git commits | All signed off |

### Design Principle Violations

Common reasons PRs get blocked:

1. **try/except blocks** - Remove unless annotated with `# LET-IT-CRASH-EXCEPTION`
2. **Over-engineering** - Simplify abstractions, avoid premature optimization
3. **Impure functions** - Business logic should have no side effects
4. **Multiple responsibilities** - Split into focused functions

## Questions?

- **GitHub Issues**: For bug reports and feature requests
- **Discord**: https://discord.gg/X2a8jr73N4 for real-time help
- **Documentation**: Check README.md and CLAUDE.md first

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
