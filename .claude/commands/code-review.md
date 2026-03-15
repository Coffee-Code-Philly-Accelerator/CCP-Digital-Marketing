---
description: Code review git changes using multi-model consensus
allowed-tools: AskUserQuestion, Bash, Read, Edit, Glob, Grep, mcp__pal__consensus, mcp__pal__codereview, mcp__pal__listmodels
argument-hint: [commits=5] [--staged] [--branch <target>] [--focus <area>] [--post-pr]
---

# Git Code Review with Multi-Model Consensus

Perform comprehensive code review using PAL MCP multi-model consensus. Reviews recent commits, staged changes, or branch comparisons with focus on security, quality, performance, and architecture.

## Arguments

- `$ARGUMENTS` - Review configuration:
  - `commits=N` - Number of recent commits to review (default: 5)
  - `--staged` - Review only staged changes instead of commits
  - `--branch <target>` - Compare current branch against target branch (e.g., `main`)
  - `--focus <area>` - Focus area: `security`, `performance`, `quality`, `architecture`, or `full` (default: `full`)
  - `--post-pr` - Post review as PR comment if in PR context

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at every decision point.** Code review is subjective -- what matters depends on context, and assumptions about reviewer priorities are frequently wrong. Specifically:

- **Before** reviewing -- confirm the review scope and what the user cares about
- **When** the diff is large -- let the user choose what to focus on first
- **When** categorization is ambiguous -- ask about severity levels
- **When** models disagree -- let the user break the tie on issue severity
- **After** findings -- ask what to do next (fix, re-review, post to PR)

## Workflow

### 1. Parse Arguments

Extract configuration from `$ARGUMENTS`:
- Default: `commits=5`, `focus=full`
- Flags: `--staged`, `--branch`, `--focus`, `--post-pr`

Determine review mode (mutually exclusive):

| Mode | Trigger | Description |
|------|---------|-------------|
| Commits | Default or `commits=N` | Review last N commits |
| Staged | `--staged` flag | Review staged changes only |
| Branch | `--branch <target>` | Compare against target branch |

### 2. Validate Git State

```bash
git rev-parse --is-inside-work-tree 2>/dev/null || { echo "Error: Not a git repository"; exit 1; }
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"
```

### 3. Discover Available Models

Call `mcp__pal__listmodels` to get available models for consensus. Select top 2 models by score, preferring different providers for diversity.

### 4. Gather Git Context

Mode-specific commands:

**Commits mode:**
```bash
git log --oneline -$N --name-only --pretty=format: | sort -u | grep -v '^$'
git diff -U10 HEAD~$N..HEAD
git log --oneline -$N --format='%h %s (%an)'
```

**Staged mode:**
```bash
git diff --cached --name-only
git diff -U10 --cached
```

**Branch comparison:**
```bash
git diff --name-only origin/$TARGET...HEAD
git diff -U10 origin/$TARGET...HEAD
git log --oneline origin/$TARGET..HEAD
```

#### 4a. Confirm Review Scope with User

After gathering context, present a summary and let the user confirm or adjust.

### 5. Categorize Changed Files

Map files to review focus areas:

| Pattern | Category | Review Focus |
|---------|----------|--------------|
| `*.py` in `scripts/` | Python Scripts | Security, KISS, error handling |
| `*.py` in `recipes/` | Rube MCP Recipes | Recipe patterns, Let It Crash, self-contained |
| `*.rs` in `gui/src-tauri/src/` | Rust Backend | SOLID, Tauri IPC, error propagation |
| `*.js` in `gui/src/` | Frontend JS | XSS, DOM sanitization, event handling |
| `*.yml`, `*.yaml` | Config/CI | Security, correctness |
| `tests/**` | Test Code | Coverage, edge cases |
| `*.md` | Documentation | Accuracy |

### 6. Handle Large Diffs

If diff exceeds ~1000 lines, ask how to handle (chunk by category, focus on high-risk, etc.).

### 7. Run PAL MCP Consensus

Use `mcp__pal__consensus` with the models discovered in Step 3.

**Review Focus Areas:**

| Focus | Checks |
|-------|--------|
| `security` | XSS, path traversal, injection, input validation, secrets |
| `performance` | Complexity, unnecessary allocations, polling efficiency |
| `quality` | Let It Crash compliance, KISS, SOLID, naming, recipe patterns |
| `architecture` | Patterns, coupling, separation of concerns, pure functions |
| `full` | All of the above (default) |

**CCP-Specific Review Checks:**
- **Let It Crash**: Any `try/except` without `# LET-IT-CRASH-EXCEPTION` annotation?
- **Recipe patterns**: Are helpers duplicated correctly? Apostrophe escaping in browser recipes?
- **Pure Functions**: Business logic separated from I/O boundaries?
- **Draft interop**: Do Rust and Python draft schemas stay in sync?

#### 7a. Present Model Disagreements to User

If models disagree on severity, present each significant disagreement for user tiebreak.

#### 7b. Validate Critical/High Findings

Present critical/high findings for user confirmation before including in the final report.

### 8. Format Output (GitHub PR Comment Style)

```markdown
## Code Review: Multi-Model Consensus

**Review Mode**: [Commits (last N) | Staged Changes | Branch Comparison vs TARGET]
**Files Reviewed**: N files
**Lines Changed**: +X / -Y

---

### Executive Summary
[2-3 sentence overview]

### Critical Issues
> Must be addressed before merge

- [ ] **[FILE:LINE]** - [Issue description]
  - **Category**: Security/Let It Crash/Recipe Pattern
  - **Severity**: Critical
  - **Recommendation**: [Specific fix]

### High Priority
### Medium Priority
### Low Priority / Suggestions

---

### Positive Observations
- [Good patterns observed]

### Review Summary

| Category | Rating | Notes |
|----------|--------|-------|
| Security | X/5 | |
| Code Quality | X/5 | |
| Let It Crash | X/5 | |
| Recipe Compliance | X/5 | |
| Architecture | X/5 | |

**Overall Assessment**: [APPROVE / REQUEST CHANGES / NEEDS DISCUSSION]

### Model Consensus

| Model | Key Findings |
|-------|--------------|

*Generated by Claude Code Review with PAL MCP Consensus*
```

### 9. Optional: Post to PR

If `--post-pr` flag is set AND in a PR context, post via `gh pr comment`.

### 10. Post-Review Follow-Up

Ask the user what to do next (auto-fix, deep-dive file, post to PR, done).

## Example Usage

```bash
/code-review
/code-review commits=10
/code-review --staged
/code-review --branch main
/code-review commits=3 --focus security
/code-review --branch main --post-pr
```

## Notes

- Requires PAL MCP server configured with at least one model provider
- Models are discovered dynamically via `mcp__pal__listmodels`
- Python files get additional Let It Crash and recipe pattern review per CLAUDE.md
- Rust files get SOLID and Tauri IPC review
- JS files get XSS and DOM sanitization review
