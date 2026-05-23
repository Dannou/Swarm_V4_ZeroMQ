"""
Swarm V4 — Agent lifecycle manager.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from shared.models import AgentInfo, AgentStatus
from shared.protocol import HEARTBEAT_TIMEOUT
from hub.store import SwarmStore
from hub.broker import ZeroMQBroker

logger = logging.getLogger("swarm.v4.agent_manager")


class AgentManager:
    """Manages agent registration, heartbeats, and cleanup."""

    def __init__(self, store: SwarmStore, broker: ZeroMQBroker):
        self.store = store
        self.broker = broker

    def register(self, name: str, model: str, provider: str, capabilities: list[str]) -> dict[str, Any]:
        if self.store.get_agent(name):
            return {"status": "error", "detail": f"Agent '{name}' already exists"}

        agent = AgentInfo(
            name=name,
            model=model,
            provider=provider,
            capabilities=capabilities,
            status=AgentStatus.IDLE,
            last_seen=time.time(),
        )
        self.store.insert_agent(agent)
        logger.info(f"Agent registered: {name} ({model})")
        return {"status": "registered", "name": name}

    def heartbeat(self, name: str) -> dict[str, Any]:
        agent = self.store.get_agent(name)
        if not agent:
            return {"status": "error", "detail": "Agent not found"}

        agent.last_seen = time.time()
        if agent.status == AgentStatus.OFFLINE:
            agent.status = AgentStatus.IDLE
        self.store.insert_agent(agent)
        return {"status": "ok"}

    def remove(self, name: str) -> dict[str, Any]:
        agent = self.store.get_agent(name)
        if not agent:
            return {"status": "error", "detail": "Agent not found"}

        self.store.delete_agent(name)
        logger.info(f"Agent removed: {name}")
        return {"status": "removed"}

    async def cleanup_stale(self) -> int:
        now = time.time()
        agents = self.store.get_all_agents()
        cleaned = 0
        for name, agent in agents.items():
            if agent.status in (AgentStatus.IDLE, AgentStatus.BUSY) and (now - agent.last_seen) > HEARTBEAT_TIMEOUT:
                self.store.update_agent_status(name, AgentStatus.OFFLINE)
                await self.broker.publish_agent_leave(name, "heartbeat_timeout")
                logger.warning(f"Agent {name} marked offline (timeout)")
                cleaned += 1
        return cleaned
