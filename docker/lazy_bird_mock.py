"""Minimal FastAPI mock of the Lazy-Bird v2.0 REST API.

Returns canned responses for all endpoints consumed by plane_lazy_bird.client.
Validates the X-API-Key header. Stores task-runs in memory so status queries
return consistent data within a test session.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Lazy-Bird Mock API")

VALID_API_KEY = "lb_test_integration_key"

# In-memory store of task runs created during this session
task_runs: Dict[str, Dict[str, Any]] = {}


def _check_api_key(x_api_key: str = Header(default="")) -> None:
    if x_api_key != VALID_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# --- Health ---


@app.get("/api/v1/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "version": "mock-2.0.0"}


# --- Task Runs ---


class QueueTaskRequest(BaseModel):
    project_id: str
    work_item_id: str
    prompt: str
    task_type: str = "feature"
    max_retries: int = 3
    work_item_url: Optional[str] = None
    work_item_title: Optional[str] = None
    work_item_description: Optional[str] = None
    complexity: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@app.post("/api/v1/task-runs")
def queue_task(
    body: QueueTaskRequest,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    task_run = {
        "id": task_id,
        "project_id": body.project_id,
        "work_item_id": body.work_item_id,
        "prompt": body.prompt,
        "task_type": body.task_type,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
    }
    task_runs[task_id] = task_run
    return task_run


@app.get("/api/v1/task-runs/{task_run_id}")
def get_task_status(
    task_run_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if task_run_id not in task_runs:
        # Return a plausible response even for unknown IDs (useful in tests)
        return {
            "id": task_run_id,
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    return task_runs[task_run_id]


@app.post("/api/v1/task-runs/{task_run_id}/cancel")
def cancel_task(
    task_run_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if task_run_id in task_runs:
        task_runs[task_run_id]["status"] = "cancelled"
        task_runs[task_run_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        return task_runs[task_run_id]
    return {
        "id": task_run_id,
        "status": "cancelled",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/task-runs/{task_run_id}/retry")
def retry_task(
    task_run_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if task_run_id in task_runs:
        task_runs[task_run_id]["status"] = "queued"
        task_runs[task_run_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        return task_runs[task_run_id]
    return {
        "id": task_run_id,
        "status": "queued",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/task-runs/{task_run_id}/logs")
def get_task_logs(
    task_run_id: str,
    x_api_key: str = Header(default=""),
    page: int = Query(default=1),
    page_size: int = Query(default=100),
    level: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    return {
        "task_run_id": task_run_id,
        "logs": [],
        "page": page,
        "page_size": page_size,
        "total": 0,
    }


# --- Webhooks ---


class RegisterWebhookRequest(BaseModel):
    url: str
    secret: str
    events: list
    project_id: Optional[str] = None
    description: str = ""


@app.post("/api/v1/webhooks")
def register_webhook(
    body: RegisterWebhookRequest,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    return {
        "id": str(uuid.uuid4()),
        "url": body.url,
        "events": body.events,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
