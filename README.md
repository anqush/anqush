# Anqush

Anqush (अंकुश) is a **control layer for AI agents** — budget limits, approval workflows, and audit logging for agents that use tools, APIs, and LLMs.

The name comes from **अंकुश (aṅkuśa)**, the elephant goad — a tool used not to harm, but to *guide and direct* something powerful. That's exactly what this does for agents.

**Status:** MVP — OpenAI SDK only. LangGraph, CrewAI, and MCP support are on the roadmap.

---

## What It Actually Does

Anqush wraps your OpenAI client and intercepts tool calls to enforce:

- **Budget controls** — session and daily spend limits
- **Approval workflows** — human-in-the-loop for sensitive actions
- **Block rules** — deterministic YAML rules that stop bad actions
- **Audit logging** — immutable record of every tool call

## What It Does NOT Do (Yet)

- Zero-code integration — you wrap your client with one line
- Automatic agent discovery — you register agents explicitly
- Tool cost tracking — tools don't self-report costs; LLM costs are estimated
- LangGraph / CrewAI / MCP support — OpenAI SDK only for now
- Hosted SaaS — self-hosted control plane via Docker

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

### 4. Wrap your client

```python
import openai
from anqush import wrap_openai

raw_client = openai.OpenAI(api_key="sk-...")
client = wrap_openai(raw_client, agent_id="my-agent")

# Use normally — controls are enforced automatically
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

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

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Agent     │────▶│  Anqush  │────▶│   OpenAI    │
│  (wrapped)  │     │   SDK Wrap   │     │    API      │
└─────────────┘     └──────────────┘     └─────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  Control     │
                    │  Plane (API) │
                    │  + SQLite    │
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  Dashboard   │
                    │  (HTML/JS)   │
                    └──────────────┘
```

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

## Honest Roadmap

**Now (MVP):**
- [x] OpenAI SDK wrapper
- [x] Budget controls (estimated LLM costs)
- [x] Approval workflows (dashboard polling)
- [x] Block/approval rules
- [x] Audit logging
- [x] Self-hosted control plane

**Next:**
- [ ] LangGraph integration (node-level interception)
- [ ] CrewAI integration (task-level controls)
- [ ] MCP server proxy (intercept MCP tool calls)
- [ ] Slack approval notifications
- [ ] Real tool cost annotation (user-defined)
- [ ] Hosted cloud option

---

## License

MIT
