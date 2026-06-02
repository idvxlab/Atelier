from __future__ import annotations

import html
import json
import os
import re
from typing import Any, Iterable

import httpx

from harness.types.tools import ToolSchema, ToolParam


WEB_SEARCH_SCHEMA = ToolSchema(
    name="web_search",
    description=(
        "Search the public web and return structured search results with title, URL, "
        "snippet, rank, and provider metadata. Uses Brave Search API when "
        "BRAVE_SEARCH_API_KEY is configured. Falls back to DuckDuckGo Instant Answer "
        "for local smoke testing only."
    ),
    params=[
        ToolParam(
            name="query",
            type="string",
            description="Search query string. Must be non-empty.",
        ),
        ToolParam(
            name="max_results",
            type="integer",
            description="Maximum number of results to return. Default 5, capped at 10.",
            required=False,
        ),
    ],
)


BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
DDG_INSTANT_ANSWER_URL = "https://api.duckduckgo.com/"

DEFAULT_SEARCH_RESULTS = 5
MAX_SEARCH_RESULTS = 10

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIharness/1.0)",
    "Accept": "application/json",
}


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    if not isinstance(value, str):
        value = str(value)

    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def _coerce_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default

    return max(min_value, min(value, max_value))


def _make_title(text: str, fallback: str = "Untitled") -> str:
    text = _clean_text(text)

    if not text:
        return fallback

    if " - " in text:
        return text.split(" - ", 1)[0].strip()

    return text[:100].strip()


async def web_search_tool(query: str, max_results: int = DEFAULT_SEARCH_RESULTS) -> str:
    query = (query or "").strip()
    max_results = _coerce_int(
        max_results,
        default=DEFAULT_SEARCH_RESULTS,
        min_value=1,
        max_value=MAX_SEARCH_RESULTS,
    )

    if not query:
        return _json(
            {
                "ok": False,
                "tool": "web_search",
                "query": query,
                "results": [],
                "error": {
                    "type": "invalid_request",
                    "message": "query must be a non-empty string",
                },
            }
        )

    brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY")

    if brave_api_key:
        return await _brave_web_search(
            query=query,
            max_results=max_results,
            api_key=brave_api_key,
        )

    return await _duckduckgo_instant_answer_fallback(
        query=query,
        max_results=max_results,
    )


async def _brave_web_search(query: str, max_results: int, api_key: str) -> str:
    try:
        timeout = httpx.Timeout(20.0, connect=5.0)

        async with httpx.AsyncClient(timeout=timeout, headers=DEFAULT_HEADERS) as client:
            response = await client.get(
                BRAVE_SEARCH_URL,
                params={
                    "q": query,
                    "count": max_results,
                },
                headers={
                    **DEFAULT_HEADERS,
                    "X-Subscription-Token": api_key,
                    "Cache-Control": "no-cache",
                },
            )

            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        return _json(
            {
                "ok": False,
                "tool": "web_search",
                "provider": "brave_search",
                "query": query,
                "results": [],
                "error": {
                    "type": "timeout",
                    "message": "Brave Search request timed out",
                },
            }
        )

    except httpx.HTTPStatusError as exc:
        return _json(
            {
                "ok": False,
                "tool": "web_search",
                "provider": "brave_search",
                "query": query,
                "results": [],
                "error": {
                    "type": "http_error",
                    "status_code": exc.response.status_code,
                    "message": f"HTTP {exc.response.status_code} from Brave Search",
                },
            }
        )

    except Exception as exc:
        return _json(
            {
                "ok": False,
                "tool": "web_search",
                "provider": "brave_search",
                "query": query,
                "results": [],
                "error": {
                    "type": "unknown_error",
                    "message": str(exc),
                },
            }
        )

    raw_results = data.get("web", {}).get("results", [])

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for item in raw_results:
        if len(results) >= max_results:
            break

        if not isinstance(item, dict):
            continue

        title = _clean_text(item.get("title"))
        url = _clean_text(item.get("url"))
        snippet = _clean_text(item.get("description"))

        if not title or not url:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        profile = item.get("profile")
        source = None

        if isinstance(profile, dict):
            source = _clean_text(profile.get("name")) or None

        results.append(
            {
                "rank": len(results) + 1,
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": source,
                "published": _clean_text(item.get("age")) or None,
            }
        )

    return _json(
        {
            "ok": True,
            "tool": "web_search",
            "provider": "brave_search",
            "query": query,
            "results": results,
            "meta": {
                "max_results": max_results,
                "is_full_web_search": True,
            },
        }
    )


