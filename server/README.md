# Anqush Server

Self-hostable reference implementation of the [Anqush Protocol](https://github.com/anqush/anqush/blob/main/docs/protocol/openapi.yaml).

**This is the reference implementation.** It passes all protocol conformance tests and is the canonical example of how to build an Anqush-compatible server.

## What is this?

This is the reference server for Anqush. It implements the Anqush Protocol spec and is useful for:

- **Local development** — run alongside the SDK for testing
- **Self-hosting** — deploy your own control plane
- **Reference** — see how the protocol is implemented

For the hosted version, see [api.anqush.dev](https://api.anqush.dev).

## Quick Start

```bash
# Install
pip install anqush-server

# Run
uvicorn server.main:app --host 0.0.0.0 --port 8000

# Or with Docker
docker-compose up
```

The dashboard is at http://localhost:8080 and the API at http://localhost:8000.

## Architecture

- **SQLite** — single-file database, zero config
- **Single-tenant** — one project per instance
- **No auth** — for dev/self-hosting (add your own for production)

## API

This server implements the [Anqush Protocol](https://github.com/anqush/anqush/blob/main/docs/protocol/openapi.yaml):

| Endpoint | Description |
|----------|-------------|
| `GET /api/agents/{id}/rules` | Fetch rules for an agent |
| `GET /api/agents/{id}/budget` | Fetch budget for an agent |
| `POST /api/approvals` | Request human approval |
| `GET /api/approvals/{id}` | Poll approval status |
| `POST /api/approvals/{id}/resolve` | Resolve an approval |
| `POST /api/audit` | Submit audit event(s) |
| `GET /health` | Liveness probe |

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/

# Run with hot reload
uv run uvicorn server.main:app --reload
```

## Conformance

This server passes all protocol conformance tests from the SDK:

```bash
# Run conformance tests against this server
ANQUSH_URL=http://localhost:8000 \
ANQUSH_API_KEY=test-key \
pytest tests/test_protocol/
```

## License

Apache-2.0
