"""
Swarm V4 — Task lifecycle manager.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from shared.models import Task, TaskStatus
from hub.store import SwarmStore
from hub.broker import ZeroMQBroker

logger = logging.getLogger("swarm.v4.task_manager")


class TaskManager:
    """Manages task creation, scheduling, and lifecycle."""

    def __init__(self, store: SwarmStore, broker: ZeroMQBroker):
        self.store = store
        self.broker = broker

    def create_task(
        self,
        requester: str,
        description: str,
        required_capabilities: list[str],
        context: dict[str, Any],
        priority: int = 1,
        max_retries: int = 2,
    ) -> Task:
        task = Task(
            requester=requester,
            description=description,
            required_capabilities=required_capabilities or [],
            context=context or {},
            priority=priority,
            max_retries=max_retries,
        )
        self.store.insert_task(task)
        logger.info(f"Task {task.task_id} created by {requester}")
        return task

    async def assign_task(self, task_id: str, agent_name: str) -> bool:
        task = self.store.get_task(task_id)
        if not task or task.status != TaskStatus.PENDING:
            return False

        self.store.update_task_status(
            task_id=task_id,
            status=TaskStatus.ASSIGNED,
            assigned_to=agent_name,
            assigned_at=time.time(),
        )
        await self.broker.publish_task_assign(task.to_dict())
        logger.info(f"Task {task_id} assigned to {agent_name}")
        return True

    async def complete_task(self, task_id: str, agent_name: str, result: dict[str, Any]) -> None:
        self.store.update_task_status(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            completed_at=time.time(),
            result=result,
        )
        await self.broker.publish_task_complete(task_id, agent_name, result)
        logger.info(f"Task {task_id} completed by {agent_name}")

    async def fail_task(self, task_id: str, agent_name: str, error: str) -> None:
        task = self.store.get_task(task_id)
        if not task:
            return

        if task.retry_count >= task.max_retries:
            self.store.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                completed_at=time.time(),
                error=error,
            )
            await self.broker.publish_task_fail(task_id, agent_name, error)
            logger.error(f"Task {task_id} failed permanently: {error}")
        else:
            self.store.increment_retry_count(task_id)
            self.store.update_task_status(
                task_id=task_id,
                status=TaskStatus.PENDING,
                assigned_to=None,
                assigned_at=None,
            )
            logger.warning(f"Task {task_id} retry {task.retry_count + 1}/{task.max_retries}")

    def _agent_matches(self, agent, task: Task) -> bool:
        if not task.required_capabilities:
            return True
        agent_caps = {c.lower() for c in agent.capabilities}
        return all(req.lower() in agent_caps for req in task.required_capabilities)

    async def schedule_pending(self) -> int:
        pending = self.store.get_tasks_by_status(TaskStatus.PENDING)
        if not pending:
            return 0

        agents = self.store.get_all_agents()
        available = [a for a in agents.values() if a.status.value == "idle"]
        if not available:
            return 0

        scheduled = 0
        for task in pending:
            scored = []
            for agent in available:
                if not self._agent_matches(agent, task):
                    continue
                agent_caps = {c.lower() for c in agent.capabilities}
                match_score = sum(1 for req in task.required_capabilities if req.lower() in agent_caps)
                scored.append((match_score, agent.total_tasks, agent))

            if not scored:
                continue

            scored.sort(key=lambda x: (-x[0], x[1]))
            best_agent = scored[0][2]
            available = [a for a in available if a.name != best_agent.name]

            if await self.assign_task(task.task_id, best_agent.name):
                scheduled += 1

        return scheduled
