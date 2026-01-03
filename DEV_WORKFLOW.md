# Development Workflow - plane-lazy-bird-integration

**Last Updated:** 2026-01-03
**Status:** Ready for development

---

## Repository Status

✅ **Clean and Ready**
- No old branches to clean up
- Main branch is up-to-date with remote
- Planning documentation committed (CLAUDE.md, DEEP_INTEGRATION_PLAN.md)

---

## Development Branch Workflow

### For the Development Instance

When working on implementation in another instance:

```bash
# 1. Make sure you're starting from latest main
git checkout main
git pull origin main

# 2. Create/checkout development branch
git checkout -b development

# 3. Do your work (implement models, signals, views, etc.)
# ... make changes ...

# 4. Commit your changes
git add .
git commit -m "feat: implement Django models and signals"

# 5. Rebase from main before pushing (keeps history clean)
git fetch origin
git rebase origin/main

# 6. Push development branch
git push origin development

# 7. Create PR when ready
gh pr create --base main --head development
```

### Rebase Development from Main (when main updates)

If main branch gets updated while you're working:

```bash
# On development branch
git fetch origin
git rebase origin/main

# If conflicts, resolve them, then:
git add .
git rebase --continue

# Force push (rebase rewrites history)
git push origin development --force
```

---

## Current Repository State

**Main Branch Commits:**
```
403441f - docs: Add development documentation and deep integration plan
3b30311 - docs: Update README for v2.0 standalone repository architecture
60a72d7 - Initial setup: Python package structure and documentation
```

**Remote Branches:**
- `main` - Base branch (protected, requires PR)

**Local Branches:**
- `main` - Currently checked out, up-to-date with remote

**No old branches to clean up** - Repository is clean ✅

---

## Implementation Checklist (from IMPLEMENTATION.md)

### Day 1: Package Setup & API Client
- [ ] Django package structure
- [ ] `LazyBirdClient` class with httpx
- [ ] API methods: queue_task, get_status, cancel_task, get_logs
- [ ] Error handling and retries
- [ ] Client tests

### Day 2: Django Integration
- [ ] `AutomationConfig` model
- [ ] `TaskRunMapping` model
- [ ] Database migrations
- [ ] Django signals (pre_save, post_save)
- [ ] Auto-queue logic for "Ready" state
- [ ] Signal tests

### Day 3: Webhooks & Polish
- [ ] Webhook endpoint view
- [ ] HMAC signature verification
- [ ] Event handlers (started, completed, failed, pr_created)
- [ ] Issue state updates in Plane
- [ ] PR linking
- [ ] Webhook tests
- [ ] Integration tests
- [ ] Package for PyPI

---

## Code Quality Commands

Before committing:

```bash
# Format code
black plane_lazy_bird/ tests/

# Lint
flake8 plane_lazy_bird/ tests/

# Type check
mypy plane_lazy_bird/

# Run tests
pytest --cov=plane_lazy_bird --cov-report=html

# All checks at once
black plane_lazy_bird/ tests/ && \
flake8 plane_lazy_bird/ tests/ && \
mypy plane_lazy_bird/ && \
pytest --cov=plane_lazy_bird --cov-report=html
```

---

## Coordination Between Instances

### This Instance (Main Repository Management)
- Maintains main branch
- Handles releases and tags
- Manages documentation updates
- Reviews and merges PRs

### Development Instance (Implementation)
- Works on `development` branch
- Implements features from IMPLEMENTATION.md
- Runs tests and quality checks
- Creates PRs when features are complete

### Synchronization Points

**Before starting work in dev instance:**
```bash
git pull origin main  # Get latest from this instance
```

**Before pushing from dev instance:**
```bash
git fetch origin
git rebase origin/main  # Incorporate any main updates
```

**After merging PR:**
```bash
# In dev instance
git checkout main
git pull origin main
git branch -D development  # Delete old dev branch
git checkout -b development  # Start fresh for next feature
```

---

## Branch Protection (Recommended)

Consider enabling on GitHub:
- Require PR reviews for main branch
- Require status checks to pass (tests, linting)
- Require branches to be up to date before merging

---

## Quick Reference

**Check repository status:**
```bash
git status
git log --oneline -5
git branch -a
```

**Sync with remote:**
```bash
git fetch origin
git pull origin main
```

**Clean up merged branches:**
```bash
git branch --merged main | grep -v "main" | xargs git branch -d
```

---

**Questions?** Check CLAUDE.md or IMPLEMENTATION.md for detailed guidance.
