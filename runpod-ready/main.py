from __future__ import annotations

import argparse
import logging
import re
import sys
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv

from config import AppConfig
from services.excel_service import ExcelService
from services.jupyter_service import check_jupyterlab_access
from services.recovery_service import RecoveryService
from services.runpod_service import PodCreateSpec, RunPodService
from services.url_service import build_runpod_url, build_ssh_command
from utils.logger import get_logger
from utils.naming import build_pod_name

STATUS_OK = "OK"
STATUS_DRY_RUN = "DRY_RUN"
STATUS_CHECK_SKIPPED = "CHECK_SKIPPED"
STATUS_UNREACHABLE = "UNREACHABLE"
STATUS_UNREACHABLE_RECREATED = "UNREACHABLE_RECREATED"
STATUS_POD_NOT_FOUND = "POD_NOT_FOUND"
STATUS_TERMINATED = "TERMINATED"
STATUS_STOPPED = "STOPPED"
STATUS_PLAN_TARGET = {"", STATUS_UNREACHABLE, STATUS_POD_NOT_FOUND, STATUS_TERMINATED}
STATUS_REPROVISION_TARGET = {STATUS_UNREACHABLE, STATUS_POD_NOT_FOUND, STATUS_TERMINATED}
UNREACHABLE_FALLBACK_DETAILS = {"HTTP_404"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RunPod 교육 Pod 운영 자동화 도구")
    parser.add_argument("--input", required=True, help="입력 엑셀 파일(.xlsx)")
    parser.add_argument("--output", help="출력 엑셀 파일(.xlsx). 기본값: 입력 파일 덮어쓰기")
    parser.add_argument(
        "--action",
        default="provision",
        choices=["provision", "sync", "stop", "terminate"],
        help="실행 액션: 기본 provision(생성/조회)",
    )
    parser.add_argument("--numbers", nargs="*", type=int, default=[], help="작업 대상 번호")
    parser.add_argument("--ids", nargs="*", default=[], help="작업 대상 아이디")
    parser.add_argument("--all", action="store_true", help="작업 대상을 전체 Pod로 지정")
    parser.add_argument("--overwrite-url", action="store_true", help="기존 RunPod URL이 있어도 덮어쓰기")
    parser.add_argument("--dry-run", action="store_true", help="실제 생성/삭제 없이 시뮬레이션")
    parser.add_argument("--recreate", nargs="*", type=int, default=[], help="번호 기준 재생성 대상")
    parser.add_argument("--recreate-ids", nargs="*", default=[], help="아이디 기준 재생성 대상")
    parser.add_argument(
        "--recreate-if-unhealthy",
        action="store_true",
        help="Pod 상태가 stopped/crashed/failed 계열이면 재생성",
    )
    parser.add_argument("--gpu-type", help="생성할 GPU 타입 ID")
    parser.add_argument(
        "--gpu-type-fallback",
        nargs="*",
        default=[],
        help="기본 GPU 생성 실패 시 순차적으로 시도할 대체 GPU 타입 목록",
    )
    parser.add_argument("--timeout", type=int, default=180, help="Pod runtime 대기 타임아웃(초)")
    parser.add_argument(
        "--jupyter-check",
        action="store_true",
        help="JupyterLab HTTP 접속 체크 수행 (기본: 생략)",
    )
    parser.add_argument(
        "--recreate-on-unreachable",
        action="store_true",
        help="JupyterLab 접속 불가 시 Pod 자동 재생성 (기본: 생략)",
    )
    parser.add_argument("--list-gpu-types", action="store_true", help="사용 가능한 GPU 타입 조회 후 종료")
    return parser


CAPACITY_ERROR_SIGNALS = (
    "no longer any instances available",
    "no instances available",
    "insufficient capacity",
    "requested specifications",
    "not enough free gpus",
)


def _collect_exception_texts(exc: Exception) -> list[str]:
    texts: list[str] = []
    seen: set[int] = set()
    stack: list[BaseException | None] = [exc]

    # Retry wrappers can hide the original RunPod capacity error in __cause__/__context__.
    while stack:
        current = stack.pop()
        if current is None:
            continue
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        texts.append(str(current))

        stack.append(getattr(current, "__cause__", None))
        if not getattr(current, "__suppress_context__", False):
            stack.append(getattr(current, "__context__", None))

    return texts


def _is_capacity_error(exc: Exception) -> bool:
    texts = _collect_exception_texts(exc)

    return any(signal in text.lower() for text in texts for signal in CAPACITY_ERROR_SIGNALS)


def _describe_capacity_error(exc: Exception) -> str:
    texts = _collect_exception_texts(exc)
    for text in texts:
        normalized = text.strip()
        if normalized and any(signal in normalized.lower() for signal in CAPACITY_ERROR_SIGNALS):
            return normalized
    return str(exc)


def _is_target_record(config: AppConfig, number: int, user_id: str) -> bool:
    if config.target_all:
        return True
    if number in config.target_numbers:
        return True
    if user_id.strip().lower() in config.target_ids:
        return True
    return False


def _build_create_candidates(config: AppConfig) -> list[str]:
    return [config.gpu_type] + [
        item for item in config.gpu_type_fallbacks if item.strip().lower() != config.gpu_type.strip().lower()
    ]


def _gpu_tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if token}


