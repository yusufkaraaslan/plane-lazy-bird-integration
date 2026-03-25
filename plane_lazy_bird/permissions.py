"""DRF permission classes for the Lazy-Bird API.

Wraps Plane's authentication with a fallback for testing environments.
"""

from django.conf import settings
from rest_framework.permissions import BasePermission


class IsPlaneAuthenticated(BasePermission):
    """Require an authenticated Plane user, or allow all if configured.

    In production (inside Plane), this checks request.user.is_authenticated
    which is set by Plane's session/JWT middleware.

    In tests (without Plane), set LAZY_BIRD_ALLOW_UNAUTHENTICATED = True
    to bypass authentication.
    """

    def has_permission(self, request, view):
        if getattr(settings, "LAZY_BIRD_ALLOW_UNAUTHENTICATED", False):
            return True
        return request.user and request.user.is_authenticated
