"""Integration test: Webhook flow — task completes → issue updated.

End-to-end test flow:
1. Create TaskRunMapping (simulating a queued task)
2. Send task.completed webhook with valid HMAC signature
3. Verify TaskRunMapping updated to "success" with PR details
4. Verify Plane issue state update was attempted ("In Review")
5. Verify comment with PR link was added

Also tests: task.started, task.failed, task.cancelled, pr.created webhooks,
and the full lifecycle (started → completed with PR).
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client

from plane_lazy_bird.models import AutomationConfig, TaskRunMapping

from .conftest import requires_docker_env


WEBHOOK_URL = "/api/webhooks/lazy-bird/"
SECRET = "whsec_test_secret_for_testing_min16chars"


def _sign(payload: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _post_webhook(client, payload: dict, secret: str = SECRET):
    body = json.dumps(payload).encode()
    return client.post(
        WEBHOOK_URL,
        data=body,
        content_type="application/json",
        HTTP_X_WEBHOOK_SIGNATURE=_sign(body, secret),
    )


@pytest.mark.django_db(transaction=True)
class TestWebhookFlowEndToEnd:
    """Test the complete webhook flow: task event → mapping update → Plane update."""

    def test_task_completed_updates_mapping_with_pr(self):
        """task.completed should update mapping to success with PR details."""
        client = Client()
        task_run_id = uuid.uuid4()
        mapping = TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=task_run_id,
            status="running",
        )

        response = _post_webhook(client, {
            "event": "task.completed",
            "task_run_id": str(task_run_id),
            "data": {
                "pr_url": "https://github.com/org/repo/pull/42",
                "pr_number": 42,
            },
        })

        assert response.status_code == 200
        mapping.refresh_from_db()
        assert mapping.status == "success"
        assert mapping.pr_url == "https://github.com/org/repo/pull/42"
        assert mapping.pr_number == 42

    def test_task_completed_triggers_state_update(self):
        """task.completed should attempt to update Plane issue to In Review."""
        client = Client()
        project_id = uuid.uuid4()
        task_run_id = uuid.uuid4()

        AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
            review_state_name="In Review",
        )
        TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=project_id,
            task_run_id=task_run_id,
            status="running",
        )

        with patch("plane_lazy_bird.webhooks._get_plane_model", return_value=None) as mock_model:
            response = _post_webhook(client, {
                "event": "task.completed",
                "task_run_id": str(task_run_id),
                "data": {"pr_url": "https://github.com/org/repo/pull/5", "pr_number": 5},
            })

        assert response.status_code == 200
        # _get_plane_model is called for Issue/State and IssueComment
        assert mock_model.call_count >= 2

    def test_task_completed_adds_pr_comment(self):
        """task.completed should add a comment with PR link."""
        client = Client()
        task_run_id = uuid.uuid4()
        TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=task_run_id,
            status="running",
        )

        with patch("plane_lazy_bird.webhooks._add_plane_issue_comment") as mock_comment, \
             patch("plane_lazy_bird.webhooks._update_plane_issue_state"):
            response = _post_webhook(client, {
                "event": "task.completed",
                "task_run_id": str(task_run_id),
                "data": {
                    "pr_url": "https://github.com/org/repo/pull/77",
                    "pr_number": 77,
                },
            })

        assert response.status_code == 200
        mock_comment.assert_called_once()
        comment_text = mock_comment.call_args[0][1]
        assert "https://github.com/org/repo/pull/77" in comment_text
        assert "completed successfully" in comment_text

    def test_task_failed_updates_mapping_with_error(self):
        """task.failed should update mapping and add failure comment."""
        client = Client()
        task_run_id = uuid.uuid4()
        TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=task_run_id,
            status="running",
        )

        with patch("plane_lazy_bird.webhooks._add_plane_issue_comment") as mock_comment:
            response = _post_webhook(client, {
                "event": "task.failed",
                "task_run_id": str(task_run_id),
                "data": {"error_message": "pytest: 3 tests failed"},
            })

        assert response.status_code == 200
        mapping = TaskRunMapping.objects.get(task_run_id=task_run_id)
        assert mapping.status == "failed"
        assert mapping.error_message == "pytest: 3 tests failed"

        mock_comment.assert_called_once()
        comment_text = mock_comment.call_args[0][1]
        assert "pytest: 3 tests failed" in comment_text

    def test_full_lifecycle_started_to_completed(self):
        """Full lifecycle: task.started → task.completed with PR."""
        client = Client()
        task_run_id = uuid.uuid4()
        mapping = TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=task_run_id,
            status="queued",
        )

        # Step 1: task.started
        response = _post_webhook(client, {
            "event": "task.started",
            "task_run_id": str(task_run_id),
        })
        assert response.status_code == 200
        mapping.refresh_from_db()
        assert mapping.status == "running"

        # Step 2: pr.created
        response = _post_webhook(client, {
            "event": "pr.created",
            "task_run_id": str(task_run_id),
            "data": {
                "pr_url": "https://github.com/org/repo/pull/100",
                "pr_number": 100,
            },
        })
        assert response.status_code == 200
        mapping.refresh_from_db()
        assert mapping.pr_url == "https://github.com/org/repo/pull/100"
        assert mapping.pr_number == 100
        assert mapping.status == "running"  # Status unchanged by pr.created

        # Step 3: task.completed
        with patch("plane_lazy_bird.webhooks._add_plane_issue_comment"), \
             patch("plane_lazy_bird.webhooks._update_plane_issue_state"):
            response = _post_webhook(client, {
                "event": "task.completed",
                "task_run_id": str(task_run_id),
                "data": {
                    "pr_url": "https://github.com/org/repo/pull/100",
                    "pr_number": 100,
                },
            })
        assert response.status_code == 200
        mapping.refresh_from_db()
        assert mapping.status == "success"
        assert mapping.pr_url == "https://github.com/org/repo/pull/100"

    def test_task_cancelled_updates_mapping(self):
        """task.cancelled should update mapping status."""
        client = Client()
        task_run_id = uuid.uuid4()
        TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=task_run_id,
            status="running",
        )

        response = _post_webhook(client, {
            "event": "task.cancelled",
            "task_run_id": str(task_run_id),
        })
        assert response.status_code == 200
        mapping = TaskRunMapping.objects.get(task_run_id=task_run_id)
        assert mapping.status == "cancelled"

    def test_invalid_signature_rejected(self):
        """Webhook with wrong signature should return 401."""
        client = Client()
        body = json.dumps({"event": "task.started", "task_run_id": str(uuid.uuid4())}).encode()
        response = client.post(
            WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="sha256=definitely_wrong",
        )
        assert response.status_code == 401

    def test_unknown_task_run_returns_404(self):
        """Webhook for unknown task_run_id should return 404."""
        client = Client()
        response = _post_webhook(client, {
            "event": "task.started",
            "task_run_id": str(uuid.uuid4()),
        })
        assert response.status_code == 404

    def test_idempotent_completed_webhook(self):
        """Processing task.completed twice should not fail."""
        client = Client()
        task_run_id = uuid.uuid4()
        TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=task_run_id,
            status="running",
        )

        payload = {
            "event": "task.completed",
            "task_run_id": str(task_run_id),
            "data": {"pr_url": "https://github.com/org/repo/pull/1", "pr_number": 1},
        }

        with patch("plane_lazy_bird.webhooks._add_plane_issue_comment"), \
             patch("plane_lazy_bird.webhooks._update_plane_issue_state"):
            r1 = _post_webhook(client, payload)
            r2 = _post_webhook(client, payload)

        assert r1.status_code == 200
        assert r2.status_code == 200
        mapping = TaskRunMapping.objects.get(task_run_id=task_run_id)
        assert mapping.status == "success"


@requires_docker_env
@pytest.mark.django_db(transaction=True)
class TestWebhookFlowDocker:
    """Docker-based webhook flow tests (skipped without Docker env)."""

    def test_placeholder_for_docker_webhook_flow(self, plane_api_url, lazy_bird_mock_url):
        """Placeholder: full Docker-based webhook flow test.

        When running in Docker with a real Plane instance:
        1. Create issue + trigger task via signal
        2. Send task.completed webhook to plane-api
        3. Verify issue state changed to In Review via Plane API
        4. Verify comment with PR link added via Plane API
        """
        assert plane_api_url.startswith("http")
        assert lazy_bird_mock_url.startswith("http")
