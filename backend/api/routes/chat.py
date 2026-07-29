import time

from fastapi import APIRouter, HTTPException, Request

from backend.api.models import (
    ChatRequest,
    ChatResponse,
    CreateThreadRequest,
    CreateThreadResponse,
)

router = APIRouter(prefix="/api")

_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "expired"}
_POLL_INTERVAL = 1.5  # seconds between run-status polls


def _get_latest_assistant_text(project_client, thread_id: str) -> str:
    """Return the text of the most recent assistant message in the thread."""
    messages = project_client.agents.list_messages(thread_id=thread_id)
    last_text = "(No response received)"
    for msg in messages.data:
        if msg.role == "assistant":
            for part in msg.content:
                if part.type == "text":
                    last_text = part.text.value
    return last_text


@router.post("/thread", response_model=CreateThreadResponse)
def create_thread(body: CreateThreadRequest, request: Request) -> CreateThreadResponse:
    """Create a new agent conversation thread and return its ID."""
    project_client = request.app.state.project_client
    thread = project_client.agents.create_thread()
    return CreateThreadResponse(thread_id=thread.id)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """
    Send a user message to the orchestrator and return its response.

    Polls the run until a terminal status is reached. Raises HTTP 500
    if the run ends in any status other than 'completed'.
    """
    project_client = request.app.state.project_client
    orchestrator_agent_id: str = request.app.state.orchestrator_agent_id

    # Post the user's message to the thread
    project_client.agents.create_message(
        thread_id=body.thread_id,
        role="user",
        content=body.message,
    )

    # Kick off a run against the orchestrator
    run = project_client.agents.create_run(
        thread_id=body.thread_id,
        assistant_id=orchestrator_agent_id,
    )

    # Poll until the run reaches a terminal state
    while run.status not in _TERMINAL_STATUSES:
        time.sleep(_POLL_INTERVAL)
        run = project_client.agents.get_run(
            thread_id=body.thread_id,
            run_id=run.id,
        )

    if run.status != "completed":
        raise HTTPException(
            status_code=500,
            detail=f"Run ended with status '{run.status}' for thread '{body.thread_id}'.",
        )

    response_text = _get_latest_assistant_text(project_client, body.thread_id)
    return ChatResponse(response=response_text, thread_id=body.thread_id)
