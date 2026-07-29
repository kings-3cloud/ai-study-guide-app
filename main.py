import subprocess
import sys
import time
from urllib.parse import urlparse

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from agents.content_agent import create_or_get_content_agent
from agents.orchestrator import create_or_get_orchestrator
from agents.progress_agent import create_or_get_progress_agent
from agents.quiz_agent import create_or_get_quiz_agent
from config import settings

_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "expired"}
_POLL_INTERVAL = 1.5  # seconds between run-status polls


# ---------------------------------------------------------------------------
# MCP server lifecycle
# ---------------------------------------------------------------------------

def _mcp_port() -> int:
    """Parse the port from MCP_SERVER_URL (default 8000)."""
    parsed = urlparse(settings.MCP_SERVER_URL)
    return parsed.port or 8000


def _start_mcp_server() -> subprocess.Popen:
    """Launch the MCP server as a background SSE subprocess."""
    port = _mcp_port()
    proc = subprocess.Popen(
        [sys.executable, "mcp_server/server.py", "--transport", "sse", "--port", str(port)],
        # Inherit parent stdio so server logs appear in the console
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    # Brief pause to let the HTTP server bind before agents connect
    time.sleep(1.5)
    print(f"[MCP] Server running on port {port} (pid={proc.pid})")
    return proc


def _stop_mcp_server(proc: subprocess.Popen) -> None:
    """Terminate the MCP server gracefully."""
    if proc.poll() is not None:
        return  # already exited
    proc.terminate()
    try:
        proc.wait(timeout=5)
        print("[MCP] Server stopped.")
    except subprocess.TimeoutExpired:
        proc.kill()
        print("[MCP] Server force-killed (did not exit within 5 s).")


# ---------------------------------------------------------------------------
# Azure AI Agent helpers
# ---------------------------------------------------------------------------

def _get_latest_assistant_text(project_client: AIProjectClient, thread_id: str) -> str:
    """Return the text of the most recent assistant message in the thread."""
    messages = project_client.agents.list_messages(thread_id=thread_id)
    last_text = "(No response received)"
    for msg in messages.data:
        if msg.role == "assistant":
            for part in msg.content:
                if part.type == "text":
                    last_text = part.text.value
    return last_text


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp_proc = _start_mcp_server()

    try:
        print("\n" + "=" * 48)
        print("  Personal Study Assistant")
        print("=" * 48)
        print("Connecting to Azure AI Foundry...")

        project_client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=settings.PROJECT_CONNECTION_STRING,
        )

        with project_client:
            print("Provisioning agents (create-or-retrieve)...")

            content_agent = create_or_get_content_agent(project_client)
            print(f"  [content-summarizer]  id={content_agent.id}")

            quiz_agent = create_or_get_quiz_agent(project_client)
            print(f"  [quiz-generator]      id={quiz_agent.id}")

            progress_agent = create_or_get_progress_agent(project_client)
            print(f"  [progress-tracker]    id={progress_agent.id}")

            orchestrator = create_or_get_orchestrator(
                project_client, content_agent, quiz_agent, progress_agent
            )
            print(f"  [study-orchestrator]  id={orchestrator.id}")

            thread = project_client.agents.create_thread()
            print(f"\nThread ready: {thread.id}")
            print("Type 'quit' or 'exit' to end the session.")
            print("-" * 48 + "\n")

            while True:
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nSession interrupted.")
                    break

                if not user_input:
                    continue
                if user_input.lower() in {"quit", "exit"}:
                    print("Ending session. Goodbye!")
                    break

                # Post user message
                project_client.agents.create_message(
                    thread_id=thread.id,
                    role="user",
                    content=user_input,
                )

                # Create run and poll until terminal status
                print("[study-orchestrator] Thinking...", flush=True)
                run = project_client.agents.create_run(
                    thread_id=thread.id,
                    assistant_id=orchestrator.id,
                )

                while run.status not in _TERMINAL_STATUSES:
                    time.sleep(_POLL_INTERVAL)
                    run = project_client.agents.get_run(
                        thread_id=thread.id,
                        run_id=run.id,
                    )

                if run.status == "completed":
                    response = _get_latest_assistant_text(project_client, thread.id)
                    print(f"\n[Study Assistant]\n{response}\n")
                else:
                    print(f"\n[Error] Run ended with status '{run.status}'.\n")

    finally:
        _stop_mcp_server(mcp_proc)


if __name__ == "__main__":
    main()
