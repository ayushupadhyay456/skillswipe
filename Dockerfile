##############################################################################
# Dockerfile  –  SkillSwap
#
# Multi-stage build:
#   base  – system deps
#   deps  – pip install (cached when requirements.txt unchanged)
#   final – production image
##############################################################################

FROM python:3.11-slim AS base

# System deps for psycopg2 (postgres driver) + bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dependency layer ──────────────────────────────────────────────────────────
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Final image ───────────────────────────────────────────────────────────────
FROM deps AS final
COPY . .

# Non-root user for security
RUN useradd -m skillswap && chown -R skillswap /app
USER skillswap

EXPOSE 5000

# gunicorn + eventlet is required for Flask-SocketIO in production
# -w 1: SocketIO requires exactly 1 worker (multi-worker needs Redis pubsub broker)
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", \
     "--bind", "0.0.0.0:5000", "--timeout", "120", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "app:app"]
