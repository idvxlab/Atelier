from __future__ import annotations
import re

import httpx

from harness.types.tools import ToolSchema, ToolParam

WEB_SEARCH_SCHEMA = ToolSchema(
    name="web_search",
    description="Search the web using DuckDuckGo (no API key required) and return titles, links, and snippets.",
    params=[
        ToolParam(name="query", type="string", description="Search query string"),
        ToolParam(
            name="max_results",
            type="integer",
            description="Maximum number of results to return (default 5)",
            required=False,
        ),
    ],
)


async def web_search_tool(query: str, max_results: int = 5) -> str:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            html = response.text
    except httpx.TimeoutException:
        return "Error: search request timed out"
    except httpx.HTTPStatusError as exc:
        return f"Error: HTTP {exc.response.status_code} during search"
    except Exception as exc:
        return f"Error during search: {exc}"

    # Parse result blocks: each result is a <a class="result__a"> for title/link
    # and a <a class="result__snippet"> for snippet, inside a <div class="result">
    results: list[str] = []
    # Split by result divider
    blocks = re.split(r'(?i)<div class="result">', html)
    for block in blocks[1:max_results + 1]:
        # Extract title and URL from result__a
        title_match = re.search(r'<a class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        snippet_match = re.search(r'<a class="result__snippet"[^>]*>(.*?)</a>', block, re.S)

        if title_match:
            link = title_match.group(1)
            title = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()
            snippet = ""
            if snippet_match:
                snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()
            results.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}\n")

    if not results:
        return "No results found."

    return "\n".join(results)
