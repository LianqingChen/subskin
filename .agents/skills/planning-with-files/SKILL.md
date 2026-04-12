---
name: planning-with-files
description: Implements Manus-style file-based planning to organize and track progress on complex tasks. Creates task_plan.md, findings.md, and progress.md. Use when asked to plan out, break down, or organize a multi-step project, research task, or any work requiring >5 tool calls. Supports automatic session recovery after /clear.
compatibility: opencode
---

# Planning with Files

Work like Manus: Use persistent markdown files as your "working memory on disk."

## Overview

The filesystem is your database. Planning files are your session memory. They survive context window limitations, power failures, and `/clear` commands.

## When to Use

**Use for:**
- Multi-step tasks (3+ steps)
- Research tasks
- Building/creating projects
- Tasks spanning many tool calls
- Anything requiring organization
- Projects where you might get interrupted

**Skip for:**
- Simple questions
- Single-file edits
- Quick lookups
- One-step operations

## The Core Pattern

```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

## Creating Planning Files

Before ANY complex task:

1. **Create `task_plan.md`** — Phase tracking and progress
2. **Create `findings.md`** — Research discoveries  
3. **Create `progress.md`** — Session log and decisions

## File Templates

### task_plan.md

```markdown
# Task Plan: [Project Name]

## Goal
[Single sentence describing what we're building]

## Phases

### Phase 1: [Name]
- **Status:** not_started / in_progress / complete
- **Goal:** [What this phase accomplishes]
- **Files to modify:**
  - [ ] file1.py
  - [ ] file2.py
- **Success criteria:**
  - [ ] Criterion 1
  - [ ] Criterion 2

### Phase 2: [Name]
[...]

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2024-01-15 | Use X instead of Y | Better performance |
```

### findings.md

```markdown
# Research Findings

## [Topic 1]
### Summary
[Key finding in 2-3 sentences]

### Details
- Point 1
- Point 2
- Code example:
  ```python
  example_code()
  ```

### Sources
- [Link 1](url)
- [Link 2](url)

## [Topic 2]
[...]
```

### progress.md

```markdown
# Progress Log

## Session: [YYYY-MM-DD]

### Phase: [Current Phase]
- **Started:** HH:MM
- **Status:** in_progress / complete / blocked

### Actions Taken
- [ ] Action 1 (completed)
- [ ] Action 2 (in progress)
- [ ] Action 3 (pending)

### Files Created/Modified
- `path/to/file.py` - Description of changes

### Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Error message | 1 | How it was fixed |

### Decisions Made
1. Decision 1 - Rationale
2. Decision 2 - Rationale

### Next Steps
- [ ] Next action 1
- [ ] Next action 2
```

## Critical Rules

### 1. Create Plan First
Never start a complex task without `task_plan.md`. Non-negotiable.

### 2. The 2-Action Rule
> "After every 2 view/browser/search operations, IMMEDIATELY save key findings to text files."

This prevents visual/multimodal information from being lost.

### 3. Read Before Decide
Before major decisions, read the plan file. This keeps goals in your attention window.

### 4. Update After Act
After completing any phase:
- Mark phase status: `in_progress` → `complete`
- Log any errors encountered
- Note files created/modified

### 5. Log ALL Errors
Every error goes in the plan file. This builds knowledge and prevents repetition.

### 6. Never Repeat Failures
```
if action_failed:
    next_action != same_action
```
Track what you tried. Mutate the approach.

### 7. Continue After Completion
When all phases are done but the user requests additional work:
- Add new phases to `task_plan.md` (e.g., Phase 6, Phase 7)
- Log a new session entry in `progress.md`
- Continue the planning workflow as normal

## Session Recovery

After `/clear` or session interruption:

1. **Read all planning files** - Recover context
2. **Check git status** - See what changed
3. **Review progress.md** - Understand what was done
4. **Continue from last phase** - Pick up where left off

## The 5-Question Reboot Test

If you can answer these, your context management is solid:

| Question | Answer Source |
|----------|---------------|
| Where am I? | Current phase in task_plan.md |
| Where am I going? | Remaining phases |
| What's the goal? | Goal statement in plan |
| What have I learned? | findings.md |
| What have I done? | progress.md |

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Use TodoWrite for persistence | Create task_plan.md file |
| State goals once and forget | Re-read plan before decisions |
| Hide errors and retry silently | Log errors to plan file |
| Stuff everything in context | Store large content in files |
| Start executing immediately | Create plan file FIRST |
| Repeat failed actions | Track attempts, mutate approach |
| Create files in skill directory | Create files in your project |
