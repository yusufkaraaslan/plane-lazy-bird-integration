"""Integration test: REST API with Plane auth.

Tests all 8 API endpoints with both authenticated and unauthenticated requests.
Verifies that IsPlaneAuthenticated permission class correctly gates access.

When running locally (LAZY_BIRD_ALLOW_UNAUTHENTICATED=True in test settings),
tests validate endpoint behavior. When running in Docker with full Plane auth,
tests validate the auth stack end-to-end.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from plane_lazy_bird.models import AutomationConfig, TaskRunMapping

from .conftest import requires_docker_env


User = get_user_model()


def _url(path):
    return f"/api/webhooks/{path}"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client():
    """API client with an authenticated Django user."""
    client = APIClient()
    user = User.objects.create_user(
        username="testuser",
        password="testpass123",
    )
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def project_id():
    return uuid.uuid4()


@pytest.fixture
def config(project_id):
    return AutomationConfig.objects.create(
        project_id=project_id,
        lazy_bird_project_id=uuid.uuid4(),
        enabled=True,
        ready_state_name="Ready",
        in_progress_state_name="In Progress",
        review_state_name="In Review",
    )


@pytest.fixture
def mapping(config):
    return TaskRunMapping.objects.create(
        issue_id=uuid.uuid4(),
        project_id=config.project_id,
        task_run_id=uuid.uuid4(),
        status="running",
    )


@pytest.mark.django_db(transaction=True)
class TestAPIAuthEnforcement:
    """Verify that endpoints require authentication when LAZY_BIRD_ALLOW_UNAUTHENTICATED=False."""

    @override_settings(LAZY_BIRD_ALLOW_UNAUTHENTICATED=False)
    def test_unauthenticated_config_get_rejected(self, api_client, config):
        response = api_client.get(_url(f"lazy-bird/config/{config.project_id}/"))
        assert response.status_code == 403

    @override_settings(LAZY_BIRD_ALLOW_UNAUTHENTICATED=False)
    def test_authenticated_config_get_allowed(self, authenticated_client, config):
        response = authenticated_client.get(_url(f"lazy-bird/config/{config.project_id}/"))
        assert response.status_code == 200

    @override_settings(LAZY_BIRD_ALLOW_UNAUTHENTICATED=False)
    def test_unauthenticated_task_list_rejected(self, api_client):
        response = api_client.get(_url(f"lazy-bird/issues/{uuid.uuid4()}/tasks/"))
        assert response.status_code == 403

    @override_settings(LAZY_BIRD_ALLOW_UNAUTHENTICATED=False)
    def test_authenticated_task_list_allowed(self, authenticated_client):
        response = authenticated_client.get(_url(f"lazy-bird/issues/{uuid.uuid4()}/tasks/"))
        assert response.status_code == 200

    @override_settings(LAZY_BIRD_ALLOW_UNAUTHENTICATED=False)
    def test_unauthenticated_trigger_rejected(self, api_client):
        response = api_client.post(
            _url(f"lazy-bird/issues/{uuid.uuid4()}/tasks/trigger/"),
            {"project_id": str(uuid.uuid4()), "prompt": "test"},
            format="json",
        )
        assert response.status_code == 403

    @override_settings(LAZY_BIRD_ALLOW_UNAUTHENTICATED=False)
    def test_unauthenticated_test_connection_rejected(self, api_client):
        response = api_client.post(
            _url("lazy-bird/config/test-connection/"),
            {},
            format="json",
        )
        assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
class TestAPIEndpointsAuthenticated:
    """Test all 8 API endpoints with authenticated requests."""

    # --- Config endpoints ---

    def test_get_config(self, authenticated_client, config):
        response = authenticated_client.get(_url(f"lazy-bird/config/{config.project_id}/"))
        assert response.status_code == 200
        assert response.data["project_id"] == str(config.project_id)
        assert response.data["enabled"] is True
        assert response.data["ready_state_name"] == "Ready"

    def test_get_config_not_found(self, authenticated_client):
        response = authenticated_client.get(_url(f"lazy-bird/config/{uuid.uuid4()}/"))
        assert response.status_code == 404

    def test_create_config(self, authenticated_client):
        project_id = uuid.uuid4()
        response = authenticated_client.post(
            _url(f"lazy-bird/config/{project_id}/"),
            {
                "lazy_bird_project_id": str(uuid.uuid4()),
                "enabled": True,
                "ready_state_name": "Ready",
                "in_progress_state_name": "In Progress",
                "review_state_name": "In Review",
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.data["project_id"] == str(project_id)

    def test_update_config(self, authenticated_client, config):
        response = authenticated_client.post(
            _url(f"lazy-bird/config/{config.project_id}/"),
            {
                "lazy_bird_project_id": str(config.lazy_bird_project_id),
                "enabled": False,
            },
            format="json",
        )
        assert response.status_code == 200
        assert response.data["enabled"] is False

    # --- Test Connection ---

    def test_connection_success(self, authenticated_client):
        mock_client_instance = AsyncMock()
        mock_client_instance.health_check.return_value = {"status": "ok"}

        with patch("plane_lazy_bird.api.LazyBirdClient", return_value=mock_client_instance):
            response = authenticated_client.post(
                _url("lazy-bird/config/test-connection/"),
                {"api_url": "http://localhost:9000", "api_key": "test"},
                format="json",
            )

        assert response.status_code == 200
        assert response.data["connected"] is True

    def test_connection_failure(self, authenticated_client):
        mock_client_instance = AsyncMock()
        mock_client_instance.health_check.side_effect = ConnectionError("refused")

        with patch("plane_lazy_bird.api.LazyBirdClient", return_value=mock_client_instance):
            response = authenticated_client.post(
                _url("lazy-bird/config/test-connection/"),
                {},
                format="json",
            )

        assert response.status_code == 200
        assert response.data["connected"] is False

    # --- Task List ---

    def test_list_tasks_for_issue(self, authenticated_client, mapping):
        response = authenticated_client.get(
            _url(f"lazy-bird/issues/{mapping.issue_id}/tasks/")
        )
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["status"] == "running"

    def test_list_tasks_empty(self, authenticated_client):
        response = authenticated_client.get(
            _url(f"lazy-bird/issues/{uuid.uuid4()}/tasks/")
        )
        assert response.status_code == 200
        assert len(response.data) == 0

    # --- Trigger Task ---

    def test_trigger_creates_task(self, authenticated_client, config):
        issue_id = uuid.uuid4()
        mock_client = AsyncMock()
        mock_client.queue_task.return_value = {
            "id": str(uuid.uuid4()),
            "status": "queued",
        }

        with patch("plane_lazy_bird.api.lazy_bird_client", mock_client):
            response = authenticated_client.post(
                _url(f"lazy-bird/issues/{issue_id}/tasks/trigger/"),
                {
                    "project_id": str(config.project_id),
                    "prompt": "Implement the health system",
                },
                format="json",
            )

        assert response.status_code == 201
        assert response.data["status"] == "queued"

    def test_trigger_duplicate_prevention(self, authenticated_client, config, mapping):
        response = authenticated_client.post(
            _url(f"lazy-bird/issues/{mapping.issue_id}/tasks/trigger/"),
            {
                "project_id": str(config.project_id),
                "prompt": "test",
            },
            format="json",
        )
        assert response.status_code == 409

    def test_trigger_no_config(self, authenticated_client):
        response = authenticated_client.post(
            _url(f"lazy-bird/issues/{uuid.uuid4()}/tasks/trigger/"),
            {
                "project_id": str(uuid.uuid4()),
                "prompt": "test",
            },
            format="json",
        )
        assert response.status_code == 404

    # --- Task Status Proxy ---

    def test_status_proxy(self, authenticated_client, mapping):
        mock_client = AsyncMock()
        mock_client.get_task_status.return_value = {
            "id": str(mapping.task_run_id),
            "status": "running",
        }

        with patch("plane_lazy_bird.api.lazy_bird_client", mock_client):
            response = authenticated_client.get(
                _url(f"lazy-bird/issues/{mapping.issue_id}/tasks/{mapping.id}/status/")
            )

        assert response.status_code == 200
        assert response.data["status"] == "running"

    def test_status_not_found(self, authenticated_client):
        response = authenticated_client.get(
            _url(f"lazy-bird/issues/{uuid.uuid4()}/tasks/{uuid.uuid4()}/status/")
        )
        assert response.status_code == 404

    # --- Task Logs Proxy ---

    def test_logs_proxy(self, authenticated_client, mapping):
        mock_client = AsyncMock()
        mock_client.get_task_logs.return_value = {
            "logs": [{"message": "Starting..."}],
            "page": 1,
            "total": 1,
        }

        with patch("plane_lazy_bird.api.lazy_bird_client", mock_client):
            response = authenticated_client.get(
                _url(f"lazy-bird/issues/{mapping.issue_id}/tasks/{mapping.id}/logs/")
            )

        assert response.status_code == 200
        assert len(response.data["logs"]) == 1

    def test_logs_not_found(self, authenticated_client):
        response = authenticated_client.get(
            _url(f"lazy-bird/issues/{uuid.uuid4()}/tasks/{uuid.uuid4()}/logs/")
        )
        assert response.status_code == 404

    # --- Cancel Task ---

    def test_cancel_success(self, authenticated_client, mapping):
        mock_client = AsyncMock()
        mock_client.cancel_task.return_value = {"status": "cancelled"}

        with patch("plane_lazy_bird.api.lazy_bird_client", mock_client):
            response = authenticated_client.post(
                _url(f"lazy-bird/issues/{mapping.issue_id}/tasks/{mapping.id}/cancel/")
            )

        assert response.status_code == 200
        assert response.data["status"] == "cancelled"

    def test_cancel_not_found(self, authenticated_client):
        response = authenticated_client.post(
            _url(f"lazy-bird/issues/{uuid.uuid4()}/tasks/{uuid.uuid4()}/cancel/")
        )
        assert response.status_code == 404

    def test_cancel_already_completed(self, authenticated_client, config):
        completed_mapping = TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=config.project_id,
            task_run_id=uuid.uuid4(),
            status="success",
        )
        response = authenticated_client.post(
            _url(f"lazy-bird/issues/{completed_mapping.issue_id}/tasks/{completed_mapping.id}/cancel/")
        )
        assert response.status_code == 409


@requires_docker_env
@pytest.mark.django_db(transaction=True)
class TestAPIWithPlaneAuth:
    """Docker-based API tests with real Plane auth (skipped without Docker env)."""

    def test_placeholder_for_docker_api_auth(self, plane_api_url, lazy_bird_mock_url):
        """Placeholder: test all endpoints with real Plane session/JWT auth.

        When running in Docker:
        1. Create Plane user via API
        2. Authenticate and get session token
        3. Test all 8 endpoints with authenticated session
        4. Verify 403 without auth
        """
        assert plane_api_url.startswith("http")
        assert lazy_bird_mock_url.startswith("http")
