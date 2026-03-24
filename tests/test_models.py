"""Tests for plane_lazy_bird Django models."""

import uuid

import pytest

from plane_lazy_bird.models import AutomationConfig, TaskRunMapping


@pytest.mark.django_db
class TestAutomationConfig:
    def test_create_automation_config(self):
        config = AutomationConfig.objects.create(
            project_id=uuid.uuid4(),
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
            ready_state_name="Ready",
        )
        assert config.id is not None
        assert config.enabled is True
        assert config.ready_state_name == "Ready"
        assert config.in_progress_state_name == "In Progress"
        assert config.review_state_name == "In Review"

    def test_default_values(self):
        config = AutomationConfig.objects.create(
            project_id=uuid.uuid4(),
            lazy_bird_project_id=uuid.uuid4(),
        )
        assert config.enabled is False
        assert config.ready_state_name == "Ready"

    def test_unique_project_id(self):
        project_id = uuid.uuid4()
        AutomationConfig.objects.create(
            project_id=project_id,
            lazy_bird_project_id=uuid.uuid4(),
        )
        with pytest.raises(Exception):  # IntegrityError
            AutomationConfig.objects.create(
                project_id=project_id,
                lazy_bird_project_id=uuid.uuid4(),
            )

    def test_str_representation(self):
        config = AutomationConfig(
            project_id=uuid.uuid4(),
            lazy_bird_project_id=uuid.uuid4(),
            enabled=True,
        )
        assert "enabled" in str(config)

        config.enabled = False
        assert "disabled" in str(config)


@pytest.mark.django_db
class TestTaskRunMapping:
    def test_create_task_run_mapping(self):
        mapping = TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=uuid.uuid4(),
        )
        assert mapping.id is not None
        assert mapping.status == "queued"
        assert mapping.pr_url == ""
        assert mapping.pr_number is None
        assert mapping.error_message == ""

    def test_update_status(self):
        mapping = TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=uuid.uuid4(),
        )
        mapping.status = "running"
        mapping.save()
        mapping.refresh_from_db()
        assert mapping.status == "running"

    def test_update_pr_details(self):
        mapping = TaskRunMapping.objects.create(
            issue_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_run_id=uuid.uuid4(),
        )
        mapping.status = "success"
        mapping.pr_url = "https://github.com/org/repo/pull/42"
        mapping.pr_number = 42
        mapping.save()
        mapping.refresh_from_db()
        assert mapping.pr_url == "https://github.com/org/repo/pull/42"
        assert mapping.pr_number == 42

    def test_str_representation(self):
        mapping = TaskRunMapping(
            issue_id=uuid.uuid4(),
            task_run_id=uuid.uuid4(),
            status="running",
        )
        result = str(mapping)
        assert "running" in result
