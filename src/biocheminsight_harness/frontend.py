"""Frontend review workspace integration."""
from __future__ import annotations

from urllib.parse import urlencode

from . import config


def review_workspace_url(task_id: str, pdf_id: str, task_type: str) -> str:
    task_query = {
        "structure_extraction": "structureTask",
        "full_pipeline": "fullPipelineTask",
    }.get(task_type)
    if task_query is None or not pdf_id:
        raise ValueError("A PDF-backed structure or full pipeline task is required")
    query = urlencode({"pdf": pdf_id, task_query: task_id, "step": 4})
    return f"{config.biocheminsight_url().rstrip('/')}/?{query}"


def task_table_urls(task_id: str, task_type: str) -> dict[str, str]:
    names = {
        "structure_extraction": ("structures", "sar"),
        "full_pipeline": ("structures", "assays", "sar"),
        "bioactivity_extraction": ("assays",),
        "data_merge": ("merged",),
    }.get(task_type, ())
    base = config.biocheminsight_url().rstrip("/")
    return {name: f"{base}/api/tasks/{task_id}/{name}" for name in names}


def structures_url(task_id: str) -> str:
    return f"{config.biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/structures"


def assays_url(task_id: str) -> str:
    return f"{config.biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/assays"


def merged_url(task_id: str) -> str:
    return f"{config.biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/merged"
