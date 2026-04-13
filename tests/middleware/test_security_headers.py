"""Tests for SecurityHeadersMiddleware."""

import pytest
from fastapi.testclient import TestClient

from oscilla.www import app


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client with the full app."""
    return TestClient(app)


def test_security_headers_present(client: TestClient) -> None:
    """All five security headers are present on every response."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in response.headers
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_csp_frame_ancestors(client: TestClient) -> None:
    """frame-ancestors 'none' is present in the Content-Security-Policy header."""
    response = client.get("/health")
    csp = response.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in csp


def test_hsts_includes_subdomains(client: TestClient) -> None:
    """includeSubDomains is present in the Strict-Transport-Security header."""
    response = client.get("/health")
    hsts = response.headers.get("Strict-Transport-Security", "")
    assert "includeSubDomains" in hsts
