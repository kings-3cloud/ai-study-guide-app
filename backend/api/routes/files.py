from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from backend.api.models import UploadResponse

router = APIRouter(prefix="/api")

# backend/api/routes/files.py -> parent x3 = backend/
_BACKEND_DIR = Path(__file__).parent.parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_UPLOADS_DIR = _BACKEND_DIR / "data" / "uploads"


@router.post("/upload-pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile) -> UploadResponse:
    """
    Accept a PDF file upload and save it to backend/data/uploads/.

    Returns the saved file path (relative to project root) so the client
    can pass it directly to the chat as: "Study this PDF: <file_path>".
    Rejects non-PDF files with HTTP 400.
    """
    # Strip any directory components from the filename to prevent path traversal
    safe_name = Path(file.filename or "").name

    if not safe_name:
        raise HTTPException(status_code=400, detail="No filename provided.")

    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF files are accepted; received {safe_name!r}.",
        )

    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = _UPLOADS_DIR / safe_name

    try:
        content = await file.read()
        save_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save uploaded file {safe_name!r}: {exc}",
        ) from exc
    finally:
        await file.close()

    # Return a project-root-relative path so the agent can locate the file
    relative_path = save_path.relative_to(_PROJECT_ROOT)
    return UploadResponse(file_path=str(relative_path))
