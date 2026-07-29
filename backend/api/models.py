from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Thread endpoints
# ---------------------------------------------------------------------------

class CreateThreadRequest(BaseModel):
    """Request body for POST /api/thread (no required fields)."""


class CreateThreadResponse(BaseModel):
    thread_id: str


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    thread_id: str
    message: str
    user_id: str = "default_user"


class ChatResponse(BaseModel):
    response: str
    thread_id: str


# ---------------------------------------------------------------------------
# Progress endpoint
# ---------------------------------------------------------------------------

class ProgressResponse(BaseModel):
    user_id: str
    history: list[dict]


# ---------------------------------------------------------------------------
# File upload endpoint
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    file_path: str
