# api/mcp_client.py
from __future__ import annotations

import asyncio
import os
import traceback
from contextlib import AsyncExitStack
from typing import Any, Dict, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from utils.logger import logger


class MCPClient:
    """
    Starts the MCP server over stdio and exposes a simple `call_tool`
    helper.  No LLM orchestration lives here now.
    """

    def __init__(self) -> None:
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.logger = logger

    # ───────────────────────────────────────────────────────────────
    async def connect_to_server(self, server_script_path: str) -> None:
        """Spawn the MCP server (Python or Node) and initialise the session."""
        try:
            if not server_script_path.endswith((".py", ".js")):
                raise ValueError("Server script must be .py or .js")

            command = "python" if server_script_path.endswith(".py") else "node"
            server_params = StdioServerParameters(
                command=command, args=[server_script_path], env=None
            )

            stdio, write = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )
            await self.session.initialize()

            tool_names = [t.name for t in (await self.session.list_tools()).tools]
            self.logger.info(f"Connected to MCP Server. Tools: {tool_names}")

        except Exception as exc:
            self.logger.error(f"Error connecting to MCP server: {exc}")
            traceback.print_exc()
            raise

    # ───────────────────────────────────────────────────────────────
    async def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Convenience wrapper around `session.call_tool`."""
        if self.session is None:
            raise RuntimeError("MCP session not initialised")
        return await self.session.call_tool(name, args)

    # ───────────────────────────────────────────────────────────────
    async def cleanup(self) -> None:
        await self.exit_stack.aclose()
        self.logger.info("Disconnected from MCP server")
