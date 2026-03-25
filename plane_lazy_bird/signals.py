"""Django signals for automatic task queuing when Plane issues change state.

This module is imported by apps.py ready() — it registers signal handlers
that react to Plane issue state changes without modifying Plane's core code.

NOTE: These signals connect to Plane's Issue model at runtime.
When running tests without Plane, the signal connection is skipped gracefully.
"""

import asyncio
import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.db.models.signals import post_save

from plane_lazy_bird.models import AutomationConfig, TaskRunMapping

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a synchronous Django signal handler."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an existing event loop (e.g., ASGI server).
        # Schedule as a task — fire-and-forget.
        loop.create_task(coro)
    else:
        # No running loop (e.g., WSGI, management commands).
        asyncio.run(coro)


def _get_issue_model():
    """Dynamically import Plane's Issue model. Returns None if Plane is not installed."""
    try:
        from django.apps import apps
        return apps.get_model("db", "Issue")
    except LookupError:
        return None


def _get_state_model():
    """Dynamically import Plane's State model. Returns None if Plane is not installed."""
    try:
        from django.apps import apps
        return apps.get_model("db", "State")
    except LookupError:
        return None


def connect_signals():
    """Connect signal handlers to Plane's Issue model.

    Called from apps.py ready(). Fails gracefully if Plane models are not available
    (e.g., during tests without a full Plane installation).
    """
    Issue = _get_issue_model()
    if Issue is None:
        logger.debug(
            "Plane Issue model not found — signal handlers not connected. "
            "This is expected when running tests without Plane."
        )
        return

    post_save.connect(on_issue_save, sender=Issue)
    logger.info("Connected Lazy-Bird signal handlers to Plane Issue model")


def on_issue_save(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    """Handle Plane issue post_save — queue task if issue enters Ready state.

    Flow:
    1. Check if automation is enabled for this issue's project
    2. Check if the issue's current state matches the configured ready_state_name
    3. Check for duplicate (already has an active TaskRunMapping)
    4. Queue task in Lazy-Bird
    5. Create TaskRunMapping
    """
    # Skip newly created issues — only react to state changes
    if created:
        return

    # Avoid recursive saves (when we update the issue state ourselves)
    if getattr(instance, "_lazy_bird_updating", False):
        return

    try:
        config = AutomationConfig.objects.get(
            project_id=instance.project_id,
            enabled=True,
        )
    except AutomationConfig.DoesNotExist:
        return

    # Check if the issue's state matches the ready state
    state_name = _get_issue_state_name(instance)
    if state_name != config.ready_state_name:
        return

    # Duplicate detection: skip if there's already an active mapping for this issue
    active_statuses = ["queued", "running"]
    existing = TaskRunMapping.objects.filter(
        issue_id=instance.id,
        status__in=active_statuses,
    ).exists()
    if existing:
        logger.info(
            "Skipping duplicate queue for issue %s — active task run exists",
            instance.id,
        )
        return

    logger.info(
        "Issue %s moved to '%s' state — queuing Lazy-Bird task",
        instance.id,
        config.ready_state_name,
    )

    _run_async(
        _queue_task_for_issue(instance, config)
    )


async def _queue_task_for_issue(issue: Any, config: AutomationConfig) -> None:
    """Queue a task in Lazy-Bird and create the mapping record."""
    from plane_lazy_bird.client import lazy_bird_client

    try:
        # Build prompt from issue details
        title = getattr(issue, "name", "") or str(issue.id)
        description = getattr(issue, "description_html", "") or getattr(issue, "description", "") or ""
        prompt = f"Implement: {title}\n\n{description}".strip()

        result = await lazy_bird_client.queue_task(
            project_id=config.lazy_bird_project_id,
            work_item_id=str(issue.id),
            prompt=prompt,
            work_item_title=title,
            work_item_description=description,
            work_item_url=_get_issue_url(issue),
        )

        # Create mapping (ORM call wrapped for async safety)
        await sync_to_async(TaskRunMapping.objects.create)(
            issue_id=issue.id,
            project_id=issue.project_id,
            task_run_id=result["id"],
            status="queued",
        )

        # Update issue state to In Progress
        await sync_to_async(_update_issue_state)(issue, config.in_progress_state_name)

        logger.info(
            "Queued task run %s for issue %s",
            result["id"],
            issue.id,
        )

    except Exception:
        logger.exception("Failed to queue task for issue %s", issue.id)


def _get_issue_state_name(issue: Any) -> str:
    """Get the current state name of a Plane issue."""
    # Plane issues have a state FK — try to get the name
    state = getattr(issue, "state", None)
    if state is not None:
        return getattr(state, "name", "")
    return ""


def _get_issue_url(issue: Any) -> str:
    """Build a URL for the Plane issue (best-effort)."""
    workspace_slug = ""
    project_identifier = ""
    sequence_id = getattr(issue, "sequence_id", "")

    workspace = getattr(issue, "workspace", None)
    if workspace:
        workspace_slug = getattr(workspace, "slug", "")

    project = getattr(issue, "project", None)
    if project:
        project_identifier = getattr(project, "identifier", "")

    if workspace_slug and project_identifier and sequence_id:
        return f"/{workspace_slug}/projects/{project_identifier}/issues/{sequence_id}"

    return ""


def _update_issue_state(issue: Any, target_state_name: str) -> None:
    """Update a Plane issue's state by name. Sets a flag to prevent recursive signal."""
    State = _get_state_model()
    if State is None:
        logger.warning("Cannot update issue state — Plane State model not available")
        return

    try:
        new_state = State.objects.get(
            project_id=issue.project_id,
            name=target_state_name,
        )
    except State.DoesNotExist:
        logger.warning(
            "State '%s' not found for project %s — issue state not updated",
            target_state_name,
            issue.project_id,
        )
        return

    issue._lazy_bird_updating = True
    try:
        issue.state = new_state
        issue.save(update_fields=["state"])
    finally:
        issue._lazy_bird_updating = False


# Connect signals when the module is imported (called from apps.py ready())
connect_signals()
