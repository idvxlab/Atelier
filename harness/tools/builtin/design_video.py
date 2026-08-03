from __future__ import annotations

import base64
import hashlib
import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from harness.types.tools import ToolParam, ToolSchema


VIDEO_GENERATE_SCHEMA = ToolSchema(
    name="video_generate",
    description=(
        "Generate a video from a text prompt or image references using a "
        "Seedance-compatible video generation endpoint. Creates an async task, "
        "polls until completion, downloads the video file, writes a JSON sidecar "
        "with metadata, and returns the file path."
    ),
    params=[
        ToolParam(name="prompt", type="string", description="Video generation prompt."),
        ToolParam(name="referenceImagePath", type="string", description="Optional first-frame reference image path (image-to-video mode).", required=False),
        ToolParam(name="lastFrameImagePath", type="string", description="Optional last-frame reference image path (first-and-last-frame mode).", required=False),
        ToolParam(name="id", type="string", description="Stable video id / filename stem.", required=False),
        ToolParam(name="path", type="string", description="Optional explicit output file path.", required=False),
        ToolParam(name="runId", type="string", description="Optional design run id.", required=False),
        ToolParam(name="runDir", type="string", description="Optional design run directory.", required=False),
        ToolParam(name="purpose", type="string", description="Human-readable purpose for the video.", required=False),
        ToolParam(name="domainType", type="string", description="Optional design domain type for sidecar metadata.", required=False),
        ToolParam(name="deliverableCategory", type="string", description="Optional deliverable category for sidecar metadata.", required=False),
        ToolParam(name="resolution", type="string", description="Video resolution: 480p, 720p, 1080p, 4K. Default 720p.", required=False),
        ToolParam(name="ratio", type="string", description="Aspect ratio: 16:9, 4:3, 1:1, 3:4, 9:16, 21:9, adaptive. Default 16:9.", required=False),
        ToolParam(name="duration", type="integer", description="Video duration in seconds. Default 5.", required=False),
        ToolParam(name="seed", type="integer", description="Optional random seed for reproducibility.", required=False),
        ToolParam(name="cameraFixed", type="boolean", description="Whether to fix the camera. Default false.", required=False),
        ToolParam(name="watermark", type="boolean", description="Whether to add an AI watermark. Default false.", required=False),
        ToolParam(name="generateAudio", type="boolean", description="Whether to generate synchronized audio. Default false.", required=False),
        ToolParam(name="model", type="string", description="Video model override.", required=False),
    ],
)


VALID_RESOLUTIONS = {"480p", "720p", "1080p", "4K"}
VALID_RATIOS = {"16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"}

POLL_INTERVAL = 5
POLL_TIMEOUT = 300


def _load_project_env_once() -> None:
    if getattr(_load_project_env_once, "_loaded", False):
        return
    setattr(_load_project_env_once, "_loaded", True)
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _slug(value: str, default: str = "video") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip()).strip("-._")
    return (value or default)[:80]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _api_key() -> str:
    _load_project_env_once()
    return (
        os.getenv("DREAMATIC_VIDEO_API_KEY")
        or os.getenv("DREAMATIC_API_KEY")
        or os.getenv("DREAMATIC_IMAGE_API_KEY")
        or os.getenv("DESIGN_IMAGE_API_KEY")
        or os.getenv("OPENAI_HUB_API_KEY")
        or ""
    )


def _base_url() -> str:
    _load_project_env_once()
    return (
        os.getenv("DREAMATIC_VIDEO_BASE_URL")
        or os.getenv("DREAMATIC_BASE_URL")
        or os.getenv("DREAMATIC_IMAGE_BASE_URL")
        or "https://ark.ap-southeast.bytepluses.com"
    ).rstrip("/")


def _tasks_endpoint() -> str:
    _load_project_env_once()
    return (
        os.getenv("DREAMATIC_VIDEO_ENDPOINT")
        or f"{_base_url()}/api/v3/contents/generations/tasks"
    )


def _model(model: str | None) -> str:
    _load_project_env_once()
    return (
        model
        or os.getenv("DREAMATIC_VIDEO_MODEL")
        or "seedance-1-5-pro-251215"
    )


def _backend() -> str:
    _load_project_env_once()
    return (os.getenv("DREAMATIC_VIDEO_BACKEND") or "codex").lower()


def _default_resolution() -> str:
    _load_project_env_once()
    return os.getenv("DREAMATIC_VIDEO_DEFAULT_RESOLUTION") or "720p"


