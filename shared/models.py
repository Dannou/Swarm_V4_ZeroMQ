"""
Swarm V4 — Shared data models.
Simplified from V3, compatible with msgpack serialization.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AgentStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class MessageType(StrEnum):
    TASK = "task"
    RESULT = "result"
    HEARTBEAT = "heartbeat"
    REGISTER = "register"
    STATUS = "status"
    ERROR = "error"
    SYSTEM = "system"


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class AgentInfo:
    name: str
    model: str
    provider: str
    capabilities: list[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    current_task: str | None = None
    last_seen: float = field(default_factory=time.time)
    total_tasks: int = 0
    success_rate: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "provider": self.provider,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "current_task": self.current_task,
            "last_seen": self.last_seen,
            "total_tasks": self.total_tasks,
            "success_rate": self.success_rate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentInfo:
        return cls(
            name=str(data["name"]),
            model=str(data["model"]),
            provider=str(data["provider"]),
            capabilities=list(data.get("capabilities", [])),
            status=AgentStatus(data.get("status", "idle")),
            current_task=data.get("current_task"),
            last_seen=float(data.get("last_seen", time.time())),
            total_tasks=int(data.get("total_tasks", 0)),
            success_rate=float(data.get("success_rate", 1.0)),
        )


@dataclass(slots=True)
class Task:
    requester: str
    description: str
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    required_capabilities: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 1
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str | None = None
    created_at: float = field(default_factory=time.time)
    assigned_at: float | None = None
    completed_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "requester": self.requester,
            "description": self.description,
            "required_capabilities": self.required_capabilities,
            "context": self.context,
            "priority": self.priority,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at,
            "assigned_at": self.assigned_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        return cls(
            requester=str(data["requester"]),
            description=str(data["description"]),
            task_id=str(data.get("task_id", str(uuid.uuid4())[:8])),
            required_capabilities=list(data.get("required_capabilities", [])),
            context=dict(data.get("context", {})),
            priority=int(data.get("priority", 1)),
            status=TaskStatus(data.get("status", "pending")),
            assigned_to=data.get("assigned_to"),
            created_at=float(data.get("created_at", time.time())),
            assigned_at=float(data["assigned_at"]) if data.get("assigned_at") else None,
            completed_at=float(data["completed_at"]) if data.get("completed_at") else None,
            result=dict(data["result"]) if data.get("result") else None,
            error=data.get("error"),
            retry_count=int(data.get("retry_count", 0)),
            max_retries=int(data.get("max_retries", 2)),
        )


@dataclass(slots=True)
class SwarmMessage:
    sender: str
    recipient: str
    msg_type: MessageType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "msg_type": self.msg_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "msg_id": self.msg_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SwarmMessage:
        return cls(
            sender=str(data["sender"]),
            recipient=str(data["recipient"]),
            msg_type=MessageType(data["msg_type"]),
            payload=dict(data.get("payload", {})),
            timestamp=float(data.get("timestamp", time.time())),
            msg_id=str(data.get("msg_id", str(uuid.uuid4())[:8])),
        )
