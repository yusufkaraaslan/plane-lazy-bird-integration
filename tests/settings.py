"""Minimal Django settings for running tests without a full Plane installation."""

SECRET_KEY = "test-secret-key-not-for-production"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "plane_lazy_bird",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROOT_URLCONF = "tests.urls"

# Lazy-Bird settings for tests
LAZY_BIRD_API_URL = "http://localhost:8000"
LAZY_BIRD_API_KEY = "lb_test_fake_key_for_testing"
LAZY_BIRD_WEBHOOK_SECRET = "whsec_test_secret_for_testing_min16chars"

# Allow unauthenticated API access in tests (no Plane auth stack)
LAZY_BIRD_ALLOW_UNAUTHENTICATED = True

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "plane_lazy_bird.permissions.IsPlaneAuthenticated",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}
