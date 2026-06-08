"""SQLite database for the Anqush control plane."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any

DB_PATH = "anqush.db"


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn: sqlite3.Connection | None = None

    def init(self) -> None:
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                max_session_cost REAL,
                max_daily_cost REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                name TEXT NOT NULL,
                action TEXT NOT NULL,
                tool TEXT NOT NULL DEFAULT '*',
                when_json TEXT NOT NULL DEFAULT '{}',
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                params_json TEXT NOT NULL,
                rule_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            );

            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                params_json TEXT,
                result_json TEXT,
                status TEXT NOT NULL,
                reason TEXT,
                cost REAL DEFAULT 0,
                duration_ms REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS spend (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            );
        """)
        self.conn.commit()

    # ─── Agents ───────────────────────────────────────────────────────────────

    def create_agent(self, agent: Any) -> dict:
        self.conn.execute(
            "INSERT INTO agents (id, name, max_session_cost, max_daily_cost) VALUES (?, ?, ?, ?)",
            (agent.id, agent.name, agent.max_session_cost, agent.max_daily_cost),
        )
        self.conn.commit()
        return self.get_agent(agent.id)

    def list_agents(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_agent(self, agent_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        return dict(row) if row else None

    # ─── Rules ────────────────────────────────────────────────────────────────

    def create_rule(self, agent_id: str, rule: Any) -> dict:
        import json

        cur = self.conn.execute(
            "INSERT INTO rules (agent_id, name, action, tool, when_json, reason) VALUES (?, ?, ?, ?, ?, ?)",
            (agent_id, rule.name, rule.action, rule.tool, json.dumps(rule.when), rule.reason),
        )
        self.conn.commit()
        return self._get_rule(cur.lastrowid)

    def list_rules(self, agent_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM rules WHERE agent_id = ? ORDER BY created_at DESC", (agent_id,)
        ).fetchall()
        return [self._format_rule(r) for r in rows]

    def _get_rule(self, rule_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
        return self._format_rule(row)

    def _format_rule(self, row: sqlite3.Row) -> dict:
        import json

        d = dict(row)
        d["when"] = json.loads(d.pop("when_json", "{}"))
        return d

    def delete_rule(self, rule_id: int) -> None:
        self.conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        self.conn.commit()

    # ─── Approvals ────────────────────────────────────────────────────────────

    def create_approval(self, req: Any) -> dict:
        import json

        approval_id = str(uuid.uuid4())[:8]
        self.conn.execute(
            "INSERT INTO approvals (id, agent_id, tool, params_json, rule_json) VALUES (?, ?, ?, ?, ?)",
            (approval_id, req.agent_id, req.tool, json.dumps(req.params), json.dumps(req.rule)),
        )
        self.conn.commit()
        return self.get_approval(approval_id)

    def get_approval(self, approval_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        return self._format_approval(row) if row else None

    def resolve_approval(self, approval_id: str, status: str) -> dict | None:
        self.conn.execute(
            "UPDATE approvals SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, approval_id),
        )
        self.conn.commit()
        return self.get_approval(approval_id)

    def list_approvals(self, agent_id: str | None = None, status: str | None = None) -> list[dict]:
        query = "SELECT * FROM approvals WHERE 1=1"
        params: list[Any] = []
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._format_approval(r) for r in rows]

    def _format_approval(self, row: sqlite3.Row) -> dict:
        import json

        d = dict(row)
        d["params"] = json.loads(d.pop("params_json", "{}"))
        d["rule"] = json.loads(d.pop("rule_json", "{}"))
        return d

    # ─── Audit ────────────────────────────────────────────────────────────────

    def log_audit(self, event: Any) -> None:
        import json

        self.conn.execute(
            "INSERT INTO audit (agent_id, tool, params_json, result_json, status, reason, cost, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.agent_id,
                event.tool,
                json.dumps(event.params),
                json.dumps(event.result) if event.result is not None else None,
                event.status,
                event.reason,
                event.cost,
                event.duration_ms,
            ),
        )
        self.conn.commit()

    def list_audit(self, agent_id: str | None = None, limit: int = 100) -> list[dict]:
        query = "SELECT * FROM audit WHERE 1=1"
        params: list[Any] = []
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._format_audit(r) for r in rows]

    def _format_audit(self, row: sqlite3.Row) -> dict:
        import json

        d = dict(row)
        d["params"] = json.loads(d.pop("params_json", "{}"))
        result = d.pop("result_json", None)
        d["result"] = json.loads(result) if result else None
        return d

    # ─── Budget / Spend ───────────────────────────────────────────────────────

    def record_spend(self, agent_id: str, amount: float) -> None:
        self.conn.execute("INSERT INTO spend (agent_id, amount) VALUES (?, ?)", (agent_id, amount))
        self.conn.commit()

    def get_budget(self, agent_id: str) -> dict:
        agent = self.get_agent(agent_id) or {}

        # Daily spend: today
        today = datetime.now().strftime("%Y-%m-%d")
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM spend WHERE agent_id = ? AND date(created_at) = ?",
            (agent_id, today),
        ).fetchone()
        daily_spend = row["total"] if row else 0.0

        # Session spend: last hour (proxy for "current session")
        hour_ago = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM spend WHERE agent_id = ? AND created_at > ?",
            (agent_id, hour_ago),
        ).fetchone()
        session_spend = row["total"] if row else 0.0

        return {
            "agent_id": agent_id,
            "max_session_cost": agent.get("max_session_cost"),
            "max_daily_cost": agent.get("max_daily_cost"),
            "session_spend": session_spend,
            "daily_spend": daily_spend,
        }
