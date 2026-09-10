# Marine Quantum Runtime — Docker Image
# Multi-stage build: slim production image with optional quantum support

ARG PYTHON_VERSION=3.11

# ── Base stage ───────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ── Core runtime (no external deps) ──────────────────────────────────────────
FROM base AS core

COPY requirements.txt .
# Runtime core requires no pip installs — stdlib only.
# Install API server deps only.
RUN pip install --no-cache-dir fastapi uvicorn pydantic

COPY . .

EXPOSE 8000
ENV PORT=8000 \
    ENV=production \
    LOG_LEVEL=info

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT} --workers 2"]

# ── Quantum stage (includes qiskit-aer — ~800MB larger) ─────────────────────
FROM core AS quantum

RUN pip install --no-cache-dir qiskit qiskit-aer

# To build:   docker build --target quantum -t marine-runtime:quantum .
# To run:     docker run -p 8000:8000 -e RUNTIME_API_KEY=your-key marine-runtime:quantum
