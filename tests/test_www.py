"""Tests for FastAPI web application."""

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


def test_root_redirects_to_docs(fastapi_client: TestClient) -> None:
    """Test that root path redirects to /docs."""
    response = fastapi_client.get("/", follow_redirects=False)
    assert response.status_code == 307  # Temporary redirect
    assert response.headers["location"] == "/docs"


def test_root_redirect_follows(fastapi_client: TestClient) -> None:
    """Test that following redirect from root goes to docs."""
    response = fastapi_client.get("/", follow_redirects=True)
    assert response.status_code == 200
    # Should reach the OpenAPI docs page


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
    response = fastapi_client.get("/")
    assert response.status_code in [200, 307], "App should respond to requests"
