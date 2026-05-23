"""
Swarm V4 - Base agent with ZeroMQ.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import time
from abc import ABC, abstractmethod
from typing import Any

# Fix Windows ProactorEventLoop issue with ZeroMQ
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import msgpack
import zmq
import zmq.asyncio

from shared.models import AgentStatus, MessageType, SwarmMessage
from shared.protocol import (
    HUB_PUB_ADDR, HUB_PULL_ADDR, HUB_REP_ADDR,
    HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT,
)

logger = logging.getLogger("swarm.v4.agent")


class BaseAgent(ABC):
    """Base agent class using ZeroMQ."""

    def __init__(
        self,
        name: str,
        model: str,
        provider: str,
        capabilities: list[str],
    ):
        self.name = name
        self.model = model
        self.provider = provider
        self.capabilities = capabilities
        self.ctx = zmq.asyncio.Context()
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._heartbeat_task: asyncio.Task | None = None
        self._sub_task: asyncio.Task | None = None

        # Sockets
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.connect(HUB_PUB_ADDR)
        self.sub.setsockopt(zmq.SUBSCRIBE, b"")

        self.push = self.ctx.socket(zmq.PUSH)
        self.push.connect(HUB_PULL_ADDR)

        self.req = self.ctx.socket(zmq.REQ)
        self.req.connect(HUB_REP_ADDR)

    async def start(self) -> None:
        """Start the agent."""
        self._running = True

        # Register with hub
        await self._register()

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._sub_task = asyncio.create_task(self._sub_loop())

        # Run agent-specific logic
        try:
            await self.run()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Graceful shutdown."""
        if not self._running:
            return
        self._running = False
        self._shutdown_event.set()

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        if self._sub_task and not self._sub_task.done():
            self._sub_task.cancel()

        self.sub.close()
        self.push.close()
        self.req.close()
        self.ctx.term()
        logger.info(f"[{self.name}] Stopped")

    async def _register(self) -> None:
        """Register with the hub via REQ/REP."""
        payload = {
            "action": "register",
            "name": self.name,
            "model": self.model,
            "provider": self.provider,
            "capabilities": self.capabilities,
        }
        await self.req.send(msgpack.packb(payload, use_bin_type=True))
        response = await self.req.recv()
        result = msgpack.unpackb(response, raw=False)
        logger.info(f"[{self.name}] Registered: {result}")

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat every HEARTBEAT_INTERVAL."""
        while self._running and not self._shutdown_event.is_set():
            try:
                payload = {
                    "action": "heartbeat",
                    "name": self.name,
                }
                await self.req.send(msgpack.packb(payload, use_bin_type=True))
                response = await self.req.recv()
                result = msgpack.unpackb(response, raw=False)
                if result.get("status") != "ok":
                    logger.warning(f"[{self.name}] Heartbeat failed: {result}")
            except Exception as e:
                logger.warning(f"[{self.name}] Heartbeat error: {e}")

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                pass

    async def _sub_loop(self) -> None:
        """Subscribe to hub events."""
        while self._running:
            try:
                topic, data = await self.sub.recv_multipart()
                payload = msgpack.unpackb(data, raw=False)
                await self._on_event(topic, payload)
            except Exception as e:
                logger.warning(f"[{self.name}] Sub error: {e}")
                await asyncio.sleep(1)

    async def _on_event(self, topic: bytes, payload: dict[str, Any]) -> None:
        """Handle an event from the hub."""
        if topic == b"task.assign":
            task_id = payload.get("task_id")
            if payload.get("assigned_to") == self.name:
                await self._on_task_assigned(task_id, payload)
        elif topic == b"hub.status":
            pass  # Ignore status broadcasts

    async def _on_task_assigned(self, task_id: str, payload: dict[str, Any]) -> None:
        """Handle task assignment."""
        logger.info(f"[{self.name}] Task assigned: {task_id}")
        try:
            result = await self.execute_task(payload)
            await self._complete_task(task_id, result)
        except Exception as e:
            logger.error(f"[{self.name}] Task error: {e}")
            await self._fail_task(task_id, str(e))

    async def _complete_task(self, task_id: str, result: dict[str, Any]) -> None:
        """Mark task as completed."""
        payload = {
            "action": "complete_task",
            "task_id": task_id,
            "agent": self.name,
            "result": result,
        }
        await self.push.send_multipart([b"task.complete", msgpack.packb(payload, use_bin_type=True)])

    async def _fail_task(self, task_id: str, error: str) -> None:
        """Mark task as failed."""
        payload = {
            "action": "fail_task",
            "task_id": task_id,
            "agent": self.name,
            "error": error,
        }
        await self.push.send_multipart([b"task.fail", msgpack.packb(payload, use_bin_type=True)])

    @abstractmethod
    async def run(self) -> None:
        """Agent-specific main logic."""
        pass

    @abstractmethod
    async def execute_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a task. Override in subclass."""
        pass
