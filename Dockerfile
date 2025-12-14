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
    && npm i -g npm@^10 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Backend dependencies first for better layer caching
COPY backend-services/requirements.txt /app/backend-services/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r /app/backend-services/requirements.txt

# Prepare web client dependencies separately for better caching
WORKDIR /app/web-client
COPY web-client/package*.json ./
RUN npm ci --include=dev

# Copy backend source only (avoid copying entire repo)
WORKDIR /app
COPY backend-services /app/backend-services

# Copy web client sources (excluding node_modules via .dockerignore)
WORKDIR /app/web-client
COPY web-client/ .

# Build web client (Next.js)
# Build-time args for frontend env (baked into Next.js bundle)
ARG NEXT_PUBLIC_PROTECTED_USERS=

# Build Next.js - domain agnostic, no hardcoded URLs
RUN echo "export NEXT_PUBLIC_PROTECTED_USERS=${NEXT_PUBLIC_PROTECTED_USERS}" > /tmp/build-env.sh && \
    echo "export NODE_ENV=production" >> /tmp/build-env.sh && \
    echo "export NEXT_TELEMETRY_DISABLED=1" >> /tmp/build-env.sh && \
    . /tmp/build-env.sh && \
    npm run build && \
    npm prune --omit=dev

# Runtime configuration
WORKDIR /app

# Add entrypoint
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 3001 3000

CMD ["/app/docker/entrypoint.sh"]
