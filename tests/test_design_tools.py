from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.tools.builtin.design_image import image_edit_tool, image_generate_tool
from harness.tools.builtin.design_run import (
    design_bus_post_tool,
    design_bus_read_tool,
    run_init_tool,
)
from harness.tools.builtin.design_research import (
    research_asset_discover_tool,
    research_asset_fetch_tool,
    research_asset_validate_tool,
    research_fetch_tool,
)
from harness.tools.builtin.design_artifacts import artifact_lint_tool, export_package_tool


@pytest.mark.asyncio
async def test_image_generate_mock_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("DESIGN_IMAGE_BACKEND", "mock")

    raw = await image_generate_tool(
        prompt="blue icon",
        runId="r1",
        runDir=str(tmp_path),
        id="hero",
    )

    payload = json.loads(raw)
    assert payload["ok"] is True
    out = Path(payload["items"][0]["file"])
    assert out.exists()
    assert out.with_suffix(out.suffix + ".json").exists()


@pytest.mark.asyncio
async def test_image_edit_mock_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("DESIGN_IMAGE_BACKEND", "mock")
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"\x89PNG\r\n\x1a\n")

    raw = await image_edit_tool(
        prompt="edit icon",
        referenceImagePaths=[str(ref)],
        runId="r1",
        runDir=str(tmp_path),
        id="edited",
    )

    payload = json.loads(raw)
    assert payload["ok"] is True
    out = Path(payload["items"][0]["file"])
    assert out.exists()
    assert out.with_suffix(out.suffix + ".json").exists()


@pytest.mark.asyncio
async def test_run_init_and_design_bus_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("DESIGN_HARNESS_ROOT", str(tmp_path / "harness"))
    monkeypatch.setenv("DESIGN_OUTPUTS_ROOT", str(tmp_path / "outputs"))

    init = json.loads(
        await run_init_tool(
            brief="Design a small exhibition identity.",
            resolvedScope='{"language":"zh+en"}',
            runIdOverride="run-a",
        )
    )
    assert init["ok"] is True
    assert Path(init["paths"]["bus"]).exists()

    post = json.loads(
        await design_bus_post_tool(
            runId=init["runId"],
            runDir=init["runDir"],
            from_agent="design-primary",
            to="design-planner",
            type="kickoff",
            summary="Start planning.",
        )
    )
    assert post["ok"] is True

    read = json.loads(
        await design_bus_read_tool(
            runId=init["runId"],
            runDir=init["runDir"],
            agent="design-planner",
        )
    )
    assert read["count"] == 1
    assert read["messages"][0]["summary"] == "Start planning."


@pytest.mark.asyncio
async def test_research_fetch_records_evidence(tmp_path):
    run_dir = tmp_path / "run"

    raw = await research_fetch_tool(
        runId="r1",
        runDir=str(run_dir),
        title="Official homepage",
        url="https://example.com",
        kind="homepage",
        notes="Primary identity source.",
        implies_existing_asset=True,
        asset_kind="logo",
    )

    payload = json.loads(raw)
    assert payload["ok"] is True
    evidence = json.loads((run_dir / "research/evidence.json").read_text(encoding="utf-8"))
    assert len(evidence["official_sources"]) == 1
    assert evidence["existing_brand_assets_found"] is True


@pytest.mark.asyncio
async def test_research_asset_discover_finds_page_images(monkeypatch, tmp_path):
    html = tmp_path / "index.html"
    html.write_text(
        """
        <html><head>
          <meta property="og:image" content="/hero.png">
          <link rel="icon" href="/favicon.png">
        </head><body>
          <img src="/logo.png">
          <div style="background-image:url('/campus.jpg')"></div>
        </body></html>
        """,
        encoding="utf-8",
    )

    async def fake_fetch(url: str, max_bytes: int):
        return html.read_text(encoding="utf-8"), "https://atelier.test/index.html"

    monkeypatch.setattr("harness.tools.builtin.design_research._fetch_text", fake_fetch)

    payload = json.loads(
        await research_asset_discover_tool(
            runId="r1",
            pageUrl="https://atelier.test/index.html",
            includeCss=False,
        )
    )

    assert payload["ok"] is True
    urls = {c["url"] for c in payload["candidates"]}
    assert "https://atelier.test/logo.png" in urls
    assert "https://atelier.test/hero.png" in urls


@pytest.mark.asyncio
async def test_research_asset_fetch_and_validate(monkeypatch, tmp_path):
    import httpx

    run_dir = tmp_path / "run"
    png = _png_bytes(width=128, height=128)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers=None):
            return httpx.Response(
                200,
                content=png,
                headers={"content-type": "image/png"},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr("harness.tools.builtin.design_research.httpx.AsyncClient", FakeClient)

    fetched = json.loads(
        await research_asset_fetch_tool(
            runId="r1",
            runDir=str(run_dir),
            id="official-logo",
            url="https://atelier.test/logo.png",
            kind="logo",
        )
    )
    assert fetched["ok"] is True

    validation = json.loads(
        await research_asset_validate_tool(
            runId="r1",
            runDir=str(run_dir),
            minUsableAssets=1,
            requireLogo=True,
        )
    )
    assert validation["ok"] is True
    assert validation["ready"] is True


@pytest.mark.asyncio
async def test_artifact_lint_and_export_package(tmp_path):
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    (run_dir / "brief.json").write_text(
        json.dumps({"brief": "Design a poster."}),
        encoding="utf-8",
    )
    (run_dir / "bus.jsonl").write_text("", encoding="utf-8")
    (artifacts / "poster.png").write_bytes(_png_bytes(width=128, height=128))
    (artifacts / "00-gallery.html").write_text(
        "<!doctype html><html><head><title>Gallery</title></head><body><img src='poster.png'></body></html>",
        encoding="utf-8",
    )

    lint = json.loads(
        await artifact_lint_tool(
            runId="r1",
            runDir=str(run_dir),
            minPngs=1,
            requireGallery=True,
        )
    )
    assert lint["ok"] is True

    exported = json.loads(
        await export_package_tool(
            runId="r1",
            runDir=str(run_dir),
            finalDir=str(tmp_path / "final"),
        )
    )
    assert exported["ok"] is True
    assert (tmp_path / "final/package-manifest.json").exists()
    assert (tmp_path / "final/00-index.html").exists()


def _png_bytes(width: int = 1, height: int = 1) -> bytes:
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
