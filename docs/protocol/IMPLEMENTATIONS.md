# Anqush Protocol Implementations

This document lists known implementations of the [Anqush Protocol](openapi.yaml).

## Official Implementations

| Implementation | Type | License | Status |
|----------------|------|---------|--------|
| [anqush-server](https://github.com/anqush/anqush-server) | Reference server | Apache-2.0 | ✅ Passes conformance tests |
| [api.anqush.dev](https://api.anqush.dev) | Hosted service | Proprietary | ✅ Passes conformance tests |

## Community Implementations

*None yet. Be the first!*

## Creating Your Own Implementation

To build an Anqush-compatible server:

1. Read the [protocol spec](openapi.yaml)
2. Implement the required endpoints:
   - `GET /api/agents/{agent_id}/rules`
   - `GET /api/agents/{agent_id}/budget`
   - `POST /api/approvals`
   - `GET /api/approvals/{approval_id}`
   - `POST /api/approvals/{approval_id}/resolve`
   - `POST /api/audit`
   - `GET /health`
3. Run the conformance tests:

```bash
ANQUSH_URL=https://your-server.example.com \
ANQUSH_API_KEY=your-test-key \
pytest tests/test_protocol/
```

4. If your server passes, open a PR to add it to this list.

## Protocol Version

Current version: **v1.0.0**

The protocol follows semantic versioning:
- **Minor version** (v1.1.0): New optional fields, new endpoints
- **Major version** (v2.0.0): Breaking changes (renamed/removed fields)

## Authentication

All protocol endpoints require a bearer token:

```
Authorization: Bearer <project_api_key>
```

The token format is opaque to the SDK. The control plane is responsible for:
- Token issuance
- Token validation
- Token rotation
- Scoping tokens to projects

## Error Responses

All error responses follow this format:

```json
{
  "code": "unauthorized",
  "message": "Invalid or missing Bearer token",
  "request_id": "req_abc123"
}
```

Stable error codes: `invalid_request`, `unauthorized`, `forbidden`, `agent_not_found`, `not_found`, `conflict`, `batch_too_large`, `rate_limited`, `internal_error`, `unavailable`.
