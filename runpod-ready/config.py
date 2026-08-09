from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_IMAGE_NAME = "runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04"
DEFAULT_GPU_TYPE = "NVIDIA A100 80GB PCIe"
DEFAULT_GPU_TYPE_FALLBACKS = ["NVIDIA A100-SXM4-80GB"]


def _to_int(value: str | None, fallback: int) -> int:
    if value is None or value.strip() == "":
        return fallback
    return int(value)


def _to_float(value: str | None, fallback: float) -> float:
    if value is None or value.strip() == "":
        return fallback
    return float(value)


def _parse_gpu_fallbacks(value: str | None) -> list[str]:
    """Parse fallback GPU list from env (comma/semicolon separated)."""
    if value is None:
        return []
    items = [item.strip() for item in re.split(r"[,;]", value) if item.strip()]
    return items


def _normalize_fallbacks(primary_gpu: str, values: list[str]) -> list[str]:
    primary = primary_gpu.strip().lower()
    seen: set[str] = {primary}
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


@dataclass(slots=True)
class AppConfig:
    runpod_api_key: str
    input_path: Path
    output_path: Path | None
    sheet_name: str
    overwrite_url: bool
    dry_run: bool
    recreate_numbers: set[int] = field(default_factory=set)
    recreate_ids: set[str] = field(default_factory=set)
    recreate_if_unhealthy: bool = False
    action: str = "provision"
    target_numbers: set[int] = field(default_factory=set)
    target_ids: set[str] = field(default_factory=set)
    target_all: bool = False
    gpu_type: str = DEFAULT_GPU_TYPE
    gpu_type_fallbacks: list[str] = field(default_factory=list)
    timeout_seconds: int = 180
    jupyter_check_timeout_seconds: int = 20
    skip_jupyter_check: bool = True
    recreate_on_unreachable: bool = False
    image_name: str = DEFAULT_IMAGE_NAME
    volume_in_gb: int = 100
    container_disk_in_gb: int = 100
    ports: str = "8888/http"
    template_id: str | None = None
    jupyter_port: int = 8888
    jupyter_token: str | None = None
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    rate_limit_seconds: float = 1.0
    class_prefix: str = "class"
    list_gpu_types: bool = False

    @classmethod
    def from_args(cls, args: object) -> "AppConfig":
        action = str(getattr(args, "action") or "provision").strip().lower()
        input_path = Path(getattr(args, "input")).expanduser().resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        output_raw = getattr(args, "output")
        output_path = Path(output_raw).expanduser().resolve() if output_raw else None

        recreate_numbers = set(getattr(args, "recreate") or [])
        recreate_ids = {value.strip().lower() for value in (getattr(args, "recreate_ids") or []) if value.strip()}
        target_numbers = set(getattr(args, "numbers") or [])
        target_ids = {value.strip().lower() for value in (getattr(args, "ids") or []) if value.strip()}

        gpu_type_arg = (getattr(args, "gpu_type") or "").strip()
        gpu_type_env = os.getenv("RUNPOD_GPU_TYPE", "").strip()
        gpu_type = gpu_type_arg or gpu_type_env or DEFAULT_GPU_TYPE

        gpu_type_fallbacks_cli = [
            value.strip()
            for value in (getattr(args, "gpu_type_fallback") or [])
            if value and value.strip()
        ]
        gpu_type_fallbacks_env = _parse_gpu_fallbacks(os.getenv("RUNPOD_GPU_TYPE_FALLBACKS"))
        if gpu_type_fallbacks_cli:
            raw_fallbacks = gpu_type_fallbacks_cli
        elif gpu_type_fallbacks_env:
            raw_fallbacks = gpu_type_fallbacks_env
        else:
            raw_fallbacks = DEFAULT_GPU_TYPE_FALLBACKS
        gpu_type_fallbacks = _normalize_fallbacks(gpu_type, raw_fallbacks)

        runpod_api_key = os.getenv("RUNPOD_API_KEY", "").strip()
        dry_run = bool(getattr(args, "dry_run"))
        requires_api_key = action != "plan"
        if requires_api_key and not runpod_api_key and not dry_run:
            raise ValueError("RUNPOD_API_KEY is required unless --dry-run is enabled.")

        return cls(
            runpod_api_key=runpod_api_key,
            input_path=input_path,
            output_path=output_path,
            sheet_name=os.getenv("RUNPOD_SHEET_NAME", "시트1"),
            overwrite_url=bool(getattr(args, "overwrite_url")),
            dry_run=dry_run,
            recreate_numbers=recreate_numbers,
            recreate_ids=recreate_ids,
            recreate_if_unhealthy=bool(getattr(args, "recreate_if_unhealthy")),
            action=action,
            target_numbers=target_numbers,
            target_ids=target_ids,
            target_all=bool(getattr(args, "all")),
            gpu_type=gpu_type,
            gpu_type_fallbacks=gpu_type_fallbacks,
            timeout_seconds=int(getattr(args, "timeout")),
            jupyter_check_timeout_seconds=_to_int(os.getenv("RUNPOD_JUPYTER_CHECK_TIMEOUT"), 20),
            skip_jupyter_check=not bool(getattr(args, "jupyter_check", False)),
            recreate_on_unreachable=bool(getattr(args, "recreate_on_unreachable", False)),
            image_name=os.getenv("RUNPOD_IMAGE_NAME", DEFAULT_IMAGE_NAME).strip(),
            volume_in_gb=_to_int(os.getenv("RUNPOD_VOLUME_GB"), 100),
            container_disk_in_gb=_to_int(os.getenv("RUNPOD_CONTAINER_DISK_GB"), 100),
            ports=os.getenv("RUNPOD_PORTS", "8888/http").strip(),
            template_id=(os.getenv("RUNPOD_TEMPLATE_ID", "").strip() or None),
            jupyter_port=_to_int(os.getenv("RUNPOD_JUPYTER_PORT"), 8888),
            jupyter_token=(os.getenv("RUNPOD_JUPYTER_TOKEN", "").strip() or None),
            max_retries=_to_int(os.getenv("RUNPOD_RETRY_COUNT"), 3),
            retry_delay_seconds=_to_float(os.getenv("RUNPOD_RETRY_DELAY_SECONDS"), 2.0),
            rate_limit_seconds=_to_float(os.getenv("RUNPOD_RATE_LIMIT_SECONDS"), 1.0),
            class_prefix=os.getenv("RUNPOD_CLASS_PREFIX", "class").strip() or "class",
            list_gpu_types=bool(getattr(args, "list_gpu_types")),
        )
