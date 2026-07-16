# PL1 Migration Service — Architecture

## System Overview

The PL1 Migration Service is a backend API that orchestrates data migration from legacy PL1 systems to the modern data platform. It handles schema mapping, batch job scheduling, and rollback management.

## Components

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  API Gateway │────▶│ Auth Service │────▶│ Migration Engine │
│  (FastAPI)   │     │  (OAuth 2.0) │     │  (Celery workers)│
└─────────────┘     └──────────────┘     └─────────────────┘
       │                                         │
       ▼                                         ▼
┌─────────────┐                          ┌─────────────────┐
│  PostgreSQL  │                          │  Redis (queue)   │
│  (metadata)  │                          │  + S3 (artifacts)│
└─────────────┘                          └─────────────────┘
```

## API Gateway

- Framework: **FastAPI 0.110+**
- Authentication: OAuth 2.0 JWT bearer tokens (see `authentication.md`)
- Rate limiting via Redis sliding window
- All endpoints return JSON; errors follow RFC 7807

## Migration Engine

- Celery workers process migration jobs asynchronously
- Each job has states: `pending → validating → running → completed | failed`
- Rollback snapshots stored in S3 with 30-day retention
- Maximum concurrent jobs per tenant: 5

## Data Stores

| Store | Purpose | Version |
|---|---|---|
| PostgreSQL | Job metadata, user sessions, audit log | 15.x |
| Redis | Task queue, rate limit counters | 7.x |
| S3 | Migration artifacts, rollback snapshots | N/A |

## Deployment

- Containerized via Docker; orchestrated on Kubernetes
- Helm chart in `deploy/helm/`
- CI/CD: GitHub Actions → staging → manual promote to production
- Health checks: `/health` (liveness), `/ready` (readiness)

## Observability

- Structured JSON logging (stdlib `logging` + `python-json-logger`)
- Metrics exported via Prometheus `/metrics` endpoint
- Distributed tracing with OpenTelemetry (Jaeger backend)
- Alerting: PagerDuty for P1, Slack for P2/P3

## API Versioning

Current version: **v2**. v1 deprecated as of 2025-01-15; sunset date 2025-07-01.
