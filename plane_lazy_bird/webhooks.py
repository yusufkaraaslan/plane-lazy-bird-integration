"""Webhook receiver for Lazy-Bird task lifecycle events.

Handles incoming webhooks from Lazy-Bird with HMAC signature verification.
Events: task.started, task.completed, task.failed, task.cancelled, pr.created
"""

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from plane_lazy_bird.client import verify_webhook_signature
from plane_lazy_bird.models import TaskRunMapping

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def lazy_bird_webhook(request):
    """Receive and process webhook events from Lazy-Bird.

    Verifies HMAC signature, routes to event-specific handlers.
    Designed to be idempotent — safe to process the same event multiple times.
    """
    # Verify signature
    signature = request.headers.get("X-Webhook-Signature", "")
    secret = getattr(settings, "LAZY_BIRD_WEBHOOK_SECRET", "")

    if not secret:
        logger.error("LAZY_BIRD_WEBHOOK_SECRET not configured")
        return JsonResponse({"error": "Webhook not configured"}, status=500)

    if not verify_webhook_signature(request.body, signature, secret):
        logger.warning("Invalid webhook signature")
        return JsonResponse({"error": "Invalid signature"}, status=401)

    # Parse event payload
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event_type = payload.get("event")
    task_run_id = payload.get("task_run_id")

    if not event_type:
        return JsonResponse({"error": "Missing event type"}, status=400)

    logger.info("Received webhook event: %s (task_run=%s)", event_type, task_run_id)

    # Route to event handlers
    handlers = {
        "task.started": _handle_task_started,
        "task.completed": _handle_task_completed,
        "task.failed": _handle_task_failed,
        "task.cancelled": _handle_task_cancelled,
        "pr.created": _handle_pr_created,
    }

    handler = handlers.get(event_type)
    if handler is None:
        logger.info("Ignoring unhandled event type: %s", event_type)
        return JsonResponse({"received": True, "handled": False})

    try:
        handler(payload)
    except TaskRunMapping.DoesNotExist:
        logger.warning("No TaskRunMapping found for task_run_id=%s", task_run_id)
        return JsonResponse({"error": "Unknown task run"}, status=404)
    except Exception:
        logger.exception("Error handling webhook event %s", event_type)
        return JsonResponse({"error": "Internal error"}, status=500)

    return JsonResponse({"received": True, "handled": True})


def _handle_task_started(payload: dict) -> None:
    """Update mapping status when task execution begins."""
    mapping = TaskRunMapping.objects.get(task_run_id=payload["task_run_id"])
    mapping.status = "running"
    mapping.save(update_fields=["status", "updated_at"])
    logger.info("Task started: %s", mapping.task_run_id)


def _handle_task_completed(payload: dict) -> None:
    """Update mapping and Plane issue when task completes successfully."""
    data = payload.get("data", {})
    mapping = TaskRunMapping.objects.get(task_run_id=payload["task_run_id"])
    mapping.status = "success"
    mapping.pr_url = data.get("pr_url", "")
    mapping.pr_number = data.get("pr_number")
    mapping.save(update_fields=["status", "pr_url", "pr_number", "updated_at"])
    logger.info("Task completed: %s (PR: %s)", mapping.task_run_id, mapping.pr_url)

    # Issue state update and comment will be implemented in issues #18/#19


def _handle_task_failed(payload: dict) -> None:
    """Update mapping when task fails."""
    data = payload.get("data", {})
    mapping = TaskRunMapping.objects.get(task_run_id=payload["task_run_id"])
    mapping.status = "failed"
    mapping.error_message = data.get("error_message", "")
    mapping.save(update_fields=["status", "error_message", "updated_at"])
    logger.info("Task failed: %s", mapping.task_run_id)


def _handle_task_cancelled(payload: dict) -> None:
    """Update mapping when task is cancelled."""
    mapping = TaskRunMapping.objects.get(task_run_id=payload["task_run_id"])
    mapping.status = "cancelled"
    mapping.save(update_fields=["status", "updated_at"])
    logger.info("Task cancelled: %s", mapping.task_run_id)


def _handle_pr_created(payload: dict) -> None:
    """Update mapping with PR details."""
    data = payload.get("data", {})
    mapping = TaskRunMapping.objects.get(task_run_id=payload["task_run_id"])
    mapping.pr_url = data.get("pr_url", "")
    mapping.pr_number = data.get("pr_number")
    mapping.save(update_fields=["pr_url", "pr_number", "updated_at"])
    logger.info("PR created for task: %s (PR: %s)", mapping.task_run_id, mapping.pr_url)
