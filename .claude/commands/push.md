---
description: Push to Remote
allowed-tools: AskUserQuestion, Bash, Read, Glob, Grep
---

# Push to Remote

Push changes to the `origin` remote.

## Arguments
- `$ARGUMENTS` - Optional: branch name (defaults to current branch)

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at decision points.** Pushing to remotes is a visible, hard-to-reverse action. Always confirm before pushing.

## Instructions

1. **Determine the branch to push:**
   - If `$ARGUMENTS` is provided, use that as the branch name
   - Otherwise, get the current branch with `git rev-parse --abbrev-ref HEAD`

2. **Check for uncommitted changes:**
   - Run `git status --porcelain`
   - If there are uncommitted changes, ask:

   ```
   AskUserQuestion:
     question: "You have uncommitted changes. What should I do?"
     header: "Uncommitted"
     multiSelect: false
     options:
       - label: "Commit first"
         description: "Stage and commit changes before pushing"
       - label: "Push existing commits only"
         description: "Push what's already committed -- leave working tree as-is"
       - label: "Abort"
         description: "Don't push -- I need to review my changes first"
   ```

3. **Confirm push:**

   ```
   AskUserQuestion:
     question: "Ready to push branch '<branch>' to origin. Proceed?"
     header: "Push"
     multiSelect: false
     options:
       - label: "Push"
         description: "Push <branch> to origin"
       - label: "Abort"
         description: "Don't push"
   ```

4. **Push to origin:**
   ```bash
   git push origin <branch>
   ```
   Report success or failure.

5. **Summary:**
   - Report what was pushed
   - Show the remote URL for reference

## Example Usage

```
/push           # Push current branch to origin
/push main      # Push main branch to origin
/push feat/new  # Push specific branch
```

## Notes

- Single remote: `origin` only
- Never force pushes unless explicitly requested by the user
- Always confirms before pushing
