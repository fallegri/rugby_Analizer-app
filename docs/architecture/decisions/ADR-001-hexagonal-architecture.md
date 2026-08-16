# ADR-001: Hexagonal Architecture (Ports & Adapters)

## Status

Accepted

## Date

2024-01-15

## Context

The Rugby Analyzer integrates with multiple external services:
- Multiple AI providers (NVIDIA, OpenAI, Claude, Gemini, Ollama)
- Computer vision models (YOLO, potentially others)
- Storage backends (local filesystem, cloud storage)
- Databases (PostgreSQL)
- Message queues (Redis/Celery)

The system must be testable without GPU or external API keys.

## Decision

We adopt Hexagonal Architecture (Ports and Adapters).

### Rules

1. Core contains domain models with NO external imports.
2. Ports define abstract interfaces using Python ABCs.
3. Adapters implement ports for each external service.
4. Dependency direction always points inward.
5. Dependency injection wires adapters to ports at startup.

## Consequences

### Positive
- AI providers are interchangeable without touching core logic
- Tests can mock any external dependency via ports
- Clear boundaries prevent accidental coupling

### Negative
- More initial boilerplate
- Developers must understand the architecture
- Indirection can make debugging slightly harder
