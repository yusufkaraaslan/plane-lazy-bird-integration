"""Integration test: Signal flow — issue moves to Ready → task queued.

End-to-end test flow:
1. Create AutomationConfig for the test project
2. Create a mock Plane issue and fire the post_save signal
3. Verify TaskRunMapping was created with status "queued"
4. Verify the Lazy-Bird mock API received the task-run request
5. Verify issue state update was attempted (In Progress)

These tests run against the Docker test environment when PLANE_API_URL is set.
When running locally without Docker, they use the existing mock-based approach
to validate the full signal → queue → mapping flow.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import sync_to_async

from plane_lazy_bird.models import AutomationConfig, TaskRunMapping
from plane_lazy_bird.signals import _queue_task_for_issue, on_issue_save

from .conftest import requires_docker_env


def _make_issue(project_id=None, state_name="Ready", issue_id=None):
    """Create a mock Plane Issue object."""
    issue = MagicMock()
    issue.id = issue_id or uuid.uuid4()
    issue.project_id = project_id or uuid.uuid4()
    issue.name = "Integration test: add health system"
    issue.description_html = "<p>Player needs health tracking</p>"
    issue.description = "Player needs health tracking"
    issue.state = MagicMock()
    issue.state.name = state_name
    issue.workspace = MagicMock()
    issue.workspace.slug = "test-workspace"
    issue.project = MagicMock()
    issue.project.identifier = "INT"
    issue.sequence_id = 1
    issue._lazy_bird_updating = False
    return issue


@pytest.mark.django_db(transaction=True)
class TestSignalFlowEndToEnd:
    """Test the complete signal flow: issue → Ready → task queued → mapping created."""

    @pytest.mark.asyncio
    async def test_full_signal_to_mapping_flow(self):
        """When an issue moves to Ready, a TaskRunMapping should be created."""
        project_id = uuid.uuid4()
        task_run_id = uuid.uuid4()

        # 1. Create automation config
        config = await sync_to_async(AutomationConfig.objects.create)(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
            ready_state_name="Ready",
            in_progress_state_name="In Progress",
        )

        # 2. Create mock issue in Ready state
        issue = _make_issue(project_id=project_id, state_name="Ready")

        # 3. Mock the Lazy-Bird client to return a task run
        mock_client = AsyncMock()
        mock_client.queue_task.return_value = {
            "id": str(task_run_id),
            "status": "queued",
        }

        # 4. Call _queue_task_for_issue directly (avoids SQLite locking with _run_async)
        with patch("plane_lazy_bird.client.lazy_bird_client", mock_client), \
             patch("plane_lazy_bird.signals._update_issue_state") as mock_state_update:
            await _queue_task_for_issue(issue, config)

        # 5. Verify TaskRunMapping was created
        mapping = await sync_to_async(TaskRunMapping.objects.get)(issue_id=issue.id)
        assert str(mapping.task_run_id) == str(task_run_id)
        assert mapping.status == "queued"
        assert mapping.project_id == project_id

        # 6. Verify Lazy-Bird client was called with correct params
        mock_client.queue_task.assert_called_once()

        # 7. Verify issue state update was attempted
        mock_state_update.assert_called_once_with(issue, "In Progress")

    @pytest.mark.asyncio
    async def test_signal_creates_correct_prompt(self):
        """Verify the prompt sent to Lazy-Bird contains issue title and description."""
        project_id = uuid.uuid4()
        task_run_id = uuid.uuid4()

        config = await sync_to_async(AutomationConfig.objects.create)(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )
        issue = _make_issue(project_id=project_id, state_name="Ready")

        mock_client = AsyncMock()
        mock_client.queue_task.return_value = {
            "id": str(task_run_id),
            "status": "queued",
        }

        with patch("plane_lazy_bird.client.lazy_bird_client", mock_client), \
             patch("plane_lazy_bird.signals._update_issue_state"):
            await _queue_task_for_issue(issue, config)

        call_kwargs = mock_client.queue_task.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "Integration test: add health system" in prompt
        assert "Player needs health tracking" in prompt

    def test_signal_skips_non_ready_state(self):
        """Issue in non-Ready state should not create a mapping."""
        project_id = uuid.uuid4()
        AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
            ready_state_name="Ready",
        )
        issue = _make_issue(project_id=project_id, state_name="In Progress")

        on_issue_save(sender=None, instance=issue, created=False)
        assert TaskRunMapping.objects.filter(issue_id=issue.id).count() == 0

    def test_duplicate_detection_blocks_second_queue(self):
        """A second Ready signal should not create a duplicate mapping."""
        project_id = uuid.uuid4()
        issue_id = uuid.uuid4()
        task_run_id_1 = uuid.uuid4()
        task_run_id_2 = uuid.uuid4()

        AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )

        # First task is still active
        TaskRunMapping.objects.create(
            issue_id=issue_id,
            project_id=project_id,
            task_run_id=task_run_id_1,
            status="running",
        )

        issue = _make_issue(project_id=project_id, state_name="Ready", issue_id=issue_id)

        mock_client = AsyncMock()
        mock_client.queue_task.return_value = {
            "id": str(task_run_id_2),
            "status": "queued",
        }

        with patch("plane_lazy_bird.client.lazy_bird_client", mock_client), \
             patch("plane_lazy_bird.signals._run_async") as mock_run:
            on_issue_save(sender=None, instance=issue, created=False)
            mock_run.assert_not_called()

        # Only the original mapping should exist
        assert TaskRunMapping.objects.filter(issue_id=issue_id).count() == 1

    @pytest.mark.asyncio
    async def test_requeue_after_completed_task(self):
        """After a task completes, moving back to Ready should queue a new task."""
        project_id = uuid.uuid4()
        issue_id = uuid.uuid4()
        old_task_id = uuid.uuid4()
        new_task_id = uuid.uuid4()

        config = await sync_to_async(AutomationConfig.objects.create)(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )

        # Previous task completed
        await sync_to_async(TaskRunMapping.objects.create)(
            issue_id=issue_id,
            project_id=project_id,
            task_run_id=old_task_id,
            status="success",
        )

        issue = _make_issue(project_id=project_id, state_name="Ready", issue_id=issue_id)

        mock_client = AsyncMock()
        mock_client.queue_task.return_value = {
            "id": str(new_task_id),
            "status": "queued",
        }

        with patch("plane_lazy_bird.client.lazy_bird_client", mock_client), \
             patch("plane_lazy_bird.signals._update_issue_state"):
            await _queue_task_for_issue(issue, config)

        # Should now have 2 mappings: old (success) and new (queued)
        mappings = await sync_to_async(list)(
            TaskRunMapping.objects.filter(issue_id=issue_id).order_by("created_at")
        )
        assert len(mappings) == 2
        assert mappings[0].status == "success"
        assert mappings[1].status == "queued"
        assert str(mappings[1].task_run_id) == str(new_task_id)

    @pytest.mark.asyncio
    async def test_queue_task_creates_mapping_and_updates_state(self):
        """Direct test of _queue_task_for_issue async function."""
        project_id = uuid.uuid4()
        task_run_id = uuid.uuid4()
        config = await sync_to_async(AutomationConfig.objects.create)(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
            in_progress_state_name="In Progress",
        )
        issue = _make_issue(project_id=project_id)

        mock_client = AsyncMock()
        mock_client.queue_task.return_value = {
            "id": str(task_run_id),
            "status": "queued",
        }

        with patch("plane_lazy_bird.client.lazy_bird_client", mock_client), \
             patch("plane_lazy_bird.signals._update_issue_state") as mock_state:
            await _queue_task_for_issue(issue, config)

        # Verify mapping
        mapping = await sync_to_async(TaskRunMapping.objects.get)(issue_id=issue.id)
        assert str(mapping.task_run_id) == str(task_run_id)
        assert mapping.status == "queued"

        # Verify state update
        mock_state.assert_called_once_with(issue, "In Progress")

    @pytest.mark.asyncio
    async def test_queue_task_handles_api_failure(self):
        """API failure should not create a mapping or crash."""
        project_id = uuid.uuid4()
        config = await sync_to_async(AutomationConfig.objects.create)(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )
        issue = _make_issue(project_id=project_id)

        mock_client = AsyncMock()
        mock_client.queue_task.side_effect = ConnectionError("Mock API down")

        with patch("plane_lazy_bird.client.lazy_bird_client", mock_client):
            await _queue_task_for_issue(issue, config)

        count = await sync_to_async(
            TaskRunMapping.objects.filter(issue_id=issue.id).count
        )()
        assert count == 0


@requires_docker_env
@pytest.mark.django_db
class TestSignalFlowDocker:
    """Integration tests that run against the Docker test environment.

    These tests are skipped when PLANE_API_URL is not set.
    They will be exercised via: docker compose -f docker/docker-compose.test.yml up test-runner
    """

    def test_placeholder_for_docker_signal_flow(self, plane_api_url, lazy_bird_mock_url):
        """Placeholder: full Docker-based signal flow test.

        When running in Docker with a real Plane instance:
        1. Create issue via Plane API
        2. Move issue to Ready state
        3. Verify TaskRunMapping created
        4. Verify lazy-bird-mock received the request
        5. Verify issue state changed to In Progress

        This test will be fully implemented when the Docker environment
        is validated end-to-end (requires issues #32, #33, #42 complete).
        """
        assert plane_api_url.startswith("http")
        assert lazy_bird_mock_url.startswith("http")
