"""
factories.py — constructs fully-wired AgentClient instances.

Single Responsibility: all object construction and dependency wiring lives
here, keeping app.py and agent_client.py free of configuration logic.

Dependency Inversion: app.py calls create_agent_client() and receives an
AgentClient — it never touches OpenAI, Azure, or tool imports directly.

Open/Closed: adding a new mode means adding a new _build_*_backend()
function and a branch in create_agent_client(), without touching
AgentClient, app.py, or the backends themselves.
"""
import functools
import json as _json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Ensure study-assistant/ is on sys.path so mcp_server.* imports resolve
# regardless of which directory the Flask app is launched from.
_STUDY_ROOT = Path(__file__).resolve().parent.parent
if str(_STUDY_ROOT) not in sys.path:
    sys.path.insert(0, str(_STUDY_ROOT))

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

# Configurable default question count — reads the same env var as quiz.py.
_QUIZ_NUM_QUESTIONS: int = max(1, int(os.getenv("QUIZ_NUM_QUESTIONS", "5")))


# ---------------------------------------------------------------------------
# Quiz state — updated every time generate_quiz is called so that score_quiz
# can grade answers deterministically instead of relying on LLM reasoning.
# ---------------------------------------------------------------------------
_active_quiz_answers: list = []


def _quiz_state_wrapper(fn):
    """Wrap a quiz-generation callable to capture the correct answers."""
    @functools.wraps(fn)
    def _wrapper(*args, **kwargs):
        global _active_quiz_answers
        result = fn(*args, **kwargs)
        try:
            if isinstance(result, list):
                questions = result
                # Normalise to JSON string so the LLM always receives the same format
                serialised = _json.dumps(questions)
            else:
                raw = str(result).strip()
                # Strip optional markdown code fences from LLM output
                if raw.startswith("```"):
                    raw = raw.split("```", 2)[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                    raw = raw.rsplit("```", 1)[0].strip()
                questions = _json.loads(raw)
                serialised = result
            _active_quiz_answers = [
                str(q.get("answer", "")).strip().upper() for q in questions
            ]
            return serialised
        except Exception as exc:
            logger.warning("Could not store quiz answers for scoring: %s", exc)
            return result
    return _wrapper


def _score_quiz(answers) -> str:
    """Compare the user's answers to the stored correct answers. Returns 'X/Y'."""
    if not _active_quiz_answers:
        return "Error: no active quiz. Please call generate_quiz first."
    if isinstance(answers, str):
        user = [a.strip().upper() for a in answers.replace(",", " ").split() if a.strip()]
    else:
        user = [str(a).strip().upper() for a in answers]
    total = len(_active_quiz_answers)
    correct = sum(
        1 for i, a in enumerate(user[:total]) if a == _active_quiz_answers[i]
    )
    return f"{correct}/{total}"


def create_agent_client(mode: str = "online"):
    """
    Build and return a fully-wired AgentClient (or Orchestrator) for the given mode.

    Args:
        mode: "online" or "multi-agent"

    Returns:
        AgentClient or Orchestrator ready to use.

    Raises:
        ValueError: for unknown mode or missing required env vars.
    """
    from agent_client import AgentClient

    if mode == "online":
        backend = _build_online_backend()
        return AgentClient(backend=backend)
    elif mode == "multi-agent":
        return create_multi_agent_client()
    else:
        raise ValueError(f"Unknown mode: {mode!r}. Must be 'online' or 'multi-agent'.")


# ── System prompts for specialist agents ──────────────────────────────────────

_ROUTER_PROMPT = (
    "You are an intent classifier for a personal study assistant app. "
    "Read the user's message and respond with EXACTLY ONE of these labels:\n"
    "  CONTENT  — user provides a URL or asks to fetch/read/summarise a web page.\n"
    "  QUIZ     — user asks for a quiz, or is submitting answers to quiz questions.\n"
    "  PROGRESS — user asks about past quiz scores, results, or study history.\n"
    "  GENERAL  — anything else: greetings, how-to questions, general conversation.\n"
    "Rules:\n"
    "- Reply with ONLY the single label word — no punctuation, no explanation.\n"
    "- When in doubt between QUIZ and another label, prefer QUIZ.\n"
    "- If the message looks like quiz answers (letters like A, B, C, D), label it QUIZ."
)

_CONTENT_PROMPT = (
    "You are the Content Agent of a personal study assistant. "
    "Your only responsibility is to fetch web pages and summarise their key learning points.\n"
    "RULES:\n"
    "1. When the user provides a URL, your FIRST action MUST be a fetch_url_content tool call.\n"
    "2. After fetching, produce a clear summary: main topic, key concepts, and 3-5 bullet points.\n"
    "3. Never generate quizzes or save progress — those belong to other agents."
)

_QUIZ_PROMPT = (
    "You are the Quiz Agent of a personal study assistant. "
    "You handle quiz generation, answer grading, and saving the result.\n"
    "CRITICAL RULES:\n"
    "1. When asked for a quiz, IMMEDIATELY call generate_quiz — never announce it first.\n"
    "2. After the user answers all questions, call score_quiz(answers=[...]) to get the exact score.\n"
    "3. NEVER estimate or calculate the score yourself — always use score_quiz.\n"
    "4. After scoring, call save_progress(topic, score, total) with the numbers from score_quiz.\n"
    "5. Only respond with text AFTER all required tool calls are complete."
)

_PROGRESS_PROMPT = (
    "You are the Progress Agent of a personal study assistant. "
    "Help the user save or review study results.\n"
    "When the user provides a topic and score, call save_progress to record it. "
    "Respond in an encouraging, motivating tone."
)

_GENERAL_PROMPT = (
    "You are a friendly personal study assistant. "
    "Help users understand the app: they can paste a URL to fetch content, "
    "ask for a quiz on any topic, or ask about their past scores. "
    "Be concise and welcoming."
)


def create_multi_agent_client():
    """
    Build an Orchestrator where each specialist is a real, separately deployed
    Microsoft Foundry agent — not just prompt engineering on a shared endpoint.

    How it works
    ────────────
    Each specialist reads its own endpoint env var (e.g. CONTENT_AGENT_ENDPOINT).
    That URL points to a DIFFERENT Foundry agent you created in the portal, with
    its own name, instructions, and knowledge.  Because the agent already knows
    its role from the Foundry portal, we do NOT inject a local system prompt —
    we pass system_prompt="" which tells OnlineAgentBackend to skip it.

    Fallback (shared endpoint)
    ──────────────────────────
    If a specialist env var is not set, it falls back to the shared AGENT_ENDPOINT
    and a local system prompt is injected — this reverts to the "prompt-based"
    multi-agent mode for that specialist only.  You can migrate one agent at a
    time as you create them in Foundry.

    Required env vars
    ─────────────────
    AGENT_ENDPOINT            — base fallback (your existing single agent endpoint)

    Optional per-specialist env vars (set these as you create agents in Foundry):
    ROUTER_AGENT_ENDPOINT     — classifies intent (outputs CONTENT/QUIZ/PROGRESS/GENERAL)
    CONTENT_AGENT_ENDPOINT    — fetches and summarises web pages
    QUIZ_AGENT_ENDPOINT       — generates quizzes, grades answers, saves progress
    PROGRESS_AGENT_ENDPOINT   — saves/reports study progress
    GENERAL_AGENT_ENDPOINT    — handles greetings and general questions

    Returns:
        Orchestrator that satisfies the same duck-typing interface as AgentClient.
    """
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from backends.online import OnlineAgentBackend, TOOL_SCHEMAS
    from backends.base import ToolRegistry
    from mcp_server.tools.fetch_url import fetch_url_content
    from mcp_server.tools.progress import save_progress
    from mcp_server.tools.quiz import generate_quiz as _generate_quiz_azure
    from agent_client import AgentClient
    from orchestrator import Orchestrator

    shared_raw = os.getenv("AGENT_ENDPOINT", "")
    if not shared_raw:
        raise ValueError("AGENT_ENDPOINT is not set in environment variables.")

    shared_endpoint = shared_raw.replace("/responses", "").rstrip("/")
    # MULTI_AGENT_MODEL lets you set a different model for specialists without
    # changing the single-agent ONLINE_MODEL.  Falls back to ONLINE_MODEL.
    main_model   = os.getenv("MULTI_AGENT_MODEL", os.getenv("ONLINE_MODEL", "gpt-4o"))
    router_model = os.getenv("ROUTER_MODEL", main_model)

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://ai.azure.com/.default"
    )

    def _clean(url: str) -> str:
        return url.replace("/responses", "").rstrip("/")

    def _client_for(env_var: str) -> OpenAI:
        """Create an OpenAI client for a named agent endpoint.

        When the env var is set → dedicated Foundry agent (its own endpoint).
        When not set           → fall back to the shared AGENT_ENDPOINT.
        """
        raw = os.getenv(env_var, "")
        ep  = _clean(raw) if raw else shared_endpoint
        return OpenAI(
            api_key=token_provider,
            base_url=ep,
            default_query={"api-version": "v1"},
        )

    def _prompt_for(env_var: str, fallback: str) -> str:
        """Determine the system prompt to inject.

        Dedicated Foundry agent (env var set) → "" (empty).
            The agent's instructions are configured in the Foundry portal;
            injecting a local prompt would conflict with them.
        Shared endpoint (env var not set)     → inject the fallback prompt.
            We need to tell the model its role because it is the generic agent.
        """
        return "" if os.getenv(env_var) else fallback

    # Per-name lookup of all tool schemas.
    _schema_by_name = {s["function"]["name"]: s for s in TOOL_SCHEMAS}

    # All callable tools — built once, shared across registry factories.
    _all_tools = {
        "fetch_url_content": fetch_url_content,
        "generate_quiz": _quiz_state_wrapper(
            lambda topic, num_questions=_QUIZ_NUM_QUESTIONS:
                _generate_quiz_azure(topic, int(num_questions))
        ),
        "score_quiz": _score_quiz,
        "save_progress": lambda topic, score, total: save_progress(
            topic, int(score), int(total)
        ),
    }

    def _registry_for(*names: str) -> ToolRegistry:
        reg = ToolRegistry()
        for name in names:
            reg.register(name, _all_tools[name])
        return reg

    def _specialist(ep_var: str, prompt_fallback: str, *tool_names: str) -> OnlineAgentBackend:
        """Build one specialist backend.

        ep_var          — env var name for this agent's Foundry endpoint
        prompt_fallback — system prompt to inject when sharing the main endpoint
        tool_names      — tools this specialist is allowed to call
        """
        return OnlineAgentBackend(
            client=_client_for(ep_var),
            model=main_model,
            registry=_registry_for(*tool_names),
            system_prompt=_prompt_for(ep_var, prompt_fallback),
            tool_schemas=[_schema_by_name[n] for n in tool_names],
        )

    # ── Router ────────────────────────────────────────────────────────────────
    # The router only needs to output one label word — it never calls tools.
    router_backend = OnlineAgentBackend(
        client=_client_for("ROUTER_AGENT_ENDPOINT"),
        model=router_model,
        registry=ToolRegistry(),
        system_prompt=_prompt_for("ROUTER_AGENT_ENDPOINT", _ROUTER_PROMPT),
        tool_schemas=[],
    )

    # ── Specialists ───────────────────────────────────────────────────────────
    specialists = {
        "content": AgentClient(
            _specialist("CONTENT_AGENT_ENDPOINT", _CONTENT_PROMPT, "fetch_url_content")
        ),
        "quiz": AgentClient(
            _specialist(
                "QUIZ_AGENT_ENDPOINT", _QUIZ_PROMPT,
                "generate_quiz", "score_quiz", "save_progress"
            )
        ),
        "progress": AgentClient(
            _specialist("PROGRESS_AGENT_ENDPOINT", _PROGRESS_PROMPT, "save_progress")
        ),
        "general": AgentClient(
            OnlineAgentBackend(
                client=_client_for("GENERAL_AGENT_ENDPOINT"),
                model=main_model,
                registry=ToolRegistry(),
                system_prompt=_prompt_for("GENERAL_AGENT_ENDPOINT", _GENERAL_PROMPT),
                tool_schemas=[],
            )
        ),
    }

    return Orchestrator(
        router=AgentClient(router_backend, max_history=1),
        specialists=specialists,
    )


