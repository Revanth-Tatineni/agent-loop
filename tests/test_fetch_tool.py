from __future__ import annotations

import httpx

from agent_loop.tools.fetch import fetch_text

SAMPLE_PAGE = """
<html><head><style>.x{color:red}</style><script>var x=1;</script></head>
<body><h1>Title</h1><p>Some   visible   text.</p><script>console.log('x')</script></body></html>
"""


def test_strips_script_and_style_and_collapses_whitespace():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SAMPLE_PAGE)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    text = fetch_text("https://example.com", client=client)

    assert text == "Title Some visible text."


def test_truncates_to_max_chars():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<p>" + ("x" * 100) + "</p>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    text = fetch_text("https://example.com", max_chars=10, client=client)
    assert text == "x" * 10
