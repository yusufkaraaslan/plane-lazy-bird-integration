# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**Type:** Django package (Python library)
**Purpose:** Integration layer between Plane.so project management and Lazy-Bird automation engine
**Status:** Core implementation complete — 41 tests passing, ready for integration testing with Docker Plane
**Package name:** `plane-lazy-bird` (PyPI: `plane-lazy-bird-integration`)

Part of Lazy-Bird's v2.0 microservice architecture:
- **lazy-bird** (Core Engine) - FastAPI + PostgreSQL + Celery
- **lazy-bird-ui** (Web UI) - React + TypeScript + Vite
- **plane-lazy-bird-integration** (This Repo) - Django package for Plane

## Development Commands

```bash
# Install dependencies
poetry install

# Run tests
pytest

# Run specific test file
pytest tests/test_client.py

# Run tests with verbose output
pytest -v -s

# Format code
black plane_lazy_bird/ tests/

# Lint
flake8 plane_lazy_bird/ tests/

# Type check
mypy plane_lazy_bird/

# All quality checks
black plane_lazy_bird/ tests/ && flake8 plane_lazy_bird/ tests/ && mypy plane_lazy_bird/ && pytest
```

Coverage is auto-configured in pyproject.toml (`--cov=plane_lazy_bird --cov-report=html --cov-report=term-missing`), so bare `pytest` includes coverage.

## Configuration

**Package manager:** Poetry
**Test settings:** `tests/settings.py` (DJANGO_SETTINGS_MODULE configured in pyproject.toml)
**Python:** 3.10+ (3.10, 3.11, 3.12)
**Django:** 4.2+
**Line length:** 100 (Black)
**Type checking:** mypy strict (`disallow_untyped_defs = true`)

## Architecture

The package connects Plane.so to the lazy-bird REST API using Django signals and webhooks.

### Core flow:
1. User moves Plane issue to "Ready" state
2. `post_save` signal fires → `on_issue_save()` in `signals.py`
3. Checks: automation enabled, state matches, no duplicate active tasks
4. Queues task via async httpx client → `POST /api/v1/task-runs`
5. Creates `TaskRunMapping` to track the relationship
6. Updates issue state to "In Progress"
7. Lazy-Bird sends webhook on completion → `webhooks.py` receiver
8. Updates mapping, issue state to "In Review", adds comment with PR link

### Module summary:
- `client.py` — `LazyBirdClient` (async httpx, `X-API-Key` auth) + `verify_webhook_signature()` (HMAC-SHA256)
- `models.py` — `AutomationConfig` (project mapping, state names) + `TaskRunMapping` (issue-to-task, status, PR details)
- `signals.py` — `post_save` handler with duplicate detection, recursive-save guard, async bridging via `sync_to_async`
- `webhooks.py` — HMAC-verified receiver for 5 events (task.started/completed/failed/cancelled, pr.created) + Plane issue state updates + comments
- `admin.py` — Django admin for both models
- `urls.py` — `/lazy-bird/` webhook endpoint
- `management/commands/lazy_bird_setup_webhook.py` — Registers webhook subscription in Lazy-Bird

### Lazy-Bird API endpoints used:
- `POST /api/v1/task-runs` — Queue task (requires `project_id`, `work_item_id`, `prompt`)
- `GET /api/v1/task-runs/{id}` — Get task status
- `POST /api/v1/task-runs/{id}/cancel` — Cancel task
- `POST /api/v1/task-runs/{id}/retry` — Retry failed task
- `GET /api/v1/task-runs/{id}/logs` — Get logs (paginated)
- `POST /api/v1/webhooks` — Register webhook subscription

### Plane model dependencies (loaded dynamically):
- `db.Issue` — State changes trigger signals, state updated on completion
- `db.State` — Looked up by name to set issue state
- `db.IssueComment` — Created on task completion/failure

### Key design patterns:
- Plane models loaded dynamically via `apps.get_model("db", "Model")` — gracefully returns None in tests
- `_lazy_bird_updating` flag on issue prevents recursive signal loops
- `sync_to_async` wraps ORM calls inside `_queue_task_for_issue` coroutine
- `_run_async()` bridges sync Django signals to async client (detects ASGI vs WSGI)

### Environment variables:
```bash
LAZY_BIRD_API_URL=http://localhost:8000
LAZY_BIRD_API_KEY=lb_live_your_api_key_here
LAZY_BIRD_WEBHOOK_SECRET=whsec_your_webhook_secret
```

## Planning Documents

- `IMPLEMENTATION.md` - 3-day implementation plan with task checklist
- `DEEP_INTEGRATION_PLAN.md` - Phase 2/3 plans for REST API endpoints and React UI components in Plane
- `DEV_WORKFLOW.md` - Git branching strategy and multi-instance coordination