# ── Backend builders ──────────────────────────────────────────────────────────

def _build_online_backend():
    """Wire up an OnlineAgentBackend with Foundry Chat Completions and local tools."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from backends.online import OnlineAgentBackend
    from backends.base import ToolRegistry
    from mcp_server.tools.fetch_url import fetch_url_content
    from mcp_server.tools.progress import save_progress
    from mcp_server.tools.quiz import generate_quiz as _generate_quiz_azure

    endpoint = os.getenv("AGENT_ENDPOINT", "").replace("/responses", "").rstrip("/")
    if not endpoint:
        raise ValueError("AGENT_ENDPOINT is not set in environment variables.")

    model = os.getenv("ONLINE_MODEL", "gpt-4o")

    client = OpenAI(
        api_key=get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://ai.azure.com/.default",
        ),
        base_url=endpoint,
        default_query={"api-version": "v1"},
    )

    registry = ToolRegistry()
    registry.register("fetch_url_content", fetch_url_content)
    registry.register(
        "save_progress",
        lambda topic, score, total: save_progress(topic, int(score), int(total))
    )
    registry.register(
        "generate_quiz",
        _quiz_state_wrapper(
            lambda topic, num_questions=_QUIZ_NUM_QUESTIONS: _generate_quiz_azure(topic, int(num_questions))
        )
    )
    registry.register("score_quiz", _score_quiz)

    return OnlineAgentBackend(client=client, model=model, registry=registry)
