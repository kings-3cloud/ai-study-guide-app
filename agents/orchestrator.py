from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import Agent, ConnectedAgentTool

from config import settings

AGENT_NAME = "study-orchestrator"

_INSTRUCTIONS = (
    "You are a personal study assistant orchestrator. "
    "Delegate to the right specialist: "
    "(1) URL or PDF provided \u2192 Content Summarizer Agent, "
    "(2) Quiz requested \u2192 Quiz Generator Agent, "
    "(3) Progress/history asked \u2192 Progress Tracker Agent. "
    "For multi-step requests like 'study then quiz me', chain agents in order. "
    "Greet the user at the start and ask what they want to study today."
)


def create_or_get_orchestrator(
    project_client: AIProjectClient,
    content_agent: Agent,
    quiz_agent: Agent,
    progress_agent: Agent,
) -> Agent:
    """Return the study-orchestrator agent, creating it if it does not yet exist."""
    for existing in project_client.agents.list_agents():
        if existing.name == AGENT_NAME:
            return existing

    content_tool = ConnectedAgentTool(
        id=content_agent.id,
        name=content_agent.name,
        description="Fetches and summarizes study content from URLs and PDF files.",
    )
    quiz_tool = ConnectedAgentTool(
        id=quiz_agent.id,
        name=quiz_agent.name,
        description="Generates structured quizzes and scores user responses.",
    )
    progress_tool = ConnectedAgentTool(
        id=progress_agent.id,
        name=progress_agent.name,
        description="Logs study activities and retrieves a user's full progress history.",
    )

    return project_client.agents.create_agent(
        model=settings.AZURE_OPENAI_DEPLOYMENT_GPT4O,
        name=AGENT_NAME,
        instructions=_INSTRUCTIONS,
        tools=[
            *content_tool.definitions,
            *quiz_tool.definitions,
            *progress_tool.definitions,
        ],
    )
