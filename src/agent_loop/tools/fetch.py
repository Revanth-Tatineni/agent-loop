"""Fetches a URL and extracts its visible text, for an agent reading a page a search result
pointed at. Strips script/style/noscript tags and collapses whitespace; doesn't render
JavaScript, so a page that needs client-side rendering to show its real content won't yield
much -- a known, documented limitation, not a bug.
"""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup


def fetch_text(url: str, max_chars: int = 4000, *, client: httpx.Client | None = None) -> str:
    owns_client = client is None
    client = client or httpx.Client(
        timeout=10.0, follow_redirects=True, headers={"User-Agent": "agent-loop/0.1"}
    )
    try:
        response = client.get(url)
        response.raise_for_status()
        return _extract_text(response.text, max_chars)
    finally:
        if owns_client:
            client.close()


def _extract_text(html: str, max_chars: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return text[:max_chars]
