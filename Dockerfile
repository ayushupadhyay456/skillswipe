##############################################################################
# Dockerfile  –  SkillSwap
#
# Multi-stage build:
#   base  – system deps
#   deps  – pip install (cached when requirements.txt unchanged)
#   final – production image
##############################################################################

FROM python:3.12-slim AS base

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
CMD ["python", "app.py"]
