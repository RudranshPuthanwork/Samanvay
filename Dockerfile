# =============================================================================
# Stage 1: Build Frontend Assets
# =============================================================================
FROM node:20-slim AS frontend-builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json vite.config.ts postcss.config.js tailwind.config.js index.html ./
COPY scripts/ ./scripts/
COPY public/ ./public/
COPY src/ ./src/

# Compile frontend bundle and sync MapLibre worker distribution assets
RUN npm run build
RUN node scripts/copy-maplibre.cjs

# =============================================================================
# Stage 2: Production Python Server
# =============================================================================
FROM python:3.11-slim AS runner
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install runtime dependencies for geospatial packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# Copy server code, pre-cached offline data, and compiled frontend
COPY samanvay/ ./samanvay/
COPY public/ ./public/
COPY registry.jsonl ./
COPY --from=frontend-builder /app/dist/ ./dist/

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/zones')" || exit 1

CMD ["python", "-m", "uvicorn", "samanvay.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
