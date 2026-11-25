"""Perception requests as the polling tools surface them."""
import base64
import json

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


@pytest.mark.parametrize("status, note", [
    ("awaiting_perception", "All answers are in and the task is being resumed. Keep polling."),
    ("pending", "The task is queued or starting; its next requests appear here. Keep polling."),
])
def test_status_says_what_an_idle_task_is_doing(deployment, status, note):
    tools, _calls, pending, task = deployment
    pending["requests"], pending["pending"] = [], 0
    task["status"] = status

    out = tools["task_status"]("t1")

    assert "awaiting_perception" not in out
    assert out["note"] == note


def test_status_adds_no_note_to_a_running_task(deployment):
    tools, _calls, pending, _task = deployment
    pending["requests"], pending["pending"] = [], 0

    assert "note" not in tools["task_status"]("t1")


def test_a_text_question_carries_no_sheet_url(deployment):
    tools, _calls, pending, _task = deployment
    pending["requests"] = [{"request_id": "r9", "task_name": "route_assays_for_content",
                            "task_id": "t1", "prompt": "Which assays does this page mention?"}]

    (request,) = tools["pipeline_perception_requests"]("t1")

    assert "sheet_url" not in request
    assert request["prompt"].startswith("Which assays")


_PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c63000100000500010d2a2db40000000049454e44ae426082")


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


def test_the_batch_tool_returns_each_request_with_its_image(deployment, monkeypatch):
    sheets = []

    def get(request):
        if request.url.path.endswith("/sheet"):
            sheets.append(request.url.path)
            return httpx.Response(200, content=_PNG, headers={"content-type": "image/png"})
        return httpx.Response(200, json={"requests": [
            {"request_id": "r1", "task_name": "roles", "task_id": "t1", "prompt": "Roles?",
             "sheet": "/app/output/.perception/requests/r1.png"},
            {"request_id": "r2", "task_name": "plan", "task_id": "t1", "prompt": "Which assays?"},
        ], "pending": 5})

    server = _session(monkeypatch, get, lambda request: httpx.Response(500))
    result = _run(_call(server, "perception_batch", {"task_id": "t1"}))

    # ordered by task name, so one batch stays inside one answer contract
    assert [block.type for block in result.content] == ["text", "text", "image"]
    question, image_request = (json.loads(block.text) for block in result.content[:2])
    assert (question["request_id"], question["index"], question["batch"]) == ("r2", 1, 2)
    assert (image_request["request_id"], image_request["index"], image_request["pending"]) == ("r1", 2, 5)
    assert (image_request["prompt"], "sheet" in image_request) == ("Roles?", False)
    assert base64.b64decode(result.content[2].data) == _PNG
    assert sheets == ["/api/tasks/t1/perception/requests/r1/sheet"]


def test_the_batch_tool_limits_itself_and_says_when_nothing_is_pending(deployment, monkeypatch):
    def get(request):
        if request.url.path == "/api/tasks/t1":
            return httpx.Response(200, json={"status": "awaiting_perception", "progress": 0.4, "message": "x"})
        return httpx.Response(200, json={"requests": [
            {"request_id": "r1", "task_name": "roles", "task_id": "t1", "prompt": "Roles?", "sheet": "s.png"},
            {"request_id": "r2", "task_name": "plan", "task_id": "t1", "prompt": "Which assays?"},
        ], "pending": 2})

    server = _session(monkeypatch, get, lambda request: httpx.Response(500))
    one = _run(_call(server, "perception_batch", {"task_id": "t1", "limit": 1}))
    assert [block.type for block in one.content] == ["text"]
    assert json.loads(one.content[0].text)["batch"] == 1

    def nothing(request):
        return get(request) if request.url.path == "/api/tasks/t1" else httpx.Response(200, json={"requests": [], "pending": 0})

    server = _session(monkeypatch, nothing, lambda request: httpx.Response(500))
    empty = _run(_call(server, "perception_batch", {"task_id": "t1"}))
    note = json.loads(empty.content[0].text)
    assert note["pending"] == 0
    assert note["note"] == "All answers are in and the task is being resumed. Keep polling."


def test_the_answers_tool_submits_a_whole_batch(deployment, monkeypatch):
    posted = []

    def post(request):
        import json as _json
        posted.append(_json.loads(request.content))
        return httpx.Response(200, json={"answered": "x", "pending": 1})

    def get(request):
        return httpx.Response(200, json={"requests": [], "pending": 3})

    server = _session(monkeypatch, get, post)
    result = _run(_call(server, "perception_answers", {"task_id": "t1", "answers": json.dumps([
        {"request_id": "r1", "answer": {"boxes": {}}},
        {"request_id": "r2", "answer": '{"assays": []}'},
    ])}))

    assert json.loads(result.content[0].text) == {"results": [
        {"request_id": "r1", "ok": True, "answered": "x", "pending": 1},
        {"request_id": "r2", "ok": True, "answered": "x", "pending": 1}], "pending": 3}
    assert posted == [{"answer": '{"boxes": {}}'}, {"answer": '{"assays": []}'}]


def test_a_rejected_answer_is_reported_not_raised(deployment, monkeypatch):
    def post(request):
        return httpx.Response(422, json={"error": "answer for roles missing required keys ['boxes']"})

    server = _session(monkeypatch, lambda request: httpx.Response(200, json={"requests": [], "pending": 1}), post)
    result = _run(_call(server, "perception_answers",
                        {"task_id": "t1", "answers": '[{"request_id": "r9", "answer": {}}]'}))

    assert json.loads(result.content[0].text)["results"] == [
        {"request_id": "r9", "ok": False, "error": "answer for roles missing required keys ['boxes']"}]
