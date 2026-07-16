# Authentication

## Overview

The PL1 Migration service uses **OAuth 2.0 with JWT bearer tokens** for all API authentication. Every client request must include a valid OAuth access token obtained through the authorization code flow.

## Configuration

Set the following environment variables:

```
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_TOKEN_URL=https://auth.example.com/oauth/token
OAUTH_SCOPES=read,write
```

## Token Validation

The API gateway validates tokens on every request:

1. Extract bearer token from `Authorization` header
2. Verify JWT signature against the OAuth provider's JWKS endpoint
3. Check token expiry and required scopes
4. Map OAuth `sub` claim to internal user ID

## Supported Grant Types

| Grant Type | Status | Use Case |
|---|---|---|
| Authorization Code | **Active** | Web applications |
| Client Credentials | **Active** | Service-to-service |
| Resource Owner Password | Deprecated | Legacy only — do not use |
| API Key (header) | **Not supported** | N/A |

## Security Requirements

- Tokens must expire within 1 hour
- Refresh tokens rotate on every use
- All OAuth endpoints require TLS 1.2+
- Rate limiting: 100 token requests/minute per client

## Migration Notes

The team evaluated API key authentication in Q3 2024 but decided to **retain OAuth 2.0** as the sole authentication mechanism. API keys were deemed insufficient for our multi-tenant audit requirements.
