# Agent Worktree Assignments

## Quick Reference for Multi-Agent Development

Each agent should work in their designated worktree directory to avoid conflicts:

### Current Worktree Assignments

| Agent Role | Worktree Path | Branch | Purpose |
|------------|---------------|---------|---------|
| **Main Agent** | `/nav_insights-main/` | `main` | Production releases, merges |
| **Immediate Steps Agent** | `/nav_insights-immediate-steps/` | `feat/immediate-steps` | Quick tasks |
| **Parser Agent** | `/nav_insights/` | `feat/paid-search-parsers` | Parsing functionality |
| **Available** | - | - | Ready for next issue assignment |
| **DSL Hardening Agent** | `/nav_insights-dsl-hardening/` | `feat/dsl-hardening` | Core DSL hardening |

### Agent Commands

When starting work, each agent should:

```bash
# Navigate to assigned worktree
cd /Users/robertwelborn/PycharmProjects/[worktree-name]

# Verify correct branch
git branch  # Should show * on your assigned branch

# Pull latest changes
git pull origin [branch-name]

# Work normally
git add .
git commit -m "message"  
git push origin [branch-name]
```

### Current Status

- ✅ **Issue #3**: COMPLETED - Merged/closed (worktree cleaned up)
- ✅ **Issue #5**: COMPLETED - Merged/closed (worktree cleaned up)  
- ✅ **Immediate Steps**: Latest commit `23463ff` - Ruff formatting applied
- ✅ **Main**: Latest commit `1ad1bfb` - Base repository state
- 🔄 **Parsers**: Latest commit `4e7ae0a` - Current work in main directory; PR #52 open
<<<<<<< HEAD
- 🧩 **DSL Hardening**: Tracking Issue #54 — branch `feat/dsl-hardening`
=======
>>>>>>> origin/main

### When to Create New Worktrees

```bash
# For new feature branches
git worktree add -b feat/new-feature ../nav_insights-new-feature

# For existing remote branches  
git worktree add ../nav_insights-branch-name origin/branch-name
```

### Cleanup When Done

```bash
# Remove worktree when feature is complete
git worktree remove ../nav_insights-issue-3
git worktree prune  # Clean up references
```

## Benefits

✅ **No Conflicts**: Each agent works in isolation  
✅ **No Branch Switching**: Stay on your assigned branch  
✅ **Parallel Development**: Multiple agents work simultaneously  
✅ **Shared Git Database**: All worktrees share history and refs  
✅ **Fast Setup**: Worktrees are much faster than full clones