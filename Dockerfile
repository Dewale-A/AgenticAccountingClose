# ============================================================
# Dockerfile for Agentic Accounting Close Assistant
# ============================================================
# Multi-stage build for smaller final image:
#   Stage 1: Install dependencies with Poetry
#   Stage 2: Copy only what's needed to run
# ============================================================

FROM python:3.12-slim AS builder

WORKDIR /app

# Install poetry for dependency management
RUN pip install --no-cache-dir poetry

# Copy dependency files first (Docker layer caching).
# Dependencies are only reinstalled when pyproject.toml changes,
# not when application code changes.
COPY pyproject.toml ./

# Install dependencies into a virtual environment
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root --no-interaction --no-ansi

# ---- Runtime Stage ----
FROM python:3.12-slim

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv .venv

# Copy application code
COPY src/ src/
COPY run_server.py .

# Use the virtual environment's Python
ENV PATH="/app/.venv/bin:$PATH"

# Default environment variables
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV PYTHONPATH=/app

# Expose the API port
EXPOSE 8000

# Health check: verify the server is responding.
# Runs every 30 seconds after a 5-second startup grace period.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the server
CMD ["python", "run_server.py"]
