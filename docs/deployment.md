# Deployment Guide

## Prerequisites

- Docker 24+ and Docker Compose v2
- Python 3.11+
- Access to OAuth provider credentials (see authentication.md)
- AWS credentials for S3 artifact storage (or LocalStack for dev)

## Local Development

```bash
git clone https://github.com/example/pl1-migration.git
cd pl1-migration
cp .env.example .env
docker compose up -d postgres redis
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `OAUTH_CLIENT_ID` | Yes | OAuth client ID |
| `OAUTH_CLIENT_SECRET` | Yes | OAuth client secret |
| `S3_BUCKET` | Yes | S3 bucket for migration artifacts |
| `LOG_LEVEL` | No | Default: `INFO` |

## Staging Deployment

Staging deploys automatically on merge to `main` via GitHub Actions.

1. Push to `main` branch
2. CI runs tests + builds Docker image
3. Image pushed to ECR
4. ArgoCD syncs to staging cluster
5. Smoke tests run against staging URL

## Production Deployment

Production requires manual approval in GitHub Actions:

1. Go to Actions → "Deploy Production"
2. Click "Run workflow", select tag
3. Two approvers required (team lead + on-call)
4. Blue-green deployment with automatic rollback on health check failure

## Rollback Procedure

If a production deployment fails:

```bash
kubectl rollout undo deployment/pl1-migration -n production
```

Or use the admin API:

```bash
curl -X POST https://api.pl1.example.com/admin/rollback \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"version": "v2.3.1"}'
```

## Monitoring Post-Deploy

After any deployment, verify:

- [ ] `/health` returns 200
- [ ] `/ready` returns 200
- [ ] Prometheus metrics flowing
- [ ] No error rate spike in Grafana dashboard
- [ ] OAuth token flow works end-to-end

## Known Issues

- Helm chart version 1.4.x has a known issue with Redis password injection — use 1.5.0+
- Celery worker memory leak fixed in v2.4.0; do not deploy older versions
