"""The deployment probe: connectivity, round-trip times and the slow-path note."""
import httpx
import pytest

from biocheminsight_harness import mcp_server


@pytest.fixture
def deployment(monkeypatch):
    """A transport that advances a fake clock by a configured number of
    seconds per host, so the probe measures exactly that delay."""
    latency = {}
    failing = set()
    clock = [0.0]

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        clock[0] += latency.get(host, 0.02)
        if host in failing:
            return httpx.Response(500)
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)

    def get(url, **kw):
        kw.pop("auth", None), kw.pop("verify", None)
        return httpx.Client(transport=transport).get(url, **kw)

    monkeypatch.setattr(mcp_server.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(mcp_server, "biocheminsight_url",
                        lambda: "https://deploy.example")
    monkeypatch.setattr("biocheminsight_harness.config.harness_url",
                        lambda: "https://chem.example")
    monkeypatch.setattr("biocheminsight_harness.config.ocr_url",
                        lambda: "https://ocr.example")
    monkeypatch.setattr(mcp_server, "auth_credentials", lambda: None)
    tools = {tool.name: tool.fn for tool in mcp_server.create_server()._tool_manager.list_tools()}
    return tools["deployment_status"], latency, failing


def test_reports_connectivity_and_roundtrip_for_every_endpoint(deployment):
    status, _latency, failing = deployment
    failing.add("chem.example")
    out = status()
    assert (out["pipeline"], out["harness_chemistry"], out["ocr_service"]) == (True, False, True)
    assert out["connected"] is True
    assert out["roundtrip_ms"] == {"pipeline": 20, "harness_chemistry": 20, "ocr_service": 20}
    assert "note" not in out


def test_warns_when_the_deployment_answers_slowly(deployment):
    status, latency, _failing = deployment
    latency["deploy.example"] = 1.5
    latency["chem.example"] = 2.25
    out = status()
    assert out["roundtrip_ms"] == {"pipeline": 1500, "harness_chemistry": 2250, "ocr_service": 20}
    assert "BIOCHEMINSIGHT_URL" in out["note"]
    assert out["connected"] is True


def test_a_slow_ocr_service_alone_does_not_trigger_the_note(deployment):
    status, latency, _failing = deployment
    latency["ocr.example"] = 3.0
    assert "note" not in status()
