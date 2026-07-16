# API Reference

## Base URL

```
https://api.pl1-migration.example.com/v2
```

All endpoints require OAuth 2.0 bearer token authentication.

## Endpoints

### POST /migrations

Create a new migration job.

**Request:**
```json
{
  "source_schema": "legacy_pl1",
  "target_schema": "modern_v2",
  "tables": ["customers", "orders", "inventory"],
  "options": {
    "batch_size": 1000,
    "validate_before_run": true
  }
}
```

**Response (201):**
```json
{
  "job_id": "mig_abc123",
  "status": "pending",
  "created_at": "2025-06-01T10:00:00Z"
}
```

### GET /migrations/{job_id}

Get migration job status.

**Response (200):**
```json
{
  "job_id": "mig_abc123",
  "status": "running",
  "progress_pct": 45.2,
  "tables_completed": 1,
  "tables_total": 3,
  "started_at": "2025-06-01T10:05:00Z"
}
```

### POST /migrations/{job_id}/rollback

Initiate rollback to pre-migration snapshot.

**Response (202):**
```json
{
  "rollback_id": "rb_xyz789",
  "status": "pending"
}
```

### GET /health

Liveness probe. No authentication required.

### GET /ready

Readiness probe. Checks DB + Redis connectivity.

## Error Format

All errors follow RFC 7807:

```json
{
  "type": "https://api.pl1-migration.example.com/errors/validation",
  "title": "Validation Error",
  "status": 422,
  "detail": "source_schema is required"
}
```

## Rate Limits

| Tier | Requests/min | Burst |
|---|---|---|
| Standard | 100 | 150 |
| Enterprise | 500 | 750 |

Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

## Webhooks

Configure webhook URLs to receive job status updates:

```json
{
  "event": "migration.completed",
  "job_id": "mig_abc123",
  "timestamp": "2025-06-01T12:00:00Z"
}
```

Supported events: `migration.started`, `migration.completed`, `migration.failed`, `rollback.completed`.
