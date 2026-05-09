"""Local launcher for Contexly MCP server without requiring editable install."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contexly.mcp_server import main


if __name__ == "__main__":
    main()
