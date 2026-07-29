from html.parser import HTMLParser

import httpx
from mcp.server.fastmcp import FastMCP

_MAX_CHARS = 8000


class _TextExtractor(HTMLParser):
    """Collects visible text nodes, skipping script/style/head content."""

    _SKIP_TAGS = {"script", "style", "head", "meta", "link", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        return " ".join(self._parts)


def fetch_url_content(url: str) -> str:
    """Fetch a web page and return its plain-text content (max 8 000 chars)."""
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.TimeoutException:
        return f"Error: request to {url!r} timed out after 10 seconds."
    except httpx.HTTPStatusError as exc:
        return f"Error: HTTP {exc.response.status_code} from {url!r}."
    except httpx.RequestError as exc:
        return f"Error: could not reach {url!r}: {exc}"

    parser = _TextExtractor()
    parser.feed(html)
    text = parser.get_text()

    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + "… [truncated]"

    return text


def register_tools(mcp: FastMCP) -> None:
    """Register fetch_url tools with the MCP server."""
    mcp.tool()(fetch_url_content)
