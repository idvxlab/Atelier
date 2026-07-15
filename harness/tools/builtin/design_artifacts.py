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
        ToolParam(name="recommendedBatch", type="string", description="Optional recommended batch id.", required=False),
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
    recommendedBatch: str | None = None,
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
        "generated_at": _now_iso(),
        "recommended_batch": recommendedBatch,
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
    cards = "\n".join(
        f'<figure><img src="{_esc_attr(i["file"])}" alt=""><figcaption>{_esc(i["file"])}</figcaption></figure>'
        for i in images
    )
    file_rows = "\n".join(
        f"<tr><td>{_esc(i['file'])}</td><td>{i['bytes']}</td><td><code>{_esc(i['sha256'][:16])}</code></td></tr>"
        for i in items
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Atelier Design Package · {_esc(run_id)}</title>
  <style>
    body {{ font-family: Inter, system-ui, sans-serif; margin: 32px; background: #f7f7f4; color: #1b1b1b; }}
    h1 {{ margin-bottom: 4px; }}
    .brief {{ max-width: 900px; color: #555; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin: 24px 0; }}
    figure {{ margin: 0; padding: 12px; background: white; border: 1px solid #ddd; }}
    img {{ width: 100%; height: auto; display: block; }}
    figcaption {{ font-size: 12px; color: #666; margin-top: 8px; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    td, th {{ border-bottom: 1px solid #e0e0e0; padding: 8px; text-align: left; }}
  </style>
</head>
<body>
  <h1>Atelier Design Package</h1>
  <p class="brief"><strong>Run:</strong> {_esc(run_id)}<br><strong>Brief:</strong> {_esc(brief)}</p>
  <section class="grid">{cards}</section>
  <h2>Files</h2>
  <table><thead><tr><th>File</th><th>Bytes</th><th>SHA-256</th></tr></thead><tbody>{file_rows}</tbody></table>
</body>
</html>
"""


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _esc(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(value: Any) -> str:
    return _esc(value).replace('"', "&quot;")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
