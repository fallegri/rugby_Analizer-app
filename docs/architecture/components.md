# Component Architecture

## High-Level Components

1. **Frontend (React)** - UI with canvas, charts, real-time updates
2. **API Layer (FastAPI)** - REST endpoints, WebSocket handlers, middleware
3. **Core Domain** - Business logic, use cases, domain models
4. **Ports (Interfaces)** - Abstract contracts for external services
5. **Adapters** - Concrete implementations (AI providers, storage, CV)
6. **Infrastructure** - PostgreSQL, Redis, Celery, filesystem

## Frontend Components

| Component | Responsibility |
|-----------|---------------|
| Pages | Route-level views (Upload, Analysis, Results) |
| Canvas (Konva) | Interactive field visualization, player markers |
| Charts (Recharts) | Performance graphs, speed/distance metrics |
| WebSocket Client | Real-time updates during live analysis |
| Stores (Zustand) | Client-side state management |

## Backend Components

| Component | Responsibility |
|-----------|---------------|
| REST Routes | CRUD for videos, analyses, settings |
| WebSocket Handlers | Real-time frame processing updates |
| Use Cases | Orchestrate domain operations |
| CV Pipeline | YOLO detection, ByteTrack tracking, homography |
| AI Providers | Natural language analysis via multiple LLM backends |
| Task Queue | Async video processing via Celery |

## Communication Patterns

- **REST**: Video upload, configuration, results retrieval
- **WebSocket**: Real-time tracking updates, progress notifications
- **Message Queue**: Background video processing (Celery + Redis)
