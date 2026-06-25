"""
Tests for the improved web_search (Serper) and web_fetch (trafilatura) tools.

Uses respx to mock httpx calls so tests run offline and deterministically.
"""
from __future__ import annotations

import json
import os
import pytest
import respx
import httpx

from harness.tools.builtin import web_search, web_fetch


# ── web_search tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_serper_provider_extracts_results(monkeypatch):
    """Serper returns organic results + knowledge graph + PAA."""
    monkeypatch.setenv("SERPER_API_KEY", "test-serper-key")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "")  # disable brave

    mock_response = {
        "searchParameters": {"q": "python async", "gl": "us"},
        "organic": [
            {
                "title": "Python async/await — official docs",
                "link": "https://docs.python.org/3/library/asyncio.html",
                "snippet": "asyncio is a library to write concurrent code.",
                "date": "Yesterday",
            },
            {
                "title": "Real Python — Async IO in Python",
                "link": "https://realpython.com/async-io-python/",
                "snippet": "A complete guide to async programming.",
                "date": "2 days ago",
            },
            {
                "title": "Dupe result, same URL",
                "link": "https://docs.python.org/3/library/asyncio.html",
                "snippet": "duplicate",
            },
        ],
        "knowledgeGraph": {
            "title": "Python (programming language)",
            "type": "Programming language",
            "description": "Python is a high-level, interpreted programming language.",
            "website": "https://python.org",
        },
        "peopleAlsoAsk": [
            {"question": "What is asyncio?", "snippet": "asyncio is...", "link": "https://example.com"},
        ],
        "relatedSearches": [
            {"query": "asyncio python tutorial"},
            {"query": "python coroutine"},
        ],
        "searchMetadata": {
            "totalTimeTaken": 0.42,
            "googleDomain": "google.com",
            "credits": 1,
        },
    }

    with respx.mock:
        route = respx.post("https://google.serper.dev/search").mock(
            return_value=httpx.Response(200, json=mock_response),
        )
        result_str = await web_search.web_search_tool(query="python async", max_results=5)
        result = json.loads(result_str)

    assert route.called
    assert result["ok"] is True
    assert result["provider"] == "serper"
    assert result["query"] == "python async"
    assert result["result_count"] == 2  # third was duplicate URL
    assert result["results"][0]["rank"] == 1
    assert result["results"][0]["title"] == "Python async/await — official docs"
    assert result["results"][0]["source"] == "google_serper"
    # Knowledge graph + PAA + related present
    assert "knowledge_graph" in result
    assert result["knowledge_graph"]["title"] == "Python (programming language)"
    assert len(result["people_also_ask"]) == 1
    assert "python coroutine" in result["related_searches"]
    # Search metadata
    assert result["meta"]["credits_used"] == 1


@pytest.mark.asyncio
async def test_serper_takes_priority_over_brave(monkeypatch):
    """If both keys are set, Serper (Google) wins."""
    monkeypatch.setenv("SERPER_API_KEY", "serper-key")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-key")

    with respx.mock:
        serper_route = respx.post("https://google.serper.dev/search").mock(
            return_value=httpx.Response(200, json={"organic": []}),
        )
        brave_route = respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=httpx.Response(200, json={"web": {"results": []}}),
        )
        result = json.loads(await web_search.web_search_tool("hello"))

    assert serper_route.called
    assert not brave_route.called
    assert result["provider"] == "serper"


@pytest.mark.asyncio
async def test_brave_used_when_serper_unavailable(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-key")

    with respx.mock:
        brave_route = respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=httpx.Response(200, json={
                "web": {
                    "results": [
                        {
                            "title": "Brave Result",
                            "url": "https://example.com",
                            "description": "a brave result",
                        }
                    ]
                }
            }),
        )
        result = json.loads(await web_search.web_search_tool("hi"))

    assert brave_route.called
    assert result["provider"] == "brave_search"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Brave Result"


