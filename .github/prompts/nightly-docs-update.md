# Nightly Documentation Update (Autonomous CI Mode)

You are running in a CI pipeline. You MUST operate fully autonomously.
Do NOT use AskUserQuestion. Do NOT pause for user input. Do NOT use Write to create new files.

## Rules

1. ONLY modify files listed in AFFECTED_DOCS (provided at the end of this prompt)
2. NEVER modify: .github/, .env*, *.py, *.rs, *.js, *.yml, *.yaml
3. Be CONSERVATIVE — only update sections where code has demonstrably changed
4. Do NOT add new sections, restructure documents, or change formatting/style
5. Do NOT modify design principles, philosophy, or instructional content in CLAUDE.md
6. Focus on: factual data (tables, file paths, recipe IDs, env vars, command examples)
7. When cross-doc inconsistency found: code is the source of truth — update the doc to match code
8. When ambiguous: SKIP the change entirely (do not guess)
9. Preserve all existing markdown formatting, heading levels, and whitespace conventions
10. Do NOT remove content unless it references files/features that no longer exist in the codebase

## Steps

### Step 1: Gather Context

Run `git log --oneline -N` (N = COMMITS_TO_ANALYZE) to see recent changes and understand what was modified.

Run `git log --oneline -N --name-only --pretty=format: | sort -u | grep -v '^$'` to get the full list of changed files.

### Step 2: For Each File in AFFECTED_DOCS

For each documentation file listed in AFFECTED_DOCS:

1. **Read the documentation file** using the Read tool
2. **Read the relevant source-of-truth code files** (see mapping below)
3. **Compare**: identify sections that are factually outdated (wrong file paths, missing recipes, incorrect recipe IDs, outdated env vars, stale tables)
4. **Use Edit tool** to update ONLY the outdated sections — make minimal, targeted edits
5. Move on to the next file

### Step 3: Verify Changes

After all updates, run `git diff` to verify:
- Changes are minimal and correct
- No unintended modifications
- Formatting is preserved

## Source-of-Truth Mapping

Use this mapping to determine which code files to read when validating each documentation file.

### README.md

| Doc Section | Source of Truth |
|-------------|----------------|
| Recipe table | `recipes/*.py` (recipe ID in docstring header) |
| CLI commands | `scripts/recipe_client.py` (argparse subcommands) |
| Environment variables | `.env.example`, `scripts/recipe_client.py`, `gui/src-tauri/src/config.rs` |
| GUI description | `gui/src-tauri/src/main.rs`, `gui/src/index.html` |
| Skills table | `.claude/skills/*/` directories |

### CLAUDE.md

| Doc Section | Source of Truth |
|-------------|----------------|
| Key Recipes table | `recipes/*.py` (recipe IDs in docstring headers) |
| Architecture section | `gui/src-tauri/src/*.rs` (module purposes), `gui/src/*.js` (frontend files) |
| Environment Variables table | `gui/src-tauri/src/config.rs` (`AppConfig`), `scripts/recipe_client.py` |
| Composio Tool Reference | `recipes/*.py` (tool names in `run_composio_tool()` calls) |
| Claude Code Skills table | `.claude/skills/*/` directories |
| Draft Workflow | `scripts/draft_store.py`, `gui/src-tauri/src/draft.rs` |
| Platform Quirks | `recipes/create_event_*.py` (task instruction comments) |

## Per-Document Validation Rules

### README.md
- Recipe table must list all recipes in `recipes/` with correct IDs
- CLI commands must match `recipe_client.py` subcommands
- Environment variables section must match actual env var usage
- Do NOT modify the project description, badges, or contribution guidelines

### CLAUDE.md
- Key Recipes table recipe IDs must match actual recipe file docstrings
- Architecture tables must list actual files that exist
- Environment Variables table must be accurate
- Do NOT modify Design Philosophy, Principle Priority, Let It Crash, SOLID, KISS, or Pure Functions sections
- Do NOT modify CI/CD section unless workflow files changed

## Important Reminders

- You are in CI — there is NO human to ask questions to
- If a documentation file in AFFECTED_DOCS does not exist, skip it silently
- Every edit must be verifiable against actual source code — do not infer or hallucinate
- Prefer no change over a wrong change
