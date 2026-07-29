from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import Agent, McpTool

from config import settings

AGENT_NAME = "quiz-generator"

_INSTRUCTIONS = (
    "You are an expert educational quiz creator. "
    "Generate quizzes from provided content or topics. "
    "Always create a balanced mix: 60% multiple choice (4 options labeled A\u2013D), "
    "20% true/false, 20% short answer. "
    "For every question include the correct answer and a one-sentence explanation. "
    "Default to 5 questions unless specified. "
    "Use the generate_quiz tool to structure and save quiz data before presenting it. "
    "After the user answers, score their responses."
)


def create_or_get_quiz_agent(project_client: AIProjectClient) -> Agent:
    """Return the quiz-generator agent, creating it if it does not yet exist."""
    for existing in project_client.agents.list_agents():
        if existing.name == AGENT_NAME:
            return existing

    mcp_tool = McpTool(
        server_label="study-assistant-mcp",
        server_url=settings.MCP_SERVER_URL,
        allowed_tools=["generate_quiz"],
    )

    return project_client.agents.create_agent(
        model=settings.AZURE_OPENAI_DEPLOYMENT_GPT4O,
        name=AGENT_NAME,
        instructions=_INSTRUCTIONS,
        tools=mcp_tool.definitions,
        tool_resources=mcp_tool.resources,
    )
