# syntax=docker/dockerfile:1.7

# --- Builder: install deps into an isolated prefix --------------------------
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt ./
RUN pip install --prefix=/install -r requirements.txt

# --- Runtime: minimal image, non-root user ---------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/app"

# Create non-root user; assign owned data dir for the SQLite file
RUN useradd --create-home --shell /bin/bash app \
 && mkdir -p /app/data \
 && chown -R app:app /app

WORKDIR /app

COPY --from=builder /install /install
COPY --chown=app:app src ./src
COPY --chown=app:app data ./data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Seed on first boot if the DB doesn't exist, then start the API
CMD ["sh", "-c", "[ -f places.db ] || python -m src.seed; exec uvicorn src.main:app --host 0.0.0.0 --port 8000"]
