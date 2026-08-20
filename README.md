---
title: Rugby Analyzer
emoji: 🏉
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
---

# Rugby Analyzer

Full-stack web application for analyzing rugby match videos using computer vision and AI.

## Features

- Single Player Tracking: Track specific player movement, speed, and distance
- Ball Carrier Tracking: Follow the player in possession
- Ball Tracking: Track the rugby ball throughout the match
- Group Tracking: Monitor positioning of multiple players
- Real-time Analysis: Live video streaming analysis
- AI Integration: NVIDIA Nemotron, OpenAI, Claude, Gemini, Ollama
- Field Calibration: Automatic line detection with manual override

## Tech Stack

- Backend: Python 3.11, FastAPI, Uvicorn, Celery
- CV: YOLO (Ultralytics), ByteTrack, OpenCV
- Frontend: React 18, TypeScript, Vite, TailwindCSS, Konva
- Database: PostgreSQL, SQLAlchemy, Alembic
- Cache/Queue: Redis, Celery
- Deployment: Docker Compose

## Quick Start

```bash
cp .env.example .env
cd backend && uv sync
cd ../frontend && npm install && npm run dev
```

## Docker

```bash
docker-compose up --build
```

## Hugging Face Spaces Deployment

This app is configured for deployment on Hugging Face Spaces using Docker SDK.
A single container runs both the frontend (nginx on port 7860) and backend (uvicorn on port 8000)
managed by supervisord.

```bash
# Build the HF Spaces container locally
docker build -t rugby-analyzer .
docker run -p 7860:7860 rugby-analyzer
```

## Commands

```bash
make test           # Run all tests
make test-backend   # Backend tests only
make test-frontend  # Frontend tests only
make lint           # Lint code
make build          # Production build
```

## Architecture

Hexagonal architecture (ports and adapters) with SOLID principles.
See docs/architecture/ for ISO 42010 documentation.

## Hardware Requirements

- Minimum: GTX 1060 (6GB VRAM), 16GB RAM
- Recommended: GTX 1060 (8GB VRAM), 32GB RAM

## License

MIT
