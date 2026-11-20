"""REST client behavior against a mock transport."""
import httpx

from biocheminsight_harness.client import BioChemInsightClient


def _client(routes: dict[str, dict]) -> BioChemInsightClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in routes:
            return httpx.Response(200, json=routes[path])
        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    return BioChemInsightClient(base_url="http://mock",
                                http=httpx.Client(transport=transport))


def test_upload_returns_pdf_id(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    client = _client({"/api/pdfs": {"pdf_id": "abc123", "total_pages": 9}})
    assert client.upload_pdf(pdf) == "abc123"


def test_start_full_pipeline_and_status(tmp_path):
    client = _client({
        "/api/tasks/full-pipeline": {"task_id": "t1"},
        "/api/tasks/t1": {"task_id": "t1", "status": "running",
                          "progress": 0.5},
    })
    task_id = client.start_full_pipeline("abc123")
    assert task_id == "t1"
    assert client.task(task_id)["status"] == "running"


def test_wait_for_task_returns_terminal_state():
    states = iter([{"status": "running"}, {"status": "completed"}])

    client = _client({"/api/tasks/t9": {}})
    monkey = lambda: next(states)
    client_http_states = states

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(client_http_states))

    transport = httpx.MockTransport(handler)
    client.http = httpx.Client(transport=transport)
    task = client.wait_for_task("t9", poll_seconds=0.01)
    assert task["status"] == "completed"


def test_wait_for_task_times_out():
    client = _client({"/api/tasks/t9": {}})
    client.http = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status": "running"})))
    import pytest
    with pytest.raises(TimeoutError):
        client.wait_for_task("t9", poll_seconds=0.01, timeout_seconds=0.05)
