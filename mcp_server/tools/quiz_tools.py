import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

_PROGRESS_DIR = os.environ.get("PROGRESS_DATA_DIR", "data/progress")
_DEFAULT_QUESTION_TYPES = ["multiple_choice", "true_false", "short_answer"]


def generate_quiz(
    content: str,
    num_questions: int,
    question_types: list[str] | None = None,
) -> str:
    """
    Create a structured quiz template from study content and persist it as JSON.

    Returns a JSON string of the quiz template dict. The 'questions' list is
    intentionally empty — the calling agent populates it with actual questions.

    Args:
        content: Source study material the quiz should be based on.
        num_questions: How many questions the agent should generate.
        question_types: Allowed question kinds. Defaults to
            ["multiple_choice", "true_false", "short_answer"].
    """
    resolved_types = list(_DEFAULT_QUESTION_TYPES) if question_types is None else question_types

    quiz: dict = {
        "quiz_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "template",
        "source_content": content,
        "num_questions": num_questions,
        "question_types": resolved_types,
        "questions": [],
    }

    try:
        quiz_dir = Path(_PROGRESS_DIR) / "quizzes"
        quiz_dir.mkdir(parents=True, exist_ok=True)
        quiz_file = quiz_dir / f"{quiz['quiz_id']}.json"
        quiz_file.write_text(
            json.dumps(quiz, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        # Persist failure is non-fatal — include a warning so the agent is aware
        quiz["save_warning"] = f"Could not save quiz file: {exc}"

    return json.dumps(quiz, indent=2, ensure_ascii=False)


def register_tools(mcp: FastMCP) -> None:
    """Register quiz tools with the MCP server."""
    mcp.tool()(generate_quiz)
