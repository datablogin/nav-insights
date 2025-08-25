# Git Worktrees for Multi-Agent Development

This repository uses git worktrees to allow multiple agents to work simultaneously on different branches without conflicts.

## Current Structure

```
/Users/robertwelborn/PycharmProjects/
├── nav_insights/                    # Main worktree (currently feat/paid-search-parsers)
├── nav_insights-main/              # Worktree for main branch
├── nav_insights-issue-3/           # Worktree for Issue #3 (Core IR base types)  
├── nav_insights-issue-5/           # Worktree for Issue #5 (Safe DSL registry)
├── nav_insights-immediate-steps/   # Worktree for immediate steps branch
└── nav_insights-[feature-name]/    # Additional worktrees as needed
```

## Creating New Worktrees

### For existing branches:
```bash
# Create worktree for existing branch
git worktree add ../nav_insights-main main
git worktree add ../nav_insights-issue-3 feat/issue-3-core-ir-base-types
git worktree add ../nav_insights-issue-5 feature/issue-5-safe-dsl-registry
```

### For new branches:
```bash
# Create worktree with new branch
git worktree add -b feat/new-feature ../nav_insights-new-feature
```

## Agent Workflow

### 1. Assign Worktree to Agent
Each agent should work in their designated worktree:
- **Agent working on Issue #3**: Use `/nav_insights-issue-3/`
- **Agent working on Issue #5**: Use `/nav_insights-issue-5/`
- **Agent working on main**: Use `/nav_insights-main/`

### 2. Switching Between Worktrees
```bash
# Agent switches to their assigned worktree
cd /Users/robertwelborn/PycharmProjects/nav_insights-issue-3
```

### 3. Normal Git Operations
Each worktree works independently:
```bash
# In each worktree, normal git commands work
git status
git add .
git commit -m "message"
git push origin branch-name
```

## Managing Worktrees

### List all worktrees:
```bash
git worktree list
```

### Remove worktree when done:
```bash
git worktree remove ../nav_insights-issue-3
```

### Prune deleted worktrees:
```bash
git worktree prune
```

## Benefits for Multi-Agent Development

1. **Isolation**: Each agent works in separate directories
2. **No branch switching**: No need to switch branches or stash changes
3. **Parallel work**: Multiple agents can work simultaneously
4. **Shared repository**: All worktrees share the same .git database
5. **Fast operations**: Creating worktrees is much faster than cloning

## Current Active Branches

- `main` - Production ready code
- `feat/issue-3-core-ir-base-types` - Core IR base types implementation  
- `feature/issue-5-safe-dsl-registry` - Safe DSL expression evaluator
- `feat/immediate-steps` - Immediate development tasks
- `feat/paid-search-parsers` - Paid search parsing functionality

## Notes

- The main `.git` directory is shared across all worktrees
- Configuration, hooks, and refs are shared
- Working directory and index are separate per worktree
- Always use absolute paths when creating worktrees to avoid issues