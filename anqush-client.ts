/**
 * Anqush TypeScript client — talks to the Anqush control plane API.
 *
 * Usage:
 *   import { anqush } from "./anqush-client.js";
 *   await anqush.checkBlock("db.delete", { id: 123 });
 *   await anqush.logAudit("my-agent", "db.delete", { id: 123 }, null, "blocked", "rule: no deletes");
 */

const SERVER_URL = process.env.ANQUSH_URL ?? "http://localhost:8000";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface AuditEvent {
  agent_id: string;
  tool: string;
  params: Record<string, unknown>;
  result: unknown;
  status: "success" | "error" | "blocked" | "rejected";
  reason: string | null;
  cost: number;
  duration_ms: number;
}

export interface Rule {
  id: number;
  name: string;
  action: "block" | "approval";
  tool: string;
  when: Record<string, unknown>;
  reason: string | null;
}

export interface Approval {
  id: string;
  agent_id: string;
  tool: string;
  params: Record<string, unknown>;
  rule: Record<string, unknown>;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

export interface BudgetInfo {
  max_session_cost: number | null;
  max_daily_cost: number | null;
  session_spend: number;
  daily_spend: number;
}

// ─── Client ──────────────────────────────────────────────────────────────────

class AnqushClient {
  private baseUrl: string;

  constructor(baseUrl: string = SERVER_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "unknown error");
      throw new Error(`Anqush API error ${res.status}: ${text}`);
    }
    return res.json() as Promise<T>;
  }

  // ─── Agents ──────────────────────────────────────────────────────────────

  async registerAgent(
    id: string,
    name: string,
    maxSessionCost?: number,
    maxDailyCost?: number
  ): Promise<void> {
    await this.request("POST", "/api/agents", {
      id,
      name,
      max_session_cost: maxSessionCost,
      max_daily_cost: maxDailyCost,
    });
  }

  async getBudget(agentId: string): Promise<BudgetInfo> {
    return this.request("GET", `/api/agents/${agentId}/budget`);
  }

  // ─── Rules ───────────────────────────────────────────────────────────────

  async getRules(agentId: string): Promise<Rule[]> {
    return this.request("GET", `/api/agents/${agentId}/rules`);
  }

  /** Check if a tool call is blocked. Returns block reason or null. */
  async checkBlock(
    agentId: string,
    tool: string,
    params: Record<string, unknown>
  ): Promise<string | null> {
    const rules = await this.getRules(agentId);
    for (const rule of rules) {
      if (rule.action !== "block") continue;
      if (this.matchesTool(rule.tool, tool) && this.matchesWhen(rule.when, params)) {
        return rule.reason ?? `Blocked by rule: ${rule.name}`;
      }
    }
    return null;
  }

  /** Check if a tool call requires approval. Returns the rule or null. */
  async checkApproval(
    agentId: string,
    tool: string,
    params: Record<string, unknown>
  ): Promise<Rule | null> {
    const rules = await this.getRules(agentId);
    for (const rule of rules) {
      if (rule.action !== "approval") continue;
      if (this.matchesTool(rule.tool, tool) && this.matchesWhen(rule.when, params)) {
        return rule;
      }
    }
    return null;
  }

  private matchesTool(pattern: string, tool: string): boolean {
    if (pattern === "*") return true;
    if (pattern.endsWith(".*")) return tool.startsWith(pattern.slice(0, -1));
    return pattern === tool;
  }

  private matchesWhen(
    conditions: Record<string, unknown>,
    params: Record<string, unknown>
  ): boolean {
    for (const [key, condition] of Object.entries(conditions)) {
      const value = this.getNested(params, key);
      if (!this.evalCondition(condition, value)) return false;
    }
    return true;
  }

  private getNested(data: Record<string, unknown>, path: string): unknown {
    const parts = path.split(".");
    let current: unknown = data;
    for (const part of parts) {
      if (current && typeof current === "object") {
        current = (current as Record<string, unknown>)[part];
      } else {
        return undefined;
      }
    }
    return current;
  }

  private evalCondition(condition: unknown, value: unknown): boolean {
    if (typeof condition === "object" && condition !== null) {
      for (const [op, target] of Object.entries(condition as Record<string, unknown>)) {
        switch (op) {
          case "eq": if (value !== target) return false; break;
          case "ne": if (value === target) return false; break;
          case "gt": if (typeof value !== "number" || value <= (target as number)) return false; break;
          case "gte": if (typeof value !== "number" || value < (target as number)) return false; break;
          case "lt": if (typeof value !== "number" || value >= (target as number)) return false; break;
          case "lte": if (typeof value !== "number" || value > (target as number)) return false; break;
          case "in": if (!Array.isArray(target) || !target.includes(value)) return false; break;
          case "contains": if (typeof value !== "string" || !value.includes(target as string)) return false; break;
          case "starts_with": if (typeof value !== "string" || !value.startsWith(target as string)) return false; break;
          case "ends_with": if (typeof value !== "string" || !value.endsWith(target as string)) return false; break;
        }
      }
      return true;
    }
    return value === condition;
  }

  // ─── Approvals ───────────────────────────────────────────────────────────

  /** Request approval and wait for resolution. Returns true if approved. */
  async requestApproval(
    agentId: string,
    tool: string,
    params: Record<string, unknown>,
    rule: Rule,
    timeoutMs = 300_000,
    pollMs = 2000
  ): Promise<boolean> {
    const approval = await this.request<Approval>("POST", "/api/approvals", {
      agent_id: agentId,
      tool,
      params,
      rule,
    });

    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const status = await this.request<Approval>(
        "GET",
        `/api/approvals/${approval.id}`
      );
      if (status.status === "approved") return true;
      if (status.status === "rejected") return false;
      await new Promise((r) => setTimeout(r, pollMs));
    }

    return false; // timeout → reject
  }

  // ─── Audit ───────────────────────────────────────────────────────────────

  async logAudit(event: AuditEvent): Promise<void> {
    // Fire-and-forget
    fetch(`${this.baseUrl}/api/audit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    }).catch(() => {}); // best-effort
  }
}

export const anqush = new AnqushClient();
