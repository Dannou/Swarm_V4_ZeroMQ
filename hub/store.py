"""
Swarm V4 — SQLite persistence layer.
Simplified from V3.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from shared.models import AgentInfo, AgentStatus, Task, TaskStatus
from shared.protocol import DB_PATH


class SwarmStore:
    """Thread-safe SQLite store for agents and tasks."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    name TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    capabilities TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'offline',
                    current_task TEXT,
                    last_seen REAL,
                    total_tasks INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 1.0
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    requester TEXT NOT NULL,
                    description TEXT NOT NULL,
                    required_capabilities TEXT NOT NULL,
                    context TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'pending',
                    assigned_to TEXT,
                    created_at REAL NOT NULL,
                    assigned_at REAL,
                    completed_at REAL,
                    result TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 2
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);
                """
            )
            conn.commit()

    # ── Agents ────────────────────────────────────────────────────────────────

    def get_agent(self, name: str) -> AgentInfo | None:
        row = self._conn().execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        return self._row_to_agent(row)

    def get_all_agents(self) -> dict[str, AgentInfo]:
        rows = self._conn().execute("SELECT * FROM agents").fetchall()
        return {row["name"]: self._row_to_agent(row) for row in rows}

    def insert_agent(self, agent: AgentInfo) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agents
                (name, model, provider, capabilities, status, current_task, last_seen, total_tasks, success_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent.name, agent.model, agent.provider,
                    json.dumps(agent.capabilities), agent.status.value,
                    agent.current_task, agent.last_seen,
                    agent.total_tasks, agent.success_rate,
                ),
            )
            conn.commit()

    def update_agent_status(self, name: str, status: AgentStatus, current_task: str | None = None) -> None:
        with self._conn() as conn:
            if current_task is not None:
                conn.execute(
                    "UPDATE agents SET status = ?, current_task = ? WHERE name = ?",
                    (status.value, current_task, name),
                )
            else:
                conn.execute(
                    "UPDATE agents SET status = ? WHERE name = ?",
                    (status.value, name),
                )
            conn.commit()

    def delete_agent(self, name: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM agents WHERE name = ?", (name,))
            conn.commit()

    def _row_to_agent(self, row: sqlite3.Row) -> AgentInfo:
        return AgentInfo(
            name=row["name"],
            model=row["model"],
            provider=row["provider"],
            capabilities=json.loads(row["capabilities"]),
            status=AgentStatus(row["status"]),
            current_task=row["current_task"],
            last_seen=row["last_seen"],
            total_tasks=row["total_tasks"],
            success_rate=row["success_rate"],
        )

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Task | None:
        row = self._conn().execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def get_all_tasks(self) -> list[Task]:
        rows = self._conn().execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [self._row_to_task(row) for row in rows]

    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        rows = self._conn().execute("SELECT * FROM tasks WHERE status = ?", (status.value,)).fetchall()
        return [self._row_to_task(row) for row in rows]

    def insert_task(self, task: Task) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                (task_id, requester, description, required_capabilities, context, priority, status,
                 assigned_to, created_at, assigned_at, completed_at, result, error, retry_count, max_retries)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id, task.requester, task.description,
                    json.dumps(task.required_capabilities), json.dumps(task.context),
                    task.priority, task.status.value, task.assigned_to,
                    task.created_at, task.assigned_at, task.completed_at,
                    json.dumps(task.result) if task.result else None,
                    task.error, task.retry_count, task.max_retries,
                ),
            )
            conn.commit()

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        assigned_to: str | None = None,
        assigned_at: float | None = None,
        completed_at: float | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE tasks SET status = ?, assigned_to = ?, assigned_at = ?,
                completed_at = ?, result = ?, error = ? WHERE task_id = ?
                """,
                (
                    status.value, assigned_to, assigned_at,
                    completed_at, json.dumps(result) if result else None,
                    error, task_id,
                ),
            )
            conn.commit()

    def increment_retry_count(self, task_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE tasks SET retry_count = retry_count + 1 WHERE task_id = ?",
                (task_id,),
            )
            conn.commit()

    def delete_task(self, task_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            requester=row["requester"],
            description=row["description"],
            task_id=row["task_id"],
            required_capabilities=json.loads(row["required_capabilities"]),
            context=json.loads(row["context"]),
            priority=row["priority"],
            status=TaskStatus(row["status"]),
            assigned_to=row["assigned_to"],
            created_at=row["created_at"],
            assigned_at=row["assigned_at"],
            completed_at=row["completed_at"],
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
        )
