"""MCP server over stdio; list_tools from registry, call_tool dispatch."""

import asyncio
import logging
import sys
import traceback

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.tools.registry import call_tool as registry_call_tool
from src.tools.registry import get_tools

LOG_PREFIX = "[awscodecommit-mcp]"


class _FlushingStreamHandler(logging.StreamHandler):
    """StreamHandler that flushes after each emit so logs show immediately."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def _setup_logging() -> None:
    """Configure logging to stderr so stdout stays clean for MCP JSON-RPC."""
    handler = _FlushingStreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_PREFIX + " %(levelname)s: %(message)s"))
    log = logging.getLogger("awscodecommit_mcp")
    log.setLevel(logging.INFO)
    log.addHandler(handler)
    # Prevent propagation to root (avoids duplicate or unexpected output)
    log.propagate = False


def _log() -> logging.Logger:
    return logging.getLogger("awscodecommit_mcp")


def _create_server() -> Server:
    """Create server using MCP SDK decorator API (list_tools / call_tool)."""
    server = Server("awscodecommit-mcp")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        tools = get_tools()
        _log().debug("list_tools: returning %d tools", len(tools))
        return tools

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list[TextContent]:
        _log().debug("call_tool: %s", name)
        try:
            content_text = await registry_call_tool(name, arguments or {})
            _log().debug("call_tool: %s ok", name)
            return [TextContent(type="text", text=content_text)]
        except Exception as e:
            _log().exception("call_tool: %s failed: %s", name, e)
            raise

    return server


async def run_server() -> None:
    """Run MCP server over stdio."""
    _setup_logging()
    _log().info("server starting (stdio)")
    server = _create_server()
    async with stdio_server() as (read_stream, write_stream):
        _log().info("stdio connected, running")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Entrypoint for console_scripts and python -m src."""
    try:
        asyncio.run(run_server())
    except asyncio.CancelledError:
        _setup_logging()
        _log().info("server stopped (stream closed or interrupted)")
    except KeyboardInterrupt:
        _setup_logging()
        _log().info("server stopped (interrupted)")
    except Exception:  # noqa: BLE001
        # Log to stderr so Cursor/MCP host can show why the server exited
        sys.stderr.write(LOG_PREFIX + " FATAL: " + traceback.format_exc())
        sys.stderr.flush()
        raise SystemExit(1)
