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
        kw.pop("auth", None), kw.pop("verify", None)
        return getattr(httpx.Client(transport=transport), client_method)(url, **kw)

    monkeypatch.setattr(httpx, "get", lambda url, **kw: call("get", url, **kw))
    monkeypatch.setattr(httpx, "post", lambda url, **kw: call("post", url, **kw))
    monkeypatch.setattr("biocheminsight_harness.config.biocheminsight_url",
                        lambda: "https://deploy.example")
    monkeypatch.setattr("biocheminsight_harness.config.auth_credentials", lambda: None)
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
