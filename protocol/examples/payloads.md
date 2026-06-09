# Protocol Examples

Concrete request/response pairs from each protocol endpoint. Useful when
implementing a server or debugging client behavior. The fixtures here are
what `tests/test_protocol/conformance.py` uses.

## 1. Fetch rules

### Request

```http
GET /v1/agents/billing-bot/rules HTTP/1.1
Host: api.anqush.dev
Authorization: Bearer ak_proj_abc123
```

### Response

```http
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: max-age=30
```

```json
{
  "rules": [
    {
      "id": "r_01HZ",
      "name": "refund-approval",
      "action": "approval",
      "tool": "stripe.refund",
      "when": { "amount": { "gt": 100 } },
      "reason": "Refunds over $100 require approval"
    },
    {
      "id": "r_02AB",
      "name": "block-destructive",
      "action": "block",
      "tool": "*",
      "when": { "tool_name": { "contains": "delete" } },
      "reason": "Delete operations are blocked by default"
    }
  ],
  "version": "v_01HZ7K9P"
}
```

The SDK evaluates rules in array order. The first match wins. If both a
`block` and an `approval` rule match, `block` wins.

## 2. Fetch budget

### Request

```http
GET /v1/agents/billing-bot/budget HTTP/1.1
Authorization: Bearer ak_proj_abc123
```

### Response

```json
{
  "agent_id": "billing-bot",
  "max_session_cost": 10.0,
  "max_daily_cost": 100.0,
  "session_spend": 2.45,
  "daily_spend": 17.30,
  "currency": "USD"
}
```

A `null` for either limit means "no cap." The SDK should NOT treat `null`
as 0.

## 3. Request approval

### Request

```http
POST /v1/approvals HTTP/1.1
Authorization: Bearer ak_proj_abc123
Idempotency-Key: 5e1f8a3b-2c7d-4a9e-bf01-1234567890ab
Content-Type: application/json
```

```json
{
  "agent_id": "billing-bot",
  "tool": "stripe.refund",
  "params": {
    "charge_id": "ch_3Pq2xL",
    "amount": 250.00
  },
  "rule": {
    "id": "r_01HZ",
    "name": "refund-approval",
    "action": "approval",
    "tool": "stripe.refund",
    "when": { "amount": { "gt": 100 } },
    "reason": "Refunds over $100 require approval"
  },
  "callback_url": "https://agent.example.com/approvals/abc/callback",
  "timeout_seconds": 300,
  "context": {
    "agent_goal": "Refund duplicate charges from last week",
    "chain_of_thought_summary": "Customer reported duplicate $250 charge."
  }
}
```

### Response (201)

```json
{
  "id": "apr_8x7k2m",
  "agent_id": "billing-bot",
  "tool": "stripe.refund",
  "params": { "charge_id": "ch_3Pq2xL", "amount": 250.00 },
  "rule": { "...": "..." },
  "status": "pending",
  "created_at": "2026-06-08T14:23:11Z",
  "resolved_at": null,
  "resolved_by": null,
  "comment": null,
  "resume_url": "https://api.anqush.dev/v1/approvals/apr_8x7k2m"
}
```

### Callback (server → agent)

```http
POST https://agent.example.com/approvals/abc/callback HTTP/1.1
Content-Type: application/json
X-Anqush-Signature: sha256=4f8a...e91b
X-Anqush-Approval-Id: apr_8x7k2m
```

```json
{
  "approval_id": "apr_8x7k2m",
  "status": "approved",
  "resolved_by": "alice@example.com",
  "resolved_at": "2026-06-08T14:24:55Z",
  "comment": "Verified duplicate with customer."
}
```

The agent MUST verify the `X-Anqush-Signature` header before acting on
the callback. Signature is `HMAC-SHA256(secret, raw_body)`, hex-encoded,
prefixed with `sha256=`.

## 4. Submit audit event (single)

### Request

```http
POST /v1/audit HTTP/1.1
Authorization: Bearer ak_proj_abc123
Idempotency-Key: ev_20260608_142345_8x7k
Content-Type: application/json
```

```json
{
  "kind": "single",
  "agent_id": "billing-bot",
  "tool": "stripe.refund",
  "params": { "charge_id": "ch_3Pq2xL", "amount": 250.00 },
  "result": { "id": "re_4nQ2mK", "status": "succeeded" },
  "status": "success",
  "reason": null,
  "cost": 0.0034,
  "duration_ms": 1240.5,
  "occurred_at": "2026-06-08T14:24:56.123Z",
  "approval_id": "apr_8x7k2m"
}
```

### Response (202)

```json
{ "accepted": 1 }
```

## 5. Submit audit event (batch)

```json
{
  "kind": "batch",
  "events": [
    { "...": "..." },
    { "...": "..." }
  ]
}
```

Response: `{"accepted": 2}` — events are committed atomically. Any
validation failure rejects the entire batch with `400` and a
`rejected` array identifying the offending indexes.

## 6. Error responses

All errors share a common shape:

```json
{
  "code": "agent_not_found",
  "message": "No agent with id 'billing-bot' visible to this token.",
  "request_id": "req_01HZ7KABCD"
}
```

Stable `code` values (do not localize, do not change without a major
version):

| HTTP | `code` | When |
|------|--------|------|
| 400 | `invalid_request` | Malformed JSON, missing required field |
| 400 | `invalid_rule` | Rule evaluation rejected a value (e.g., bad regex) |
| 401 | `unauthorized` | Missing or malformed `Authorization` header |
| 403 | `forbidden` | Token does not have access to this agent/project |
| 404 | `agent_not_found` | The agent id doesn't exist for this token |
| 404 | `not_found` | Generic 404 (approval, rule, etc.) |
| 409 | `conflict` | Idempotency-Key reused with different body |
| 413 | `batch_too_large` | Audit batch exceeds 100 events |
| 429 | `rate_limited` | Per-token rate limit exceeded |
| 500 | `internal_error` | Server bug. Safe to retry. |
| 503 | `unavailable` | Maintenance. Safe to retry with backoff. |
