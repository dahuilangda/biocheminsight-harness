"""Frontend review workspace integration."""
from __future__ import annotations

from .config import biocheminsight_url


def review_workspace_url(task_id: str) -> str:
    return f"{biocheminsight_url().rstrip('/')}/review/{task_id}"


def structures_url(task_id: str) -> str:
    return f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/structures"


def assays_url(task_id: str) -> str:
    return f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/assays"


def merged_url(task_id: str) -> str:
    return f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/merged"
