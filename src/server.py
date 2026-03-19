"""MCP server over stdio; list_tools from registry, call_tool dispatch."""

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, TextContent, Tool

from src.tools.registry import get_tools, call_tool as registry_call_tool


async def handle_list_tools() -> ListToolsResult:
    """Return tools from registry."""
    tools = get_tools()
    return ListToolsResult(tools=tools)


async def handle_call_tool(params: CallToolRequestParams) -> CallToolResult:
    """Dispatch tool by name; run boto3 in thread pool when needed."""
    name = params.name
    arguments = params.arguments or {}
    try:
        content_text = await registry_call_tool(name, arguments)
        return CallToolResult(
            content=[TextContent(type="text", text=content_text)]
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            is_error=True,
        )


async def run_server() -> None:
    """Run MCP server over stdio."""
    server = Server(
        "awscodecommit-mcp",
        on_list_tools=lambda ctx, _: handle_list_tools(),
        on_call_tool=lambda ctx, params: handle_call_tool(params),
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Entrypoint for console_scripts and python -m src."""
    asyncio.run(run_server())
