import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agents.content_agent import create_or_get_content_agent
from agents.orchestrator import create_or_get_orchestrator
from agents.progress_agent import create_or_get_progress_agent
from agents.quiz_agent import create_or_get_quiz_agent
from backend.api.routes import chat, files, progress
from config import settings

_PROJECT_ROOT = Path(__file__).parent.parent
_MCP_SERVER = _PROJECT_ROOT / "mcp_server" / "server.py"
_FRONTEND_DIR = _PROJECT_ROOT / "frontend"

_CORS_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


# ---------------------------------------------------------------------------
# MCP server helpers
# ---------------------------------------------------------------------------

def _mcp_port() -> int:
    parsed = urlparse(settings.MCP_SERVER_URL)
    return parsed.port or 8000


def _start_mcp_server() -> subprocess.Popen:
    port = _mcp_port()
    proc = subprocess.Popen(
        [sys.executable, str(_MCP_SERVER), "--transport", "sse", "--port", str(port)],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    # Allow the HTTP server time to bind before agents attempt to connect
    time.sleep(1.5)
    return proc


def _stop_mcp_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return  # already exited
    proc.terminate()
    try:
        proc.wait(timeout=5)
        print("[shutdown] MCP server stopped.")
    except subprocess.TimeoutExpired:
        proc.kill()
        print("[shutdown] MCP server force-killed.")


# ---------------------------------------------------------------------------
# Lifespan: startup and shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("[startup] Launching MCP server...")
    mcp_proc = _start_mcp_server()
    app.state.mcp_proc = mcp_proc
    print(f"[startup] MCP server running on port {_mcp_port()} (pid={mcp_proc.pid})")

    print("[startup] Connecting to Azure AI Foundry...")
    project_client = AIProjectClient.from_connection_string(
        credential=DefaultAzureCredential(),
        conn_str=settings.PROJECT_CONNECTION_STRING,
    )
    app.state.project_client = project_client

    print("[startup] Provisioning agents (create-or-retrieve)...")
    content_agent = create_or_get_content_agent(project_client)
    quiz_agent = create_or_get_quiz_agent(project_client)
    progress_agent = create_or_get_progress_agent(project_client)
    orchestrator = create_or_get_orchestrator(
        project_client, content_agent, quiz_agent, progress_agent
    )

    app.state.content_agent_id = content_agent.id
    app.state.quiz_agent_id = quiz_agent.id
    app.state.progress_agent_id = progress_agent.id
    app.state.orchestrator_agent_id = orchestrator.id

    print(f"  [content-summarizer]  id={content_agent.id}")
    print(f"  [quiz-generator]      id={quiz_agent.id}")
    print(f"  [progress-tracker]    id={progress_agent.id}")
    print(f"  [study-orchestrator]  id={orchestrator.id}")
    print("[startup] Ready — application is live.")

    yield  # Application runs here

    # --- Shutdown ---
    print("[shutdown] Shutting down...")
    _stop_mcp_server(app.state.mcp_proc)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title="Study Assistant API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes — registered before the static mount so they take precedence
app.include_router(chat.router)
app.include_router(progress.router)
app.include_router(files.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Static files — mounted LAST; serves frontend/index.html at "/"
# Skipped gracefully if the frontend directory does not exist yet
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
else:
    print(
        f"[warning] Frontend directory not found at {_FRONTEND_DIR}. "
        "Static files will not be served until the frontend is built."
    )
