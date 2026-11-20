"""Chemistry client calls against the harness endpoints."""
import json

import httpx
import pytest

from biocheminsight_harness import chemistry
from biocheminsight_harness.config import harness_url


@pytest.fixture
def harness_http(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/harness/parse-notation":
            return httpx.Response(200, json={"tokens": ["ac", "I", "H", "Ogl"],
                                             "linear": True})
        if request.url.path == "/v1/harness/mass-arbitration":
            payload = json.loads(request.content.decode())
            return httpx.Response(200, json={"accepted": True,
                                             "convention": "exact",
                                             "delta": 0.0})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "post",
                        lambda url, json=None, timeout=None:
                        httpx.Client(transport=transport).post(url, json=json,
                                                               timeout=timeout))


def test_parse_notation_calls_harness(harness_http):
    parsed = chemistry.parse_notation("ac-I-H-Ogl-T-I")
    assert parsed["tokens"][:2] == ["ac", "I"]


def test_mass_arbitration_round_trip(harness_http):
    verdict = chemistry.mass_arbitration("Cc1ccccc1", 92.063)
    assert verdict["accepted"] is True
    assert verdict["convention"] == "exact"


def test_default_url_points_at_deployment():
    assert ":8011" in harness_url()