def _default_duration() -> int:
    _load_project_env_once()
    try:
        return int(os.getenv("DREAMATIC_VIDEO_DEFAULT_DURATION") or "5")
    except (TypeError, ValueError):
        return 5


def _coerce_resolution(value: str | None) -> str:
    res = (value or _default_resolution()).strip()
    if res not in VALID_RESOLUTIONS:
        raise ValueError(f"Invalid resolution {res!r}. Use one of: {', '.join(sorted(VALID_RESOLUTIONS))}")
    return res


def _coerce_ratio(value: str | None) -> str:
    ratio = (value or "16:9").strip()
    if ratio not in VALID_RATIOS:
        raise ValueError(f"Invalid ratio {ratio!r}. Use one of: {', '.join(sorted(VALID_RATIOS))}")
    return ratio


def _coerce_duration(value: int | None) -> int:
    try:
        dur = int(value if value is not None else _default_duration())
    except (TypeError, ValueError):
        dur = _default_duration()
    return max(2, min(dur, 15))


def _output_dir(runDir: str | None) -> Path:
    if runDir:
        return Path(runDir) / "artifacts" / "generated-videos"
    return Path("outputs") / "videos"


def _output_path(
    *,
    explicit_path: str | None,
    runDir: str | None,
    video_id: str | None,
) -> Path:
    if explicit_path:
        return Path(explicit_path)
    out_dir = _output_dir(runDir)
    stem = _slug(video_id or f"video-{int(time.time())}")
    return out_dir / f"{stem}.mp4"


def _image_to_base64_url(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    if ext not in ("jpeg", "png", "webp", "bmp", "tiff", "gif", "heic", "heif"):
        ext = "png"
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/{ext};base64,{b64}"


def _build_content(
    prompt: str,
    reference_image_path: str | None,
    last_frame_image_path: str | None,
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []

    content.append({"type": "text", "text": prompt})

    if reference_image_path:
        url = _image_to_base64_url(reference_image_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": url},
            "role": "first_frame",
        })

    if last_frame_image_path:
        url = _image_to_base64_url(last_frame_image_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": url},
            "role": "last_frame",
        })

    return content


async def _create_task(
    *,
    endpoint: str,
    key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Create task failed ({response.status_code}): {_safe_response(response)}")
    body = response.json()
    task_id = body.get("id")
    if not task_id:
        raise RuntimeError(f"Create task returned no id: {body}")
    return body


async def _poll_task(
    *,
    base_url: str,
    key: str,
    task_id: str,
    timeout: int = POLL_TIMEOUT,
    interval: int = POLL_INTERVAL,
) -> dict[str, Any]:
    url = f"{base_url}/api/v3/contents/generations/tasks/{task_id}"
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=30) as client:
        while time.monotonic() < deadline:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {key}"},
            )
            if response.status_code >= 400:
                raise RuntimeError(f"Poll task failed ({response.status_code}): {_safe_response(response)}")
            body = response.json()
            status = body.get("status", "")
            if status == "succeeded":
                return body
            if status in ("failed", "expired"):
                error = body.get("error", {})
                raise RuntimeError(f"Task {status}: {error or body}")
            await asyncio.sleep(interval)
    raise RuntimeError(f"Task {task_id} timed out after {timeout}s")


