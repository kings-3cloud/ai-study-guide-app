"""
AgentBackend — abstract base for all agent communication backends.

Dependency Inversion: AgentClient depends on this abstraction, not on
concrete OpenAI or Azure clients.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., str]


class TransientBackendError(Exception):
    """
    Raised by a backend when the error is transient (e.g. rate limit, temporary
    service unavailability) and the caller should roll back the last user message
    so the user can safely retry without corrupting the conversation history.
    """


class AgentBackend(ABC):
    """Minimal interface for sending a conversation to an agent backend."""

    @property
    @abstractmethod
    def mode(self) -> str:
        """Return the mode identifier ('online' or 'multi-agent')."""

    @abstractmethod
    def send(self, history: List[Dict[str, Any]]) -> str:
        """
        Send the current conversation history and return the assistant reply.

        Args:
            history: Full conversation as a list of role/content dicts.

        Returns:
            The assistant's response text.
        """


class ToolRegistry:
    """
    Registry of callable tool handlers.

    Open/Closed: new tools are registered via register() without modifying
    the execute() dispatch logic.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        """Register a callable handler under the given tool name."""
        self._handlers[name] = handler

    def execute(self, name: str, arguments_json: str) -> str:
        """Parse JSON arguments and call the named tool. Returns a string result."""
        try:
            args: Dict[str, Any] = json.loads(arguments_json)
        except json.JSONDecodeError:
            return f"Error: invalid JSON arguments for tool '{name}'"

        handler = self._handlers.get(name)
        if handler is None:
            return f"Error: unknown tool '{name}'"

        try:
            return str(handler(**args))
        except Exception as exc:
            logger.error("Tool execution error (%s): %s", name, exc)
            return f"Error executing {name}: {exc}"

