# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**Type:** Django package (Python library)
**Purpose:** Integration layer between Plane.so project management and Lazy-Bird automation engine
**Status:** Early development - package scaffolded, no implementation yet
**Package name:** `plane-lazy-bird` (PyPI: `plane-lazy-bird-integration`)

Part of Lazy-Bird's v2.0 microservice architecture:
- **lazy-bird** (Core Engine) - FastAPI + PostgreSQL + Celery
- **lazy-bird-ui** (Web UI) - React + TypeScript + Vite
- **plane-lazy-bird-integration** (This Repo) - Django package for Plane

## Current State

Only the package skeleton exists:
- `plane_lazy_bird/__init__.py` - Version string only (`__version__ = "0.1.0"`)
- `tests/__init__.py` - Empty
- `pyproject.toml` - Poetry config with dependencies defined

All module files described in planning docs (client.py, models.py, signals.py, webhooks.py, etc.) **do not exist yet**. See IMPLEMENTATION.md for the build plan.

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
**Test settings:** `tests/settings.py` (DJANGO_SETTINGS_MODULE configured in pyproject.toml) - does not exist yet, needs to be created for pytest-django
**Python:** 3.10+ (3.10, 3.11, 3.12)
**Django:** 4.2+
**Line length:** 100 (Black)
**Type checking:** mypy strict (`disallow_untyped_defs = true`)

## Planned Architecture

The package connects Plane.so to the lazy-bird REST API using Django signals and webhooks. The core flow:

1. User moves Plane issue to "Ready" state
2. Django `post_save` signal fires, queues task in Lazy-Bird via async HTTP client (httpx)
3. `TaskRunMapping` model tracks the Plane issue <-> Lazy-Bird task relationship
4. Lazy-Bird sends webhook on completion -> issue updated to "In Review" with PR link

### Planned modules (see IMPLEMENTATION.md for full details):
- `client.py` - Async httpx client for Lazy-Bird REST API (Bearer token auth)
- `models.py` - `AutomationConfig` (project mapping), `TaskRunMapping` (issue-to-task mapping)
- `signals.py` - `post_save` on Issue model, duplicate detection, auto-queue
- `webhooks.py` - HMAC-verified webhook receiver for task.started/completed/failed/pr.created
- `admin.py` - Django admin for configuration
- `urls.py` - Webhook endpoint routing
- `management/commands/lazy_bird_setup_webhook.py` - Setup command

### Key design constraints:
- Installs inside a Plane instance as a Django app (extends Plane without modifying core)
- Django signals are synchronous but API client is async - use `asyncio.run()` or `sync_to_async()`
- Webhook handlers must be idempotent (safe to process same event multiple times)
- Signal handlers must include duplicate detection to prevent double-queuing

### Environment variables (when implemented):
```bash
LAZY_BIRD_API_URL=http://localhost:8000
LAZY_BIRD_API_KEY=lb_live_your_api_key_here
LAZY_BIRD_WEBHOOK_SECRET=whsec_your_webhook_secret
```

## Planning Documents

- `IMPLEMENTATION.md` - 3-day implementation plan with task checklist
- `DEEP_INTEGRATION_PLAN.md` - Phase 2/3 plans for REST API endpoints and React UI components in Plane
- `DEV_WORKFLOW.md` - Git branching strategy and multi-instance coordination
