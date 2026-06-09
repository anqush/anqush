# Anqush

Anqush (अंकुश) is a control layer for AI agents. This monorepo contains the
open-source SDKs, protocol specification, reference server, and proxy.

## Workspace Layout

| Directory | What |
|-----------|------|
| `sdk-python/` | Python SDK (`pip install anqush`) |
| `sdk-typescript/` | TypeScript SDK |
| `protocol/` | OpenAPI specification and contract tests |
| `server/` | Reference server (single-tenant, dev) |
| `proxy/` | Network proxy/gateway |

## Quick Start

```bash
cd anqush
uv sync
uv run pytest sdk-python/tests/
```