async def _download_video(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _write_sidecar(
    *,
    video_path: Path,
    data: bytes,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(data)
    sidecar = {
        **metadata,
        "file": str(video_path),
        "sha256": _sha256(data),
        "bytes": len(data),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    video_path.with_suffix(video_path.suffix + ".json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "file": str(video_path),
        "relativePath": video_path.name,
        "sha256": sidecar["sha256"],
        "bytes": len(data),
    }


def _safe_response(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except Exception:
        return response.text[:1000]
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        err = payload["error"]
        return {k: err.get(k) for k in ("message", "type", "code", "param") if k in err}
    return payload


async def video_generate_tool(
    prompt: str,
    referenceImagePath: str | None = None,
    lastFrameImagePath: str | None = None,
    id: str | None = None,
    path: str | None = None,
    runId: str | None = None,
    runDir: str | None = None,
    purpose: str | None = None,
    domainType: str | None = None,
    deliverableCategory: str | None = None,
    resolution: str | None = None,
    ratio: str | None = None,
    duration: int | None = None,
    seed: int | None = None,
    cameraFixed: bool | None = None,
    watermark: bool | None = None,
    generateAudio: bool | None = None,
    model: str | None = None,
) -> str:
    if not prompt or not prompt.strip():
        return _json({"ok": False, "error": "prompt is required"})

    if referenceImagePath and not Path(referenceImagePath).exists():
        return _json({"ok": False, "error": f"referenceImagePath not found: {referenceImagePath}"})
    if lastFrameImagePath and not Path(lastFrameImagePath).exists():
        return _json({"ok": False, "error": f"lastFrameImagePath not found: {lastFrameImagePath}"})

    try:
        vid_resolution = _coerce_resolution(resolution)
        vid_ratio = _coerce_ratio(ratio)
        vid_duration = _coerce_duration(duration)
    except ValueError as exc:
        return _json({"ok": False, "error": str(exc)})

    out_path = _output_path(
        explicit_path=path,
        runDir=runDir,
        video_id=id,
    )

    if _backend() == "mock":
        sidecar_meta = {
            "tool": "video_generate",
            "backend": "mock",
            "runId": runId,
            "domain_type": domainType,
            "deliverable_category": deliverableCategory,
            "purpose": purpose,
            "prompt": prompt,
            "resolution": vid_resolution,
            "ratio": vid_ratio,
            "duration": vid_duration,
        }
        written = _write_sidecar(
            video_path=out_path,
            data=b"mock-video-placeholder",
            metadata=sidecar_meta,
        )
        return _json({"ok": True, "backend": "mock", "items": [written]})

    key = _api_key()
    if not key:
        return _json({
            "ok": False,
            "error": "Missing DREAMATIC_VIDEO_API_KEY, DREAMATIC_API_KEY, DREAMATIC_IMAGE_API_KEY, or OPENAI_HUB_API_KEY",
        })

    try:
        content = _build_content(prompt, referenceImagePath, lastFrameImagePath)
    except Exception as exc:
        return _json({"ok": False, "error": "Failed to encode reference image", "detail": str(exc)})

    vid_model = _model(model)
    payload: dict[str, Any] = {
        "model": vid_model,
        "content": content,
        "resolution": vid_resolution,
        "ratio": vid_ratio,
        "duration": vid_duration,
        "watermark": bool(watermark) if watermark is not None else False,
    }
    if seed is not None:
        payload["seed"] = seed
    if cameraFixed is not None:
        payload["camera_fixed"] = bool(cameraFixed)
    if generateAudio is not None:
        payload["generate_audio"] = bool(generateAudio)

    try:
        task_body = await _create_task(
            endpoint=_tasks_endpoint(),
            key=key,
            payload=payload,
        )
    except (httpx.RequestError, RuntimeError) as exc:
        return _json({
            "ok": False,
            "error": "video generation task creation failed",
            "detail": f"{type(exc).__name__}: {exc}",
        })

    task_id = task_body["id"]

    try:
        result = await _poll_task(
            base_url=_base_url(),
            key=key,
            task_id=task_id,
        )
    except (httpx.RequestError, RuntimeError) as exc:
        return _json({
            "ok": False,
            "error": "video generation polling failed",
            "task_id": task_id,
            "detail": f"{type(exc).__name__}: {exc}",
        })

    video_url = result.get("video_url")
    if not video_url:
        content_field = result.get("content") or {}
        if isinstance(content_field, list) and content_field:
            video_url = content_field[0].get("video_url", {})
        elif isinstance(content_field, dict):
            video_url = content_field.get("video_url", {})
    if isinstance(video_url, dict):
        video_url = video_url.get("url")
    if not video_url:
        return _json({"ok": False, "error": "Task succeeded but no video_url returned", "task_id": task_id, "raw": result})

    try:
        video_data = await _download_video(str(video_url))
    except httpx.RequestError as exc:
        return _json({
            "ok": False,
            "error": "Failed to download generated video",
            "video_url": str(video_url),
            "detail": f"{type(exc).__name__}: {exc}",
        })

    sidecar_meta = {
        "tool": "video_generate",
        "backend": "codex",
        "endpoint": _tasks_endpoint(),
        "model": vid_model,
        "task_id": task_id,
        "runId": runId,
        "id": id,
        "domain_type": domainType,
        "deliverable_category": deliverableCategory,
        "purpose": purpose,
        "prompt": prompt,
        "resolution": vid_resolution,
        "ratio": vid_ratio,
        "duration": vid_duration,
        "seed": seed,
        "camera_fixed": cameraFixed,
        "watermark": watermark,
        "generate_audio": generateAudio,
        "reference_image": referenceImagePath,
        "last_frame_image": lastFrameImagePath,
        "video_url": str(video_url),
    }
    written = _write_sidecar(
        video_path=out_path,
        data=video_data,
        metadata=sidecar_meta,
    )
    return _json({"ok": True, "backend": "codex", "model": vid_model, "task_id": task_id, "items": [written]})
