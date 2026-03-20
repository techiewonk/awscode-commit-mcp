"""Scaffold: one test tool (ping) is listed and callable."""

import pytest

from src.tools.registry import call_tool, get_tools


def test_get_tools_includes_ping():
    tools = get_tools()
    names = [t.name for t in tools]
    assert "ping" in names
    ping = next(t for t in tools if t.name == "ping")
    assert "pong" in (ping.description or "").lower() or "test" in (ping.description or "").lower()


def test_get_tools_includes_repository_tools():
    tools = get_tools()
    names = [t.name for t in tools]
    repo_tools = [
        "repos_list", "repo_get", "branches_list", "branch_get",
        "file_get", "folder_get", "code_search", "commit_get", "diff_get",
    ]
    for name in repo_tools:
        assert name in names, f"Missing tool: {name}"


@pytest.mark.asyncio
async def test_call_tool_ping():
    result = await call_tool("ping", {})
    assert "pong" in result or "ok" in result


@pytest.mark.asyncio
async def test_call_tool_ping_with_message():
    result = await call_tool("ping", {"message": "hello"})
    assert "hello" in result


@pytest.mark.asyncio
async def test_call_tool_unknown_raises():
    with pytest.raises(ValueError, match="Unknown tool"):
        await call_tool("unknown_tool", {})
