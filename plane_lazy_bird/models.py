import uuid

from django.conf import settings
from django.db import models


class AutomationConfig(models.Model):
    """Maps a Plane project to a Lazy-Bird project with automation settings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_id = models.UUIDField(
        unique=True,
        help_text="Plane project UUID (references plane.db.models.Project)",
    )
    lazy_bird_project_id = models.UUIDField(
        help_text="Lazy-Bird project UUID",
    )
    enabled = models.BooleanField(default=False)
    ready_state_name = models.CharField(
        max_length=100,
        default="Ready",
        help_text="Plane state name that triggers task queuing",
    )
    in_progress_state_name = models.CharField(
        max_length=100,
        default="In Progress",
    )
    review_state_name = models.CharField(
        max_length=100,
        default="In Review",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plane_lazy_bird_automation_config"
        verbose_name = "Automation Config"
        verbose_name_plural = "Automation Configs"

    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"AutomationConfig(project={self.project_id}, {status})"


class TaskRunMapping(models.Model):
    """Maps a Plane issue to a Lazy-Bird task run."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue_id = models.UUIDField(
        help_text="Plane issue UUID (references plane.db.models.Issue)",
    )
    project_id = models.UUIDField(
        help_text="Plane project UUID",
    )
    task_run_id = models.UUIDField(
        help_text="Lazy-Bird task run UUID",
    )
    status = models.CharField(
        max_length=50,
        default="queued",
        help_text="Mirrored status from Lazy-Bird (queued, running, success, failed, cancelled, timeout)",
    )
    pr_url = models.URLField(blank=True, default="")
    pr_number = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plane_lazy_bird_task_run_mapping"
        verbose_name = "Task Run Mapping"
        verbose_name_plural = "Task Run Mappings"
        indexes = [
            models.Index(fields=["issue_id"]),
            models.Index(fields=["task_run_id"]),
            models.Index(fields=["project_id", "status"]),
        ]

    def __str__(self) -> str:
        return f"TaskRunMapping(issue={self.issue_id}, task_run={self.task_run_id}, status={self.status})"