def _iter_ddg_related_topics(items: list[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for item in items:
        if not isinstance(item, dict):
            continue

        topics = item.get("Topics")

        if isinstance(topics, list):
            yield from _iter_ddg_related_topics(topics)
        else:
            yield item


async def _duckduckgo_instant_answer_fallback(query: str, max_results: int) -> str:
    try:
        timeout = httpx.Timeout(20.0, connect=5.0)

        async with httpx.AsyncClient(timeout=timeout, headers=DEFAULT_HEADERS) as client:
            response = await client.get(
                DDG_INSTANT_ANSWER_URL,
                params={
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "no_redirect": "1",
                    "skip_disambig": "1",
                },
            )

            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        return _json(
            {
                "ok": False,
                "tool": "web_search",
                "provider": "duckduckgo_instant_answer_fallback",
                "query": query,
                "results": [],
                "error": {
                    "type": "timeout",
                    "message": "DuckDuckGo Instant Answer request timed out",
                },
            }
        )

    except httpx.HTTPStatusError as exc:
        return _json(
            {
                "ok": False,
                "tool": "web_search",
                "provider": "duckduckgo_instant_answer_fallback",
                "query": query,
                "results": [],
                "error": {
                    "type": "http_error",
                    "status_code": exc.response.status_code,
                    "message": f"HTTP {exc.response.status_code} from DuckDuckGo",
                },
            }
        )

    except Exception as exc:
        return _json(
            {
                "ok": False,
                "tool": "web_search",
                "provider": "duckduckgo_instant_answer_fallback",
                "query": query,
                "results": [],
                "error": {
                    "type": "search_error",
                    "message": str(exc),
                },
            }
        )

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    def add_result(title: str, url: str, snippet: str, source_type: str) -> None:
        if len(results) >= max_results:
            return

        title = _clean_text(title)
        url = _clean_text(url)
        snippet = _clean_text(snippet)

        if not title or not url:
            return

        if url in seen_urls:
            return

        seen_urls.add(url)

        results.append(
            {
                "rank": len(results) + 1,
                "title": title,
                "url": url,
                "snippet": snippet,
                "source_type": source_type,
            }
        )

    abstract_text = _clean_text(data.get("AbstractText"))
    abstract_url = _clean_text(data.get("AbstractURL"))
    heading = _clean_text(data.get("Heading"))

    if abstract_text and abstract_url:
        add_result(
            title=heading or _make_title(abstract_text, "DuckDuckGo instant answer"),
            url=abstract_url,
            snippet=abstract_text[:500],
            source_type="abstract",
        )

    for item in data.get("Results", []):
        if not isinstance(item, dict):
            continue

        text = _clean_text(item.get("Text"))
        url = _clean_text(item.get("FirstURL"))

        add_result(
            title=_make_title(text),
            url=url,
            snippet=text,
            source_type="result",
        )

    related_topics = data.get("RelatedTopics", [])

    if isinstance(related_topics, list):
        for item in _iter_ddg_related_topics(related_topics):
            text = _clean_text(item.get("Text"))
            url = _clean_text(item.get("FirstURL"))

            add_result(
                title=_make_title(text),
                url=url,
                snippet=text,
                source_type="related_topic",
            )

    return _json(
        {
            "ok": True,
            "tool": "web_search",
            "provider": "duckduckgo_instant_answer_fallback",
            "query": query,
            "results": results,
            "meta": {
                "max_results": max_results,
                "is_full_web_search": False,
                "warning": (
                    "DuckDuckGo Instant Answer is not a full web search API. "
                    "Configure BRAVE_SEARCH_API_KEY for real search results."
                ),
            },
        }
    )