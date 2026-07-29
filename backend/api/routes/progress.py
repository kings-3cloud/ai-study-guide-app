import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.api.models import ProgressResponse

router = APIRouter(prefix="/api")

_SAFE_USER_ID = re.compile(r"^[\w\-]{1,64}$")

# Resolve data directory relative to this file so it works regardless of CWD.
# backend/api/routes/progress.py -> parent x3 = backend/ -> data/progress/
_BACKEND_DIR = Path(__file__).parent.parent.parent
_PROGRESS_DIR = _BACKEND_DIR / "data" / "progress"


@router.get("/progress/{user_id}", response_model=ProgressResponse)
def get_progress(user_id: str) -> ProgressResponse:
    """
    Return the full study history for a user.

    Reads directly from the JSON file written by the MCP save_progress tool.
    Raises 404 if no history exists yet for this user.
    """
    if not _SAFE_USER_ID.match(user_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid user_id {user_id!r}. "
                "Use only letters, digits, hyphens, and underscores (max 64 chars)."
            ),
        )

    path = _PROGRESS_DIR / f"{user_id}.json"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No progress found for user {user_id!r}.",
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        history: list[dict] = raw if isinstance(raw, list) else []
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Progress file for user {user_id!r} is corrupted: {exc}",
        )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read progress data for user {user_id!r}: {exc}",
        )

    return ProgressResponse(user_id=user_id, history=history)
