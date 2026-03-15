---
description: Create a new branch, commit changes, push, create PR, and fix all failed checks (except claude review)
allowed-tools: AskUserQuestion, Bash, Read, Glob, Grep, Edit, Write
argument-hint: <branch-name> [commit message]
---

# PR Workflow Skill

Create a new branch from main, stage all changes, commit, push, create a PR, and iteratively fix all failing checks until they pass.

## Arguments

- `$ARGUMENTS` - Branch name (required) and optional commit message
  - Format: `<branch-name> [commit message in quotes]`
  - Example: `feat/add-auth "Add user authentication"`

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at every decision point.** PRs are visible to the team -- assumptions about commit messages, PR descriptions, and fix strategies should be validated.

- **Before** committing -- confirm commit message and staged files
- **Before** creating the PR -- confirm title and description
- **When** checks fail -- ask how to handle before auto-fixing
- **After** completion -- ask about next steps

## Workflow

### 1. Parse Arguments

Extract branch name and commit message from `$ARGUMENTS`:
- First word is the branch name
- Remaining text (if any) is the commit message

### 2. Verify Clean State & Create Branch

```bash
git fetch origin
git checkout -b <branch-name> origin/main
```

### 3. Stage and Commit Changes

#### 3a. Confirm What Gets Committed

Present changes and ask the user to confirm before staging.

Generate a commit message following conventional commits format if not provided:
- `feat:` for new features
- `fix:` for bug fixes
- `refactor:` for refactoring
- `docs:` for documentation
- `test:` for tests
- `chore:` for maintenance

```bash
git commit -m "$(cat <<'EOF'
<commit message>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### 4. Push to Remote

```bash
git push -u origin <branch-name>
```

### 5. Create Pull Request

#### 5a. Confirm PR Title and Description

```bash
gh pr create --title "<PR title>" --body "$(cat <<'EOF'
## Summary
<bullet points summarizing changes>

## Test plan
- [ ] <testing steps>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### 6. Monitor and Fix Failed Checks

**CRITICAL**: Iterative loop until all checks pass (except claude review).

1. **Get check status**:
   ```bash
   PR_NUMBER=$(gh pr view --json number -q .number)
   gh pr checks $PR_NUMBER --json name,state,conclusion
   ```

2. **Identify failed checks** (exclude "claude" from check names)

3. **For each failed check**, ask the user before fixing

4. **CCP CI checks to watch for:**

   | Check Name | Fix Strategy |
   |------------|-------------|
   | Lint (Ruff) | `ruff check scripts/ recipes/ --fix` |
   | Format (Ruff) | `ruff format scripts/ recipes/` |
   | Recipe Validation | Fix recipe structure per `validate_recipes.py` |
   | Security Scan | Address Bandit findings |
   | Cargo Check (Rust) | `cd gui/src-tauri && cargo clippy --fix && cargo fmt` |
   | Test (Python) | Fix failing tests |
   | Design Principles | Fix Let It Crash / KISS / Pure Functions violations |
   | CI Pass | Meta-check -- fix upstream failures |

5. **After fix**: commit, push, wait for re-run, re-check

6. **Repeat until all non-claude checks pass**

### 7. Report Success

Once all checks pass:
- Display the PR URL
- List all commits made
- Summarize what was fixed

```
AskUserQuestion:
  question: "PR created and all checks passing. What next?"
  header: "Next"
  multiSelect: false
  options:
    - label: "Done"
      description: "PR is ready -- no further action needed"
    - label: "Request review"
      description: "Assign reviewers to the PR"
    - label: "Run code review"
      description: "Run /code-review on the PR changes"
```

## Skipped Checks

The following checks are intentionally skipped and NOT addressed:
- Any check with "claude" in the name (claude review, claude-review, etc.)

## Example Usage

```
/pr feat/add-dark-mode "Add dark mode toggle to settings"
/pr fix/auth-bug
/pr refactor/cleanup-utils "Refactor utility functions for clarity"
```

## Notes

- Always creates branch from `origin/main`
- Uses conventional commit format
- Single remote: `origin` only
- Will make multiple commits if multiple check fixes are needed
- Times out after 10 failed check fix attempts (asks for user guidance)
- Never skips or bypasses checks -- always fixes the underlying issue
