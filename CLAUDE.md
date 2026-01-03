# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**Type:** Django package (Python library)
**Purpose:** Integration layer between Plane.so project management and Lazy-Bird automation engine
**Status:** v2.0 - Production Ready (standalone repository architecture)
**Published:** PyPI package (`pip install plane-lazy-bird-integration`)

This is the **Plane.so integration package** for Lazy-Bird's v2.0 microservice architecture:
- **lazy-bird** (Core Engine) - FastAPI + PostgreSQL + Celery
- **lazy-bird-ui** (Web UI) - React + TypeScript + Vite
- **plane-lazy-bird-integration** (This Repo) - Django package for Plane

The package connects Plane.so to the lazy-bird REST API using Django signals and webhooks to automatically queue tasks when issues move to "Ready" state and update issues when tasks complete.

## Development Commands

### Testing

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=plane_lazy_bird --cov-report=html

# Run specific test file
pytest tests/test_client.py

# Run tests with output
pytest -v -s
```

### Code Quality

```bash
# Format code (Black)
black plane_lazy_bird/ tests/

# Lint code (Flake8)
flake8 plane_lazy_bird/ tests/

# Type checking (mypy)
mypy plane_lazy_bird/
```

### Package Management

```bash
# Install dependencies
poetry install

# Install with dev dependencies
poetry install --with dev

# Add dependency
poetry add <package>

# Add dev dependency
poetry add --group dev <package>

# Build package
poetry build

# Publish to PyPI
poetry publish
```

### Django Development

```bash
# Create migrations (when installed in Plane)
python manage.py makemigrations plane_lazy_bird

# Run migrations
python manage.py migrate plane_lazy_bird

# Setup webhook in Lazy-Bird
python manage.py lazy_bird_setup_webhook

# Django shell for testing
python manage.py shell
```

## Architecture & Code Structure

### Package Structure

```
plane_lazy_bird/
├── __init__.py              # Version info
├── apps.py                  # Django app configuration
├── client.py                # Lazy-Bird API client (httpx)
├── models.py                # Django models (AutomationConfig, TaskRunMapping)
├── signals.py               # Signal handlers for automatic task queuing
├── webhooks.py              # Webhook receiver for task completion events
├── admin.py                 # Django admin interface
├── urls.py                  # URL routing for webhook endpoint
└── management/
    └── commands/
        └── lazy_bird_setup_webhook.py
```

### Core Components

#### 1. API Client (`client.py`)

**Purpose:** Async HTTP client for Lazy-Bird REST API

**Key Methods:**
- `queue_task()` - Queue a new task in Lazy-Bird
- `get_task_status()` - Get current task status
- `cancel_task()` - Cancel a running task
- `get_task_logs()` - Retrieve task execution logs

**Technology:** httpx (async HTTP), Bearer token authentication

**Usage Pattern:**
```python
from plane_lazy_bird.client import lazy_bird_client

task_run = await lazy_bird_client.queue_task(
    project_id='proj_abc123',
    work_item_id='issue-42',
    title='Add health system',
    description='Player needs health tracking...'
)
```

#### 2. Django Models (`models.py`)

**AutomationConfig:**
- Maps Plane projects to Lazy-Bird projects
- Stores configuration (enabled/disabled, state names)
- One-to-one relationship with Plane Project

**TaskRunMapping:**
- Maps Plane issues to Lazy-Bird task runs
- Tracks task status and PR URLs
- Foreign key to Plane Issue

**Key Pattern:** These models bridge the two systems, creating a mapping layer between Plane's issue tracking and Lazy-Bird's task execution.

#### 3. Django Signals (`signals.py`)

**Purpose:** Automatically queue tasks when issues change state

**Flow:**
1. User moves Plane issue to "Ready" state
2. `post_save` signal fires on Issue model
3. Signal handler checks if automation is enabled for the project
4. If enabled and state matches, queue task in Lazy-Bird
5. Create TaskRunMapping to track the task
6. Update issue state to "In Progress"

**Key Pattern:** Uses Django's signal system to react to Plane's data changes without modifying Plane's core code.

**Important:** Includes duplicate detection to prevent double-queuing.

#### 4. Webhook Receiver (`webhooks.py`)

**Purpose:** Receive and process events from Lazy-Bird

**Events Handled:**
- `task.started` - Task execution began
- `task.completed` - Task completed successfully (update issue, add PR link)
- `task.failed` - Task failed (update issue with error)
- `pr.created` - Pull request created

**Security:** HMAC signature verification using webhook secret

**Flow (task completion):**
1. Lazy-Bird sends webhook POST request
2. Verify HMAC signature
3. Find TaskRunMapping by task_run_id
4. Add comment to Plane issue with PR link
5. Move issue to "In Review" state
6. Update TaskRunMapping with PR URL

**Key Pattern:** Idempotent webhook handling - can safely process same event multiple times.

### Configuration

**Environment Variables:**
```bash
LAZY_BIRD_API_URL=http://localhost:8000
LAZY_BIRD_API_KEY=lb_live_your_api_key_here
LAZY_BIRD_WEBHOOK_SECRET=whsec_your_webhook_secret
```

**Django Settings (in Plane):**
```python
# plane/settings/common.py
INSTALLED_APPS = [
    ...
    'plane_lazy_bird',
]

LAZY_BIRD_API_URL = env('LAZY_BIRD_API_URL')
LAZY_BIRD_API_KEY = env('LAZY_BIRD_API_KEY')
LAZY_BIRD_WEBHOOK_SECRET = env('LAZY_BIRD_WEBHOOK_SECRET')

