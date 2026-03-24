"""Tests for the webhook receiver endpoint."""

import hashlib
import hmac
import json
import uuid

import pytest
from django.test import Client

from plane_lazy_bird.models import TaskRunMapping


def _sign(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


WEBHOOK_URL = "/api/webhooks/lazy-bird/"
SECRET = "whsec_test_secret_for_testing_min16chars"


@pytest.mark.django_db
class TestWebhookReceiver:
    def setup_method(self):
        self.client = Client()
        self.task_run_id = uuid.uuid4()
        self.mapping = TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=self.task_run_id,
            status="queued",
        )

    def _post_webhook(self, payload: dict) -> object:
        body = json.dumps(payload).encode()
        return self.client.post(
            WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=_sign(body, SECRET),
        )

    def test_invalid_signature_rejected(self):
        body = b'{"event": "task.started"}'
        response = self.client.post(
            WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="sha256=invalid",
        )
        assert response.status_code == 401

    def test_missing_event_type(self):
        response = self._post_webhook({"task_run_id": str(self.task_run_id)})
        assert response.status_code == 400

    def test_task_started(self):
        response = self._post_webhook({
            "event": "task.started",
            "task_run_id": str(self.task_run_id),
        })
        assert response.status_code == 200
        self.mapping.refresh_from_db()
        assert self.mapping.status == "running"

    def test_task_completed(self):
        response = self._post_webhook({
            "event": "task.completed",
            "task_run_id": str(self.task_run_id),
            "data": {
                "pr_url": "https://github.com/org/repo/pull/99",
                "pr_number": 99,
            },
        })
        assert response.status_code == 200
        self.mapping.refresh_from_db()
        assert self.mapping.status == "success"
        assert self.mapping.pr_url == "https://github.com/org/repo/pull/99"
        assert self.mapping.pr_number == 99

    def test_task_failed(self):
        response = self._post_webhook({
            "event": "task.failed",
            "task_run_id": str(self.task_run_id),
            "data": {"error_message": "Tests did not pass"},
        })
        assert response.status_code == 200
        self.mapping.refresh_from_db()
        assert self.mapping.status == "failed"
        assert self.mapping.error_message == "Tests did not pass"

    def test_task_cancelled(self):
        response = self._post_webhook({
            "event": "task.cancelled",
            "task_run_id": str(self.task_run_id),
        })
        assert response.status_code == 200
        self.mapping.refresh_from_db()
        assert self.mapping.status == "cancelled"

    def test_pr_created(self):
        response = self._post_webhook({
            "event": "pr.created",
            "task_run_id": str(self.task_run_id),
            "data": {
                "pr_url": "https://github.com/org/repo/pull/42",
                "pr_number": 42,
            },
        })
        assert response.status_code == 200
        self.mapping.refresh_from_db()
        assert self.mapping.pr_url == "https://github.com/org/repo/pull/42"
        assert self.mapping.pr_number == 42

    def test_unknown_event_ignored(self):
        response = self._post_webhook({
            "event": "some.unknown.event",
            "task_run_id": str(self.task_run_id),
        })
        assert response.status_code == 200
        data = response.json()
        assert data["handled"] is False

    def test_unknown_task_run_returns_404(self):
        response = self._post_webhook({
            "event": "task.started",
            "task_run_id": str(uuid.uuid4()),
        })
        assert response.status_code == 404

    def test_idempotent_handling(self):
        """Processing the same event twice should not fail."""
        payload = {
            "event": "task.completed",
            "task_run_id": str(self.task_run_id),
            "data": {"pr_url": "https://github.com/org/repo/pull/1", "pr_number": 1},
        }
        response1 = self._post_webhook(payload)
        response2 = self._post_webhook(payload)
        assert response1.status_code == 200
        assert response2.status_code == 200
        self.mapping.refresh_from_db()
        assert self.mapping.status == "success"
