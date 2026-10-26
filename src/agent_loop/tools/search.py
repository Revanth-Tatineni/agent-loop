"""Web search via DuckDuckGo's HTML endpoint -- no API key needed. Deliberately best-effort:
DuckDuckGo's markup isn't a stable contract, so a layout change degrades to an empty result
list rather than raising and crashing whatever tool call the agent was in the middle of. The
`client` parameter exists so tests can inject an httpx.MockTransport instead of hitting the
real network.
"""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

SEARCH_URL = "https://html.duckduckgo.com/html/"


def duckduckgo_search(
    query: str, max_results: int = 5, *, client: httpx.Client | None = None
) -> list[dict[str, str]]:
    owns_client = client is None
    client = client or httpx.Client(timeout=10.0, headers={"User-Agent": "agent-loop/0.1"})
    try:
        response = client.post(SEARCH_URL, data={"q": query})
        response.raise_for_status()
        return _parse_results(response.text, max_results)
    finally:
        if owns_client:
            client.close()


def _parse_results(html: str, max_results: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for link in soup.select("a.result__a")[:max_results]:
        title = link.get_text(strip=True)
        url = link.get("href", "")
        snippet = ""
        body = link.find_parent("div", class_="result__body")
        if body is not None:
            snippet_node = body.select_one(".result__snippet")
            if snippet_node is not None:
                snippet = snippet_node.get_text(strip=True)
        if title and url:
            results.append({"title": title, "url": str(url), "snippet": snippet})
    return results
