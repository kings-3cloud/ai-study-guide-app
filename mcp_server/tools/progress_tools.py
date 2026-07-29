import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

_PROGRESS_DIR = os.environ.get("PROGRESS_DATA_DIR", "data/progress")

# Restrict user_id to safe filename characters to prevent path traversal
_SAFE_USER_ID = re.compile(r"^[\w\-]{1,64}$")


def _validate_user_id(user_id: str) -> str | None:
    """Return an error message if user_id is invalid, else None."""
    if not _SAFE_USER_ID.match(user_id):
        return (
            f"Error: invalid user_id {user_id!r}. "
            "Use only letters, digits, hyphens, and underscores (max 64 chars)."
        )
    return None


def _user_progress_path(user_id: str) -> Path:
    return Path(_PROGRESS_DIR) / f"{user_id}.json"


def save_progress(user_id: str, activity_type: str, data: dict) -> str:
    """
    Append a study activity entry to the user's progress history JSON file.

    Returns a confirmation string on success, or an error message on failure.
    """
    if error := _validate_user_id(user_id):
        return error

    progress_dir = Path(_PROGRESS_DIR)
    try:
        progress_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"Error: could not create progress directory: {exc}"

    path = _user_progress_path(user_id)

    history: list[dict] = []
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            history = raw if isinstance(raw, list) else []
        except (json.JSONDecodeError, OSError):
            history = []  # treat corrupted file as empty; will be overwritten

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "activity_type": activity_type,
        "data": data,
    }
    history.append(entry)

    try:
        path.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        return f"Error: could not write progress for user {user_id!r}: {exc}"

    return (
        f"Progress saved for user {user_id!r}: "
        f"{activity_type!r} recorded at {entry['timestamp']}."
    )


def get_progress(user_id: str) -> str:
    """
    Return the full study progress history for a user as a JSON string.

    Returns a plain message if no history exists yet.
    """
    if error := _validate_user_id(user_id):
        return error

    path = _user_progress_path(user_id)

    if not path.exists():
        return f"No progress found for user {user_id!r}."

    try:
        history = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"Error: progress file for user {user_id!r} is corrupted: {exc}"
    except OSError as exc:
        return f"Error: could not read progress for user {user_id!r}: {exc}"

    return json.dumps(history, indent=2, ensure_ascii=False)


def register_tools(mcp: FastMCP) -> None:
    """Register progress tools with the MCP server."""
    mcp.tool()(save_progress)
    mcp.tool()(get_progress)
