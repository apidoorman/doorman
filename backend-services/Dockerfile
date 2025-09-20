# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001

WORKDIR /app

# Create non-root user for better container security
RUN groupadd -g 10001 doorman \
  && useradd -m -u 10001 -g 10001 -s /usr/sbin/nologin doorman

COPY backend-services/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend-services /app

# Ensure writable dirs for non-root runtime
RUN mkdir -p /app/logs /app/generated \
  && chown -R doorman:doorman /app

# Switch to non-root user
USER doorman

EXPOSE 5001

# Default to run mode (development users may override with CMD/compose)
CMD ["python", "doorman.py", "run"]
