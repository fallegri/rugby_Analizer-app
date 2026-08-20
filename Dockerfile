# =============================================================================
# Hugging Face Spaces Dockerfile
# Single container serving React frontend (nginx :7860) + FastAPI backend (uvicorn :8000)
# =============================================================================

# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ .

# In HF Spaces, frontend talks to backend on same origin via nginx proxy
ENV VITE_API_URL=/api
ENV VITE_WS_URL=

RUN npm run build

# Stage 2: Install Backend Dependencies
FROM python:3.11-slim AS backend-build

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --no-dev --frozen

COPY backend/src ./src

# Stage 3: Final Runtime
FROM python:3.11-slim

# Install nginx, supervisord, and CV dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend with virtualenv
COPY --from=backend-build /app/backend /app/backend

# Copy frontend build output
COPY --from=frontend-build /app/dist /usr/share/nginx/html

# Copy nginx config for HF Spaces (port 7860)
COPY nginx.hf.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# Copy supervisord config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create required directories
RUN mkdir -p /app/backend/uploads /app/backend/models /app/backend/results

# Set environment
ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PYTHONPATH="/app/backend"
ENV YOLO_DEVICE=cpu
ENV DEBUG=true

WORKDIR /app/backend

EXPOSE 7860

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
