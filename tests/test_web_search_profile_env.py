import json
from unittest.mock import patch

import pytest

from harness.tools.builtin import web_search


@pytest.mark.asyncio
async def test_atelier_search_profile_selects_serper(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.setenv("ATELIER_SEARCH_PROVIDER", "serper")
    monkeypatch.setenv("ATELIER_SEARCH_API_KEY", "atelier-serper-key")
    calls = []

    async def fake_serper(**kwargs):
        calls.append(("serper", kwargs))
        return json.dumps({"ok": True, "provider": "serper"})

    async def fake_brave(**kwargs):
        calls.append(("brave", kwargs))
        return json.dumps({"ok": True, "provider": "brave"})

    with (
        patch.object(web_search, "_serper_web_search", fake_serper),
        patch.object(web_search, "_brave_web_search", fake_brave),
    ):
        result = json.loads(await web_search.web_search_tool("hello"))

    assert result["provider"] == "serper"
    assert calls == [
        (
            "serper",
            {
                "query": "hello",
                "api_key": "atelier-serper-key",
                "max_results": web_search.DEFAULT_SEARCH_RESULTS,
            },
        )
    ]


@pytest.mark.asyncio
async def test_atelier_search_profile_selects_brave(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.setenv("ATELIER_SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("ATELIER_SEARCH_API_KEY", "atelier-brave-key")
    calls = []

    async def fake_serper(**kwargs):
        calls.append(("serper", kwargs))
        return json.dumps({"ok": True, "provider": "serper"})

    async def fake_brave(**kwargs):
        calls.append(("brave", kwargs))
        return json.dumps({"ok": True, "provider": "brave"})

    with (
        patch.object(web_search, "_serper_web_search", fake_serper),
        patch.object(web_search, "_brave_web_search", fake_brave),
    ):
        result = json.loads(await web_search.web_search_tool("hello"))

    assert result["provider"] == "brave"
    assert calls == [
        (
            "brave",
            {
                "query": "hello",
                "api_key": "atelier-brave-key",
                "max_results": web_search.DEFAULT_SEARCH_RESULTS,
            },
        )
    ]
