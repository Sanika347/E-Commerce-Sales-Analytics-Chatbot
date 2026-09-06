import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClientHelper:
    def __init__(self):
        self.server_params = StdioServerParameters(
            command="python",
            args=["-m", "app.mcp_server.server"],
            env=None
        )

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    
                    if not result.content:
                        return json.dumps({"error": "Empty response from tool", "type": "empty"})
                    
                    # Assuming the tool returns a TextContent object
                    return result.content[0].text
        except Exception as e:
            return json.dumps({"error": str(e), "type": "mcp_failure", "tool": tool_name})
