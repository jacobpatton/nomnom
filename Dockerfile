# Stage 1: build dependencies into a virtualenv
FROM python:3.12-slim AS builder

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Stage 2: lean runtime image
FROM python:3.12-slim AS runtime

# Create non-root user
RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid appuser --no-create-home appuser

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy application package only
COPY nomnom/ ./nomnom/

# Data directory (mounted as volume at runtime)
RUN mkdir -p /data && chown appuser:appuser /data

USER appuser

EXPOSE 3002

CMD ["uvicorn", "nomnom.main:app", "--host", "0.0.0.0", "--port", "3002"]
