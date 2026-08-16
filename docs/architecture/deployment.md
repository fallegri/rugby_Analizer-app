# Deployment Architecture

## Local Development

- Frontend dev server on port 5173
- Backend API on port 8000
- PostgreSQL on port 5432
- Redis on port 6379
- GPU (CUDA) for inference

## Docker Compose Deployment

Services orchestrated by Docker Compose:
- **backend**: FastAPI with GPU access
- **frontend**: Nginx serving static React build
- **postgres**: PostgreSQL 16
- **redis**: Redis 7 for caching and message broker
- **celery_worker**: Background task processing with GPU

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | GTX 1060 6GB | GTX 1060 8GB+ |
| RAM | 16GB | 32GB |
| Storage | 50GB SSD | 100GB+ SSD |
| CPU | 4 cores | 8+ cores |

## Scaling

- Multiple Celery workers for parallel video processing
- Redis caching for repeated analyses
- GPU upgrade for faster inference
