from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from harness.types.tools import ToolParam, ToolSchema


ARTIFACT_LINT_SCHEMA = ToolSchema(
    name="artifact_lint",
    description=(
        "Lint design artifacts in a run directory. Checks images, JSON, HTML gallery, "
        "placeholder text, missing manifest files, and protected reference usage."
    ),
    params=[
        ToolParam(name="runId", type="string", description="Design run id."),
        ToolParam(name="runDir", type="string", description="Design run directory."),
        ToolParam(name="artifactsDir", type="string", description="Optional artifacts directory override.", required=False),
        ToolParam(name="minPngs", type="integer", description="Minimum PNG count. Default 1.", required=False),
        ToolParam(name="requireGallery", type="boolean", description="Require 00-gallery.html. Default false.", required=False),
    ],
)


EXPORT_PACKAGE_SCHEMA = ToolSchema(
    name="export_package",
    description=(
        "Package a design run into a final delivery folder. Copies artifacts, research, "
        "review, plan, and bus files, then writes package-manifest.json and 00-index.html."
    ),
    params=[
        ToolParam(name="runId", type="string", description="Design run id."),
        ToolParam(name="runDir", type="string", description="Design run directory."),
        ToolParam(name="finalDir", type="string", description="Optional final output directory.", required=False),
        ToolParam(name="brief", type="string", description="Optional brief for index page.", required=False),
    ],
)


PLACEHOLDER_PATTERNS = [
    re.compile(r"\blorem ipsum\b", re.I),
    re.compile(r"\bplaceholder\b", re.I),
    re.compile(r"\bsample headline\b", re.I),
    re.compile(r"\bTODO[:\s]", re.I),
    re.compile(r"\bFIXME[:\s]", re.I),
]


async def artifact_lint_tool(
    runId: str,
    runDir: str,
    artifactsDir: str | None = None,
    minPngs: int | None = None,
    requireGallery: bool | None = None,
) -> str:
    run_dir = Path(runDir)
    artifacts_dir = Path(artifactsDir) if artifactsDir else run_dir / "artifacts"
    min_pngs = max(0, int(minPngs if minPngs is not None else 1))
    require_gallery = bool(requireGallery) if requireGallery is not None else False

    report: dict[str, Any] = {
        "ok": True,
        "runId": runId,
        "domain_type": _domain_type(run_dir),
        "checked": [],
        "errors": [],
        "warnings": [],
        "summary": {},
    }

    if not artifacts_dir.exists():
        _issue(report, "errors", str(artifacts_dir), "artifacts.exists", "Artifacts directory is missing.")
        return _finish_report(report)

    files = [p for p in artifacts_dir.rglob("*") if p.is_file()]
    pngs = [p for p in files if p.suffix.lower() == ".png"]
    htmls = [p for p in files if p.suffix.lower() in {".html", ".htm"}]
    jsons = [p for p in files if p.suffix.lower() == ".json"]
    report["checked"] = [str(p) for p in files]

    if len(pngs) < min_pngs:
        _issue(report, "errors", str(artifacts_dir), "png.count", f"PNG count {len(pngs)} < required {min_pngs}.")

    gallery = artifacts_dir / "00-gallery.html"
    if require_gallery and not gallery.exists():
        _issue(report, "errors", str(gallery), "gallery.exists", "Required gallery is missing.")
    if gallery.exists():
        content = gallery.read_text(encoding="utf-8", errors="replace")
        _lint_html(report, gallery, content)
        for png in pngs:
            rel = png.relative_to(artifacts_dir).as_posix()
            if rel not in content and png.name not in content:
                _issue(report, "warnings", str(gallery), "gallery.references", f"Gallery does not reference {rel}.")

    for path in htmls:
        text = path.read_text(encoding="utf-8", errors="replace")
        _lint_placeholders(report, path, text)
        if path != gallery:
            _lint_html(report, path, text)

    for path in jsons:
        try:
            json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            _issue(report, "errors", str(path), "json.parse", str(exc))

    manifest_path = artifacts_dir / "artifact-manifest.json"
    if manifest_path.exists():
        manifest = _read_json(manifest_path, {})
        listed = set()
        if isinstance(manifest, dict):
            for item in manifest.get("items", []):
                if isinstance(item, dict) and item.get("file"):
                    listed.add(str(item["file"]).replace("\\", "/"))
        for png in pngs:
            rel = png.relative_to(artifacts_dir).as_posix()
            if listed and rel not in listed and png.name not in listed:
                _issue(report, "warnings", str(manifest_path), "manifest.superset", f"PNG not listed: {rel}")
    else:
        _issue(report, "warnings", str(manifest_path), "manifest.exists", "artifact-manifest.json is missing.")

    _check_protected_references(report, run_dir, files)
    return _finish_report(report)


