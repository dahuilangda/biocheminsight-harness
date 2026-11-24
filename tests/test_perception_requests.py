"""Perception requests as the polling tools surface them."""
import httpx
import pytest

from biocheminsight_harness import mcp_server


@pytest.fixture
def deployment(monkeypatch):
    calls = []
    pending = {"requests": [
        {"request_id": "r1", "task_name": "classify_structure_candidate",
         "task_id": "t1", "prompt": "p", "sheet": "/app/output/.perception/requests/r1.png",
         "sheet_url": "/api/tasks/t1/perception/requests/r1/sheet"},
        {"request_id": "r2", "task_name": "structure_page_detection",
         "task_id": "t1", "prompt": "p", "sheet": "/app/output/.perception/requests/r2.png"},
    ], "pending": 12}
    task = {"status": "running", "progress": 0.1, "message": "Detecting", "error": None}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/tasks/t1":
            return httpx.Response(200, json=task)
        if request.url.path == "/api/tasks/t1/perception/requests":
            return httpx.Response(200, json=pending)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    def get(url, **kw):
        kw.pop("auth", None), kw.pop("verify", None)
        return httpx.Client(transport=transport).get(url, **kw)

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr("biocheminsight_harness.config.biocheminsight_url",
                        lambda: "https://deploy.example")
    monkeypatch.setattr("biocheminsight_harness.config.auth_credentials", lambda: None)
    tools = {tool.name: tool.fn for tool in mcp_server.create_server()._tool_manager.list_tools()}
    return tools, calls, pending, task


def test_status_carries_requests_while_the_task_still_reports_running(deployment):
    tools, calls, _pending, task = deployment
    assert task["status"] == "running"
    out = tools["task_status"]("t1")
    waiting = out["awaiting_perception"]
    assert waiting["pending"] == 12
    # ordered by task name, so one batch stays inside one answer contract
    assert [r["request_id"] for r in waiting["requests"]] == ["r1", "r2"]
    assert calls.count("/api/tasks/t1/perception/requests") == 1


def test_requests_carry_a_download_url_and_no_server_path(deployment):
    tools, _calls, _pending, _task = deployment
    for request in tools["pipeline_perception_requests"]("t1"):
        assert "sheet" not in request
        assert request["sheet_url"] == ("https://deploy.example/api/tasks/t1/perception/requests/"
                                        f"{request['request_id']}/sheet")


def test_status_omits_the_block_when_nothing_is_pending(deployment):
    tools, _calls, pending, _task = deployment
    pending.update(requests=[], pending=0)
    assert "awaiting_perception" not in tools["task_status"]("t1")
    assert tools["pipeline_perception_requests"]("t1") == []


def test_status_keeps_the_block_when_only_the_total_is_known(deployment):
    tools, _calls, pending, _task = deployment
    pending.update(requests=[])
    out = tools["task_status"]("t1")
    assert out["awaiting_perception"] == {"pending": 12, "requests": []}
