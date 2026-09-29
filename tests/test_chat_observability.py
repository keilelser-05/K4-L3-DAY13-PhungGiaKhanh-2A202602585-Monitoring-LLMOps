from __future__ import annotations

import json
import asyncio
from pathlib import Path

import httpx

from app import logging_config
from app.main import app
from app.pii import hash_user_id


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert response_event["quality_score"] == response.json()["quality_score"]
    assert response_event["ttft_ms"] == response.json()["ttft_ms"]
    assert response_event["tool_name"] == "retrieval"
    assert response_event["tool_success"] is True


def test_chat_propagates_request_id_and_enriches_logs(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    monkeypatch.setenv("APP_ENV", "test")

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                headers={"x-request-id": "req-deadbeef"},
                json={
                    "user_id": "fake.user@example.test",
                    "session_id": "session-02",
                    "feature": "qa",
                    "message": "Call me at 090 123 4567",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-deadbeef"
    assert float(response.headers["x-response-time-ms"]) >= 0
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    request_event = next(event for event in records if event["event"] == "request_received")
    assert request_event["correlation_id"] == "req-deadbeef"
    assert request_event["user_id_hash"] == hash_user_id("fake.user@example.test")
    assert request_event["session_id"] == "session-02"
    assert request_event["feature"] == "qa"
    assert request_event["model"]
    assert request_event["env"] == "test"
    assert "fake.user@example.test" not in log_path.read_text(encoding="utf-8")
    assert "090 123 4567" not in log_path.read_text(encoding="utf-8")


def test_chat_generates_request_id_when_header_is_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-03",
                    "session_id": "session-03",
                    "feature": "qa",
                    "message": "Explain logging",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 12
    assert request_id.startswith("req-")
    assert all(character in "0123456789abcdef" for character in request_id[4:])
