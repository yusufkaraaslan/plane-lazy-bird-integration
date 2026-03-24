from django.contrib import admin

from plane_lazy_bird.models import AutomationConfig, TaskRunMapping


@admin.register(AutomationConfig)
class AutomationConfigAdmin(admin.ModelAdmin):
    list_display = [
        "project_id",
        "lazy_bird_project_id",
        "enabled",
        "ready_state_name",
        "updated_at",
    ]
    list_filter = ["enabled"]
    search_fields = ["project_id", "lazy_bird_project_id"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(TaskRunMapping)
class TaskRunMappingAdmin(admin.ModelAdmin):
    list_display = [
        "issue_id",
        "task_run_id",
        "status",
        "pr_url",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["issue_id", "task_run_id"]
    readonly_fields = ["id", "created_at", "updated_at"]
