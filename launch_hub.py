#!/usr/bin/env python3
"""
Swarm V4 — Hub launcher.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hub.main import main

if __name__ == "__main__":
    main()
