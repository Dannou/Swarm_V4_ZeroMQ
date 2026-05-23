# Swarm V4 — ZeroMQ Multi-Agent Hub

Architecture ZeroMQ remplaçant FastAPI/WebSocket de V3.

## Architecture

```
┌─────────────────────────────────────┐
│           HUB (ZeroMQ)              │
│  ┌────────┐ ┌────────┐ ┌────────┐ │
│  │  PUB   │ │  PULL  │ │  REP   │ │
│  │ 5555   │ │ 5556   │ │ 5557   │ │
│  └────┬───┘ └────┬───┘ └────┬───┘ │
└───────┼──────────┼──────────┼─────┘
        │          │          │
   ┌────▼────┐ ┌───▼────┐ ┌──▼────┐
   │  SUB    │ │  PUSH  │ │  REQ  │
   │ Worker  │ │ Worker │ │Worker │
   └─────────┘ └────────┘ └───────┘
```

## Sockets

| Socket | Type | Port | Usage |
|--------|------|------|-------|
| PUB | Publish | 5555 | Events broadcast |
| PULL | Pull | 5556 | Workers push results |
| REP | Reply | 5557 | Sync requests (register, heartbeat) |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the hub
python launch_hub.py

# 3. Start workers (in separate terminals)
python launch_workers.py --profile code-general --count 2
python launch_workers.py --profile researcher --count 1
```

## Topics

| Topic | Direction | Payload |
|-------|-----------|---------|
| `agent.join` | Hub → All | `{name, model, capabilities}` |
| `agent.leave` | Hub → All | `{name, reason}` |
| `agent.status` | Hub → All | `{name, status, current_task}` |
| `task.create` | Hub → All | Task dict |
| `task.assign` | Hub → Worker | `{task_id, assigned_to, ...}` |
| `task.complete` | Worker → Hub | `{task_id, agent, result}` |
| `task.fail` | Worker → Hub | `{task_id, agent, error}` |

## Why ZeroMQ?

- **10x faster** than HTTP/WebSocket
- **No web server** (no FastAPI/uvicorn)
- **Binary messages** (msgpack, not JSON)
- **Native pub/sub** (no SSE artificiel)
- **Durable** (pas de déconnexion)
- **Windows natif** (pas de problème toolchain)

## Differences from V3

| Feature | V3 (FastAPI) | V4 (ZeroMQ) |
|---------|-------------|-------------|
| Protocol | HTTP/WebSocket | ZeroMQ |
| Serialization | JSON | msgpack |
| Server | uvicorn | None (pure ZMQ) |
| Dashboard | HTML/JS | CLI only |
| Speed | ~1ms latency | ~0.1ms latency |
| Dependencies | 8 packages | 3 packages |
