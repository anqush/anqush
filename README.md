# Anqush

Anqush (अंकुश) is a **control layer for AI agents** — budget limits, approval workflows, and audit logging for agents that use tools, APIs, and LLMs.

The name comes from **अंकुश (aṅkuśa)**, the elephant goad — a tool used not to harm, but to *guide and direct* something powerful. That's exactly what this does for agents.

**Status:** Phase 1 complete — Multi-framework SDK (OpenAI, LangGraph, MCP). Hosted SaaS on roadmap.

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

### 1. Start the control plane

```bash
uv sync
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Or with Docker:

```bash
docker-compose up
```

The dashboard is at http://localhost:8080 and the API at http://localhost:8000.

### 2. Register an agent

```bash
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{"id":"my-agent","name":"My Agent","max_session_cost":10.0,"max_daily_cost":100.0}'
```

### 3. Add a rule

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

### 4. Wrap your agent

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
│              Framework-specific adapters                     │
│         (intercept tool calls, apply controls)               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Control Plane (API)                        │
│              FastAPI + SQLite (self-hosted)                  │
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

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents` | POST | Register an agent |
| `/api/agents` | GET | List agents |
| `/api/agents/{id}/rules` | POST | Create a rule |
| `/api/agents/{id}/rules` | GET | List rules |
| `/api/approvals` | POST | Request approval |
| `/api/approvals/{id}` | GET | Get approval status |
| `/api/approvals/{id}/approve` | POST | Approve |
| `/api/approvals/{id}/reject` | POST | Reject |
| `/api/audit` | POST | Log audit event |
| `/api/audit` | GET | Query audit log |

---

## Testing

```bash
# Run all tests
uv run pytest tests/

# With coverage
uv run pytest tests/ --cov=anqush --cov-report=term-missing
```

**Coverage:** 80%+ (configured as minimum in `pyproject.toml`)

---

## Roadmap

### Phase 1: Multi-Framework SDK ✅

- [x] Extract framework-agnostic core (`anqush/core/`)
- [x] OpenAI adapter (`anqush/adapters/openai.py`)
- [x] LangGraph adapter (`anqush/adapters/langgraph.py`)
- [x] MCP adapter (`anqush/adapters/mcp.py`)
- [x] Test suite (118 tests, 80%+ coverage)

### Phase 2: Hosted Control Plane (Next)

- [ ] Multi-tenancy (organizations, projects, environments)
- [ ] JWT-based auth (or Clerk/Auth0)
- [ ] PostgreSQL (replace SQLite)
- [ ] Redis for async job queue
- [ ] Async approvals (webhook + Slack)
- [ ] Multi-tenant dashboard (React/Vue)

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

MIT
