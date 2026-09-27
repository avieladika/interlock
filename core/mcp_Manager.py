import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Dict, List, Optional, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPManager:
    """
    Manager for multiple MCP servers.
    Handles lifecycle, connectivity, and tool execution.
    """

    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.server_tools: Dict[str, List] = {}

    async def connect_to_server(self, name: str, command: str, args: list, env: Optional[dict] = None):
        """
        Starts an MCP server and establishes a session.
        """
        print(f"🔌 Connecting to {name} MCP server...")

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env={**os.environ, **(env or {})}
        )

        try:
            # We use a timeout to prevent hanging indefinitely if the server is unresponsive
            async with asyncio.timeout(30):  # 30 seconds timeout for connection
                print(f"DEBUG: [{name}] Starting stdio_client process...")
                # הפעלת השרת ב-Process נפרד (Stdio)
                stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
                read, write = stdio_transport
                print(f"DEBUG: [{name}] stdio_client started. Streams obtained.")

                print(f"DEBUG: [{name}] Creating ClientSession...")
                # יצירת ה-Session
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                print(f"DEBUG: [{name}] ClientSession created.")

                print(f"DEBUG: [{name}] Initializing session (Handshake)...")
                # Initialization (Handshake)
                await session.initialize()
                print(f"DEBUG: [{name}] Session initialized.")

                self.sessions[name] = session

                print(f"DEBUG: [{name}] Listing tools...")
                # משיכת רשימת הכלים הזמינים מהשרת הזה
                response = await session.list_tools()
                self.server_tools[name] = response.tools
                print(f"DEBUG: [{name}] Tools listed.")

                print(f"✅ {name} connected. {len(response.tools)} tools available.")

        except TimeoutError:
            print(f"❌ Connection to {name} timed out! The server might be hanging or waiting for input.")
            # We might want to re-raise or handle this, but for now let's print.
            raise RuntimeError(f"Connection to {name} timed out.")
        except Exception as e:
            print(f"❌ Failed to connect to {name}: {str(e)}")
            raise e

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        if server_name not in self.sessions:
            raise ValueError(f"Server '{server_name}' is not connected.")

        # Call the tool with a timeout as well, just in case
        try:
            async with asyncio.timeout(120): # 2 minutes max for tool execution
                resp = await self.sessions[server_name].call_tool(tool_name, arguments)
                return self._normalize_mcp_response(resp)
        except TimeoutError:
             raise RuntimeError(f"Tool call '{tool_name}' on '{server_name}' timed out.")

    async def get_all_tools_metadata(self) -> List[dict]:
        """
        Returns all tools formatted for LLM function calling.
        """
        all_metadata = []
        for server, tools in self.server_tools.items():
            for tool in tools:
                all_metadata.append({
                    "server": server,
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })
        return all_metadata

    async def shutdown(self):
        """Gracefully close all connections."""
        print("🛑 Shutting down MCP Manager...")
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            print(f"⚠️ Error during shutdown: {e}")

    def print_tools(self, server_name: str):
        if server_name not in self.server_tools:
            print(f"No tools cached for server '{server_name}'.")
            return

        print(f"🧰 Tools for '{server_name}':")
        for t in self.server_tools[server_name]:
            print(f" - {t.name}")

    def _normalize_mcp_response(self, resp) -> Any:
        """
        MCP tools often return a CallToolResult where resp.content is a list of content blocks,
        usually TextContent with a .text field containing JSON.
        This function converts that into Python objects (dict/list/str).
        """
        data = getattr(resp, "content", resp)

        # Case 1: content blocks list (TextContent, etc.)
        if isinstance(data, list) and len(data) > 0:
            first = data[0]

            # Most common: TextContent with .text holding JSON string
            if hasattr(first, "text") and isinstance(first.text, str):
                text = first.text.strip()

                # Try JSON parse
                try:
                    return json.loads(text)
                except Exception:
                    return text  # not JSON, return raw text

            # If it's already a dict-like object inside list
            if isinstance(first, (dict, list)):
                return first

            return data  # fallback

        # Case 2: already a dict/list
        if isinstance(data, (dict, list)):
            return data

        # Case 3: string that might be JSON
        if isinstance(data, str):
            s = data.strip()
            try:
                return json.loads(s)
            except Exception:
                return s

        return data