def _is_equivalent_gpu_label(left: str, right: str) -> bool:
    left_tokens = _gpu_tokens(left)
    right_tokens = _gpu_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    return left_tokens.issubset(right_tokens) or right_tokens.issubset(left_tokens)


def _should_prefer_fallback_gpu_on_unreachable(detail: str) -> bool:
    return detail.strip().upper() in UNREACHABLE_FALLBACK_DETAILS


def _build_unreachable_recreate_candidates(
    config: AppConfig,
    *,
    current_gpu: str | None,
    detail: str,
) -> list[str] | None:
    if not _should_prefer_fallback_gpu_on_unreachable(detail):
        return None

    candidates = _build_create_candidates(config)
    if len(candidates) < 2 or not current_gpu:
        return None

    preferred = [candidate for candidate in candidates if not _is_equivalent_gpu_label(candidate, current_gpu)]
    deferred = [candidate for candidate in candidates if _is_equivalent_gpu_label(candidate, current_gpu)]
    if not preferred or not deferred:
        return None
    return preferred + deferred


def _extract_gpu_type_from_pod(pod: dict[str, Any] | None) -> str | None:
    if not pod:
        return None

    machine = pod.get("machine") or {}
    candidates = [
        machine.get("gpuDisplayName"),
        machine.get("gpuTypeId"),
        machine.get("gpuType"),
        pod.get("gpuDisplayName"),
        pod.get("gpuTypeId"),
        pod.get("gpuType"),
        pod.get("gpu_type_id"),
    ]
    for value in candidates:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _split_gpu_types_by_memory(
    gpu_types: list[tuple[str, float, float | None]],
    *,
    threshold_gb: float,
) -> tuple[list[tuple[str, float, float | None]], list[tuple[str, float, float | None]]]:
    high_memory: list[tuple[str, float, float | None]] = []
    low_memory: list[tuple[str, float, float | None]] = []

    for item in gpu_types:
        if item[1] >= threshold_gb:
            high_memory.append(item)
        else:
            low_memory.append(item)

    return high_memory, low_memory


def _format_secure_price(secure_price: float | None) -> str:
    if secure_price is None:
        return "정보 없음"
    return f"${secure_price:g}/hr"


def _create_or_get_with_fallback(
    *,
    config: AppConfig,
    runpod_service: RunPodService,
    existing_pod: dict[str, Any] | None,
    force_recreate: bool,
    pod_name: str,
    app_logger: logging.Logger,
    gpu_candidates: list[str] | None = None,
) -> tuple[dict[str, Any], str | None]:
    if existing_pod is not None and not force_recreate:
        return existing_pod, _extract_gpu_type_from_pod(existing_pod)

    candidates = list(gpu_candidates) if gpu_candidates is not None else _build_create_candidates(config)
    pod = None
    selected_gpu_type: str | None = None
    for idx, gpu_type in enumerate(candidates):
        spec = PodCreateSpec(
            name=pod_name,
            image_name=config.image_name,
            gpu_type_id=gpu_type,
            volume_in_gb=config.volume_in_gb,
            container_disk_in_gb=config.container_disk_in_gb,
            ports=config.ports,
            template_id=config.template_id,
            jupyter_port=config.jupyter_port,
            jupyter_token=config.jupyter_token,
        )

        try:
            pod = runpod_service.create_or_get_pod(
                spec=spec,
                existing_pod=existing_pod,
                force_recreate=force_recreate,
                dry_run=config.dry_run,
            )
            if idx > 0:
                app_logger.info(
                    "Pod '%s' created with fallback GPU type '%s'",
                    pod_name,
                    gpu_type,
                )
            selected_gpu_type = _extract_gpu_type_from_pod(pod) or gpu_type
            break
        except Exception as exc:
            is_last = idx == len(candidates) - 1
            if (not _is_capacity_error(exc)) or is_last:
                raise

            app_logger.warning(
                "GPU '%s' unavailable for pod '%s'. Trying fallback GPU '%s'",
                gpu_type,
                pod_name,
                candidates[idx + 1],
            )

    if pod is None:
        raise RuntimeError(f"Pod creation failed without a pod result: {pod_name}")
    return pod, selected_gpu_type


