"""Tests for the Lazy-Bird API client."""

import hashlib
import hmac

from plane_lazy_bird.client import LazyBirdClient, verify_webhook_signature


class TestLazyBirdClient:
    def test_client_init_defaults(self):
        client = LazyBirdClient(
            base_url="http://localhost:8000",
            api_key="lb_test_key",
        )
        assert client.base_url == "http://localhost:8000"
        assert client.api_key == "lb_test_key"
        assert client.timeout == 30.0

    def test_client_strips_trailing_slash(self):
        client = LazyBirdClient(base_url="http://localhost:8000/")
        assert client.base_url == "http://localhost:8000"

    def test_url_construction(self):
        client = LazyBirdClient(base_url="http://localhost:8000")
        assert client._url("/task-runs") == "http://localhost:8000/api/v1/task-runs"
        assert client._url("/health") == "http://localhost:8000/api/v1/health"

    def test_headers(self):
        client = LazyBirdClient(
            base_url="http://localhost:8000",
            api_key="lb_test_key",
        )
        headers = client._headers()
        assert headers["X-API-Key"] == "lb_test_key"
        assert headers["Content-Type"] == "application/json"


class TestVerifyWebhookSignature:
    def test_valid_signature(self):
        secret = "test_webhook_secret"
        payload = b'{"event": "task.completed", "task_run_id": "abc123"}'
        digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"sha256={digest}"

        assert verify_webhook_signature(payload, signature, secret) is True

    def test_invalid_signature(self):
        secret = "test_webhook_secret"
        payload = b'{"event": "task.completed"}'
        signature = "sha256=invalid_hex_digest"

        assert verify_webhook_signature(payload, signature, secret) is False

    def test_missing_prefix(self):
        secret = "test_webhook_secret"
        payload = b'{"event": "task.completed"}'
        digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        assert verify_webhook_signature(payload, digest, secret) is False

    def test_tampered_payload(self):
        secret = "test_webhook_secret"
        original = b'{"event": "task.completed"}'
        tampered = b'{"event": "task.failed"}'
        digest = hmac.new(secret.encode(), original, hashlib.sha256).hexdigest()
        signature = f"sha256={digest}"

        assert verify_webhook_signature(tampered, signature, secret) is False