# Optional custom state names
LAZY_BIRD_READY_STATE = env('LAZY_BIRD_READY_STATE', 'Ready')
LAZY_BIRD_IN_PROGRESS_STATE = env('LAZY_BIRD_IN_PROGRESS_STATE', 'In Progress')
LAZY_BIRD_REVIEW_STATE = env('LAZY_BIRD_REVIEW_STATE', 'In Review')
```

### Testing Strategy

**Test Framework:** pytest + pytest-django + pytest-asyncio

**Test Files:**
- `test_client.py` - API client unit tests
- `test_signals.py` - Signal handler tests
- `test_webhooks.py` - Webhook receiver tests
- `test_models.py` - Model tests

**Fixtures:** factory_boy for test data generation

**Coverage Target:** 80%+ (configured in pyproject.toml)

**Testing Settings:** `tests/settings.py` contains minimal Django settings for testing without full Plane installation.

### Key Design Patterns

**1. Signal-Driven Architecture**
- Reacts to Plane's data changes without modifying Plane core
- Decouples automation logic from Plane's business logic

**2. Mapping Layer**
- Models create a bridge between two independent systems
- Maintains relationships without tight coupling

**3. Async API Client**
- Uses httpx for async HTTP requests
- Non-blocking when queuing tasks or checking status

**4. Webhook Idempotency**
- Handles duplicate webhook events gracefully
- Safe to retry failed webhook processing

**5. Admin Interface Integration**
- Leverages Django admin for configuration management
- No custom UI needed for basic operations

## Integration with Plane

This package is designed to be installed **inside a Plane instance** as a Django app. It extends Plane's functionality without modifying Plane's core code.

**Installation in Plane:**
1. `pip install plane-lazy-bird-integration`
2. Add `'plane_lazy_bird'` to `INSTALLED_APPS`
3. Configure environment variables
4. Run migrations: `python manage.py migrate plane_lazy_bird`
5. Add webhook URL route
6. Setup webhook: `python manage.py lazy_bird_setup_webhook`

**URL Configuration:**
```python
# plane/urls.py
urlpatterns = [
    ...
    path('api/webhooks/', include('plane_lazy_bird.urls')),
]
```

## Dependencies

**Runtime:**
- `django ^4.2` - Web framework
- `httpx ^0.25.0` - Async HTTP client
- `python-dotenv ^1.0.0` - Environment configuration

**Development:**
- `pytest ^7.4.0` - Test framework
- `pytest-django ^4.5.0` - Django testing support
- `pytest-asyncio ^0.21.0` - Async test support
- `pytest-cov ^4.1.0` - Coverage reporting
- `black ^23.9.0` - Code formatter (100 char line length)
- `flake8 ^6.1.0` - Linter
- `mypy ^1.5.0` - Type checker
- `factory-boy ^3.3.0` - Test fixtures

**External Services:**
- Lazy-Bird API (FastAPI backend)
- Plane.so (Django project management)

## Code Style

**Formatter:** Black with 100 character line length
**Type Checking:** mypy with strict settings (`disallow_untyped_defs = true`)
**Python Version:** 3.10+ (configured for 3.10, 3.11, 3.12)

## Publishing Workflow

```bash
# 1. Update version in plane_lazy_bird/__init__.py and pyproject.toml
# 2. Build package
poetry build

# 3. Publish to PyPI
poetry publish

# 4. Tag release
git tag v0.1.0
git push origin v0.1.0
```

## Important Notes

### State Transitions

The automation follows this state flow in Plane:
1. **Ready** → Task queued in Lazy-Bird → **In Progress**
2. **In Progress** → Task completes → **In Review** (with PR link)
3. **In Review** → Manual review/merge by developer

### Preventing Double-Queuing

Signal handlers include duplicate detection:
- Check if TaskRunMapping already exists for issue
- Check if issue is already in a terminal state
- Only queue if automation is enabled AND state matches

### Webhook Security

Always verify webhook signatures:
```python
# In webhook handler
if not verify_hmac_signature(request.body, request.headers['X-Lazy-Bird-Signature']):
    return JsonResponse({'error': 'Invalid signature'}, status=401)
```

### Async Code in Django Signals

Django signals are synchronous, but API client is async:
- Use `asyncio.run()` or `sync_to_async()` wrapper
- Handle async context properly in signal handlers
- Ensure database connections are closed correctly

## Troubleshooting

**Tasks Not Queuing:**
1. Check `AutomationConfig.enabled = True` for the project
2. Verify state name matches exactly (case-sensitive)
3. Check API key is valid and Lazy-Bird is reachable
4. Review signal handler logs

**Webhooks Not Working:**
1. Verify webhook is registered: `python manage.py lazy_bird_setup_webhook`
2. Check webhook secret matches in settings
3. Ensure webhook URL is publicly accessible (if Lazy-Bird is remote)
4. Check webhook signature verification logic

**API Connection Issues:**
1. Verify `LAZY_BIRD_API_URL` is correct and reachable
2. Check API key format: `lb_live_...` or `lb_test_...`
3. Test connection: `curl -H "Authorization: Bearer $LAZY_BIRD_API_KEY" $LAZY_BIRD_API_URL/api/v1/status`

## Related Repositories

- **lazy-bird** (Core Engine): https://github.com/yusufkaraaslan/lazy-bird
- **lazy-bird-ui** (Web UI): https://github.com/yusufkaraaslan/lazy-bird-ui
- **Documentation**: https://lazy-bird.dev/docs
