from __future__ import annotations

import httpx

from agent_loop.tools.search import duckduckgo_search

SAMPLE_HTML = """
<html><body>
<div class="result__body">
  <a class="result__a" href="https://example.com/anthropic">Anthropic - Home</a>
  <a class="result__snippet">Anthropic is an AI safety company.</a>
</div>
<div class="result__body">
  <a class="result__a" href="https://example.com/claude">Claude - Anthropic</a>
  <a class="result__snippet">Claude is Anthropic's family of models.</a>
</div>
</body></html>
"""


def _fake_transport(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=SAMPLE_HTML)


def test_parses_titles_urls_and_snippets():
    client = httpx.Client(transport=httpx.MockTransport(_fake_transport))
    results = duckduckgo_search("anthropic", max_results=5, client=client)

    assert len(results) == 2
    assert results[0] == {
        "title": "Anthropic - Home",
        "url": "https://example.com/anthropic",
        "snippet": "Anthropic is an AI safety company.",
    }


def test_respects_max_results():
    client = httpx.Client(transport=httpx.MockTransport(_fake_transport))
    results = duckduckgo_search("anthropic", max_results=1, client=client)
    assert len(results) == 1


def test_malformed_html_returns_empty_list_not_an_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>no results here</body></html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert duckduckgo_search("anything", client=client) == []
