import httpx

from biocheminsight_harness.perception import (
    PerceptionRouter,
    assess_quality,
    needs_escalation,
)


def _mock_http(monkeypatch, markdown_by_page):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/pdf-to-markdown":
            return httpx.Response(200, json={"job_id": "j1"})
        if request.url.path == "/v1/jobs/j1":
            return httpx.Response(200, json={"status": "completed"})
        if request.url.path == "/v1/jobs/j1/result":
            return httpx.Response(200, json={"pages": [
                {"page_number": 1, "markdown": markdown_by_page.get(1, "")},
                {"page_number": 2, "markdown": markdown_by_page.get(2, "")},
            ]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx, "post",
        lambda url, **kw: httpx.Client(transport=transport).post(url, **kw))
    monkeypatch.setattr(
        httpx, "get",
        lambda url, **kw: httpx.Client(transport=transport).get(url, **kw))


def test_assess_quality_flags_degenerate_output():
    good = ("Ac-D-Phe-[SEQ ID NO:1] Compound 1 example table with "
            "potency values across endpoints and replicate columns")
    assert assess_quality(good)["quality"] in ("good", "fair")
    assert not needs_escalation(assess_quality(good))
    assert needs_escalation(assess_quality(""))
    assert needs_escalation(assess_quality("abababab" * 40))


def test_route_pages_splits_agent_and_paddle(tmp_path, monkeypatch):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    _mock_http(monkeypatch, {
        1: "Ac-D-Phe-[SEQ ID NO:1] Compound 1 table with potency "
           "values across endpoints and replicate columns",
        2: "short",
    })
    router = PerceptionRouter(base_url="http://paddle")
    out = router.route_pages(pdf, [1, 2, 3], {3: "rotated_table"})
    assert 1 in out["markdowns"]
    assert sorted(out["agent_pages"]) == [2, 3]


def test_route_pages_escalates_degenerate_paddle_output(tmp_path, monkeypatch):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    _mock_http(monkeypatch, {1: "ab" * 300, 2: "Ac-D-Phe compound table "
                                           "with potency values"})
    router = PerceptionRouter(base_url="http://paddle")
    out = router.route_pages(pdf, [1, 2])
    assert 1 in out["agent_pages"]
    assert 1 not in out["markdowns"]