@pytest.mark.asyncio
async def test_serper_http_error(monkeypatch):
    """Serper returns 401/403/500 with explicit error payload."""
    monkeypatch.setenv("SERPER_API_KEY", "bad-key")
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)

    with respx.mock:
        respx.post("https://google.serper.dev/search").mock(
            return_value=httpx.Response(403, text="Forbidden - invalid API key"),
        )
        result = json.loads(await web_search.web_search_tool("anything"))

    assert result["ok"] is False
    assert result["provider"] == "serper"
    assert result["error"]["type"] == "http_error"
    assert "403" in result["error"]["message"]


@pytest.mark.asyncio
async def test_empty_query_returns_invalid_request(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    result = json.loads(await web_search.web_search_tool("   "))
    assert result["ok"] is False
    assert result["error"]["type"] == "invalid_request"


@pytest.mark.asyncio
async def test_serper_no_results_is_clean(monkeypatch):
    """Serper returning empty organic array → result_count: 0, ok: True."""
    monkeypatch.setenv("SERPER_API_KEY", "k")
    with respx.mock:
        respx.post("https://google.serper.dev/search").mock(
            return_value=httpx.Response(200, json={"organic": []}),
        )
        result = json.loads(await web_search.web_search_tool("zzznevermatches"))
    assert result["ok"] is True
    assert result["result_count"] == 0
    assert result["results"] == []


# ── web_fetch tests ─────────────────────────────────────────────────────────

def test_html_extraction_strips_navigation():
    html = """<html><head><title>Article</title></head><body>
    <nav>navigation junk</nav>
    <header>site header</header>
    <article><h1>Real Title</h1><p>Real content here.</p></article>
    <aside>sidebar ad</aside>
    <footer>site footer</footer></body></html>"""
    title, text = web_fetch._html_to_text(html)
    assert "navigation junk" not in text
    assert "site header" not in text
    assert "sidebar ad" not in text
    assert "site footer" not in text
    # Article body should be present (either via trafilatura or bs4 fallback)
    assert "Real content" in text or "Real Title" in text


def test_html_extraction_handles_pure_text():
    html = "<html><body><p>hello world</p></body></html>"
    _, text = web_fetch._html_to_text(html)
    assert "hello world" in text


def test_html_extraction_falls_back_when_trafilatura_fails():
    """Pathological HTML shouldn't crash; should fall back to bs4/regex."""
    html = "<<<<not real html" * 50 + "<p>but has paragraph</p>"
    _, text = web_fetch._html_to_text(html)
    # Should produce something non-empty without raising
    assert isinstance(text, str)


@pytest.mark.asyncio
async def test_user_agent_override_via_env(monkeypatch):
    """WEB_FETCH_USER_AGENT can override the default UA."""
    monkeypatch.setenv("WEB_FETCH_USER_AGENT", "TestAgent/1.0")
    # Re-import the module to pick up env (since DEFAULT_HEADERS is module-level)
    import importlib
    importlib.reload(web_fetch)
    assert web_fetch.DEFAULT_HEADERS["User-Agent"] == "TestAgent/1.0"
    # Restore
    monkeypatch.delenv("WEB_FETCH_USER_AGENT", raising=False)
    importlib.reload(web_fetch)
    assert "Mozilla" in web_fetch.DEFAULT_HEADERS["User-Agent"]


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_ips():
    """URL pointing at 127.0.0.1 / private IP should be rejected."""
    result = json.loads(await web_fetch.web_fetch_tool(url="http://127.0.0.1:8000/"))
    assert result["ok"] is False
    assert result["error"]["type"] == "invalid_url"

    result = json.loads(await web_fetch.web_fetch_tool(url="http://10.0.0.1/"))
    assert result["ok"] is False

    result = json.loads(await web_fetch.web_fetch_tool(url="http://localhost/"))
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_web_fetch_handles_http_error(monkeypatch):
    """When the server returns 500, web_fetch returns a structured error."""
    with respx.mock:
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )
        result = json.loads(await web_fetch.web_fetch_tool(url="https://example.com/"))
    assert result["ok"] is False
    assert result["error"]["type"] == "http_error"
    assert result["status_code"] == 500
