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
    mcp.run()
