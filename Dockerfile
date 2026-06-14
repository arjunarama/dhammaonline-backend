# ── dhammaonline-backend container image ──────────────────────────────
# Small FastAPI app. python:3.12-slim keeps the image lean; psycopg2-binary
# and bcrypt ship prebuilt wheels so we don't need a compiler in the image.
FROM python:3.12-slim

# PYTHONUNBUFFERED → logs appear immediately in `kubectl logs` (no buffering).
# PYTHONDONTWRITEBYTECODE → no .pyc clutter in the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install dependencies FIRST, in their own layer. Docker caches this layer and
# only re-runs it when requirements.txt changes — so code edits rebuild fast.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the application code.
COPY . .

# Document the port the app listens on (informational; the Service maps to it).
EXPOSE 8080

# Shell form so ${PORT} is expanded at runtime. uvicorn binds 0.0.0.0 so the
# container accepts traffic from outside the pod.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
