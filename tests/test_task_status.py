"""What task_status reports while a task runs and once it completes."""
import json

import httpx
import pytest

from biocheminsight_harness import mcp_server


@pytest.fixture(autouse=True)
def clean_samples():
    mcp_server._ETA_SAMPLES.clear()
    yield
    mcp_server._ETA_SAMPLES.clear()


def _session(monkeypatch, get, post):
    transport = httpx.MockTransport(lambda request: get(request) if request.method == "GET" else post(request))

    def call(client_method, url, **kw):
        assert "auth" not in kw
        kw.pop("verify", None)
        return getattr(httpx.Client(transport=transport), client_method)(url, **kw)

    monkeypatch.setattr(httpx, "get", lambda url, **kw: call("get", url, **kw))
    monkeypatch.setattr(httpx, "post", lambda url, **kw: call("post", url, **kw))
    monkeypatch.setattr("biocheminsight_harness.config.biocheminsight_url",
                        lambda: "https://deploy.example")
    return mcp_server.create_server()._mcp_server


def _run(coro):
    import asyncio
    return asyncio.run(coro)


async def _call(server, name, arguments):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server) as session:
        return await session.call_tool(name, arguments)


def _task(status="running", progress=0.2, **extra):
    return {"task_id": "t1", "type": "full_pipeline", "status": status, "progress": progress,
            "message": "Working", "error": None, "created_at": "2026-11-27T10:00:00",
            "updated_at": "2026-11-27T10:05:00", **extra}


def _handler(states):
    """GET /api/tasks/t1 answers each state in order; perception requests stay empty."""
    remaining = list(states)

    def get(request):
        if request.url.path == "/api/tasks/t1":
            return httpx.Response(200, json=remaining.pop(0))
        return httpx.Response(200, json={"requests": [], "pending": 0})

    return get


def _status(server, monkeypatch=None):
    out = _run(_call(server, "task_status", {"task_id": "t1"}))
    return json.loads(out.content[0].text)


def test_status_carries_the_deployments_timestamps_and_queue_position(monkeypatch):
    def get(request):
        if request.url.path == "/api/tasks/t1":
            return httpx.Response(200, json=_task(queue_position=2))
        return httpx.Response(200, json={"requests": [], "pending": 0})

    server = _session(monkeypatch, get, lambda request: httpx.Response(500))
    out = _status(server)

    assert out["created_at"] == "2026-11-27T10:00:00"
    assert out["updated_at"] == "2026-11-27T10:05:00"
    assert out["queue_position"] == 2


def test_status_estimates_the_remaining_time_from_the_observed_pace(monkeypatch):
    get = _handler([_task(progress=0.2), _task(progress=0.5)])
    server = _session(monkeypatch, get, lambda request: httpx.Response(500))

    _status(server)
    # pretend 100 active seconds passed between the two polls
    sample = mcp_server._ETA_SAMPLES["t1"]
    sample["first_seen"] -= 120
    sample["last"] -= 100

    out = _status(server)

    # half of 100 s per 0.3 progress
    assert out["elapsed_seconds"] == 120
    assert out["eta_seconds"] == 167


def test_the_perception_wait_is_kept_out_of_the_pace(monkeypatch):
    get = _handler([_task(progress=0.2), _task(progress=0.2, status="awaiting_perception"),
                    _task(progress=0.5)])
    server = _session(monkeypatch, get, lambda request: httpx.Response(500))

    _status(server)
    sample = mcp_server._ETA_SAMPLES["t1"]
    sample["first_seen"] -= 40
    sample["last"] -= 30

    _status(server)
    # the task then waited ten minutes for answers before running again
    sample["last"] -= 600

    out = _status(server)

    # only the 30 running seconds count, not the ten minutes of waiting
    assert out["eta_seconds"] == 50


def test_without_a_pace_there_is_no_estimate(monkeypatch):
    get = _handler([_task(progress=0.2), _task(progress=0.2)])
    server = _session(monkeypatch, get, lambda request: httpx.Response(500))

    _status(server)
    out = _status(server)

    assert out["elapsed_seconds"] >= 0
    assert "eta_seconds" not in out


def test_a_completed_task_returns_download_and_table_links(monkeypatch):
    def get(request):
        if request.url.path == "/api/tasks/t1":
            return httpx.Response(200, json=_task(progress=1.0, status="completed", message="Completed"))
        return httpx.Response(200, json={"requests": [], "pending": 0})

    server = _session(monkeypatch, get, lambda request: httpx.Response(500))
    out = _status(server)

    assert out["result"]["download_url"] == "https://deploy.example/api/tasks/t1/download"
    assert sorted(out["result"]["tables"]) == ["assays", "sar", "structures"]
    assert out["result"]["tables"]["structures"] == "https://deploy.example/api/tasks/t1/structures"


def test_task_list_trims_each_task_and_filters_by_status(monkeypatch):
    seen = {}

    def get(request):
        seen["query"] = dict(request.url.params)
        return httpx.Response(200, json={"tasks": [
            {"task_id": "t1", "type": "full_pipeline", "status": "completed", "progress": 1.0,
             "message": "Completed", "updated_at": "2026-11-27T09:00:00", "result_path": "/x", "params": {}},
            {"task_id": "t2", "type": "structures", "status": "running", "progress": 0.4,
             "message": "Working", "updated_at": "2026-11-27T09:30:00", "result_path": None, "params": {}},
        ]})

    server = _session(monkeypatch, get, lambda request: httpx.Response(500))
    out = json.loads(_run(_call(server, "task_list", {"status": "running"})).content[0].text)

    # the deployment filters on the status; the tool passes the query
    # through and trims each task to what a caller needs
    assert seen["query"]["status"] == "running"
    assert [task["task_id"] for task in out["tasks"]] == ["t1", "t2"]
    assert set(out["tasks"][0]) == {"task_id", "type", "status", "progress",
                                    "message", "updated_at"}


@pytest.mark.parametrize(("table", "key"), [
    ("structures", "records"),
    ("assays", "records"),
    ("merged", "records"),
    ("sar", "units"),
])
def test_task_tables_reads_deployment_records(monkeypatch, table, key):
    row = {"COMPOUND_ID": "A", "PAGE_NUM": 14}
    server = _session(monkeypatch, lambda request: httpx.Response(200, json={key: [row]}),
                      lambda request: httpx.Response(500))
    result = _run(_call(server, "task_tables", {"task_id": "t1", "table": table}))
    assert not result.isError
    assert json.loads(result.content[0].text) == row


@pytest.mark.parametrize(("task_type", "parameter"), [
    ("structure_extraction", "structureTask"),
    ("full_pipeline", "fullPipelineTask"),
])
def test_open_review_workspace_restores_pdf_and_task(monkeypatch, task_type, parameter):
    from urllib.parse import parse_qs, urlsplit

    task = _task(status="completed", pdf_id="pdf-1", type=task_type, progress=1)
    server = _session(monkeypatch, lambda request: httpx.Response(200, json=task),
                      lambda request: httpx.Response(500))
    result = _run(_call(server, "open_review_workspace", {"task_id": "t1"}))
    assert not result.isError
    url = urlsplit(json.loads(result.content[0].text)["url"])
    assert url.path == "/"
    assert parse_qs(url.query) == {"pdf": ["pdf-1"], parameter: ["t1"], "step": ["4"]}
