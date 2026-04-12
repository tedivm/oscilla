"""Tests for FastAPI web application."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from oscilla.www import app


def test_app_exists() -> None:
    """Test that the FastAPI app is properly instantiated."""
    assert app is not None
    assert hasattr(app, "router")


def test_static_files_mounted() -> None:
    """Test that static files are properly mounted."""
    # Check for mounted static files by looking at route paths
    route_paths = []
    for route in app.routes:
        if hasattr(route, "path"):
            route_paths.append(getattr(route, "path"))
        elif hasattr(route, "path_regex"):
            # Mount objects have path_regex instead
            route_paths.append(str(route.path_regex.pattern))

    has_static = any("/static" in str(path) for path in route_paths)
    assert has_static, "Static files should be mounted"


def test_root_redirects_to_app(fastapi_client: TestClient) -> None:
    """Test that root path redirects to /app."""
    response = fastapi_client.get("/", follow_redirects=False)
    assert response.status_code == 307  # Temporary redirect
    assert response.headers["location"] == "/app"


def test_root_redirect_follows(fastapi_client: TestClient) -> None:
    """Test that following redirect from root reaches the frontend mount."""
    response = fastapi_client.get("/", follow_redirects=True)
    # In local and CI tests the frontend build may not exist, so the mount can
    # return 404 even though the redirect itself is correct.
    assert response.status_code in [200, 404]


def test_docs_accessible(fastapi_client: TestClient) -> None:
    """Test that /docs endpoint is accessible."""
    response = fastapi_client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_openapi_schema(fastapi_client: TestClient) -> None:
    """Test that OpenAPI schema is accessible."""
    response = fastapi_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema


def test_static_route_exists() -> None:
    """Test that static route is configured."""
    route_paths = []
    for route in app.routes:
        if hasattr(route, "path"):
            route_paths.append(getattr(route, "path"))
        elif hasattr(route, "path_regex"):
            route_paths.append(str(route.path_regex.pattern))

    has_static = any("/static" in str(path) for path in route_paths)
    assert has_static, "Static files route should be configured"


def test_lifespan_configured() -> None:
    """Test that lifespan context manager is configured."""
    # Check that the app has a lifespan handler
    assert app.router.lifespan_context is not None, "Should have lifespan context configured"


def test_app_can_start(fastapi_client: TestClient) -> None:
    """Test that the app can start successfully."""
    # Making any request will trigger startup event
    response = fastapi_client.get("/docs")
    assert response.status_code == 200


def test_basic_health(fastapi_client: TestClient) -> None:
    """Test basic application health by accessing root."""
    response = fastapi_client.get("/", follow_redirects=False)
    assert response.status_code == 307, "App should redirect from root"


def test_lifespan_skips_broken_game_and_loads_healthy(tmp_path: Path) -> None:
    """Lifespan handler skips a failing game and still loads the healthy one.

    Spec requirement: "If loading any single game raises an exception, the handler
    SHALL log the error at ERROR level with a full traceback and skip that game —
    it MUST NOT abort startup or crash the server."
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from oscilla.www import lifespan

    # Minimal fake registry returned by the healthy game load
    fake_registry: Any = type(
        "_FakeRegistry",
        (),
        {
            "game": type(
                "_FakeGame",
                (),
                {
                    "metadata": type("_Meta", (), {"name": "healthy-game"})(),
                },
            )()
        },
    )()

    call_count = 0

    def _load_side_effect(content_path: Path) -> Any:
        nonlocal call_count
        call_count += 1
        if "broken" in content_path.name:
            raise ValueError("Simulated parse failure")
        return (fake_registry, [])

    # Create two dummy game directories so the lifespan scans both
    (tmp_path / "broken-game").mkdir()
    (tmp_path / "broken-game" / "game.yaml").write_text("invalid: yaml: [")
    (tmp_path / "healthy-game").mkdir()
    (tmp_path / "healthy-game" / "game.yaml").write_text("valid: true")

    test_app = FastAPI(lifespan=lifespan)

    with (
        patch("oscilla.www.settings") as mock_settings,
        patch("oscilla.www.load_from_disk", side_effect=_load_side_effect),
    ):
        mock_settings.games_path = tmp_path
        with TestClient(test_app) as client:
            # Server must start without raising
            response = client.get("/openapi.json")
            assert response.status_code == 200

            # Healthy game is present; broken game is absent
            assert "healthy-game" in test_app.state.registries
            assert "broken-game" not in test_app.state.registries
            # Both directories were attempted
            assert call_count == 2
