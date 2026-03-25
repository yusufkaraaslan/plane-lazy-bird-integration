"""Tests for signal handlers that auto-queue tasks on issue state changes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import sync_to_async

from plane_lazy_bird.models import AutomationConfig, TaskRunMapping
from plane_lazy_bird.signals import (
    _get_issue_state_name,
    _queue_task_for_issue,
    on_issue_save,
)


def _make_issue(project_id=None, state_name="Ready", issue_id=None):
    """Create a mock Plane Issue object."""
    issue = MagicMock()
    issue.id = issue_id or uuid.uuid4()
    issue.project_id = project_id or uuid.uuid4()
    issue.name = "Add health system"
    issue.description_html = "<p>Player needs health tracking</p>"
    issue.description = "Player needs health tracking"
    issue.state = MagicMock()
    issue.state.name = state_name
    issue.workspace = MagicMock()
    issue.workspace.slug = "my-workspace"
    issue.project = MagicMock()
    issue.project.identifier = "PROJ"
    issue.sequence_id = 42
    issue._lazy_bird_updating = False
    return issue


@pytest.mark.django_db
class TestOnIssueSave:
    def test_skips_newly_created_issues(self):
        """Signal should not fire for brand new issues."""
        issue = _make_issue()
        # created=True means the issue was just created, not updated
        on_issue_save(sender=None, instance=issue, created=True)
        # No error, no task queued — nothing to assert except no crash

    def test_skips_when_no_automation_config(self):
        """Signal should do nothing if no AutomationConfig exists for the project."""
        issue = _make_issue()
        on_issue_save(sender=None, instance=issue, created=False)
        assert TaskRunMapping.objects.count() == 0

    def test_skips_when_automation_disabled(self):
        """Signal should do nothing if automation is disabled."""
        project_id = uuid.uuid4()
        AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=False,
        )
        issue = _make_issue(project_id=project_id, state_name="Ready")
        on_issue_save(sender=None, instance=issue, created=False)
        assert TaskRunMapping.objects.count() == 0

    def test_skips_when_state_does_not_match(self):
        """Signal should do nothing if issue state doesn't match ready_state_name."""
        project_id = uuid.uuid4()
        AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
            ready_state_name="Ready",
        )
        issue = _make_issue(project_id=project_id, state_name="In Progress")
        on_issue_save(sender=None, instance=issue, created=False)
        assert TaskRunMapping.objects.count() == 0

    def test_skips_duplicate_active_task(self):
        """Signal should not queue if there's already an active task for this issue."""
        project_id = uuid.uuid4()
        issue_id = uuid.uuid4()
        AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )
        TaskRunMapping.objects.create(
            issue_id=issue_id,
            project_id=project_id,
            task_run_id=uuid.uuid4(),
            status="running",
        )
        issue = _make_issue(project_id=project_id, state_name="Ready", issue_id=issue_id)

        with patch("plane_lazy_bird.signals._run_async") as mock_run:
            on_issue_save(sender=None, instance=issue, created=False)
            mock_run.assert_not_called()

    def test_allows_requeue_after_completed_task(self):
        """Signal should queue if all previous tasks are completed (not active)."""
        project_id = uuid.uuid4()
        issue_id = uuid.uuid4()
        AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )
        TaskRunMapping.objects.create(
            issue_id=issue_id,
            project_id=project_id,
            task_run_id=uuid.uuid4(),
            status="success",  # Completed — not active
        )
        issue = _make_issue(project_id=project_id, state_name="Ready", issue_id=issue_id)

        with patch("plane_lazy_bird.signals._run_async") as mock_run:
            on_issue_save(sender=None, instance=issue, created=False)
            mock_run.assert_called_once()

    def test_queues_task_when_conditions_met(self):
        """Signal should queue task when automation enabled and state is Ready."""
        project_id = uuid.uuid4()
        config = AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )
        issue = _make_issue(project_id=project_id, state_name="Ready")

        with patch("plane_lazy_bird.signals._run_async") as mock_run:
            on_issue_save(sender=None, instance=issue, created=False)
            mock_run.assert_called_once()

    def test_skips_recursive_save(self):
        """Signal should not fire when _lazy_bird_updating flag is set."""
        project_id = uuid.uuid4()
        AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )
        issue = _make_issue(project_id=project_id, state_name="Ready")
        issue._lazy_bird_updating = True

        with patch("plane_lazy_bird.signals._run_async") as mock_run:
            on_issue_save(sender=None, instance=issue, created=False)
            mock_run.assert_not_called()


@pytest.mark.django_db
class TestQueueTaskForIssue:
    @pytest.mark.asyncio
    async def test_creates_mapping_on_success(self):
        """_queue_task_for_issue should create a TaskRunMapping."""
        project_id = uuid.uuid4()
        task_run_id = uuid.uuid4()
        config = await sync_to_async(AutomationConfig.objects.create)(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )
        issue = _make_issue(project_id=project_id)

        mock_client = AsyncMock()
        mock_client.queue_task.return_value = {"id": str(task_run_id), "status": "queued"}

        with patch("plane_lazy_bird.client.lazy_bird_client", mock_client), \
             patch("plane_lazy_bird.signals._update_issue_state"):
            await _queue_task_for_issue(issue, config)

        mock_client.queue_task.assert_called_once()
        mapping = await sync_to_async(TaskRunMapping.objects.get)(issue_id=issue.id)
        assert str(mapping.task_run_id) == str(task_run_id)
        assert mapping.status == "queued"

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(self):
        """_queue_task_for_issue should not crash on API failure."""
        project_id = uuid.uuid4()
        config = await sync_to_async(AutomationConfig.objects.create)(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )
        issue = _make_issue(project_id=project_id)

        mock_client = AsyncMock()
        mock_client.queue_task.side_effect = Exception("Connection refused")

        with patch("plane_lazy_bird.client.lazy_bird_client", mock_client):
            await _queue_task_for_issue(issue, config)

        # No mapping created for this specific issue on failure
        count = await sync_to_async(
            TaskRunMapping.objects.filter(issue_id=issue.id).count
        )()
        assert count == 0


class TestGetIssueStateName:
    def test_returns_state_name(self):
        issue = _make_issue(state_name="Ready")
        assert _get_issue_state_name(issue) == "Ready"

    def test_returns_empty_when_no_state(self):
        issue = MagicMock()
        issue.state = None
        assert _get_issue_state_name(issue) == ""
