# Anqush

Anqush (अंकुश) is a **control layer for AI agents** — budget limits, approval workflows, and audit logging for agents that use tools, APIs, and LLMs.

The name comes from **अंकुश (aṅkuśa)**, the elephant goad — a tool used not to harm, but to *guide and direct* something powerful. That's exactly what this does for agents.

**Status:** Phase 1 complete — Multi-framework SDK (OpenAI, LangGraph, MCP). Hosted SaaS on roadmap.

## What's What

| Component | Repo | License | Type |
|-----------|------|---------|------|
| **SDK** (`pip install anqush`) | [anqush/anqush](https://github.com/anqush/anqush) | Apache-2.0 | Open source |
| **Protocol spec** (`openapi.yaml`) | [anqush/anqush](https://github.com/anqush/anqush) | Apache-2.0 | Open spec |
| **Reference server** | [anqush/anqush-server](https://github.com/anqush/anqush-server) | Apache-2.0 | Self-hostable |
| **Hosted control plane** (`api.anqush.dev`) | — | Proprietary | Managed service (multi-tenant, async approvals, team management) |

The protocol is open, so you can use our hosted service or run your own compatible control plane. The SDK works with any server that implements the [protocol spec](docs/protocol/openapi.yaml). See [IMPLEMENTATIONS.md](docs/protocol/IMPLEMENTATIONS.md) for known servers.

---

## What It Actually Does

Anqush intercepts tool calls across frameworks to enforce:

- **Budget controls** — session and daily spend limits
- **Approval workflows** — human-in-the-loop for sensitive actions
- **Block rules** — deterministic YAML rules that stop bad actions
- **Audit logging** — immutable record of every tool call

### Supported Frameworks

| Framework | Integration | Lines of Code |
|-----------|-------------|---------------|
| **OpenAI SDK** | `wrap_openai()` | ~3 |
| **LangGraph** | `wrap_tool_node()` | ~3 |
| **MCP** | `create_mcp_proxy()` | ~3 |

---

## Quick Start

### 1. Install

```bash
pip install anqush
```

Or with specific adapters:

```bash
pip install anqush[openai]       # OpenAI SDK
pip install anqush[langgraph]    # LangGraph
pip install anqush[mcp]          # MCP
pip install anqush[all]          # Everything
```

### 2. Start the control plane

Use the [reference server](https://github.com/anqush/anqush-server) for local development:

```bash
# Option A: Docker
docker run -p 8000:8000 ghcr.io/anqush/anqush-server:latest

# Option B: Install and run
pip install anqush-server
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Or use the hosted service at [api.anqush.dev](https://api.anqush.dev).

### 3. Register an agent

```bash
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{"id":"my-agent","name":"My Agent","max_session_cost":10.0,"max_daily_cost":100.0}'
```

### 4. Add a rule

```bash
curl -X POST http://localhost:8000/api/agents/my-agent/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name":"block-dangerous",
    "action":"block",
    "tool":"*",
    "when":{"tool_name":{"contains":"delete"}},
    "reason":"Delete operations are blocked"
  }'
```

### 5. Wrap your agent

#### OpenAI SDK

```python
import openai
from anqush.adapters.openai import wrap_openai

raw_client = openai.OpenAI(api_key="sk-...")
client = wrap_openai(raw_client, agent_id="my-agent")

# Use normally — controls are enforced automatically
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

#### LangGraph

```python
from langgraph.prebuilt import create_react_agent
from anqush.adapters.langgraph import wrap_tool_node

tools = [search, calculator, send_email]
controlled_tools = wrap_tool_node(tools, agent_id="my-agent")

# Use in a LangGraph agent
graph = create_react_agent(model, controlled_tools)
result = graph.invoke({"messages": [HumanMessage(content="Search for tutorials")]})
```

#### MCP

```python
from anqush.adapters.mcp import create_mcp_proxy
import asyncio

# Create proxy for your MCP server
proxy = create_mcp_proxy(
    upstream_url="http://localhost:3000/sse",
    agent_id="my-mcp-agent",
)

# Run the proxy
asyncio.run(proxy.run_sse(port=8001))

# Point your MCP client at http://localhost:8001/sse
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Anqush SDK                           │
├─────────────────────────────────────────────────────────────┤
│  adapters/                 │  core/                         │
│  ├── openai.py             │  ├── rules.py    (RuleEngine)  │
│  ├── langgraph.py          │  ├── budget.py   (BudgetTracker)│
│  └── mcp.py                │  ├── audit.py    (AuditLogger) │
│                            │  ├── approvals.py              │
│                            │  └── models.py   (Data types)  │
├─────────────────────────────────────────────────────────────┤
│  protocol/                                                   │
│  ├── types.py       (Pydantic models from openapi.yaml)     │
│  ├── transport.py   (Abstract Transport interface)          │
│  ├── http.py        (HTTPTransport)                         │
│  └── local.py       (LocalTransport for testing)            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Control Plane (API)                        │
│         [Reference](https://github.com/anqush/anqush-server)│
│         [Hosted](https://api.anqush.dev)                    │
└─────────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `core/rules.py` | Rule engine — evaluates block/approval rules |
| `core/budget.py` | Budget tracker — enforces spend limits |
| `core/audit.py` | Audit logger — records all tool calls |
| `core/approvals.py` | Approval client — human-in-the-loop workflows |
| `core/models.py` | Shared data types and exceptions |

### Adapters

| Adapter | Framework | How It Works |
|---------|-----------|--------------|
| `adapters/openai.py` | OpenAI SDK | Wraps client, intercepts `chat.completions.create` |
| `adapters/langgraph.py` | LangGraph | Wraps `ToolNode`, uses `interrupt()` for approvals |
| `adapters/mcp.py` | MCP | Proxy server, intercepts all tool calls |

### Protocol

| Module | Purpose |
|--------|---------|
| `protocol/types.py` | Pydantic models matching the [Anqush Protocol spec](docs/protocol/openapi.yaml) |
| `protocol/transport.py` | Abstract Transport interface |
| `protocol/http.py` | HTTPTransport for talking to control planes |
| `protocol/local.py` | LocalTransport for in-process testing |

---

## Rule Format

Rules are deterministic YAML/JSON. No natural language.

```yaml
rules:
  - name: block-after-hours
    action: block
    tool: gmail.send
    when:
      hour:
        lt: 9
    reason: No emails before 9am

  - name: refund-approval
    action: approval
    tool: stripe.refund
    when:
      amount:
        gt: 100
    reason: Refunds over $100 require approval
```

Supported conditions: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `contains`, `starts_with`.

---

## Protocol

The [Anqush Protocol](docs/protocol/openapi.yaml) is an open spec for SDK-server communication. Any server that implements it can be used with this SDK.

**Protocol endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents/{id}/rules` | GET | Fetch rules for an agent |
| `/api/agents/{id}/budget` | GET | Fetch budget for an agent |
| `/api/approvals` | POST | Request approval |
| `/api/approvals/{id}` | GET | Poll approval status |
| `/api/approvals/{id}/resolve` | POST | Resolve approval |
| `/api/audit` | POST | Submit audit event(s) |
| `/health` | GET | Liveness probe |

**Implementations:**
- [anqush-server](https://github.com/anqush/anqush-server) — self-hostable reference (SQLite, single-tenant)
- [api.anqush.dev](https://api.anqush.dev) — hosted service (PostgreSQL, multi-tenant)

---

## Testing

```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=anqush --cov-report=term-missing

# Run protocol conformance tests against a server
ANQUSH_URL=http://localhost:8000 uv run pytest tests/test_protocol/
```

**Coverage:** 80%+ (configured as minimum in `pyproject.toml`)

---

## Roadmap

### Phase 1: Multi-Framework SDK ✅

- [x] Extract framework-agnostic core (`anqush/core/`)
- [x] OpenAI adapter (`anqush/adapters/openai.py`)
- [x] LangGraph adapter (`anqush/adapters/langgraph.py`)
- [x] MCP adapter (`anqush/adapters/mcp.py`)
- [x] Protocol layer (`anqush/protocol/`)
- [x] Contract test suite (`tests/test_protocol/`)
- [x] Reference server rebuilt against spec

### Phase 2: Hosted Control Plane (Next)

- [ ] Multi-tenancy (organizations, projects, environments)
- [ ] Clerk auth
- [ ] PostgreSQL via SQLModel (Neon)
- [ ] Redis for async job queue
- [ ] Async approvals (webhook + Slack)
- [ ] Next.js dashboard

### Phase 3: Commercial Features

- [ ] Slack approvals
- [ ] Webhook rules
- [ ] Advanced rules (AND/OR, time-based, rate-limiting)
- [ ] Audit exports (CSV/JSON)
- [ ] Team management (RBAC)
- [ ] Stripe billing (usage-based pricing)

### Phase 4: Validation & Launch

- [ ] 5 design partners onboarded
- [ ] Documentation rewrite
- [ ] Landing page
- [ ] Public launch (HN, Reddit, Discord)
- [ ] Go/no-go decision

---

## License

Apache-2.0
