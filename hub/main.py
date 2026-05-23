"""
Swarm V4 - ZeroMQ Hub.
Entry point. No FastAPI, no HTTP. Pure ZeroMQ.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
from typing import Any

# Fix Windows ProactorEventLoop issue with ZeroMQ
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import msgpack
import zmq
import zmq.asyncio

from shared.models import AgentStatus, MessageType, TaskStatus
from shared.protocol import (
    HUB_PUB_ADDR, HUB_PULL_ADDR, HUB_REP_ADDR,
    HEARTBEAT_INTERVAL, AGENT_CLEANUP_INTERVAL,
)
from hub.store import SwarmStore
from hub.broker import ZeroMQBroker
from hub.task_manager import TaskManager
from hub.agent_manager import AgentManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("swarm.v4.hub")


class SwarmHub:
    """ZeroMQ-based Swarm Hub."""

    def __init__(self):
        self.ctx = zmq.asyncio.Context()
        self.store = SwarmStore()
        self.broker = ZeroMQBroker()
        self.task_mgr = TaskManager(self.store, self.broker)
        self.agent_mgr = AgentManager(self.store, self.broker)
        self._running = False

    async def start(self) -> None:
        """Start the hub."""
        self._running = True
        logger.info("=" * 50)
        logger.info("  SWARM V4 — ZeroMQ Hub")
        logger.info("=" * 50)

        # Start broker
        await self.broker.start()

        # Start background loops
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._scheduler_loop())
        asyncio.create_task(self._heartbeat_loop())

        logger.info("Hub ready")
        logger.info(f"  PUB: {HUB_PUB_ADDR}")
        logger.info(f"  PULL: {HUB_PULL_ADDR}")
        logger.info(f"  REP: {HUB_REP_ADDR}")

        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        await self.broker.stop()
        logger.info("Hub stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up stale agents."""
        while self._running:
            try:
                await asyncio.sleep(AGENT_CLEANUP_INTERVAL)
                cleaned = await self.agent_mgr.cleanup_stale()
                if cleaned:
                    logger.info(f"Cleaned {cleaned} stale agents")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def _scheduler_loop(self) -> None:
        """Periodically schedule pending tasks."""
        while self._running:
            try:
                await asyncio.sleep(5.0)
                scheduled = await self.task_mgr.schedule_pending()
                if scheduled:
                    logger.info(f"Scheduled {scheduled} tasks")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat broadcast."""
        while self._running:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                agents = self.store.get_all_agents()
                tasks = self.store.get_all_tasks()
                status = {
                    "agents_online": len([a for a in agents.values() if a.status != AgentStatus.OFFLINE]),
                    "agents_total": len(agents),
                    "tasks_pending": len([t for t in tasks if t.status == TaskStatus.PENDING]),
                    "tasks_running": len([t for t in tasks if t.status == TaskStatus.ASSIGNED]),
                    "tasks_completed": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
                }
                await self.broker.publish(b"hub.status", status)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")


def main() -> None:
    hub = SwarmHub()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(hub.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(hub.start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
