# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**Type:** Django package (Python library)
**Purpose:** Integration layer between Plane.so project management and Lazy-Bird automation engine
**Status:** Phase 3 complete — 107 tests passing (5 skipped), 71% coverage, Docker test env, Plane UI components
**Package name:** `plane-lazy-bird` (PyPI: `plane-lazy-bird-integration`)

Part of Lazy-Bird's v2.0 microservice architecture:
- **lazy-bird** (Core Engine) - FastAPI + PostgreSQL + Celery
- **lazy-bird-ui** (Web UI) - React + TypeScript + Vite
- **plane-lazy-bird-integration** (This Repo) - Django package for Plane
- **yusufkaraaslan/plane** (Fork, branch `feat/lazy-bird-integration`) - React UI components in Plane

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
**DRF:** 3.14+
**Line length:** 100 (Black)
**Type checking:** mypy strict (`disallow_untyped_defs = true`)

## Architecture

The package connects Plane.so to the lazy-bird REST API using Django signals, webhooks, and a DRF REST API.

### Core flow:
1. User moves Plane issue to "Ready" state
2. `post_save` signal fires -> `on_issue_save()` in `signals.py`
3. Checks: automation enabled, state matches, no duplicate active tasks
4. Queues task via async httpx client -> `POST /api/v1/task-runs`
5. Creates `TaskRunMapping` to track the relationship
6. Updates issue state to "In Progress"
7. Lazy-Bird sends webhook on completion -> `webhooks.py` receiver
8. Updates mapping, issue state to "In Review", adds comment with PR link

### Module summary:
- `client.py` — `LazyBirdClient` (async httpx, `X-API-Key` auth) + `verify_webhook_signature()` (HMAC-SHA256)
- `models.py` — `AutomationConfig` (project mapping, state names) + `TaskRunMapping` (issue-to-task, status, PR details)
- `signals.py` — `post_save` handler with duplicate detection, recursive-save guard, async bridging via `sync_to_async`
- `webhooks.py` — HMAC-verified receiver for 5 events (task.started/completed/failed/cancelled, pr.created) + Plane issue state updates + comments
- `serializers.py` — DRF serializers: `AutomationConfigSerializer`, `TaskRunMappingSerializer`, `TriggerTaskSerializer`, `TestConnectionSerializer`
- `permissions.py` — `IsPlaneAuthenticated` permission class (wraps Plane auth, fallback for tests via `LAZY_BIRD_ALLOW_UNAUTHENTICATED`)
- `api.py` — 7 DRF APIView classes for REST API endpoints
- `admin.py` — Django admin for both models
- `urls.py` — Webhook + 7 API routes
- `management/commands/lazy_bird_setup_webhook.py` — Registers webhook subscription in Lazy-Bird

### REST API endpoints (served by `api.py`):
- `GET /lazy-bird/config/<project_id>/` — Get automation config
- `POST /lazy-bird/config/<project_id>/` — Upsert automation config
- `POST /lazy-bird/config/test-connection/` — Test Lazy-Bird API connectivity
- `GET /lazy-bird/issues/<issue_id>/tasks/` — List task runs for an issue
- `POST /lazy-bird/issues/<issue_id>/tasks/trigger/` — Manually trigger a task (requires `project_id`, `prompt`)
- `GET /lazy-bird/issues/<issue_id>/tasks/<task_id>/status/` — Proxy task status from Lazy-Bird
- `GET /lazy-bird/issues/<issue_id>/tasks/<task_id>/logs/` — Proxy task logs from Lazy-Bird
- `POST /lazy-bird/issues/<issue_id>/tasks/<task_id>/cancel/` — Cancel a task

### Lazy-Bird API endpoints consumed (by `client.py`):
- `POST /api/v1/task-runs` — Queue task
- `GET /api/v1/task-runs/{id}` — Get task status
- `POST /api/v1/task-runs/{id}/cancel` — Cancel task
- `POST /api/v1/task-runs/{id}/retry` — Retry failed task
- `GET /api/v1/task-runs/{id}/logs` — Get logs (paginated)
- `GET /api/v1/health` — Health check
- `POST /api/v1/webhooks` — Register webhook subscription

### Plane model dependencies (loaded dynamically):
- `db.Issue` — State changes trigger signals, state updated on completion
- `db.State` — Looked up by name to set issue state
- `db.IssueComment` — Created on task completion/failure

### Key design patterns:
- Plane models loaded dynamically via `apps.get_model("db", "Model")` — gracefully returns None in tests
- `_lazy_bird_updating` flag on issue prevents recursive signal loops
- `sync_to_async` wraps ORM calls inside async coroutines
- `async_to_sync` (from asgiref) bridges async client methods into sync DRF views
- `IsPlaneAuthenticated` permission checks `request.user.is_authenticated`; bypassed in tests via `LAZY_BIRD_ALLOW_UNAUTHENTICATED = True`
- Proxy endpoints (status, logs, cancel) call Lazy-Bird API and opportunistically sync local TaskRunMapping status

### Environment variables:
```bash
LAZY_BIRD_API_URL=http://localhost:8000
LAZY_BIRD_API_KEY=lb_live_your_api_key_here
LAZY_BIRD_WEBHOOK_SECRET=whsec_your_webhook_secret
```

### Docker test environment (`docker/`):
- `docker-compose.test.yml` — 5 services: plane-db, plane-redis, plane-api, lazy-bird-mock, test-runner
- `Dockerfile.plane-api` — Extends `makeplane/plane-backend` with our package
- `Dockerfile.lazy-bird-mock` — FastAPI mock of Lazy-Bird API
- `Dockerfile.test-runner` — Runs pytest integration tests
- `lazy_bird_mock.py` — Mock server implementing all 7 Lazy-Bird API endpoints
- `plane_settings_patch.py` — Build-time settings patcher
- `setup-test-env.sh` — Local setup script (clone Plane, patch, install, migrate, seed)
- `entrypoint-plane-api.sh` — Plane API startup with migrations

### Integration tests (`tests/integration/`):
- `test_signal_flow.py` — 7 tests: full signal flow, prompt construction, duplicate detection, requeue, API failure
- `test_webhook_flow.py` — 9 tests: all webhook events, lifecycle, signature validation, idempotency
- `test_api_auth.py` — 24 tests: all 8 endpoints with auth/unauth, CRUD, proxy, cancel

### Plane fork components (`yusufkaraaslan/plane:feat/lazy-bird-integration`):
- `apps/web/ce/components/lazy-bird/` — types.ts, api.ts, index.ts, task-panel.tsx, settings.tsx, task-logs-modal.tsx, trigger-task-modal.tsx, task-status-badge.tsx
- `apps/web/ce/components/issues/issue-detail-widgets/collapsibles.tsx` — Wires LazyBirdTaskPanel into issue sidebar
- `apps/web/app/.../lazy-bird/page.tsx` + `header.tsx` — Settings route
- `apps/api/plane/settings/common.py` — INSTALLED_APPS + env vars
- `apps/api/plane/urls.py` — URL routing
- `apps/api/requirements/base.txt` — Package dependency

## Planning Documents

- `IMPLEMENTATION.md` - Phase 1 implementation plan (complete)
- `DEEP_INTEGRATION_PLAN.md` - Phase 3 plans for React UI components in Plane (complete)
- `DEV_WORKFLOW.md` - Git branching strategy and multi-instance coordination
