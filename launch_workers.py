#!/usr/bin/env python3
"""
Swarm V4 — Worker launcher.
"""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


def load_profiles():
    profiles_file = PROJECT_ROOT / "worker_profiles.json"
    if not profiles_file.exists():
        print(f"❌ Profiles not found: {profiles_file}")
        sys.exit(1)
    with open(profiles_file, encoding="utf-8") as f:
        return json.load(f)


def start_worker(name, profile):
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "agents" / "worker.py"),
        "--name", name,
        "--model", profile["model"],
        "--provider", profile["provider"],
        "--capabilities", ",".join(profile["capabilities"]),
    ]
    return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))


async def main():
    parser = argparse.ArgumentParser(description="Launch Swarm V4 Workers")
    parser.add_argument("--profile", required=True, help="Profile name")
    parser.add_argument("--count", type=int, default=1, help="Number of workers")
    parser.add_argument("--prefix", default=None, help="Name prefix")

    args = parser.parse_args()
    profiles = load_profiles()

    if args.profile not in profiles:
        print(f"❌ Unknown profile: {args.profile}")
        print(f"   Available: {', '.join(profiles.keys())}")
        sys.exit(1)

    profile = profiles[args.profile]
    prefix = args.prefix or args.profile

    print(f"🚀 Launching {args.count} worker(s) — profile: {args.profile}")
    print(f"   Model: {profile['model']}")
    print(f"   Capabilities: {', '.join(profile['capabilities'])}")

    processes = []
    for i in range(args.count):
        name = f"{prefix}_{i+1}"
        proc = start_worker(name, profile)
        processes.append(proc)
        print(f"  🟢 {name}")

    print("\nPress Ctrl+C to stop...")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping workers...")
        for proc in processes:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
