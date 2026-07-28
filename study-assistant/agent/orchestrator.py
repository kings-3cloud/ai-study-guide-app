"""
Orchestrator — routes each user message to the right specialist AgentClient.

Architecture
------------
          User message
               │
               ▼
        RouterAgent (Foundry)         ← tiny system prompt, no tools, 1-word reply
         CONTENT │ QUIZ │ PROGRESS │ GENERAL
               │
               ▼
       ┌────────────────┐
       │ Specialist     │  ← its own system prompt + restricted tool set
       │  AgentClient   │
       └────────────────┘

Each specialist is a fully independent AgentClient with its own conversation
history and ToolRegistry.  The router is also a stateless AgentClient (
max_history=1) that only ever returns a single classification label.

Open/Closed: adding a new specialist means adding an entry to _INTENT_MAP
and passing the new AgentClient in the specialists dict — nothing else changes.
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Maps the router's classification label to the specialists dict key.
_INTENT_MAP: Dict[str, str] = {
    "CONTENT":  "content",
    "QUIZ":     "quiz",
    "PROGRESS": "progress",
    "GENERAL":  "general",
}


class Orchestrator:
    """
    Routes user messages to specialist AgentClient instances.

    Args:
        router:      A stateless AgentClient (max_history=1) whose backend has
                     no tools and a system prompt that outputs only a label word.
        specialists: Dict mapping intent labels (content/quiz/progress/general)
                     to their AgentClient instances.
    """

    def __init__(self, router, specialists: Dict[str, object]) -> None:
        self._router = router
        self._specialists = specialists
        # Remember the last-used specialist so we can continue mid-flow (e.g.
        # the user is mid-quiz and sends a short follow-up like "B, C, A").
        self._last_key: str = "quiz"

    # ── Duck-typing interface expected by app.py ──────────────────────────────

    @property
    def mode(self) -> str:
        return "multi-agent"

    def send_message(self, user_message: str) -> str:
        """Classify the message then delegate to the matching specialist."""
        key = self._classify(user_message)
        logger.info("Routing message to '%s' agent", key)
        return self._specialists[key].send_message(user_message)

    def reset_session(self) -> None:
        """Reset history for the router and all specialists."""
        self._router.reset_session()
        for client in self._specialists.values():
            client.reset_session()
        self._last_key = "quiz"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _classify(self, message: str) -> str:
        """Ask the router to classify the message intent; fall back gracefully."""
        try:
            raw = self._router.send_message(message).strip().upper()
        except Exception:
            logger.warning("Router failed; using last specialist '%s'", self._last_key)
            return self._last_key

        # The router should return a single word, but extract it defensively.
        for word in raw.split():
            candidate = word.strip(".,!?:")
            if candidate in _INTENT_MAP:
                key = _INTENT_MAP[candidate]
                self._last_key = key
                return key

        # Unknown label — continue in the last-used specialist (avoids losing
        # mid-quiz or mid-fetch context when the router mis-classifies).
        logger.warning("Router returned unrecognised label %r; keeping '%s'", raw, self._last_key)
        return self._last_key
