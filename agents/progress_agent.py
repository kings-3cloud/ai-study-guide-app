from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import Agent, McpTool

from config import settings

AGENT_NAME = "progress-tracker"

_INSTRUCTIONS = (
    "You are a study progress tracking specialist. "
    "Use save_progress to log every study activity (topics read, quizzes taken, scores). "
    "Use get_progress to retrieve a user's history. "
    "Always report: topics studied, average quiz score, best and worst topics, "
    "and current study streak. "
    "Be encouraging \u2014 celebrate milestones. "
    "If a user has weak topics (score below 60%), recommend re-studying that content."
)


def create_or_get_progress_agent(project_client: AIProjectClient) -> Agent:
    """Return the progress-tracker agent, creating it if it does not yet exist."""
    for existing in project_client.agents.list_agents():
        if existing.name == AGENT_NAME:
            return existing

    mcp_tool = McpTool(
        server_label="study-assistant-mcp",
        server_url=settings.MCP_SERVER_URL,
        allowed_tools=["save_progress", "get_progress"],
    )

    return project_client.agents.create_agent(
        model=settings.AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI,
        name=AGENT_NAME,
        instructions=_INSTRUCTIONS,
        tools=mcp_tool.definitions,
        tool_resources=mcp_tool.resources,
    )
