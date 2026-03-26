"""Shared fixtures for integration tests.

Integration tests run against the Docker test environment (docker-compose.test.yml).
They require PLANE_API_URL and LAZY_BIRD_MOCK_URL environment variables.

When these env vars are not set, integration tests are skipped automatically.
"""

import os

import pytest

PLANE_API_URL = os.environ.get("PLANE_API_URL", "")
LAZY_BIRD_MOCK_URL = os.environ.get("LAZY_BIRD_MOCK_URL", "")
LAZY_BIRD_API_KEY = os.environ.get("LAZY_BIRD_API_KEY", "lb_test_integration_key")
LAZY_BIRD_WEBHOOK_SECRET = os.environ.get(
    "LAZY_BIRD_WEBHOOK_SECRET", "whsec_test_integration_secret_min16"
)

# Skip all integration tests if not running in Docker test environment
requires_docker_env = pytest.mark.skipif(
    not PLANE_API_URL or not LAZY_BIRD_MOCK_URL,
    reason="Integration tests require PLANE_API_URL and LAZY_BIRD_MOCK_URL env vars "
    "(run via docker-compose.test.yml)",
)


@pytest.fixture
def plane_api_url():
    return PLANE_API_URL


@pytest.fixture
def lazy_bird_mock_url():
    return LAZY_BIRD_MOCK_URL


@pytest.fixture
def lazy_bird_api_key():
    return LAZY_BIRD_API_KEY


@pytest.fixture
def lazy_bird_webhook_secret():
    return LAZY_BIRD_WEBHOOK_SECRET
