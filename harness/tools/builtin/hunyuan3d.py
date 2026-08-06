from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from harness.types.tools import ToolParam, ToolSchema


HUNYUAN3D_SCHEMA = ToolSchema(
    name="hunyuan3d",
    description=(
        "Generate a Hunyuan 3D model and preview render from text, one reference "
        "image, or a front image plus labeled multi-view reference images. "
        "Downloads the generated files and writes JSON metadata sidecars."
    ),
    params=[
        ToolParam(
            name="inputMode",
            type="string",
            description="Input mode: text, single_view, or multi_view.",
            enum=["text", "single_view", "multi_view"],
        ),
        ToolParam(
            name="prompt",
            type="string",
            description="Text description. Required in text mode and not accepted in image modes.",
            required=False,
        ),
        ToolParam(
            name="frontImagePath",
            type="string",
            description="Local primary/front image path for single_view or multi_view mode.",
            required=False,
        ),
        ToolParam(
            name="viewImagePaths",
            type="object",
            description=(
                "Additional local image paths keyed by view name. Supported keys: "
                "left, right, back, top, bottom, left_front, right_front. "
                "Required only in multi_view mode."
            ),
            required=False,
        ),
        ToolParam(name="id", type="string", description="Stable artifact filename stem.", required=False),
        ToolParam(name="runId", type="string", description="Optional design run id.", required=False),
        ToolParam(name="runDir", type="string", description="Optional design run directory.", required=False),
        ToolParam(name="purpose", type="string", description="Human-readable purpose for the model.", required=False),
        ToolParam(name="domainType", type="string", description="Optional design domain metadata.", required=False),
        ToolParam(name="deliverableCategory", type="string", description="Optional deliverable category metadata.", required=False),
        ToolParam(
            name="generateType",
            type="string",
            description="Generation type.",
            required=False,
            enum=["Normal", "Geometry", "LowPoly", "Sketch"],
        ),
        ToolParam(name="enablePbr", type="boolean", description="Whether to generate PBR materials.", required=False),
        ToolParam(name="faceCount", type="integer", description="Target face count from 3000 to 1500000.", required=False),
        ToolParam(
            name="resultFormat",
            type="string",
            description="Optional requested result format.",
            required=False,
            enum=["STL", "USDZ", "FBX"],
        ),
    ],
)


DEFAULT_BASE_URL = "https://tokenhub.tencentmaas.com/v1/api/3d"
DEFAULT_MODEL = "hy-3d-3.1"
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MODES = {"text", "single_view", "multi_view"}
ALLOWED_MODELS = {"hy-3d-3.0", "hy-3d-3.1"}
ALLOWED_GENERATE_TYPES = {"Normal", "Geometry", "LowPoly", "Sketch"}
ALLOWED_RESULT_FORMATS = {"STL", "USDZ", "FBX"}
VIEW_TYPES_30 = {"left", "right", "back"}
VIEW_TYPES_31 = VIEW_TYPES_30 | {"top", "bottom", "left_front", "right_front"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
POLL_INTERVAL_SECONDS = 5.0
JOB_TIMEOUT_SECONDS = 1800.0


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _slug(value: str, default: str = "model3d") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip()).strip("-._")
    return (cleaned or default)[:80]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _api_key() -> str:
    return os.getenv("DREAMATIC_HUNYUAN3D_API_KEY", "").strip()


def _base_url() -> str:
    return (os.getenv("DREAMATIC_HUNYUAN3D_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")


def _model(value: str | None) -> str:
    return (value or os.getenv("DREAMATIC_HUNYUAN3D_MODEL") or DEFAULT_MODEL).strip()


def _first_value(data: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in data and data[name] is not None:
            return data[name]
    return None


def _validate_image(path_text: str, label: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} image not found: {path}")
    if path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_SUFFIXES))
        raise ValueError(f"{label} image must use one of these formats: {allowed}")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError(f"{label} image exceeds the 8 MiB limit: {path}")
    return path


