---
description: Assign roles to Agent teams for planning purposes given a user prompt
allowed-tools: AskUserQuestion, Read, Glob, Grep, Edit, Bash, mcp__pal__consensus, mcp__pal__listmodels
argument-hint: <task-description>
---

# Agent Team Planner

Analyze a user prompt, decompose it into workstreams, and interactively assign agent roles to form a coordinated team plan.

## Arguments

- `$ARGUMENTS` - A description of the task, feature, or project to plan for.

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at every decision point.** Do NOT assume user intent -- validate it.

- **Before** narrowing scope -- confirm what's in and out
- **Before** committing to an approach -- present alternatives
- **After** discovering something unexpected -- share findings and get direction
- **Between** phases -- checkpoint progress and confirm next steps
- **When** models disagree -- let the user break the tie

## Workflow

### Phase 1: Analyze the Prompt

Read and understand `$ARGUMENTS`. Identify:

1. **Scope** - What is being asked?
2. **Domains touched** - Which parts of the codebase?

| Domain | Key Paths |
|--------|-----------|
| Python Scripts | `scripts/recipe_client.py`, `scripts/draft_store.py`, `scripts/validate_recipes.py` |
| Recipes | `recipes/*.py` (Rube MCP self-contained scripts) |
| Rust Backend | `gui/src-tauri/src/*.rs` (8 modules) |
| Frontend JS | `gui/src/*.js` (8 files) |
| Tests | `tests/` |
| CI/CD | `.github/workflows/` |
| Documentation | `CLAUDE.md` |

3. **Complexity signals** - Multi-file? Cross-cutting? External dependencies?
4. **Risks** - What could go wrong?

#### 1a. Validate Understanding with User
#### 1b. Clarify Ambiguities

### Phase 2: Propose Workstreams

Decompose the task into **2-5 parallel workstreams**.

| Task Type | Possible Workstreams |
|-----------|---------------------|
| New recipe | Recipe implementation, CLI integration, Skills wrapper, Tests |
| Bug fix | Root cause analysis, Fix implementation, Regression tests |
| Refactor | Architecture design, Migration, Test updates |
| New GUI feature | Rust commands, Frontend JS, Tests, Docs |
| Migration | Schema changes, Code updates, Validation |

#### 2a. Prioritize Workstreams with User
#### 2b. Surface Unexpected Findings

### Phase 3: Multi-Model Consensus on Workstreams

Use PAL MCP consensus to validate the proposed workstreams.

#### 3a. Discover Available Models
#### 3b. Run Consensus Review
#### 3c. Present Consensus Disagreements to User
#### 3d. Incorporate Consensus

### Phase 4: Interactive Role Assignment

Available agent roles:

| Role | Best For | Agent Type |
|------|----------|------------|
| **Architect** | Design decisions, API contracts | `Plan` |
| **Implementer** | Writing production code | `general-purpose` |
| **Explorer** | Codebase research, finding patterns | `Explore` |
| **Test Engineer** | Writing tests, coverage | `general-purpose` |
| **DevOps** | CI/CD, scripts, infrastructure | `general-purpose` |
| **Reviewer** | Code review, quality checks | `general-purpose` |

#### Question 1: Confirm Workstreams
#### Question 2: Execution Strategy (Parallel / Sequential / Hybrid)
#### Question 3: Agent Specialization per Workstream
#### Question 4: Risk Mitigation

### Phase 4.5: Checkpoint

Confirm before generating detailed briefs.

### Phase 5: Generate Team Plan

**Output format:**

```markdown
## Team Plan: <Task Summary>

### Mission
<1-2 sentence goal>

### Team Composition

| # | Workstream | Role | Agent Type | Dependencies | Key Files |
|---|------------|------|------------|--------------|-----------|

### Execution Order
### Agent Briefs (with AGENT_REPORT output contract)
### Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|

### Model Consensus Summary
```

### Phase 6: Offer Execution

Options: Launch supervised, Launch fire-and-forget, Export plan only, Revise plan.

### Phases 7-10: Supervised Execution

Wave planning, execution loop with handoff documents, conflict detection, final reconciliation, and execution summary.

**Reconciliation checks:**
```bash
ruff check scripts/ recipes/ --fix && ruff format scripts/ recipes/
cd gui/src-tauri && cargo clippy -- -D warnings && cargo fmt
pytest -x -q
```

## Constraints

- Maximum 5 workstreams per plan
- Maximum 4 execution waves
- Maximum 1 retry per crashed agent
- All plans must respect CLAUDE.md design principles (Let It Crash, KISS, Pure Functions, SOLID)
- Agent briefs must reference specific files discovered during Phase 1 exploration

## Example Usage

```
/team-plan Add Instagram Reels support to the social promotion recipe
/team-plan Migrate from Composio v1 recipes to v3 tool router API
/team-plan Fix the browser auth expiry issue across all event creation recipes
/team-plan Add rate limiting to the Tauri GUI recipe commands
```

## Notes

- The quality of the plan depends on thorough codebase exploration in Phase 1
- For trivial tasks (single file, single concern), skip team planning and suggest direct implementation
- Requires PAL MCP server configured with at least one model provider for consensus
- If PAL MCP is unavailable, consensus is skipped gracefully
