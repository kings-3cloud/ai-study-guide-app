from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import Agent, McpTool

from config import settings

AGENT_NAME = "content-summarizer"

_INSTRUCTIONS = (
    "You are a content summarization specialist. "
    "When given a URL, use fetch_url_content to retrieve the page text. "
    "When given a file path, use fetch_pdf_content to extract PDF text. "
    "Structure every summary into four sections: "
    "(1) Topic Overview, "
    "(2) Key Concepts as bullet list, "
    "(3) Important Details, "
    "(4) Suggested Learning Objectives. "
    "Keep summaries under 500 words unless asked for more. "
    "After every summary, suggest 3-5 quiz topics."
)


def create_or_get_content_agent(project_client: AIProjectClient) -> Agent:
    """Return the content-summarizer agent, creating it if it does not yet exist."""
    # Re-use an existing agent rather than provisioning a duplicate
    for existing in project_client.agents.list_agents():
        if existing.name == AGENT_NAME:
            return existing

    mcp_tool = McpTool(
        server_label="study-assistant-mcp",
        server_url=settings.MCP_SERVER_URL,
        allowed_tools=["fetch_url_content", "fetch_pdf_content"],
    )

    return project_client.agents.create_agent(
        model=settings.AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI,
        name=AGENT_NAME,
        instructions=_INSTRUCTIONS,
        tools=mcp_tool.definitions,
        tool_resources=mcp_tool.resources,
    )
