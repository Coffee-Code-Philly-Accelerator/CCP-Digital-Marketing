---
description: Review and update CCP documentation based on recent git changes
allowed-tools: AskUserQuestion, Bash, Read, Glob, Grep, Edit, Write
argument-hint: [commits=20] [--dry-run]
---

# CCP Documentation Review and Update

Review project documentation against recent git changes with full project context. This command understands the recipe system, Tauri GUI, CLI scripts, and browser automation architecture.

## Arguments

- **commits**: Number of recent commits to analyze (default: 20)
- **--dry-run**: Preview changes without applying them

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at decision points.** Documentation changes are visible to the whole team and affect onboarding. Confirm scope and validate findings before modifying files.

- **Before** analyzing -- confirm which docs and how many commits to review
- **After** generating the staleness report -- let the user choose what to update
- **Before** applying edits -- present proposed changes for approval
- **When** cross-section inconsistencies are found -- ask which section is the source of truth

## Documentation Files (In-Scope)

CCP has a single documentation file:

| Doc File | Purpose |
|----------|---------|
| `CLAUDE.md` | Claude Code instructions -- project overview, architecture, recipes, design principles |

## Excluded Files

- `.github/workflows/*.yml` - CI/CD (separate concern)
- `.env*` - Environment files
- `node_modules/`, `.venv/` - Dependencies
- `drafts/` - Generated draft outputs

---

## Step 1: Gather Git Context

### 1.1 Changed Files Analysis

```bash
git log --oneline -N --name-only --pretty=format: | sort -u | grep -v '^$'
```

### 1.2 Categorize Changes and Map to CLAUDE.md Sections

| Code Pattern | Affected CLAUDE.md Section |
|--------------|---------------------------|
| `scripts/recipe_client.py` | Development Commands, CLI Commands, Draft Workflow |
| `scripts/draft_store.py` | Draft Store Module, Draft JSON Schema |
| `scripts/validate_recipes.py` | Architecture |
| `recipes/*.py` | Key Recipes, Recipe Code Pattern, Composio Tool Reference |
| `gui/src-tauri/src/config.rs` | Environment Variables, Default Configuration |
| `gui/src-tauri/src/composio.rs` | Architecture (Backend modules) |
| `gui/src-tauri/src/draft.rs` | Draft Workflow, Architecture |
| `gui/src-tauri/src/draft_commands.rs` | Architecture (Backend modules) |
| `gui/src-tauri/src/recipe_commands.rs` | Architecture (Backend modules) |
| `gui/src-tauri/src/progress.rs` | Architecture (Backend modules) |
| `gui/src-tauri/src/db.rs` | Architecture (Backend modules) |
| `gui/src/*.js` | Architecture (Frontend) |
| `.env*` | Environment Variables |
| `.claude/skills/*/` | Claude Code Skills |
| `.claude/commands/*/` | (not yet in CLAUDE.md -- may need adding) |

---

## Step 2: Source-of-Truth Validation

For each affected section, validate CLAUDE.md against the actual source code.

### 2.1 Key Recipes Table

**Source of truth**: `recipes/*.py` (first line docstring contains recipe name and ID)

Verify:
- Recipe names match
- Recipe IDs match (`rcp_*` values)
- Purpose descriptions are accurate

### 2.2 Environment Variables Table

**Source of truth**: `gui/src-tauri/src/config.rs` (the `AppConfig` struct and its `from_env()` method)

Verify:
- All `CCP_*` env vars documented
- Default values match code
- Required/optional status is correct

### 2.3 Architecture - Backend Modules Table

**Source of truth**: `gui/src-tauri/src/*.rs` files

Verify:
- All modules listed
- Purpose descriptions are accurate
- IPC command counts match

### 2.4 Composio Tool Reference

**Source of truth**: `recipes/*.py` (actual tool calls in recipe code)

Verify:
- All tools used in recipes are documented
- Deprecated tools are marked
- Browser provider info is current

### 2.5 CLI Commands

**Source of truth**: `scripts/recipe_client.py` (argument parser and subcommands)

Verify:
- All subcommands documented
- Argument examples are correct

### 2.6 Draft JSON Schema

**Source of truth**: `scripts/draft_store.py` (build_draft function) and `gui/src-tauri/src/draft.rs`

Verify:
- Schema fields match both implementations
- Status lifecycle is accurate

### 2.7 Claude Code Skills Table

**Source of truth**: `.claude/skills/*/` directories

Verify:
- All skills listed
- Recipe IDs match
- Purpose descriptions accurate

### 2.8 File Path Validation

For each file path referenced in CLAUDE.md, verify it exists using Glob.

---

## Step 3: Cross-Reference Validation

Ensure information is consistent within CLAUDE.md:
- Recipe IDs in "Key Recipes" table match "Claude Code Skills" table
- Environment variables referenced in multiple sections are consistent
- Browser provider info in "Browser Provider Configuration" matches recipe code

---

## Step 4: Generate Staleness Report

```markdown
## Documentation Staleness Report

### Summary
- **Commits Analyzed**: N
- **Sections with Issues**: Y

### Critical Issues
- [ ] [Issue description]

### Missing Documentation
- [ ] [What's missing]

### Outdated Information
- [ ] [What changed]
```

## Step 5: Apply Updates

### If --dry-run:
1. Display staleness report
2. Show proposed edits (before/after snippets)
3. Exit without changes

### If applying (default):

#### 5a. Confirm Which Sections to Update

Use AskUserQuestion to let the user choose which sections to update.

1. Use Edit tool for targeted changes
2. Preserve existing formatting and style
3. Update tables in-place

After all edits:
- Run `git diff CLAUDE.md` to show changes
- Present summary for review

---

## Step 6: Output Summary

```markdown
## Documentation Update Summary

**Commits Analyzed**: N
**Sections Updated**: X

### Changes Made
| Section | Change |
|---------|--------|
| Key Recipes | Updated recipe ID for ... |
| Environment Variables | Added CCP_NEW_VAR |
| ... | ... |

### Verification
git diff CLAUDE.md
```

## Safety

- Only modifies `CLAUDE.md`
- Never touches recipe files, Rust code, or workflow files
- Git-based rollback always available
- Human review via `git diff`
- Dry-run mode for preview
