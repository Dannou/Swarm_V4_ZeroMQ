"""
Swarm V4 — ZeroMQ protocol constants.
"""

from __future__ import annotations

import os
from pathlib import Path

# ZeroMQ endpoints
HUB_PUB_ADDR = os.environ.get("SWARM_PUB_ADDR", "tcp://127.0.0.1:5555")
HUB_PULL_ADDR = os.environ.get("SWARM_PULL_ADDR", "tcp://127.0.0.1:5556")
HUB_REP_ADDR = os.environ.get("SWARM_REP_ADDR", "tcp://127.0.0.1:5557")

# Topics
TOPIC_AGENT_JOIN = b"agent.join"
TOPIC_AGENT_LEAVE = b"agent.leave"
TOPIC_AGENT_STATUS = b"agent.status"
TOPIC_TASK_CREATE = b"task.create"
TOPIC_TASK_ASSIGN = b"task.assign"
TOPIC_TASK_COMPLETE = b"task.complete"
TOPIC_TASK_FAIL = b"task.fail"
TOPIC_SYSTEM = b"system"

# Timing
HEARTBEAT_INTERVAL = 10.0
HEARTBEAT_TIMEOUT = 30.0
AGENT_CLEANUP_INTERVAL = 15.0
TASK_ASSIGN_TIMEOUT = 5.0

# Paths
SWARM_DIR = Path(__file__).parent.parent
DB_PATH = SWARM_DIR / "swarm_v4.db"
