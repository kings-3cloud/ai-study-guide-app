"""
OnlineAgentBackend — routes messages to a Foundry-hosted model via the Chat
Completions API with local tool execution.

Switching from responses.create() to chat.completions.create() lets us run
tools (fetch_url_content, generate_quiz, score_quiz, save_progress) locally,
which is required for save_progress to write to the local progress file.
"""
import logging
from typing import Any, Dict, List

from openai import OpenAI, RateLimitError, APIStatusError

from .base import AgentBackend, TransientBackendError, ToolRegistry

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a Personal Study Assistant. Help the user learn by fetching content, "
    "generating quizzes, and tracking progress. Be concise and encouraging.\n"
    "CRITICAL RULES — follow these without exception:\n"
    "1. NEVER send a plain-text message that only describes what you are about to do. "
    "   If a tool call is needed, make it your FIRST action \u2014 not a text announcement.\n"
    "2. When the user provides a URL, your very first action MUST be a fetch_url_content tool call.\n"
    "3. When the user asks for a quiz, immediately call generate_quiz.\n"
    "4. After the user answers all quiz questions:\n"
    "   a. Call score_quiz(answers=[...]) \u2014 NEVER estimate or guess the score.\n"
    "   b. Then call save_progress(topic, score, total) with the numbers from score_quiz.\n"
    "5. Only respond with text AFTER all required tool calls are complete.\n"
)

# Phrases that indicate the model announced an upcoming tool call instead of making one.
_PENDING_TOOL_PHRASES = frozenset({
    "one moment", "just a moment", "please wait", "stand by",
    "fetching", "let me fetch", "i'll fetch", "i will fetch",
    "gathering", "let me gather", "i'll gather",
    "looking that up", "i'll look", "let me look",
    "pulling up", "retrieving", "i'll retrieve",
})

# Maximum number of times the loop will nudge the model before returning its text as-is.
_MAX_NUDGES = 2

# OpenAI function-calling schema for all registered tools.
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_url_content",
            "description": "Fetch and return the plain-text content of a web page or PDF URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Fully-qualified URL to fetch"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_quiz",
            "description": "Generate multiple-choice quiz questions on a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The subject to quiz on"},
                    "num_questions": {"type": "integer", "description": "Number of questions (default 5)"}
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_progress",
            "description": "Save a quiz result to the study progress log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "score": {"type": "integer", "description": "Number of correct answers"},
                    "total": {"type": "integer", "description": "Total number of questions"}
                },
                "required": ["topic", "score", "total"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "score_quiz",
            "description": (
                "Grade the user's answers for the current quiz. "
                "Returns the exact score as 'X/Y'. "
                "Always call this after the user has answered all questions "
                "\u2014 never guess or calculate the score yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "User's answer letters in question order, e.g. ['A', 'C', 'B', 'D', 'A']"
                    }
                },
                "required": ["answers"]
            }
        }
    }
]


def _looks_like_announcement(text: str) -> bool:
    """Return True when the response is a short preamble announcing an upcoming tool call."""
    if len(text) > 400:
        return False
    lower = text.lower()
    return any(phrase in lower for phrase in _PENDING_TOOL_PHRASES)


class OnlineAgentBackend(AgentBackend):
    """Agentic Chat Completions loop against the Foundry endpoint with local tool execution.

    Args:
        client:        OpenAI-compatible client pointed at the Foundry endpoint.
        model:         Deployed model name (e.g. "gpt-4o").
        registry:      ToolRegistry with the tools this backend may call.
        system_prompt: Override the shared default system prompt. Useful for
                       giving each specialist agent its own role and constraints.
        tool_schemas:  Override the shared TOOL_SCHEMAS list. Pass a subset to
                       restrict which tools this backend may call. Pass an empty
                       list [] for the router agent (which needs no tools).
    """

    def __init__(
        self,
        client: OpenAI,
        model: str,
        registry: ToolRegistry,
        system_prompt: str | None = None,
        tool_schemas: List[Dict[str, Any]] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._registry = registry
        self._system_prompt = system_prompt   # None → shared default | "" → no override (Foundry agent) | str → inject
        self._tool_schemas = tool_schemas     # None → use full TOOL_SCHEMAS

    @property
    def mode(self) -> str:
        return "online"

    def send(self, history: List[Dict[str, Any]]) -> str:
        # system_prompt semantics:
        #   None  → inject the shared default (single-agent mode)
        #   ""    → inject nothing — this backend points at a real Foundry agent whose
        #           instructions are set in the portal; the model already knows its role
        #   "..." → inject the given specialist prompt (shared-endpoint multi-agent mode)
        effective_prompt = _SYSTEM_PROMPT if self._system_prompt is None else self._system_prompt
        tool_schemas     = self._tool_schemas if self._tool_schemas is not None else TOOL_SCHEMAS

        if effective_prompt:
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": effective_prompt}
            ] + list(history)
        else:
            # Dedicated Foundry agent — do not override its built-in instructions.
            messages = list(history)

        nudge_count = 0
        while True:
            # Build create() kwargs — omit tools/tool_choice when schemas list is empty
            # so Foundry does not reject the request with a validation error.
            create_kwargs: Dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.7,
            }
            if tool_schemas:
                create_kwargs["tools"] = tool_schemas
                create_kwargs["tool_choice"] = "auto"

            try:
                response = self._client.chat.completions.create(**create_kwargs)
            except RateLimitError:
                raise TransientBackendError(
                    "⚠️ The model is currently rate-limited (HTTP 429). "
                    "Please wait a moment and try again."
                )
            except APIStatusError as exc:
                logger.error("API error in online backend: %s", exc)
                raise TransientBackendError(
                    f"⚠️ The model returned an error ({exc.status_code}): {exc.message}"
                )

            choice = response.choices[0]

            if choice.finish_reason == "tool_calls":
                messages.append(choice.message)
                for tc in choice.message.tool_calls:
                    result = self._registry.execute(tc.function.name, tc.function.arguments)
                    logger.info("Tool %s → %s", tc.function.name, str(result)[:120])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                content = choice.message.content or ""
                if nudge_count < _MAX_NUDGES and _looks_like_announcement(content):
                    nudge_count += 1
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "system",
                        "content": "Call the appropriate tool now. Do not generate a text response first.",
                    })
                else:
                    return content

