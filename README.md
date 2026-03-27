# Plane Lazy-Bird Integration

**Status:** v0.2.0 Beta — Phase 3 complete (Docker, integration tests, Plane UI)
**Repository:** [plane-lazy-bird-integration](https://github.com/yusufkaraaslan/plane-lazy-bird-integration)
**Plane Fork:** [yusufkaraaslan/plane](https://github.com/yusufkaraaslan/plane/tree/feat/lazy-bird-integration)
**Core Engine:** [lazy-bird](https://github.com/yusufkaraaslan/lazy-bird)

Django package integrating Lazy-Bird automation with Plane.so project management.

## Architecture

Part of Lazy-Bird's v2.0 microservice architecture:

- **lazy-bird** (Core Engine) — FastAPI + PostgreSQL + Celery
- **lazy-bird-ui** (Web UI) — React + TypeScript + Vite
- **plane-lazy-bird-integration** (This Repo) — Django package for Plane
- **yusufkaraaslan/plane** (Plane Fork) — React UI components in Plane

## Features

- **Automatic Task Queuing** — Issues moving to "Ready" state trigger Lazy-Bird tasks
- **Webhook Integration** — Receive task.started/completed/failed/cancelled and pr.created events
- **Issue Updates** — Auto-update issue state and add comments with PR links
- **REST API** — 8 DRF endpoints for config, task management, status proxy, and log viewing
- **Plane UI Components** — Task panel, settings page, log viewer, trigger modal, status badge
- **Docker Test Environment** — docker-compose.test.yml with Plane, mock Lazy-Bird, and test runner
- **107 tests** (71% coverage) — Unit tests + integration tests for signals, webhooks, and API

## Installation

```bash
pip install plane-lazy-bird-integration
```

## Quick Setup

### 1. Add to INSTALLED_APPS

```python
# plane/settings/common.py
INSTALLED_APPS = [
    ...
    'plane_lazy_bird',
]
```

### 2. Configure Environment

```bash
LAZY_BIRD_API_URL=http://localhost:8000
LAZY_BIRD_API_KEY=lb_live_your_api_key_here
LAZY_BIRD_WEBHOOK_SECRET=whsec_your_webhook_secret
```

### 3. Add URL Routes

```python
# plane/urls.py
urlpatterns = [
    ...
    path('api/integrations/', include('plane_lazy_bird.urls')),
]
```

### 4. Run Migrations

```bash
python manage.py migrate plane_lazy_bird
```

### 5. Register Webhook

```bash
python manage.py lazy_bird_setup_webhook
```

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/lazy-bird/config/{project_id}/` | Get automation config |
| POST | `/lazy-bird/config/{project_id}/` | Create/update config |
| POST | `/lazy-bird/config/test-connection/` | Test Lazy-Bird connectivity |
| GET | `/lazy-bird/issues/{issue_id}/tasks/` | List task runs for issue |
| POST | `/lazy-bird/issues/{issue_id}/tasks/trigger/` | Manually trigger a task |
| GET | `/lazy-bird/issues/{issue_id}/tasks/{task_id}/status/` | Get task status |
| GET | `/lazy-bird/issues/{issue_id}/tasks/{task_id}/logs/` | Get task logs |
| POST | `/lazy-bird/issues/{issue_id}/tasks/{task_id}/cancel/` | Cancel a task |

## Plane UI Components (Fork)

The [Plane fork](https://github.com/yusufkaraaslan/plane/tree/feat/lazy-bird-integration) adds React components at `apps/web/ce/components/lazy-bird/`:

| Component | Description |
|-----------|-------------|
| `LazyBirdTaskPanel` | Issue sidebar widget — status badge, PR link, trigger/cancel/logs buttons |
| `LazyBirdSettings` | Project settings page — enable/disable, project ID, state mapping, test connection |
| `TaskLogsModal` | Paginated log viewer with level filtering |
| `TriggerTaskModal` | Manual task trigger — prompt, task type, complexity |
| `TaskStatusBadge` | Inline badge for issue list views |
| `LazyBirdService` | API service extending Plane's `APIService` pattern |

## Docker Test Environment

Run integration tests against a real Plane instance:

```bash
# Start all services and run tests
docker compose -f docker/docker-compose.test.yml up --build --abort-on-container-exit test-runner
```

Services: `plane-db` (PostgreSQL 15), `plane-redis` (Valkey 7), `plane-api` (Plane + our package), `lazy-bird-mock` (FastAPI), `test-runner` (pytest).

### Local Setup (without Docker)

```bash
./docker/setup-test-env.sh  # Clones Plane, patches settings, installs package, creates test data
```

## Development

```bash
poetry install           # Install dependencies
pytest                   # Run all tests (coverage auto-configured)
pytest -v --tb=short     # Verbose with short tracebacks
black plane_lazy_bird/   # Format
flake8 plane_lazy_bird/  # Lint
mypy plane_lazy_bird/    # Type check
```

## Core Flow

1. User moves Plane issue to "Ready" state
2. `post_save` signal fires → `on_issue_save()` checks config + duplicate detection
3. Task queued via async httpx client → `POST /api/v1/task-runs`
4. `TaskRunMapping` created, issue state → "In Progress"
5. Lazy-Bird sends webhook on completion → HMAC-verified receiver
6. Mapping updated, issue state → "In Review", comment added with PR link

## License

MIT
