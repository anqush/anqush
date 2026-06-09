# Anqush Protocol

The **Anqush Protocol** is the open contract between the Anqush SDK (runs in
the agent's process) and an Anqush-compatible control plane. The hosted service
at `api.anqush.dev` is one implementation of this protocol; the
`anqush-server` reference implementation is another.

Everything in this directory is **open** (Apache-2.0). Anyone can implement a
compatible control plane (self-hosted, on-prem, alternative cloud) and the
SDK will work against it without code changes.

## Repos

- **Spec & SDK:** [github.com/anqush/anqush](https://github.com/anqush/anqush) — Apache-2.0, public
- **Reference server:** [github.com/anqush/anqush-server](https://github.com/anqush/anqush-server) — Apache-2.0, public
- **Hosted service:** `github.com/anqush/anqush-cloud` — private, proprietary

## Contents

| File | What it is |
|------|-----------|
| [`openapi.yaml`](./openapi.yaml) | The wire-level protocol. Every endpoint the SDK calls is defined here. OpenAPI 3.1. |
| [`directory-split.md`](./directory-split.md) | What goes in the open SDK repo vs. the closed hosted-service repo, and why. |
| [`examples/`](./examples/) | Sample `anqush.yaml` rules, audit event payloads, approval request/response pairs. |

## The contract in one paragraph

The SDK has four jobs that talk to a control plane:

1. **Fetch rules** for an agent and evaluate them locally against each tool call.
2. **Fetch budget** for an agent and refuse to execute tool calls that would
   exceed the limit.
3. **Request approval** when a tool call matches an `approval` rule, and wait
   (via polling or webhook callback) for a human to resolve it.
4. **Submit audit events** for every tool call — blocked, approved, executed,
   errored — to a tamper-evident log.

That's it. Everything else (multi-tenancy, billing, dashboard, Slack
notifications, team management) is implementation detail of the hosted
product, not part of the protocol.

## Why the protocol is small on purpose

If the protocol were large, alternative implementations would lag behind and
fragment. Keeping it to four concerns means a third party can ship a
compatible server in a weekend. The hosted product gets to differentiate on
ops quality, integrations, and UX — not on protocol surface.

## Versioning

The protocol is versioned via URL prefix: `/v1/`, `/v2/`, etc. The SDK pins a
minimum protocol version and negotiates a maximum at startup. Breaking
changes get a new major version; additive changes ship within the current
version.

### Idempotency window

The `Idempotency-Key` header deduplicates writes for **24 hours** from the
first observation. After that, a reused key is treated as a new request.
This window is part of the spec and clients may rely on it.
