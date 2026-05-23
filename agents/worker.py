"""
Swarm V4 — Universal Worker.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to PYTHONPATH
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from agents.base import BaseAgent

logger = logging.getLogger("swarm.v4.worker")


class UniversalWorker(BaseAgent):
    """Universal worker with LLM execution."""

    def __init__(
        self,
        name: str,
        model: str,
        provider: str,
        capabilities: list[str],
    ):
        super().__init__(name, model, provider, capabilities)
        self.temperature = 0.6

    async def run(self) -> None:
        """Main worker loop."""
        logger.info(f"[{self.name}] Worker ready")
        while self._running:
            await asyncio.sleep(1)

    async def execute_task(self, payload: dict) -> dict:
        """Execute a task using the configured LLM."""
        description = payload.get("description", "")
        context = payload.get("context", {})

        logger.info(f"[{self.name}] Executing: {description[:60]}...")

        # TODO: Integrate with actual LLM
        # For now, return a mock result
        return {
            "output": f"[{self.name}] Processed: {description}",
            "model": self.model,
            "provider": self.provider,
        }


async def main():
    parser = argparse.ArgumentParser(description="Swarm V4 Worker")
    parser.add_argument("--name", required=True, help="Worker name")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--provider", default="openrouter", help="Provider")
    parser.add_argument("--capabilities", default="code,python", help="Capabilities (comma-separated)")
    parser.add_argument("--temperature", type=float, default=0.6, help="Temperature")

    args = parser.parse_args()

    capabilities = [c.strip() for c in args.capabilities.split(",") if c.strip()]

    worker = UniversalWorker(
        name=args.name,
        model=args.model,
        provider=args.provider,
        capabilities=capabilities,
    )
    worker.temperature = args.temperature

    print(f"🚀 Worker '{args.name}' started")
    print(f"   Model: {args.model}")
    print(f"   Provider: {args.provider}")
    print(f"   Capabilities: {', '.join(capabilities)}")

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
