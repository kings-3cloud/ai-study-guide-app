from pathlib import Path

import PyPDF2
import PyPDF2.errors
from mcp.server.fastmcp import FastMCP

_MAX_CHARS = 8000


def fetch_pdf_content(file_path: str) -> str:
    """Extract plain text from a local PDF file (max 8 000 chars)."""
    path = Path(file_path)

    try:
        reader = PyPDF2.PdfReader(str(path))
    except FileNotFoundError:
        return f"Error: file not found: {file_path!r}."
    except IsADirectoryError:
        return f"Error: {file_path!r} is a directory, not a file."
    except PermissionError:
        return f"Error: permission denied reading {file_path!r}."
    except PyPDF2.errors.PdfReadError as exc:
        return f"Error: could not parse PDF {file_path!r}: {exc}"
    except Exception as exc:
        return f"Error: unexpected error opening {file_path!r}: {exc}"

    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:
            pages.append(f"[page {i + 1} unreadable: {exc}]")

    text = "\n".join(pages).strip()

    if not text:
        return f"Warning: no extractable text found in {file_path!r}."

    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + "… [truncated]"

    return text


def register_tools(mcp: FastMCP) -> None:
    """Register fetch_pdf tools with the MCP server."""
    mcp.tool()(fetch_pdf_content)
