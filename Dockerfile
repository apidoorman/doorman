# Multi-service image: Python backend (Doorman) + Next.js web client
# Supports env files via entrypoint; override envs at runtime as needed.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install Node.js + npm and useful tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       nodejs npm curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Backend dependencies first for better layer caching
COPY backend-services/requirements.txt /app/backend-services/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r /app/backend-services/requirements.txt

# Copy full repo
COPY . /app

# Build web client (Next.js)
WORKDIR /app/web-client
RUN npm ci \
    && npm run build

# Runtime configuration
WORKDIR /app

# Add entrypoint
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 5001 3000

CMD ["/app/docker/entrypoint.sh"]
