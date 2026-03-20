#!/usr/bin/env python3
"""
Bootstrap to run the MCP server regardless of current working directory.
Use this as the Cursor MCP command so the server starts even when cwd is not the project root.

  "command": "python",
  "args": ["C:\\Users\\YOU\\...\\awscode-commit-mcp\\run_mcp_server.py"]

No cwd or PYTHONPATH needed.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.server import main

if __name__ == "__main__":
    main()
