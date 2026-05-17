from __future__ import annotations
import re

import httpx

from harness.types.tools import ToolSchema, ToolParam

WEB_FETCH_SCHEMA = ToolSchema(
    name="web_fetch",
    description="Fetch the content of a URL and return it as plain text (HTML tags stripped).",
    params=[
        ToolParam(name="url", type="string", description="URL to fetch"),
        ToolParam(
            name="max_length",
            type="integer",
            description="Maximum characters to return (default 8000)",
            required=False,
        ),
    ],
)


async def web_fetch_tool(url: str, max_length: int = 8000) -> str:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            text = response.text
    except httpx.TimeoutException:
        return f"Error: request timed out for {url}"
    except httpx.HTTPStatusError as exc:
        return f"Error: HTTP {exc.response.status_code} for {url}"
    except Exception as exc:
        return f"Error fetching {url}: {exc}"

    # Strip HTML tags
    plain = re.sub(r"(?s)<script[^>]*>.*?</script>", "", text)
    plain = re.sub(r"(?s)<style[^>]*>.*?</style>", "", plain)
    plain = re.sub(r"<[^>]+>", "", plain)
    plain = re.sub(r"&nbsp;", " ", plain)
    plain = re.sub(r"&#?\w+;", "", plain)
    plain = re.sub(r"\s+", " ", plain).strip()

    if len(plain) > max_length:
        plain = plain[:max_length] + f"\n... [truncated, {len(plain) - max_length} chars omitted]"

    return plain
