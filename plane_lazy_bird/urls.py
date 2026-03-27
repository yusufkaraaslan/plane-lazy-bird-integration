from django.urls import path

from plane_lazy_bird.api import (
    AutomationConfigView,
    BatchTaskStatusView,
    CancelTaskView,
    TaskLogsView,
    TaskRunListView,
    TaskStatusView,
    TestConnectionView,
    TriggerTaskView,
)
from plane_lazy_bird.webhooks import lazy_bird_webhook

app_name = "plane_lazy_bird"

urlpatterns = [
    # Webhook receiver (existing)
    path("lazy-bird/", lazy_bird_webhook, name="lazy_bird_webhook"),
    # Configuration API
    path("lazy-bird/config/test-connection/", TestConnectionView.as_view(), name="test_connection"),
    path("lazy-bird/config/<uuid:project_id>/", AutomationConfigView.as_view(), name="automation_config"),
    # Batch API
    path("lazy-bird/issues/batch-status/", BatchTaskStatusView.as_view(), name="batch_task_status"),
    # Task API
    path("lazy-bird/issues/<uuid:issue_id>/tasks/", TaskRunListView.as_view(), name="task_list"),
    path("lazy-bird/issues/<uuid:issue_id>/tasks/trigger/", TriggerTaskView.as_view(), name="trigger_task"),
    path("lazy-bird/issues/<uuid:issue_id>/tasks/<uuid:task_id>/status/", TaskStatusView.as_view(), name="task_status"),
    path("lazy-bird/issues/<uuid:issue_id>/tasks/<uuid:task_id>/logs/", TaskLogsView.as_view(), name="task_logs"),
    path("lazy-bird/issues/<uuid:issue_id>/tasks/<uuid:task_id>/cancel/", CancelTaskView.as_view(), name="cancel_task"),
]
