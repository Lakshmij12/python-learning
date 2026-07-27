# syntax=docker/dockerfile:1
# Multi-stage build for the FastAPI backend + Celery workers.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: libpq for psycopg, tesseract for OCR.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev tesseract-ocr curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for better layer caching.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".[dev]" || pip install .

# Copy application code.
COPY . .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Production server: gunicorn managing uvicorn workers.
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", "--bind", "0.0.0.0:8000", \
     "--timeout", "120", "--access-logfile", "-"]
