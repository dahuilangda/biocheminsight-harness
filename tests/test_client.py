"""REST client behavior against a mock transport."""
import json

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


def test_start_full_pipeline_and_status():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tasks/full-pipeline":
            assert request.method == "POST"
            assert json.loads(request.content) == {
                "pdf_id": "abc123",
                "structure_filter_strictness": "strict",
                "assemble_markush": True,
                "perception_provider": "agent",
                "lang": "en",
            }
            return httpx.Response(200, json={"task_id": "t1"})
        assert request.url.path == "/api/tasks/t1"
        return httpx.Response(200, json={"task_id": "t1", "status": "running", "progress": 0.5})

    client = BioChemInsightClient(base_url="http://mock",
                                 http=httpx.Client(transport=httpx.MockTransport(handler)))
    task_id = client.start_full_pipeline("abc123")
    assert task_id == "t1"
    assert client.task(task_id)["status"] == "running"



