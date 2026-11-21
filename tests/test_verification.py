"""Multi-evidence cross-validation tests."""
import httpx

from biocheminsight_harness.verification import (
    seq_id_coverage, dual_source_consistency,
    completeness_check, cross_check)


def _mock_inchikey(monkeypatch, keys):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        key = keys[min(calls["n"], len(keys) - 1)]
        calls["n"] += 1
        return httpx.Response(200, json={"inchikey": key})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx, "post",
        lambda url, **kw: httpx.Client(transport=transport).post(url, **kw))


def test_seq_id_coverage_finds_gaps():
    result = seq_id_coverage([163, 164, 166, 167])
    assert result["gaps"] == [165]
    assert result["found"] == 4
    assert result["expected"] == 5


def test_seq_id_coverage_no_gaps():
    result = seq_id_coverage([163, 164, 165])
    assert result["gaps"] == []


def test_dual_source_consistent(monkeypatch):
    _mock_inchikey(monkeypatch, ["LFQSCWFLJHTTHZ-UHFFFAOYNA-N"])
    result = dual_source_consistency("CCO", "OCC")
    assert result["verdict"] == "consistent"


def test_dual_source_disagreed(monkeypatch):
    _mock_inchikey(monkeypatch, ["KEY-A", "KEY-B"])
    result = dual_source_consistency("CCO", "CCC")
    assert result["verdict"] == "disagreed"


def test_dual_source_incomplete_offline(monkeypatch):
    def fail(url, **kw):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "post", fail)
    result = dual_source_consistency("CCO", "OCC")
    assert result["verdict"] == "incomplete"


def test_cross_check_agreement():
    readings = [
        {"compound_id": "C1", "value": "12"},
        {"compound_id": "C1", "value": "12"},
    ]
    result = cross_check(readings, ["compound_id", "value"])
    assert result["verdict"] == "consistent"


def test_cross_check_disagreement():
    readings = [
        {"compound_id": "C1", "value": "12"},
        {"compound_id": "C1", "value": "24"},
    ]
    result = cross_check(readings, ["compound_id", "value"])
    assert result["verdict"] == "disagreed"
    assert result["field"] == "value"
