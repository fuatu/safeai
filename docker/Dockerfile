# ==========================================
# Stage 1: Build React 18 Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Python 3.11 Backend & Static Assets
# ==========================================
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SAFEAI_DB_PATH=/data/safeai.db

# Install bash and curl for local tool execution
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend

# Copy compiled frontend assets from Stage 1
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Persistent SQLite database volume
VOLUME ["/data"]

EXPOSE 8080

ENTRYPOINT ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
