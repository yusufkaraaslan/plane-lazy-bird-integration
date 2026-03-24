"""Async HTTP client for the Lazy-Bird REST API."""

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class LazyBirdClient:
    """Client for interacting with the Lazy-Bird v2.0 REST API.

    Uses httpx for async HTTP with Bearer token authentication.
    All endpoints are under /api/v1/.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or getattr(settings, "LAZY_BIRD_API_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or getattr(settings, "LAZY_BIRD_API_KEY", "")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    async def health_check(self) -> Dict[str, Any]:
        """Check Lazy-Bird API health."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self._url("/health"),
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def queue_task(
        self,
        project_id: UUID,
        work_item_id: str,
        prompt: str,
        work_item_url: Optional[str] = None,
        work_item_title: Optional[str] = None,
        work_item_description: Optional[str] = None,
        task_type: str = "feature",
        complexity: Optional[str] = None,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Queue a new task run in Lazy-Bird.

        Returns the created TaskRun response dict including 'id' and 'status'.
        """
        payload: Dict[str, Any] = {
            "project_id": str(project_id),
            "work_item_id": work_item_id,
            "prompt": prompt,
            "task_type": task_type,
            "max_retries": max_retries,
        }
        if work_item_url:
            payload["work_item_url"] = work_item_url
        if work_item_title:
            payload["work_item_title"] = work_item_title
        if work_item_description:
            payload["work_item_description"] = work_item_description
        if complexity:
            payload["complexity"] = complexity
        if metadata:
            payload["metadata"] = metadata

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._url("/task-runs"),
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            result = response.json()
            logger.info(
                "Queued task run %s for work item %s",
                result.get("id"),
                work_item_id,
            )
            return result

    async def get_task_status(self, task_run_id: UUID) -> Dict[str, Any]:
        """Get current status and details of a task run."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self._url(f"/task-runs/{task_run_id}"),
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def cancel_task(self, task_run_id: UUID) -> Dict[str, Any]:
        """Cancel a queued or running task."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._url(f"/task-runs/{task_run_id}/cancel"),
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def retry_task(self, task_run_id: UUID) -> Dict[str, Any]:
        """Retry a failed task."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._url(f"/task-runs/{task_run_id}/retry"),
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def get_task_logs(
        self,
        task_run_id: UUID,
        page: int = 1,
        page_size: int = 100,
        level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated task run logs."""
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if level:
            params["level"] = level

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self._url(f"/task-runs/{task_run_id}/logs"),
                params=params,
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def register_webhook(
        self,
        url: str,
        secret: str,
        events: list,
        project_id: Optional[UUID] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """Register a webhook subscription in Lazy-Bird."""
        payload: Dict[str, Any] = {
            "url": url,
            "secret": secret,
            "events": events,
            "description": description,
        }
        if project_id:
            payload["project_id"] = str(project_id)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._url("/webhooks"),
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 webhook signature from Lazy-Bird.

    Lazy-Bird sends: X-Webhook-Signature: sha256=<hex_digest>
    """
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    received = signature[len("sha256="):]
    return hmac.compare_digest(expected, received)


# Module-level singleton, lazily configured from Django settings
lazy_bird_client = LazyBirdClient()