def _image_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _validate_and_build_payload(
    *,
    input_mode: str,
    prompt: str | None,
    front_image_path: str | None,
    view_image_paths: dict[str, str] | None,
    model: str,
    generate_type: str,
    enable_pbr: bool,
    face_count: int | None,
    result_format: str | None,
) -> tuple[dict[str, Any], list[Path]]:
    if input_mode not in ALLOWED_MODES:
        raise ValueError(f"inputMode must be one of: {', '.join(sorted(ALLOWED_MODES))}")
    if model not in ALLOWED_MODELS:
        raise ValueError(f"model must be one of: {', '.join(sorted(ALLOWED_MODELS))}")
    if generate_type not in ALLOWED_GENERATE_TYPES:
        raise ValueError(
            f"generateType must be one of: {', '.join(sorted(ALLOWED_GENERATE_TYPES))}"
        )
    if model == "hy-3d-3.1" and generate_type in {"LowPoly", "Sketch"}:
        raise ValueError("hy-3d-3.1 does not support LowPoly or Sketch")
    if face_count is not None:
        if isinstance(face_count, bool) or not isinstance(face_count, int):
            raise ValueError("faceCount must be an integer")
        if not 3000 <= face_count <= 1_500_000:
            raise ValueError("faceCount must be between 3000 and 1500000")
    if result_format is not None:
        result_format = str(result_format).upper()
        if result_format not in ALLOWED_RESULT_FORMATS:
            raise ValueError(
                f"resultFormat must be one of: {', '.join(sorted(ALLOWED_RESULT_FORMATS))}"
            )

    prompt_text = (prompt or "").strip()
    views = view_image_paths or {}
    if not isinstance(views, dict):
        raise ValueError("viewImagePaths must be an object mapping view names to file paths")
    views = {str(k): str(v) for k, v in views.items() if v not in (None, "")}

    payload: dict[str, Any] = {"model": model, "generate_type": generate_type}
    source_paths: list[Path] = []
    if input_mode == "text":
        if not prompt_text:
            raise ValueError("prompt is required in text mode")
        if len(prompt_text) > 1024:
            raise ValueError("prompt must not exceed 1024 characters")
        if front_image_path or views:
            raise ValueError("text mode does not accept frontImagePath or viewImagePaths")
        payload["prompt"] = prompt_text
    else:
        if prompt_text:
            raise ValueError(f"{input_mode} mode does not accept prompt")
        if not front_image_path:
            raise ValueError(f"frontImagePath is required in {input_mode} mode")
        if input_mode == "single_view" and views:
            raise ValueError("single_view mode does not accept viewImagePaths")
        if input_mode == "multi_view" and not views:
            raise ValueError("multi_view mode requires at least one additional view image")
        front = _validate_image(front_image_path, "front")
        source_paths.append(front)
        payload["image_base64"] = _image_base64(front)
        if input_mode == "multi_view":
            supported = VIEW_TYPES_31 if model == "hy-3d-3.1" else VIEW_TYPES_30
            unknown = sorted(set(views) - supported)
            if unknown:
                raise ValueError(
                    f"unsupported view type(s) for {model}: {', '.join(unknown)}"
                )
            encoded_views: list[dict[str, str]] = []
            for view_type, path_text in views.items():
                path = _validate_image(path_text, view_type)
                source_paths.append(path)
                encoded_views.append(
                    {"view_type": view_type, "view_image_base64": _image_base64(path)}
                )
            if sum(path.stat().st_size for path in source_paths) > MAX_IMAGE_BYTES:
                raise ValueError("front and multi-view images exceed the combined 8 MiB limit")
            payload["multi_view_images"] = encoded_views

    if enable_pbr:
        payload["enable_pbr"] = True
    if face_count is not None:
        payload["face_count"] = face_count
    if result_format:
        payload["result_format"] = result_format
    return payload, source_paths


