"""Quick check: do we get tools from registry and does Tool serialize correctly?"""
import sys
from pathlib import Path
out = Path(__file__).resolve().parent.parent / "scripts" / "check_tools_out.txt"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.registry import get_tools
from mcp.types import Tool

lines = []
tools = get_tools()
lines.append(f"Count: {len(tools)}")
if tools:
    t = tools[0]
    lines.append(f"First tool name: {t.name}")
    dumped = t.model_dump() if hasattr(t, "model_dump") else (t.dict() if hasattr(t, "dict") else {})
    lines.append(f"Keys: {list(dumped.keys())}")
    lines.append(f"Has inputSchema: {'inputSchema' in dumped or 'input_schema' in dumped}")
out.write_text("\n".join(lines))
