"""HTTP-level tests for the FastAPI app (docpilot/api.py)."""
import dataclasses
import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from docpilot.api import create_app  # noqa: E402
from docpilot.service import DocPilot  # noqa: E402

KEY = "test-key"
COVERED = "What is the default isolation level in PostgreSQL?"
UNCOVERED = "What is the default port of MongoDB?"


@pytest.fixture(scope="module")
def api_dp(settings):
    # Own instance: the shared `dp` fixture's semantic cache would otherwise leak between test files.
    return DocPilot(settings)


def _client(settings, dp, **overrides):
    s = dataclasses.replace(settings, **{"api_keys": [KEY], "rate_per_min": 1000, **overrides})
    return TestClient(create_app(s, dp))


@pytest.fixture(scope="module")
def client(settings, api_dp):
    return _client(settings, api_dp)


def test_health_is_open(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["chunks"] > 0


def test_ask_answers_covered_question(client):
    r = client.post("/ask", json={"question": COVERED}, headers={"X-API-Key": KEY})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] and not body["abstained"]


def test_ask_abstains_on_uncovered_question(client):
    r = client.post("/ask", json={"question": UNCOVERED}, headers={"X-API-Key": KEY})
    assert r.status_code == 200, r.text
    assert r.json()["abstained"]


def test_ask_requires_api_key(client):
    assert client.post("/ask", json={"question": COVERED}).status_code == 401
    assert client.post("/ask", json={"question": COVERED},
                       headers={"X-API-Key": "wrong"}).status_code == 401


def test_ask_validates_body(client):
    r = client.post("/ask", json={"question": "hi"}, headers={"X-API-Key": KEY})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "question"]


def test_stats(client):
    r = client.get("/stats", headers={"X-API-Key": KEY})
    assert r.status_code == 200, r.text


def test_stream_ends_with_done_event(client):
    r = client.post("/ask/stream", json={"question": COVERED}, headers={"X-API-Key": KEY})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [e for e in r.text.split("\n\n") if e.strip()]
    assert events[-1].startswith("event: done")
    done = json.loads(events[-1].split("data: ", 1)[1])
    assert done["answer"] and not done["abstained"]


def test_rate_limit_returns_429(settings, api_dp):
    c = _client(settings, api_dp, rate_per_min=2)
    codes = [c.get("/stats", headers={"X-API-Key": KEY}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
