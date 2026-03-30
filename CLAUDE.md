# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**Type:** Django package (Python library)
**Purpose:** Integration layer between Plane.so project management and Lazy-Bird automation engine
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

# Run tests (coverage auto-configured in pyproject.toml)
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

# Docker integration tests (against real Plane instance + mock Lazy-Bird)
docker compose -f docker/docker-compose.test.yml up --build --abort-on-container-exit test-runner
```

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
- `models.py` — `AutomationConfig` (project mapping, state names, optional per-project API URL/key overrides) + `TaskRunMapping` (issue-to-task, status, PR details)
- `signals.py` — `post_save` handler with duplicate detection, recursive-save guard, async bridging via `sync_to_async`
- `webhooks.py` — HMAC-verified receiver for 5 events (task.started/completed/failed/cancelled, pr.created) + Plane issue state updates + comments
- `serializers.py` — DRF serializers: `AutomationConfigSerializer`, `TaskRunMappingSerializer`, `TriggerTaskSerializer`, `TestConnectionSerializer`
- `permissions.py` — `IsPlaneAuthenticated` permission class (wraps Plane auth, fallback for tests via `LAZY_BIRD_ALLOW_UNAUTHENTICATED`)
- `api.py` — 7 DRF APIView classes for REST API endpoints
- `urls.py` — Webhook + 7 API routes under `/lazy-bird/`
- `management/commands/lazy_bird_setup_webhook.py` — Registers webhook subscription in Lazy-Bird

### Key design patterns:
- Plane models loaded dynamically via `apps.get_model("db", "Model")` — gracefully returns None in tests
- `_lazy_bird_updating` flag on issue prevents recursive signal loops
- `sync_to_async` wraps ORM calls inside async coroutines; `async_to_sync` (asgiref) bridges async client methods into sync DRF views
- `IsPlaneAuthenticated` permission checks `request.user.is_authenticated`; bypassed in tests via `LAZY_BIRD_ALLOW_UNAUTHENTICATED = True`
- Proxy endpoints (status, logs, cancel) call Lazy-Bird API and opportunistically sync local TaskRunMapping status
- `AutomationConfig.api_url` and `api_key` fields override the global `LAZY_BIRD_API_URL`/`LAZY_BIRD_API_KEY` env vars on a per-project basis (empty string = use global)

### Environment variables:
```bash
LAZY_BIRD_API_URL=http://localhost:8000
LAZY_BIRD_API_KEY=lb_live_your_api_key_here
LAZY_BIRD_WEBHOOK_SECRET=whsec_your_webhook_secret
```

### Test structure:
- `tests/test_*.py` — Unit tests (models, client, signals, webhooks, API)
- `tests/integration/` — Integration tests requiring Docker: signal flow, webhook flow, API auth (run via `docker-compose.test.yml`)
- `docker/` — Docker test environment: Plane API, mock Lazy-Bird server (`lazy_bird_mock.py`), test runner

## Planning Documents

- `IMPLEMENTATION.md` - Phase 1 implementation plan (complete)
- `DEEP_INTEGRATION_PLAN.md` - Phase 3 plans for React UI components in Plane (complete)
- `DEV_WORKFLOW.md` - Git branching strategy and multi-instance coordination