def default_runpod_factory(config: AppConfig, logger: logging.Logger) -> RunPodService:
    return RunPodService.from_api_key(
        api_key=config.runpod_api_key,
        logger=logger,
        max_retries=config.max_retries,
        retry_delay_seconds=config.retry_delay_seconds,
        rate_limit_seconds=config.rate_limit_seconds,
    )


def run(
    args: argparse.Namespace,
    *,
    runpod_factory: Callable[[AppConfig, logging.Logger], RunPodService] | None = None,
    logger: logging.Logger | None = None,
    jupyter_checker: Callable[[str, int], tuple[bool, str]] | None = None,
) -> int:
    load_dotenv()
    app_logger = logger or get_logger()

    try:
        config = AppConfig.from_args(args)
        excel_service = ExcelService(sheet_name=config.sheet_name)
        workbook, worksheet, records, header_map = excel_service.load_records(config.input_path)

        service_factory = runpod_factory or default_runpod_factory
        runpod_service = service_factory(config, app_logger)

        if config.list_gpu_types:
            gpu_types = runpod_service.list_gpu_types_with_memory_and_secure_price()
            app_logger.info("Available GPU types (%s)", len(gpu_types))
            if not gpu_types:
                app_logger.warning("No GPU types found")
                return 0

            high_memory, low_memory = _split_gpu_types_by_memory(gpu_types, threshold_gb=40.0)

            print("=== Memory >= 40GB ===")
            for gpu_type, memory_gb, secure_price in high_memory:
                secure_text = _format_secure_price(secure_price)
                print(f"{gpu_type} | {memory_gb:g} GB | securePrice: {secure_text}")

            print()
            print("=== Memory < 40GB ===")
            for gpu_type, memory_gb, secure_price in low_memory:
                secure_text = _format_secure_price(secure_price)
                print(f"{gpu_type} | {memory_gb:g} GB | securePrice: {secure_text}")
            return 0

        if config.action in {"stop", "terminate"} and not (
            config.target_all or config.target_numbers or config.target_ids
        ):
            raise ValueError("For action stop/terminate, specify targets with --all or --numbers/--ids")

        recovery_service = RecoveryService(
            recreate_numbers=config.recreate_numbers,
            recreate_ids=config.recreate_ids,
            recreate_if_unhealthy=config.recreate_if_unhealthy,
        )
        existing_pods = runpod_service.get_existing_pods_map()
        checker = jupyter_checker or check_jupyterlab_access

        updated_count = 0
        skipped_count = 0
        failed_records: list[tuple[int, str, int, str]] = []

        if config.action == "sync":
            print(f"{'번호':>4}  {'아이디':<18}  {'상태':<18}  URL  SSH")
            print("-" * 140)

        for record in records:
            is_targeted = _is_target_record(config, record.number, record.user_id)
            if config.action in {"stop", "terminate"} and not is_targeted:
                continue
            if config.action == "sync" and (config.target_all or config.target_numbers or config.target_ids) and not is_targeted:
                continue

            pod_name = build_pod_name(record.number, record.user_id, prefix=config.class_prefix)
            existing_pod = existing_pods.get(pod_name.lower())
            decision = recovery_service.should_recreate(
                number=record.number,
                user_id=record.user_id,
                pod=existing_pod,
            )
            record_status = (record.jupyter_status or "").strip().upper()
            status_based_recreate = config.action == "provision" and record_status in STATUS_REPROVISION_TARGET
            should_recreate = decision.recreate or status_based_recreate

            if config.action == "provision" and status_based_recreate:
                status_label = record_status or "<empty>"
                app_logger.info(
                    "Provision selected row=%s, number=%s, id=%s because status is '%s' (reprovision target)",
                    record.row_index,
                    record.number,
                    record.user_id,
                    status_label,
                )

            if config.action == "sync":
                try:
                    if existing_pod is None:
                        excel_service.update_jupyter_status(worksheet, header_map, record, STATUS_POD_NOT_FOUND)
                        print(f"{record.number:>4}  {record.user_id:<18}  {STATUS_POD_NOT_FOUND:<18}  -")
                        skipped_count += 1
                        continue

                    pod_id = str(existing_pod.get("id", "")).strip()
                    pod_info = runpod_service.get_pod(pod_id) if pod_id else existing_pod
                    ssh_command = build_ssh_command(pod_info)

                    runpod_url = (record.runpod_url or "").strip() or build_runpod_url(
                        pod_info,
                        jupyter_port=config.jupyter_port,
                    )
                    if not runpod_url:
                        excel_service.update_jupyter_status(worksheet, header_map, record, STATUS_UNREACHABLE)
                        print(f"{record.number:>4}  {record.user_id:<18}  {STATUS_UNREACHABLE:<18}  -")
                        continue

                    if config.dry_run:
                        status = STATUS_DRY_RUN
                        detail = ""
                    else:
                        ok, detail = checker(runpod_url, config.jupyter_check_timeout_seconds)
                        status = STATUS_OK if ok else STATUS_UNREACHABLE

                    excel_service.update_jupyter_status(worksheet, header_map, record, status)
                    if ssh_command:
                        excel_service.update_ssh_command(worksheet, header_map, record, ssh_command)
                    detail_str = f"  ({detail})" if detail and status != STATUS_OK else ""
                    ssh_text = ssh_command or (record.ssh_command or "-")
                    print(f"{record.number:>4}  {record.user_id:<18}  {status:<18}  {runpod_url}{detail_str}  {ssh_text}")
                    updated_count += 1
                except Exception as exc:
                    failed_records.append((record.row_index, record.user_id, record.number, str(exc)))
                    print(f"{record.number:>4}  {record.user_id:<18}  {'ERROR':<18}  {exc}")
                continue

            if config.action in {"stop", "terminate"}:
                try:
                    if existing_pod is None:
                        excel_service.update_jupyter_status(worksheet, header_map, record, STATUS_POD_NOT_FOUND)
                        skipped_count += 1
                        continue

                    pod_id = str(existing_pod.get("id", "")).strip()
                    if not pod_id:
                        raise ValueError(f"Pod has no id: {pod_name}")

                    if config.action == "stop":
                        gpu_type = _extract_gpu_type_from_pod(existing_pod)
                        if gpu_type:
                            excel_service.update_gpu_type(worksheet, header_map, record, gpu_type)
                        runpod_service.stop_pod(pod_id, dry_run=config.dry_run)
                        excel_service.update_jupyter_status(worksheet, header_map, record, STATUS_STOPPED)
                    elif config.action == "terminate":
                        runpod_service.terminate_pod(pod_id, dry_run=config.dry_run)
                        excel_service.update_jupyter_status(worksheet, header_map, record, STATUS_TERMINATED)

                    updated_count += 1
                except Exception as exc:
                    failed_records.append((record.row_index, record.user_id, record.number, str(exc)))
                    app_logger.error(
                        "Action '%s' failed row=%s, number=%s, id=%s, pod=%s: %s",
                        config.action,
                        record.row_index,
                        record.number,
                        record.user_id,
                        pod_name,
                        exc,
                    )
                continue

            if record.runpod_url and not config.overwrite_url and not should_recreate:
                gpu_type = _extract_gpu_type_from_pod(existing_pod)
                if gpu_type:
                    excel_service.update_gpu_type(worksheet, header_map, record, gpu_type)
                if existing_pod is not None:
                    ssh_command = build_ssh_command(existing_pod)
                    if ssh_command:
                        excel_service.update_ssh_command(worksheet, header_map, record, ssh_command)
                skipped_count += 1
                app_logger.info(
                    "Skipping row=%s, number=%s, id=%s because URL already exists",
                    record.row_index,
                    record.number,
                    record.user_id,
                )
                continue

            try:
                if should_recreate and existing_pod is None:
                    app_logger.warning(
                        "Recreate requested but no existing pod found. A new pod will be created: %s",
                        pod_name,
                    )

                pod, gpu_type_hint = _create_or_get_with_fallback(
                    config=config,
                    runpod_service=runpod_service,
                    existing_pod=existing_pod,
                    force_recreate=should_recreate,
                    pod_name=pod_name,
                    app_logger=app_logger,
                )

                pod_id = str(pod.get("id", "")).strip()
                if pod_id and not config.dry_run and not config.skip_jupyter_check:
                    pod = runpod_service.wait_for_runtime(pod_id, timeout_seconds=config.timeout_seconds)

                resolved_gpu_type = _extract_gpu_type_from_pod(pod) or gpu_type_hint
                if resolved_gpu_type:
                    excel_service.update_gpu_type(worksheet, header_map, record, resolved_gpu_type)

                ssh_command = build_ssh_command(pod)
                if ssh_command:
                    excel_service.update_ssh_command(worksheet, header_map, record, ssh_command)

                runpod_url = build_runpod_url(pod, jupyter_port=config.jupyter_port)
                if not runpod_url:
                    app_logger.warning(
                        "Could not construct URL for row=%s, number=%s, id=%s",
                        record.row_index,
                        record.number,
                        record.user_id,
                    )
                    continue

                if config.dry_run:
                    status = STATUS_DRY_RUN
                elif config.skip_jupyter_check:
                    status = STATUS_CHECK_SKIPPED
                else:
                    ok, detail = checker(runpod_url, config.jupyter_check_timeout_seconds)
                    if ok:
                        status = STATUS_OK
                    else:
                        if not config.recreate_on_unreachable:
                            status = STATUS_UNREACHABLE
                            excel_service.update_runpod_url(worksheet, header_map, record, runpod_url)
                            excel_service.update_jupyter_status(worksheet, header_map, record, status)
                            existing_pods[pod_name.lower()] = pod
                            updated_count += 1
                            app_logger.warning(
                                "JupyterLab unreachable for pod '%s' (%s). Auto-recreate disabled.",
                                pod_name,
                                detail,
                            )
                            continue

                        app_logger.warning(
                            "JupyterLab unreachable for pod '%s' (%s). Recreating pod.",
                            pod_name,
                            detail,
                        )
                        current_gpu = _extract_gpu_type_from_pod(pod) or gpu_type_hint or record.gpu_type or config.gpu_type
                        recreate_candidates = _build_unreachable_recreate_candidates(
                            config,
                            current_gpu=current_gpu,
                            detail=detail,
                        )
                        if recreate_candidates is not None:
                            app_logger.warning(
                                "JupyterLab unreachable for pod '%s' (%s). Trying fallback-first GPU order with current GPU '%s': %s",
                                pod_name,
                                detail,
                                current_gpu,
                                ", ".join(recreate_candidates),
                            )
                        pod, gpu_type_hint = _create_or_get_with_fallback(
                            config=config,
                            runpod_service=runpod_service,
                            existing_pod=pod,
                            force_recreate=True,
                            pod_name=pod_name,
                            app_logger=app_logger,
                            gpu_candidates=recreate_candidates,
                        )
                        pod_id = str(pod.get("id", "")).strip()
                        if pod_id:
                            pod = runpod_service.wait_for_runtime(pod_id, timeout_seconds=config.timeout_seconds)
                        resolved_gpu_type = _extract_gpu_type_from_pod(pod) or gpu_type_hint
                        if resolved_gpu_type:
                            excel_service.update_gpu_type(worksheet, header_map, record, resolved_gpu_type)
                        runpod_url = build_runpod_url(pod, jupyter_port=config.jupyter_port)
                        if not runpod_url:
                            raise RuntimeError(f"No URL after recreate: {pod_name}")
                        ok2, detail2 = checker(runpod_url, config.jupyter_check_timeout_seconds)
                        if not ok2:
                            raise RuntimeError(f"JupyterLab still unreachable after recreate ({detail2})")
                        status = STATUS_UNREACHABLE_RECREATED

                excel_service.update_runpod_url(worksheet, header_map, record, runpod_url)
                excel_service.update_jupyter_status(worksheet, header_map, record, status)
                existing_pods[pod_name.lower()] = pod
                updated_count += 1
                app_logger.info(
                    "Updated URL for row=%s, number=%s, id=%s",
                    record.row_index,
                    record.number,
                    record.user_id,
                )
            except Exception as exc:
                failed_records.append((record.row_index, record.user_id, record.number, str(exc)))
                app_logger.error(
                    "Failed row=%s, number=%s, id=%s, pod=%s: %s",
                    record.row_index,
                    record.number,
                    record.user_id,
                    pod_name,
                    exc,
                )
                continue

        output_path = excel_service.save_updated_copy(workbook, config.input_path, config.output_path)
        if failed_records:
            app_logger.error(
                "Completed with failures. updated=%s skipped=%s failed=%s output=%s",
                updated_count,
                skipped_count,
                len(failed_records),
                output_path,
            )
            for row_index, user_id, number, reason in failed_records:
                app_logger.error(
                    "Failure detail row=%s number=%s id=%s reason=%s",
                    row_index,
                    number,
                    user_id,
                    reason,
                )
            return 1

        app_logger.info(
            "Completed. updated=%s skipped=%s output=%s",
            updated_count,
            skipped_count,
            output_path,
        )
        return 0
    except Exception:
        app_logger.exception("Execution failed")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
