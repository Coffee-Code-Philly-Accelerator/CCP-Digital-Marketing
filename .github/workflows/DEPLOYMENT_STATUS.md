# CCP Digital Marketing - Autonomous AI Workflow Deployment Status

## Overview

CCP Digital Marketing is a desktop application (Tauri v2) with Python CLI scripts. There is no web deployment -- the app runs locally. AI workflows automate code review, issue triage, and code quality scanning via GitHub Actions.

## Workflow Status

### Active Workflows

| Workflow | File | Trigger | Status | Purpose |
|----------|------|---------|--------|---------|
| CI | `ci.yml` | Push/PR to main | Active | Lint, format, test, security scan, clippy, design principles |
| Claude Code Review | `claude.yml` | PR (disabled) / @claude comment | Partial | Bedrock primary + Anthropic fallback code review |
| AI Issue Triage | `ai-issue-triage.yml` | Issue opened | Active | Auto-label issues by type, component, priority |
| Issue to PR | `issue-to-pr.yml` | Issue labeled `claude-fix` | Active | Autonomous fix implementation with guardrails |
| Nightly Code Review | `nightly-code-review.yml` | Cron (4 AM UTC weekdays) | Active | Scan recent commits for code quality issues |
| Autonomous Code Scanner | `autonomous-code-scanner.yml` | Cron (2 AM UTC daily) | Active | Deep security and quality scanning |
| Nightly Docs Update | `nightly-docs-update.yml` | Cron | Active | Keep documentation in sync with code |

### Autonomous AI Workflow Details

#### Issue to PR (`issue-to-pr.yml`)

Converts GitHub issues into draft PRs with automated fixes.

| Feature | Implementation |
|---------|---------------|
| Trigger | Issue labeled `claude-fix` or manual dispatch |
| AI Provider | Bedrock primary, Anthropic fallback |
| Allowed tools | `ruff`, `cargo clippy`, `validate_recipes.py`, `py_compile`, `git`, `gh` |
| Protected paths | Read from `.github/config/protected-paths.json` |
| Diff size gate | 1000 lines max |
| Secret scanning | Regex patterns for API keys, tokens, private keys |
| Syntax validation | Python (py_compile + ruff) and Rust (cargo clippy) |
| PR labels | `ai-generated`, `needs-human-review`, `issue-fix` |
| PR type | Draft (requires human review) |

#### Nightly Code Review (`nightly-code-review.yml`)

Scans recent commits for code quality issues and creates fix PRs.

| Feature | Implementation |
|---------|---------------|
| Trigger | Cron 4 AM UTC weekdays, or manual dispatch |
| AI Provider | Bedrock primary, Anthropic fallback |
| File filter | `\.py\|\.rs\|\.js\|\.html` only |
| Allowed tools | `ruff`, `cargo clippy`, `validate_recipes.py`, `py_compile`, `git` |
| Protected paths | Read from `.github/config/protected-paths.json` |
| Diff size gate | 500 lines max |
| Deduplication | Checks for existing nightly PR from same day |
| PR labels | `ai-generated`, `needs-human-review`, `nightly-review` |
| PR type | Draft (requires human review) |

### Guardrails (All Autonomous Workflows)

| Guardrail | Description |
|-----------|-------------|
| Protected-path reversion | Changes to workflow files, .env, CLAUDE.md, Cargo.toml, tauri.conf.json are automatically reverted |
| Secret scanning | Diffs scanned for API keys, tokens, private keys before PR creation |
| Diff size gates | Issue-to-PR: 1000 lines, Nightly: 500 lines |
| Syntax validation | Python (py_compile + ruff), Rust (cargo clippy), Recipes (validate_recipes.py) |
| Draft PR only | All AI-generated PRs are drafts requiring human review |
| Deduplication | Nightly review checks for existing PR from same day |
| Concurrency control | One workflow run per issue/day at a time |

### Review Prompts

| Prompt | File | Purpose |
|--------|------|---------|
| Issue to PR | `.github/prompts/issue-to-pr.md` | Guides Claude through reading issue, exploring codebase, implementing fix |
| Nightly Code Review | `.github/prompts/nightly-code-review.md` | Guides Claude through reviewing recent commits for quality issues |
| Nightly Docs Update | `.github/prompts/nightly-docs-update.md` | Guides Claude through updating documentation to match code |

## Secrets Required

| Secret | Required By | Purpose |
|--------|-------------|---------|
| `ANTHROPIC_API_KEY` | All Claude workflows | Anthropic API (fallback provider) |
| `AWS_BEARER_TOKEN_BEDROCK` | All Claude workflows | AWS Bedrock (primary provider) |
| `AWS_REGION` | All Claude workflows | AWS region (default: us-east-1) |
| `PAT_TOKEN` | issue-to-pr, nightly-code-review, autonomous-scanner | Branch creation and PR submission |
| `GEMINI_API_KEY` | claude.yml (PAL MCP) | Multi-model consensus reviews |
| `OPENAI_API_KEY` | claude.yml (PAL MCP) | Multi-model consensus reviews |

## Architecture Notes

- **No web deployment**: CCP is a Tauri desktop app. CI/CD validates code quality but does not deploy to any server.
- **Bedrock primary + Anthropic fallback**: All Claude workflows try AWS Bedrock first, falling back to direct Anthropic API.
- **Protected paths config**: Centralized in `.github/config/protected-paths.json`, read by all autonomous workflows.
- **File type scope**: Nightly review only touches `.py`, `.rs`, `.js`, `.html` files.
- **Recipe isolation**: Recipes in `recipes/` are self-contained for the Rube MCP runtime. They have intentionally duplicated helpers.

## Cost Controls

| Control | Value |
|---------|-------|
| Issue-to-PR max turns | 40 |
| Nightly review max turns | 50 |
| Auto-review max turns | 25 |
| Interactive @claude max turns | 10 |
| Bot loop prevention | Sender type check on all comment triggers |
| Concurrency limits | One run per issue/day |

---

**Last updated**: 2026-03-15
**Project**: CCP Digital Marketing -- event creation + social promotion automation
