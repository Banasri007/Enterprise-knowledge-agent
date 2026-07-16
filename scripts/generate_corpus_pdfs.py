"""Generate bundled Acme Corp PDF documentation corpus for demo."""

from __future__ import annotations
import matplotlib
from pathlib import Path
import urllib.request
from fpdf import FPDF
FONT_PATH = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"
CORPUS_DIR = Path(__file__).resolve().parent.parent / "docs" / "corpus"

DOCUMENTS: dict[str, str] = {
    "authentication_guide.pdf": """Acme Corp - Nexus Integration Hub
Authentication & Identity Guide

Overview
The Nexus Integration Hub uses OAuth 2.0 with JWT bearer tokens for all API authentication.
Enterprise clients authenticate via SAML 2.0 SSO federated to our OAuth provider.
Every client request must include a valid OAuth access token obtained through the authorization code flow.

Configuration
Set the following environment variables:
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_TOKEN_URL=https://auth.nexus.acme-corp.example.com/oauth/token
OAUTH_SCOPES=read,write,admin
SAML_IDP_METADATA_URL=https://sso.acme-corp.example.com/metadata

Token Validation
The API gateway validates tokens on every request:
1. Extract bearer token from Authorization header
2. Verify JWT signature against the OAuth provider JWKS endpoint
3. Check token expiry and required scopes
4. Map OAuth sub claim to internal enterprise user ID

Supported Grant Types
Authorization Code — Active — Web applications and enterprise SSO
Client Credentials — Active — Service-to-service integrations
Resource Owner Password — Deprecated — Legacy only, do not use
API Key (header) — Not supported — N/A

Security Requirements
- Tokens must expire within 1 hour
- Refresh tokens rotate on every use
- All OAuth endpoints require TLS 1.2+
- Rate limiting: 100 token requests per minute per client
- SOC 2 Type II audit logging on all auth events

Migration Notes
The platform team evaluated API key authentication in Q3 2024 but decided to retain OAuth 2.0
and SAML SSO as the sole authentication mechanisms. API keys were deemed insufficient for
Acme Corp multi-tenant audit and compliance requirements.
""",
    "architecture_overview.pdf": """Acme Corp - Nexus Integration Hub
Architecture Overview

System Overview
The Nexus Integration Hub is Acme Corp enterprise middleware connecting ERP (SAP), CRM (Salesforce),
HRIS (Workday), and legacy mainframe systems. It handles event routing, schema transformation,
and real-time sync orchestration across 40+ downstream systems.

Components
API Gateway (FastAPI) connects to Auth Service (OAuth 2.0 + SAML SSO) and Integration Engine
(Celery workers). PostgreSQL stores metadata; Redis handles queues; Kafka handles event streaming.

API Gateway
- Framework: FastAPI 0.110+
- Authentication: OAuth 2.0 JWT bearer tokens (see authentication_guide.pdf)
- Rate limiting via Redis sliding window
- All endpoints return JSON; errors follow RFC 7807

Integration Engine
- Celery workers process sync jobs asynchronously
- Each job has states: pending, validating, running, completed, failed
- Rollback snapshots stored in S3 with 30-day retention
- Maximum concurrent jobs per tenant: 5

Data Stores
PostgreSQL 15.x — Job metadata, user sessions, audit log
Redis 7.x — Task queue, rate limit counters
Kafka 3.x — Event streaming between connectors
S3 — Sync artifacts, rollback snapshots

Deployment
Containerized via Docker; orchestrated on Kubernetes (Acme Corp EKS cluster).
Helm chart in deploy/helm/. CI/CD: GitHub Actions to staging to manual promote to production.
Health checks: /health (liveness), /ready (readiness).

Observability
Structured JSON logging, Prometheus /metrics, OpenTelemetry tracing (Jaeger backend).
Alerting: PagerDuty for P1, Slack for P2/P3.

API Versioning
Current version: v2. v1 deprecated as of 2025-01-15; sunset date 2025-07-01.
""",
    "api_reference.pdf": """Acme Corp - Nexus Integration Hub
API Reference v2

Base URL
https://api.nexus.acme-corp.example.com/v2

All endpoints require OAuth 2.0 bearer token authentication.

POST /integrations
Create a new integration sync job.
Request body includes source_system, target_system, entity_types, and options.
Response 201 returns job_id, status pending, and created_at timestamp.

GET /integrations/{job_id}
Get integration job status including progress_pct, entities_completed, entities_total.

POST /integrations/{job_id}/rollback
Initiate rollback to pre-sync snapshot. Returns 202 with rollback_id.

GET /health — Liveness probe. No authentication required.
GET /ready — Readiness probe. Checks DB, Redis, and Kafka connectivity.

Error Format
All errors follow RFC 7807 with type, title, status, and detail fields.

Rate Limits
Standard tier: 100 requests/min, burst 150
Enterprise tier: 500 requests/min, burst 750
Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

Webhooks
Configure webhook URLs for job status updates.
Supported events: integration.started, integration.completed, integration.failed, rollback.completed.
""",
    "deployment_guide.pdf": """Acme Corp - Nexus Integration Hub
Deployment Guide

Prerequisites
- Docker 24+ and Docker Compose v2
- Python 3.11+
- Access to OAuth provider credentials (see authentication_guide.pdf)
- AWS credentials for S3 artifact storage

Local Development
git clone https://github.com/acme-corp/nexus-integration-hub.git
cd nexus-integration-hub
cp .env.example .env
docker compose up -d postgres redis kafka
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

Environment Variables
DATABASE_URL — PostgreSQL connection string (required)
REDIS_URL — Redis connection string (required)
OAUTH_CLIENT_ID — OAuth client ID (required)
OAUTH_CLIENT_SECRET — OAuth client secret (required)
S3_BUCKET — S3 bucket for sync artifacts (required)
KAFKA_BOOTSTRAP_SERVERS — Kafka brokers (required)

Staging Deployment
Staging deploys automatically on merge to main via GitHub Actions.
Push to main, CI runs tests and builds Docker image, ArgoCD syncs to staging cluster.

Production Deployment
Production requires manual approval in GitHub Actions with two approvers.
Blue-green deployment with automatic rollback on health check failure.

Rollback Procedure
kubectl rollout undo deployment/nexus-integration-hub -n production
Or use admin API POST https://api.nexus.acme-corp.example.com/admin/rollback

Monitoring Post-Deploy
Verify /health returns 200, /ready returns 200, Prometheus metrics flowing,
no error rate spike in Grafana, OAuth token flow works end-to-end.

Known Issues
Helm chart 1.4.x has Redis password injection bug — use 1.5.0+
Celery worker memory leak fixed in v2.4.0; do not deploy older versions
""",
    "data_model.pdf": """Acme Corp - Nexus Integration Hub
Data Model & Schema Mapping

Overview
The Nexus Integration Hub maps legacy mainframe data structures and SaaS API payloads
to Acme Corp canonical v2 schema. This document describes mapping rules and validation logic.

Source Systems
SAP ERP — Customer master, order headers, inventory (IDoc format)
Salesforce CRM — Accounts, opportunities, contacts (REST API v58)
Workday HRIS — Employee records, org units (SOAP API)
Legacy Mainframe — Fixed-width EBCDIC tables (CUSTMAST, ORDHDR, ORDDTL, INVMST)

Target Schema (Canonical v2)
Modern tables use UTF-8, JSONB metadata columns, and UUID primary keys.
customers from SAP KNA1 and legacy CUSTMAST
orders from SAP VBAK plus ORDDTL line items nested as JSONB
employees from Workday Worker API

Validation Rules
Before a sync job runs, the engine validates:
1. Schema compatibility — all source fields have a mapping
2. Referential integrity — foreign keys resolvable in target
3. Data type coercion — no silent truncation
4. Duplicate detection — primary key uniqueness in source batch

Rollback Snapshots
Point-in-time snapshots stored in S3 as Parquet files, 30-day retention, monthly restore tests.

Performance Tuning
batch_size default 1000, recommended 5000 for large jobs
worker_count default 4, recommended 8
parallel_entities default 1, recommended 3 for jobs over 1M records
""",
}


class CorpusPDF(FPDF):
    def header(self) -> None:
        self.set_font("DejaVu", "", 11)
        self.cell(0, 8, "Acme Corp - Nexus Integration Hub", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def sanitize(text: str) -> str:
    # Remove characters not renderable even by DejaVu, replace with '?'
    return "".join(c if c.isprintable() else " " for c in text)

def write_pdf(filename: str, text: str) -> None:
    pdf = CorpusPDF()
    pdf.add_font("DejaVu", "", str(FONT_PATH))
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("DejaVu", size=10)
    for line in text.strip().split("\n"):
        clean_line = line.strip()
        if not clean_line:
            pdf.ln(3)
            continue
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, clean_line)
    pdf.output(str(CORPUS_DIR / filename))


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in DOCUMENTS.items():
        write_pdf(name, content)
        print(f"Generated {CORPUS_DIR / name}")


if __name__ == "__main__":
    main()
