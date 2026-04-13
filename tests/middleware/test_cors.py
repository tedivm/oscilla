"""Tests for CORSMiddleware configuration."""

import pytest
from fastapi.testclient import TestClient

from oscilla.www import app


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client with the full app."""
    return TestClient(app)


def test_cors_preflight_allowed_origin(client: TestClient) -> None:
    """OPTIONS request from the default allowed origin returns the CORS header."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_preflight_disallowed_origin(client: TestClient) -> None:
    """OPTIONS request from a disallowed origin does not return a permissive wildcard header."""
    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # A disallowed origin must not receive a wildcard or reflected allow-origin header.
    allow_origin = response.headers.get("access-control-allow-origin", "")
    assert allow_origin != "*"
    assert allow_origin != "https://evil.example.com"
