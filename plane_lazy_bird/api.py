"""DRF API views for the Lazy-Bird integration.

Provides REST endpoints for managing automation configuration and
task runs from Plane's frontend.
"""

import logging
from uuid import UUID

from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from plane_lazy_bird.client import LazyBirdClient, lazy_bird_client
from plane_lazy_bird.models import AutomationConfig, TaskRunMapping
from plane_lazy_bird.serializers import (
    AutomationConfigSerializer,
    TaskRunMappingSerializer,
    TestConnectionSerializer,
    TriggerTaskSerializer,
)

logger = logging.getLogger(__name__)


# --- Configuration endpoints ---


class AutomationConfigView(APIView):
    """GET/POST automation config for a project (upsert on POST)."""

    def get(self, request: Request, project_id: UUID) -> Response:
        try:
            config = AutomationConfig.objects.get(project_id=project_id)
        except AutomationConfig.DoesNotExist:
            return Response(
                {"error": "No automation config for this project"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AutomationConfigSerializer(config).data)

    def post(self, request: Request, project_id: UUID) -> Response:
        serializer = AutomationConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        config, created = AutomationConfig.objects.update_or_create(
            project_id=project_id,
            defaults=serializer.validated_data,
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(AutomationConfigSerializer(config).data, status=response_status)


class TestConnectionView(APIView):
    """POST to test connectivity to Lazy-Bird API."""

    def post(self, request: Request) -> Response:
        serializer = TestConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        api_url = serializer.validated_data.get("api_url") or None
        api_key = serializer.validated_data.get("api_key") or None

        client = LazyBirdClient(base_url=api_url, api_key=api_key)

        try:
            result = async_to_sync(client.health_check)()
            return Response({"connected": True, "details": result})
        except Exception as e:
            logger.warning("Lazy-Bird connection test failed: %s", e)
            return Response({"connected": False, "error": str(e)})


# --- Task endpoints ---


class TaskRunListView(APIView):
    """GET list of task runs for an issue."""

    def get(self, request: Request, issue_id: UUID) -> Response:
        mappings = TaskRunMapping.objects.filter(issue_id=issue_id).order_by("-created_at")
        return Response(TaskRunMappingSerializer(mappings, many=True).data)


class TriggerTaskView(APIView):
    """POST to manually trigger a Lazy-Bird task for an issue."""

    def post(self, request: Request, issue_id: UUID) -> Response:
        serializer = TriggerTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        project_id = data["project_id"]

        # Check automation config exists
        try:
            config = AutomationConfig.objects.get(project_id=project_id)
        except AutomationConfig.DoesNotExist:
            return Response(
                {"error": "No automation config for this project"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Duplicate prevention
        active = TaskRunMapping.objects.filter(
            issue_id=issue_id,
            status__in=["queued", "running"],
        ).exists()
        if active:
            return Response(
                {"error": "An active task run already exists for this issue"},
                status=status.HTTP_409_CONFLICT,
            )

        # Queue task via async client
        try:
            result = async_to_sync(lazy_bird_client.queue_task)(
                project_id=config.lazy_bird_project_id,
                work_item_id=str(issue_id),
                prompt=data["prompt"],
                task_type=data.get("task_type", "feature"),
                complexity=data.get("complexity"),
                metadata=data.get("metadata"),
            )
        except Exception as e:
            logger.exception("Failed to queue task for issue %s", issue_id)
            return Response(
                {"error": f"Lazy-Bird API error: {type(e).__name__}: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Create local mapping
        mapping = TaskRunMapping.objects.create(
            issue_id=issue_id,
            project_id=project_id,
            task_run_id=result["id"],
            status="queued",
        )
        return Response(
            TaskRunMappingSerializer(mapping).data,
            status=status.HTTP_201_CREATED,
        )


class TaskStatusView(APIView):
    """GET task status (proxied from Lazy-Bird API)."""

    def get(self, request: Request, issue_id: UUID, task_id: UUID) -> Response:
        try:
            mapping = TaskRunMapping.objects.get(id=task_id, issue_id=issue_id)
        except TaskRunMapping.DoesNotExist:
            return Response(
                {"error": "Task run not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = async_to_sync(lazy_bird_client.get_task_status)(mapping.task_run_id)
        except Exception as e:
            logger.exception("Failed to get task status from Lazy-Bird")
            return Response(
                {"error": f"Lazy-Bird API error: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Opportunistically sync local status
        remote_status = result.get("status")
        if remote_status and remote_status != mapping.status:
            mapping.status = remote_status
            mapping.save(update_fields=["status", "updated_at"])

        return Response(result)


class TaskLogsView(APIView):
    """GET task logs (proxied from Lazy-Bird API)."""

    def get(self, request: Request, issue_id: UUID, task_id: UUID) -> Response:
        try:
            mapping = TaskRunMapping.objects.get(id=task_id, issue_id=issue_id)
        except TaskRunMapping.DoesNotExist:
            return Response(
                {"error": "Task run not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 100))
        level = request.query_params.get("level")

        try:
            result = async_to_sync(lazy_bird_client.get_task_logs)(
                mapping.task_run_id,
                page=page,
                page_size=page_size,
                level=level,
            )
        except Exception as e:
            logger.exception("Failed to get task logs from Lazy-Bird")
            return Response(
                {"error": f"Lazy-Bird API error: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(result)


class CancelTaskView(APIView):
    """POST to cancel a task run."""

    def post(self, request: Request, issue_id: UUID, task_id: UUID) -> Response:
        try:
            mapping = TaskRunMapping.objects.get(id=task_id, issue_id=issue_id)
        except TaskRunMapping.DoesNotExist:
            return Response(
                {"error": "Task run not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if mapping.status not in ("queued", "running"):
            return Response(
                {"error": f"Cannot cancel task with status '{mapping.status}'"},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            async_to_sync(lazy_bird_client.cancel_task)(mapping.task_run_id)
        except Exception as e:
            logger.exception("Failed to cancel task in Lazy-Bird")
            return Response(
                {"error": f"Lazy-Bird API error: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        mapping.status = "cancelled"
        mapping.save(update_fields=["status", "updated_at"])
        return Response(TaskRunMappingSerializer(mapping).data)
