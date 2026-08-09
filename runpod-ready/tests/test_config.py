from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from config import AppConfig


def _make_args(input_path: Path) -> Namespace:
    return Namespace(
        input=str(input_path),
        output=None,
        action="provision",
        numbers=[],
        ids=[],
        all=False,
        overwrite_url=False,
        dry_run=True,
        recreate=[],
        recreate_ids=[],
        recreate_if_unhealthy=False,
        gpu_type=None,
        gpu_type_fallback=[],
        timeout=180,
        jupyter_check=False,
        recreate_on_unreachable=False,
        list_gpu_types=False,
    )


def test_from_args_uses_env_gpu_defaults(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.xlsx"
    input_path.write_text("placeholder", encoding="utf-8")

    monkeypatch.setenv("RUNPOD_GPU_TYPE", "NVIDIA A100 80GB PCIe")
    monkeypatch.setenv(
        "RUNPOD_GPU_TYPE_FALLBACKS",
        "NVIDIA A100-SXM4-80GB,NVIDIA A100-SXM4-80GB,NVIDIA A100 80GB PCIe,NVIDIA H100 PCIe",
    )

    config = AppConfig.from_args(_make_args(input_path))

    assert config.gpu_type == "NVIDIA A100 80GB PCIe"
    assert config.gpu_type_fallbacks == [
        "NVIDIA A100-SXM4-80GB",
        "NVIDIA H100 PCIe",
    ]


def test_from_args_cli_overrides_env_gpu_and_fallbacks(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.xlsx"
    input_path.write_text("placeholder", encoding="utf-8")

    monkeypatch.setenv("RUNPOD_GPU_TYPE", "NVIDIA A100 80GB PCIe")
    monkeypatch.setenv("RUNPOD_GPU_TYPE_FALLBACKS", "NVIDIA A100-SXM4-80GB")

    args = _make_args(input_path)
    args.gpu_type = "NVIDIA L40S"
    args.gpu_type_fallback = ["NVIDIA H100 PCIe", "NVIDIA A40"]

    config = AppConfig.from_args(args)

    assert config.gpu_type == "NVIDIA L40S"
    assert config.gpu_type_fallbacks == ["NVIDIA H100 PCIe", "NVIDIA A40"]


def test_from_args_uses_env_fallbacks_when_cli_fallbacks_missing(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.xlsx"
    input_path.write_text("placeholder", encoding="utf-8")

    monkeypatch.setenv("RUNPOD_GPU_TYPE", "NVIDIA A100 80GB PCIe")
    monkeypatch.setenv("RUNPOD_GPU_TYPE_FALLBACKS", "NVIDIA A100 80GB PCIe;NVIDIA A100-SXM4-80GB")

    args = _make_args(input_path)
    args.gpu_type = "NVIDIA A100 80GB PCIe"
    args.gpu_type_fallback = []

    config = AppConfig.from_args(args)

    assert config.gpu_type_fallbacks == ["NVIDIA A100-SXM4-80GB"]


def test_from_args_uses_code_default_fallback_when_env_missing(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.xlsx"
    input_path.write_text("placeholder", encoding="utf-8")

    monkeypatch.delenv("RUNPOD_GPU_TYPE", raising=False)
    monkeypatch.delenv("RUNPOD_GPU_TYPE_FALLBACKS", raising=False)

    args = _make_args(input_path)
    args.gpu_type = None
    args.gpu_type_fallback = []

    config = AppConfig.from_args(args)

    assert config.gpu_type == "NVIDIA A100 80GB PCIe"
    assert config.gpu_type_fallbacks == ["NVIDIA A100-SXM4-80GB"]


def test_from_args_defaults_to_fast_mode(tmp_path: Path) -> None:
    input_path = tmp_path / "input.xlsx"
    input_path.write_text("placeholder", encoding="utf-8")

    args = _make_args(input_path)  # 어떤 플래그도 없음 = 기본값
    config = AppConfig.from_args(args)

    assert config.skip_jupyter_check is True
    assert config.recreate_on_unreachable is False


def test_from_args_opt_in_jupyter_check_and_recreate(tmp_path: Path) -> None:
    input_path = tmp_path / "input.xlsx"
    input_path.write_text("placeholder", encoding="utf-8")

    args = _make_args(input_path)
    args.jupyter_check = True
    args.recreate_on_unreachable = True

    config = AppConfig.from_args(args)

    assert config.skip_jupyter_check is False
    assert config.recreate_on_unreachable is True