async def _post_json(client: httpx.AsyncClient, url: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {_safe_response(response)}")
    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("Hunyuan3D API returned invalid JSON") from exc
    data = result.get("Response", result) if isinstance(result, dict) else result
    if not isinstance(data, dict):
        raise RuntimeError("Hunyuan3D API returned an unexpected response shape")
    error = data.get("Error")
    if isinstance(error, dict):
        detail = f"{error.get('Code', '')} {error.get('Message', '')}".strip()
        raise RuntimeError(f"Hunyuan3D API error: {detail}")
    return data


async def _download(client: httpx.AsyncClient, url: str) -> bytes:
    response = await client.get(url, follow_redirects=True)
    response.raise_for_status()
    return response.content


def _filename_suffix(url: str, fallback: str) -> str:
    name = Path(unquote(urlparse(url).path)).name
    suffix = Path(name).suffix.lower()
    if suffix and re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
        return suffix
    normalized = re.sub(r"[^a-z0-9]", "", fallback.lower())
    return f".{normalized or 'bin'}"


async def hunyuan3d_tool(
    inputMode: str,
    prompt: str | None = None,
    frontImagePath: str | None = None,
    viewImagePaths: dict[str, str] | None = None,
    id: str | None = None,
    runId: str | None = None,
    runDir: str | None = None,
    purpose: str | None = None,
    domainType: str | None = None,
    deliverableCategory: str | None = None,
    generateType: str | None = None,
    enablePbr: bool | None = None,
    faceCount: int | None = None,
    resultFormat: str | None = None,
) -> str:
    selected_model = _model(None)
    try:
        request_payload, source_paths = _validate_and_build_payload(
            input_mode=(inputMode or "").strip(),
            prompt=prompt,
            front_image_path=frontImagePath,
            view_image_paths=viewImagePaths,
            model=selected_model,
            generate_type=generateType or "Normal",
            enable_pbr=bool(enablePbr),
            face_count=faceCount,
            result_format=resultFormat,
        )
    except (TypeError, ValueError) as exc:
        return _json({"ok": False, "error": str(exc)})

    key = _api_key()
    if not key:
        return _json({"ok": False, "error": "Missing DREAMATIC_HUNYUAN3D_API_KEY"})

    base_url = _base_url()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            submitted = await _post_json(client, f"{base_url}/submit", key, request_payload)
            job_id = _first_value(submitted, "id", "job_id", "JobId")
            if not job_id:
                raise RuntimeError("submit succeeded but the response did not contain a job id")
            job_id = str(job_id)

            deadline = time.monotonic() + JOB_TIMEOUT_SECONDS
            while True:
                if time.monotonic() >= deadline:
                    return _json(
                        {
                            "ok": False,
                            "error": "Hunyuan3D generation timed out",
                            "jobId": job_id,
                            "retryable": True,
                        }
                    )
                queried = await _post_json(
                    client,
                    f"{base_url}/query",
                    key,
                    {"model": selected_model, "id": job_id},
                )
                status = str(_first_value(queried, "Status", "status") or "UNKNOWN")
                normalized = status.upper()
                if normalized in {"DONE", "COMPLETED", "SUCCEEDED", "SUCCESS"}:
                    break
                if normalized in {"FAIL", "FAILED", "CANCELLED", "CANCELED"}:
                    code = _first_value(queried, "ErrorCode", "error_code") or ""
                    message = _first_value(queried, "ErrorMessage", "error_message") or ""
                    raise RuntimeError(f"generation failed: {code} {message}".strip())
                if normalized not in {"WAIT", "RUN", "QUEUED", "IN_PROGRESS", "PROCESSING"}:
                    raise RuntimeError(f"unknown job status: {status}")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

            result_files = _first_value(queried, "ResultFile3Ds", "result_file_3ds", "data") or []
            if not isinstance(result_files, list) or not result_files:
                raise RuntimeError("generation succeeded but no model files were returned")

            artifact_root = Path(runDir) / "artifacts" if runDir else Path("outputs") / "hunyuan3d"
            models_dir = artifact_root / "models"
            renders_dir = artifact_root / "model-renders"
            models_dir.mkdir(parents=True, exist_ok=True)
            renders_dir.mkdir(parents=True, exist_ok=True)
            stem = _slug(id or f"hunyuan3d-{job_id}")
            model_items: list[dict[str, Any]] = []
            preview_items: list[dict[str, Any]] = []

            for index, item in enumerate(result_files, start=1):
                if not isinstance(item, dict):
                    continue
                model_url = _first_value(item, "Url", "url")
                model_type = str(_first_value(item, "Type", "type") or "model")
                item_stem = stem if len(result_files) == 1 else f"{stem}-{index}"
                if model_url:
                    data = await _download(client, str(model_url))
                    model_path = models_dir / f"{item_stem}{_filename_suffix(str(model_url), model_type)}"
                    model_path.write_bytes(data)
                    model_items.append(
                        {
                            "file": str(model_path),
                            "relativePath": model_path.relative_to(artifact_root).as_posix(),
                            "type": model_type,
                            "sha256": _sha256(data),
                            "bytes": len(data),
                        }
                    )
                preview_url = _first_value(item, "PreviewImageUrl", "preview_image_url")
                if preview_url:
                    data = await _download(client, str(preview_url))
                    preview_path = renders_dir / f"{item_stem}-preview{_filename_suffix(str(preview_url), 'png')}"
                    preview_path.write_bytes(data)
                    preview_items.append(
                        {
                            "file": str(preview_path),
                            "relativePath": preview_path.relative_to(artifact_root).as_posix(),
                            "sha256": _sha256(data),
                            "bytes": len(data),
                        }
                    )

            if not model_items:
                raise RuntimeError("result contained no downloadable model URL")

            source_meta = [
                {"path": str(path), "sha256": _sha256(path.read_bytes())}
                for path in source_paths
            ]
            metadata = {
                "tool": "hunyuan3d",
                "backend": "tencent-tokenhub",
                "jobId": job_id,
                "runId": runId,
                "id": id,
                "input_mode": inputMode,
                "model": selected_model,
                "generate_type": generateType or "Normal",
                "enable_pbr": bool(enablePbr),
                "face_count": faceCount,
                "result_format": resultFormat,
                "purpose": purpose,
                "domain_type": domainType,
                "deliverable_category": deliverableCategory,
                "prompt": prompt,
                "sources": source_meta,
                "credit_consumed": _first_value(
                    queried, "ResultCreditConsumed", "result_credit_consumed"
                ),
                "models": model_items,
                "previews": preview_items,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            metadata_path = models_dir / f"{stem}.json"
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return _json(
                {
                    "ok": True,
                    "backend": "tencent-tokenhub",
                    "jobId": job_id,
                    "inputMode": inputMode,
                    "model": selected_model,
                    "creditConsumed": metadata["credit_consumed"],
                    "models": model_items,
                    "previews": preview_items,
                    "metadataFile": str(metadata_path),
                }
            )
    except httpx.RequestError as exc:
        return _json(
            {
                "ok": False,
                "error": "Hunyuan3D request failed",
                "detail": f"{type(exc).__name__}: {exc}",
                "retryable": True,
            }
        )
    except (OSError, RuntimeError) as exc:
        return _json({"ok": False, "error": str(exc)})


def _safe_response(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except Exception:
        return response.text[:1000]
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        error = payload["error"]
        return error.get("message") or error
    return payload
