"""DRF serializers for the Lazy-Bird API."""

from rest_framework import serializers

from plane_lazy_bird.models import AutomationConfig, TaskRunMapping


class AutomationConfigSerializer(serializers.ModelSerializer):
    """Serializer for AutomationConfig (read/write).

    project_id is set from the URL, not the request body.
    """

    class Meta:
        model = AutomationConfig
        fields = [
            "id",
            "project_id",
            "lazy_bird_project_id",
            "enabled",
            "ready_state_name",
            "in_progress_state_name",
            "review_state_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project_id", "created_at", "updated_at"]


class TaskRunMappingSerializer(serializers.ModelSerializer):
    """Read-only serializer for TaskRunMapping."""

    class Meta:
        model = TaskRunMapping
        fields = [
            "id",
            "issue_id",
            "project_id",
            "task_run_id",
            "status",
            "pr_url",
            "pr_number",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TriggerTaskSerializer(serializers.Serializer):
    """Write-only serializer for manually triggering a task."""

    project_id = serializers.UUIDField(required=True)
    prompt = serializers.CharField(required=True, min_length=1)
    task_type = serializers.CharField(default="feature", max_length=50, required=False)
    complexity = serializers.ChoiceField(
        choices=["simple", "medium", "complex"],
        required=False,
        allow_null=True,
        default=None,
    )
    metadata = serializers.DictField(required=False, allow_null=True, default=None)


class TestConnectionSerializer(serializers.Serializer):
    """Write-only serializer for testing Lazy-Bird API connection."""

    api_url = serializers.URLField(required=False, allow_blank=True)
    api_key = serializers.CharField(required=False, allow_blank=True)