async def export_package_tool(
    runId: str,
    runDir: str,
    finalDir: str | None = None,
    brief: str | None = None,
) -> str:
    run_dir = Path(runDir)
    if not run_dir.exists():
        return _json({"ok": False, "error": f"runDir not found: {runDir}"})
    if finalDir:
        final_dir = Path(finalDir)
    else:
        final_dir = Path("outputs") / "runs" / runId / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for name in ["artifacts", "research", "plan", "review"]:
        src = run_dir / name
        if src.exists():
            dst = final_dir / name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            copied.extend([p for p in dst.rglob("*") if p.is_file()])
    for name in ["brief.json", "bus.jsonl"]:
        src = run_dir / name
        if src.exists():
            dst = final_dir / name
            shutil.copy2(src, dst)
            copied.append(dst)

    if not brief:
        brief_json = _read_json(run_dir / "brief.json", {})
        brief = str(brief_json.get("brief") or "")

    manifest_items = []
    for path in sorted([p for p in final_dir.rglob("*") if p.is_file()]):
        if path.name == "package-manifest.json":
            continue
        data = path.read_bytes()
        manifest_items.append(
            {
                "file": path.relative_to(final_dir).as_posix(),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    manifest = {
        "ok": True,
        "runId": runId,
        "domain_type": _domain_type(run_dir),
        "generated_at": _now_iso(),
        "item_count": len(manifest_items),
        "items": manifest_items,
    }
    (final_dir / "package-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    index = _render_index(runId, brief or "", final_dir, manifest_items)
    (final_dir / "00-index.html").write_text(index, encoding="utf-8")

    return _json(
        {
            "ok": True,
            "runId": runId,
            "domain_type": _domain_type(run_dir),
            "finalDir": str(final_dir),
            "manifest": str(final_dir / "package-manifest.json"),
            "index": str(final_dir / "00-index.html"),
            "item_count": len(manifest_items),
        }
    )


def _lint_html(report: dict[str, Any], path: Path, content: str) -> None:
    if not re.search(r"<title>[^<]+</title>", content, flags=re.I):
        _issue(report, "errors", str(path), "html.title", "Missing non-empty <title>.")
    if re.search(r"<script[\s>]", content, flags=re.I):
        _issue(report, "warnings", str(path), "html.script", "Gallery should usually be no-JS/self-contained.")
    if re.search(r'(?:src|href)=["\']https?://', content, flags=re.I):
        _issue(report, "warnings", str(path), "html.network", "External http(s) reference found.")


def _lint_placeholders(report: dict[str, Any], path: Path, content: str) -> None:
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(content):
            _issue(report, "errors", str(path), "content.placeholder", f"Detected {pattern.pattern}.")


def _check_protected_references(report: dict[str, Any], run_dir: Path, artifact_files: list[Path]) -> None:
    manifest = _read_json(run_dir / "research" / "assets" / "manifest.json", {})
    protected = []
    if isinstance(manifest, dict):
        for item in manifest.get("assets", []):
            if isinstance(item, dict) and item.get("do_not_replace"):
                protected.append(str(item.get("sha256", "")))
    if not protected:
        return
    for sidecar in [p for p in artifact_files if p.suffix.lower() == ".json"]:
        data = _read_json(sidecar, {})
        refs = data.get("references", []) if isinstance(data, dict) else []
        for ref in refs:
            if isinstance(ref, dict) and ref.get("sha256") in protected:
                # This is allowed as a reference; flag only if the generated output
                # claims to replace the protected asset.
                if data.get("purpose") and "replace" in str(data["purpose"]).lower():
                    _issue(report, "errors", str(sidecar), "protected.replace", "Generated artifact appears to replace protected asset.")


def _issue(report: dict[str, Any], bucket: str, file: str, rule: str, detail: str) -> None:
    report[bucket].append({"file": file, "rule": rule, "detail": detail})


def _finish_report(report: dict[str, Any]) -> str:
    report["ok"] = not report["errors"]
    report["summary"] = {
        "checked": len(report["checked"]),
        "errors": len(report["errors"]),
        "warnings": len(report["warnings"]),
    }
    return _json(report)


def _render_index(run_id: str, brief: str, final_dir: Path, items: list[dict[str, Any]]) -> str:
    images = [i for i in items if str(i["file"]).lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    artifact_images = [
        i for i in images
        if str(i["file"]).replace("\\", "/").startswith("artifacts/")
    ]
    reference_images = [
        i for i in images
        if str(i["file"]).replace("\\", "/").startswith("research/assets/")
    ]
    other_images = [
        i for i in images
        if i not in artifact_images and i not in reference_images
    ]
    cards = "\n".join(
        f'<figure class="result-card"><img src="{_esc_attr(i["file"])}" alt=""><figcaption>{_esc(Path(str(i["file"])).name)}</figcaption></figure>'
        for i in artifact_images
    )
    reference_cards = "\n".join(
        f'<figure class="reference-card"><img src="{_esc_attr(i["file"])}" alt=""><figcaption>{_esc(Path(str(i["file"])).name)}</figcaption></figure>'
        for i in reference_images
    )
    other_cards = "\n".join(
        f'<figure class="reference-card"><img src="{_esc_attr(i["file"])}" alt=""><figcaption>{_esc(Path(str(i["file"])).name)}</figcaption></figure>'
        for i in other_images
    )
    file_rows = "\n".join(
        f"<tr><td>{_esc(i['file'])}</td><td>{i['bytes']}</td><td><code>{_esc(i['sha256'][:16])}</code></td></tr>"
        for i in items
    )
    reference_section = (
        f"""
  <section class="appendix">
    <div class="section-heading">
      <p class="eyebrow">Reference Library</p>
      <h2>Research Assets</h2>
      <p>Source images retained for grounding and audit. These are separated from final deliverables.</p>
    </div>
    <div class="reference-grid">{reference_cards}</div>
  </section>"""
        if reference_cards else ""
    )
    other_section = (
        f"""
  <section class="appendix">
    <div class="section-heading">
      <p class="eyebrow">Additional Images</p>
      <h2>Supporting Files</h2>
    </div>
    <div class="reference-grid">{other_cards}</div>
  </section>"""
        if other_cards else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Atelier Design Package · {_esc(run_id)}</title>
  <style>
    :root {{ --ink:#171717; --muted:#666; --line:#dcd8ce; --paper:#f7f5ef; --card:#fffdfa; --accent:#184b82; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; background: var(--paper); color: var(--ink); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 48px 28px 64px; }}
    header {{ border-bottom: 1px solid var(--line); padding-bottom: 28px; margin-bottom: 32px; }}
    h1 {{ margin: 0 0 10px; font-size: clamp(34px, 6vw, 72px); line-height: .95; letter-spacing: 0; }}
    h2 {{ margin: 0; font-size: 24px; }}
    .eyebrow {{ margin: 0 0 8px; color: var(--accent); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }}
    .brief {{ max-width: 900px; color: var(--muted); font-size: 15px; line-height: 1.65; }}
    .section-heading {{ display: flex; flex-direction: column; gap: 6px; margin: 36px 0 18px; max-width: 780px; }}
    .section-heading p:not(.eyebrow) {{ margin: 0; color: var(--muted); line-height: 1.55; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; margin: 20px 0 40px; align-items: start; }}
    .reference-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 16px 0 32px; }}
    figure {{ margin: 0; background: var(--card); border: 1px solid var(--line); overflow: hidden; }}
    .result-card {{ border-radius: 10px; box-shadow: 0 12px 32px rgba(20,20,20,.08); }}
    .reference-card {{ border-radius: 8px; opacity: .92; }}
    img {{ width: 100%; height: auto; display: block; }}
    figcaption {{ font-size: 12px; color: var(--muted); padding: 10px 12px; overflow-wrap: anywhere; border-top: 1px solid var(--line); }}
    .appendix {{ border-top: 1px solid var(--line); margin-top: 36px; padding-top: 8px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--line); font-size: 13px; }}
    td, th {{ border-bottom: 1px solid #e8e2d8; padding: 9px 10px; text-align: left; overflow-wrap: anywhere; }}
    th {{ color: var(--muted); font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">Atelier Design Package</p>
      <h1>{_esc(run_id)}</h1>
      <p class="brief"><strong>Brief:</strong> {_esc(brief)}</p>
    </header>
    <section>
      <div class="section-heading">
        <p class="eyebrow">Final Deliverables</p>
        <h2>Generated Design Set</h2>
        <p>Curated outputs produced for presentation. Research references are not mixed into this section.</p>
      </div>
      <div class="grid">{cards}</div>
    </section>
{reference_section}
{other_section}
    <section class="appendix">
      <div class="section-heading">
        <p class="eyebrow">Package Manifest</p>
        <h2>Files</h2>
      </div>
      <table><thead><tr><th>File</th><th>Bytes</th><th>SHA-256</th></tr></thead><tbody>{file_rows}</tbody></table>
    </section>
  </main>
</body>
</html>
"""


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _domain_type(run_dir: Path) -> str:
    brief = _read_json(run_dir / "brief.json", {})
    if isinstance(brief, dict):
        scope = brief.get("resolvedScope")
        if isinstance(scope, dict) and scope.get("domain_type"):
            return str(scope["domain_type"])
        context = brief.get("domainContext")
        if isinstance(context, dict) and context.get("domain_type"):
            return str(context["domain_type"])
    return ""


def _esc(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(value: Any) -> str:
    return _esc(value).replace('"', "&quot;")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
