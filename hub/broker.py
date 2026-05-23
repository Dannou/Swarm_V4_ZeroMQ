"""
Swarm V4 — ZeroMQ message broker.
Pub/sub for events, push/pull for tasks, req/rep for control.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Callable

import zmq
import zmq.asyncio

from shared.protocol import (
    HUB_PUB_ADDR, HUB_PULL_ADDR, HUB_REP_ADDR,
    TOPIC_AGENT_JOIN, TOPIC_AGENT_LEAVE, TOPIC_AGENT_STATUS,
    TOPIC_TASK_CREATE, TOPIC_TASK_ASSIGN, TOPIC_TASK_COMPLETE,
    TOPIC_TASK_FAIL, TOPIC_SYSTEM,
)

logger = logging.getLogger("swarm.v4.broker")


class ZeroMQBroker:
    """ZeroMQ broker: pub/sub + push/pull + req/rep."""

    def __init__(self):
        self.ctx = zmq.asyncio.Context()
        self._subscribers: list[Callable[[bytes, dict[str, Any]], Any]] = []
        self._lock = asyncio.Lock()
        self._running = False

    async def start(self) -> None:
        """Start all ZeroMQ sockets."""
        self._running = True

        # PUB socket — broadcasts events to all subscribers
        self.pub = self.ctx.socket(zmq.PUB)
        self.pub.bind(HUB_PUB_ADDR)
        logger.info(f"PUB bound to {HUB_PUB_ADDR}")

        # PULL socket — workers push tasks here
        self.pull = self.ctx.socket(zmq.PULL)
        self.pull.bind(HUB_PULL_ADDR)
        logger.info(f"PULL bound to {HUB_PULL_ADDR}")

        # REP socket — sync requests (status, etc.)
        self.rep = self.ctx.socket(zmq.REP)
        self.rep.bind(HUB_REP_ADDR)
        logger.info(f"REP bound to {HUB_REP_ADDR}")

        # Start background loops
        asyncio.create_task(self._pull_loop())
        asyncio.create_task(self._rep_loop())

    async def stop(self) -> None:
        self._running = False
        self.pub.close()
        self.pull.close()
        self.rep.close()
        self.ctx.term()
        logger.info("Broker stopped")

    async def publish(self, topic: bytes, payload: dict[str, Any]) -> None:
        """Publish an event to all subscribers."""
        import msgpack
        data = msgpack.packb(payload, use_bin_type=True)
        await self.pub.send_multipart([topic, data])

    async def _pull_loop(self) -> None:
        """Receive messages from workers via PULL."""
        while self._running:
            try:
                msg = await self.pull.recv_multipart(flags=zmq.NOBLOCK)
                await self._handle_worker_msg(msg)
            except zmq.Again:
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Pull error: {e}")

    async def _rep_loop(self) -> None:
        """Handle sync requests via REP."""
        while self._running:
            try:
                msg = await self.rep.recv_multipart(flags=zmq.NOBLOCK)
                response = await self._handle_request(msg)
                await self.rep.send_multipart(response)
            except zmq.Again:
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Rep error: {e}")

    async def _handle_worker_msg(self, msg: list[bytes]) -> None:
        """Handle a message from a worker."""
        import msgpack
        if len(msg) < 2:
            return
        topic = msg[0]
        payload = msgpack.unpackb(msg[1], raw=False)
        logger.debug(f"Worker msg: {topic} -> {payload}")

    async def _handle_request(self, msg: list[bytes]) -> list[bytes]:
        """Handle a sync request."""
        import msgpack
        try:
            request = msgpack.unpackb(msg[0], raw=False)
            action = request.get("action", "")
            result = {"status": "ok"}
            return [msgpack.packb(result, use_bin_type=True)]
        except Exception as e:
            return [msgpack.packb({"error": str(e)}, use_bin_type=True)]

    # ── Convenience publishers ────────────────────────────────────────────────

    async def publish_agent_join(self, name: str, model: str, capabilities: list[str]) -> None:
        await self.publish(TOPIC_AGENT_JOIN, {"name": name, "model": model, "capabilities": capabilities})

    async def publish_agent_leave(self, name: str, reason: str = "disconnected") -> None:
        await self.publish(TOPIC_AGENT_LEAVE, {"name": name, "reason": reason})

    async def publish_agent_status(self, name: str, status: str, current_task: str | None = None) -> None:
        await self.publish(TOPIC_AGENT_STATUS, {"name": name, "status": status, "current_task": current_task})

    async def publish_task_create(self, task: dict[str, Any]) -> None:
        await self.publish(TOPIC_TASK_CREATE, task)

    async def publish_task_complete(self, task_id: str, agent: str, result: dict[str, Any]) -> None:
        await self.publish(TOPIC_TASK_COMPLETE, {"task_id": task_id, "agent": agent, "result": result})

    async def publish_task_fail(self, task_id: str, agent: str, error: str) -> None:
        await self.publish(TOPIC_TASK_FAIL, {"task_id": task_id, "agent": agent, "error": error})
