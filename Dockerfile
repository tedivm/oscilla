ARG PYTHON_VERSION=3.13

FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json /app/frontend/
RUN npm ci

COPY frontend/ /app/frontend/
RUN npm run build

FROM ghcr.io/multi-py/python-uvicorn:py${PYTHON_VERSION}-slim-LATEST AS backend

ENV APP_MODULE=oscilla.www:app
# Bind to port 8000 (overrides the base image default of 80).
ENV PORT=8000

# Install uv for fast package installation
RUN pip install --no-cache-dir uv
RUN apt-get update && apt-get install -y netcat-traditional && rm -rf /var/lib/apt/lists/*

# Configure UV to compile bytecode and skip dev dependencies
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy
ENV UV_TOOL_BIN_DIR=/usr/local/bin

# Set working directory
WORKDIR /app

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy dependency files
COPY pyproject.toml uv.lock /app/

# Install dependencies only (cached layer)
RUN uv sync --frozen --no-install-project --python /usr/local/bin/python

# Copy application code
COPY ./docker/www/prestart.sh /app/prestart.sh
COPY . /app/

# Install project
RUN uv sync --frozen --no-dev --python /usr/local/bin/python

# Create a non-root user with a fixed UID/GID so file permissions are
# predictable across restarts and host mounts (UID 999 is below the
# normal user range and avoids conflicts with default system accounts).
RUN groupadd -g 999 oscilla && useradd -u 999 -g 999 -s /bin/bash oscilla
USER oscilla

# The python-uvicorn base image reads WEB_CONCURRENCY for worker count.
# UVICORN_WORKERS from .env is forwarded to WEB_CONCURRENCY at runtime.
# Default is 1 worker; set UVICORN_WORKERS in .env to scale up.
CMD ["/bin/bash", "-c", "WEB_CONCURRENCY=${UVICORN_WORKERS:-1} exec /start.sh"]

# Production stage: extends backend with the pre-built frontend assets.
# `docker build .` targets this by default.
# `docker build --target backend .` skips the frontend copy (used by compose.yaml).
FROM backend AS production
COPY --from=frontend-build /app/frontend/build /app/frontend/build
