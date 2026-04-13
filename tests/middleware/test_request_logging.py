"""Tests for RequestLoggingMiddleware."""

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from oscilla.www import app


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client with the full app."""
    return TestClient(app)


def test_request_id_in_log(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """A request_start log record is emitted with a valid UUID request_id."""
    with caplog.at_level(logging.INFO, logger="oscilla.middleware.request_logging"):
        client.get("/health")

    start_records = [r for r in caplog.records if r.message == "request_start"]
    assert len(start_records) >= 1
    record = start_records[0]
    # request_id must be a valid UUID string
    request_id = record.__dict__.get("request_id", "")
    assert uuid.UUID(str(request_id))  # raises if invalid


def test_request_end_logs_status_code(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """A request_end log record is emitted containing the HTTP status code."""
    with caplog.at_level(logging.INFO, logger="oscilla.middleware.request_logging"):
        client.get("/health")

    end_records = [r for r in caplog.records if r.message == "request_end"]
    assert len(end_records) >= 1
    status_code = end_records[0].__dict__.get("status_code")
    assert status_code == 200


def test_duration_ms_is_non_negative(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """The duration_ms field in request_end is a non-negative integer."""
    with caplog.at_level(logging.INFO, logger="oscilla.middleware.request_logging"):
        client.get("/health")

    end_records = [r for r in caplog.records if r.message == "request_end"]
    assert len(end_records) >= 1
    duration_ms = end_records[0].__dict__.get("duration_ms")
    assert isinstance(duration_ms, int)
    assert duration_ms >= 0
