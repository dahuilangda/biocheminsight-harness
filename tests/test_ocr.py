import httpx
import pytest

from biocheminsight_harness.ocr import OcrClient


def _transport(submit_result, status_result, fetch_result):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/pdf-to-markdown":
            return httpx.Response(200, json=submit_result)
        if request.url.path == "/v1/jobs/j1":
            return httpx.Response(200, json=status_result)
        if request.url.path == "/v1/jobs/j1/result":
            return httpx.Response(200, json=fetch_result)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _run(tmp_path, monkeypatch, fetch_result):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    transport = _transport({"job_id": "j1"}, {"status": "completed"},
                           fetch_result)
    monkeypatch.setattr(
        httpx, "post",
        lambda url, **kw: httpx.Client(transport=transport).post(url, **kw))
    monkeypatch.setattr(
        httpx, "get",
        lambda url, **kw: httpx.Client(transport=transport).get(url, **kw))
    return OcrClient(base_url="http://paddle")


def test_chunk_markdown_maps_relative_page_numbers_by_position(
        tmp_path, monkeypatch):
    client = _run(tmp_path, monkeypatch, {"pages": [
        {"page_number": 1, "markdown": "first"},
        {"page_number": 2, "markdown": "second"},
    ]})
    out = client._chunk_markdown(tmp_path / "doc.pdf", [25, 26], "en")
    assert out == {25: "first", 26: "second"}


def test_chunk_markdown_prefers_absolute_page_numbers(tmp_path, monkeypatch):
    client = _run(tmp_path, monkeypatch, {"pages": [
        {"page_number": 7, "markdown": "seven"},
        {"page_number": 8, "markdown": "eight"},
    ]})
    out = client._chunk_markdown(tmp_path / "doc.pdf", [7, 8], "en")
    assert out == {7: "seven", 8: "eight"}


def test_chunk_markdown_raises_on_count_mismatch(tmp_path, monkeypatch):
    client = _run(tmp_path, monkeypatch,
                  {"pages": [{"page_number": 1, "markdown": "only"}]})
    with pytest.raises(RuntimeError):
        client._chunk_markdown(tmp_path / "doc.pdf", [5, 6], "en")
