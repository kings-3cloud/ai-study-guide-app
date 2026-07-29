from mcp.server.fastmcp import FastMCP

from mcp_server.tools.fetch_url import register_tools as register_fetch_url
from mcp_server.tools.fetch_pdf import register_tools as register_fetch_pdf
from mcp_server.tools.quiz_tools import register_tools as register_quiz_tools
from mcp_server.tools.progress_tools import register_tools as register_progress_tools

mcp = FastMCP("study-assistant-mcp")

register_fetch_url(mcp)
register_fetch_pdf(mcp)
register_quiz_tools(mcp)
register_progress_tools(mcp)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Study Assistant MCP Server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse"],
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on for SSE transport (default: 8000)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run()
