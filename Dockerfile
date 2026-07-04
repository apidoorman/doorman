FROM rust:1.88-slim-bookworm AS rust-builder
WORKDIR /build/gateway-rs
COPY gateway-rs/Cargo.toml gateway-rs/Cargo.lock gateway-rs/rust-toolchain.toml ./
COPY gateway-rs/src ./src
RUN cargo build --locked --release

# Multi-service image: Rust gateway + Python platform service + Next.js web client
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
ARG NEXT_PUBLIC_GATEWAY_URL=

# Build Next.js - domain agnostic, no hardcoded URLs
RUN echo "export NEXT_PUBLIC_PROTECTED_USERS=${NEXT_PUBLIC_PROTECTED_USERS}" > /tmp/build-env.sh && \
    echo "export NEXT_PUBLIC_GATEWAY_URL=${NEXT_PUBLIC_GATEWAY_URL}" >> /tmp/build-env.sh && \
    echo "export NODE_ENV=production" >> /tmp/build-env.sh && \
    echo "export NEXT_TELEMETRY_DISABLED=1" >> /tmp/build-env.sh && \
    . /tmp/build-env.sh && \
    npm run build && \
    npm prune --omit=dev

COPY --from=rust-builder /build/gateway-rs/target/release/doorman-gateway /usr/local/bin/doorman-gateway

# Runtime configuration
WORKDIR /app

# Add entrypoint
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 3001 3000

CMD ["/app/docker/entrypoint.sh"]
