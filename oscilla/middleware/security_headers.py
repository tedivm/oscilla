"""Security headers middleware for oscilla.

Adds HTTP security headers to every response to mitigate common web
vulnerabilities (XSS, clickjacking, MIME sniffing, etc.).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related HTTP response headers to every response.

    Headers applied:
    - Strict-Transport-Security: enforces HTTPS for one year including sub-domains.
    - X-Content-Type-Options: prevents MIME-type sniffing.
    - X-Frame-Options: prevents embedding in iframes (clickjacking).
    - Content-Security-Policy: restricts resource loading to same-origin.
      `unsafe-inline` is required in style-src for SvelteKit's inline <style>
      injection — removing it would break the frontend's scoped CSS.
    - Referrer-Policy: limits referrer information sent on cross-origin requests.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            # unsafe-inline is required for SvelteKit's scoped CSS injection
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
