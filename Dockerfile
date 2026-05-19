# syntax=docker/dockerfile:1.7

# --- Builder: install deps into a virtualenv -------------------------------
# A venv (not pip --prefix) is the idiomatic pattern: the venv's python
# automatically resolves its own site-packages without needing PYTHONPATH
# tricks. Copying the venv into the runtime image keeps the runtime small.
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY requirements.txt ./
RUN pip install -r requirements.txt

# --- Runtime: minimal image, non-root user ---------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app"

# Non-root user owns the app dir so it can write places.db on first boot.
RUN useradd --create-home --shell /bin/bash app \
 && mkdir -p /app/data \
 && chown -R app:app /app /opt

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app src ./src
COPY --chown=app:app data ./data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

# Seed on first boot if the DB doesn't exist, then start the API.
CMD ["sh", "-c", "[ -f places.db ] || python -m src.seed; exec uvicorn src.main:app --host 0.0.0.0 --port 8000"]
