from __future__ import annotations

import contextlib
import io
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

from utils.retry import call_with_retry


class RunPodClientProtocol(Protocol):
    def get_gpus(self) -> list[dict[str, Any]]:
        ...

    def get_pods(self) -> list[dict[str, Any]]:
        ...

    def get_gpu(self, gpu_id: str) -> dict[str, Any]:
        ...

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        ...

    def create_pod(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def terminate_pod(self, pod_id: str) -> Any:
        ...

    def stop_pod(self, pod_id: str) -> Any:
        ...

    def resume_pod(self, pod_id: str, gpu_count: int = 1) -> Any:
        ...


@dataclass(slots=True)
class PodCreateSpec:
    name: str
    image_name: str
    gpu_type_id: str
    volume_in_gb: int
    container_disk_in_gb: int
    ports: str
    template_id: str | None
    jupyter_port: int
    jupyter_token: str | None

    @property
    def docker_args(self) -> str:
        token_arg = ""
        if self.jupyter_token:
            token_arg = f"--NotebookApp.token='{self.jupyter_token}' "

        return (
            f"jupyter lab --ip=0.0.0.0 --port={self.jupyter_port} --no-browser --allow-root "
            f"{token_arg}--ServerApp.allow_origin='*'"
        ).strip()


class RunPodSDKAdapter:
    """Adapter to convert runpod module functions into an object interface."""

    def __init__(self, sdk_module: Any) -> None:
        self._sdk = sdk_module

    def get_gpus(self) -> list[dict[str, Any]]:
        return self._sdk.get_gpus()

    def get_pods(self) -> list[dict[str, Any]]:
        return self._sdk.get_pods()

    def get_gpu(self, gpu_id: str) -> dict[str, Any]:
        return self._sdk.get_gpu(gpu_id)

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        return self._sdk.get_pod(pod_id)

    def create_pod(self, **kwargs: Any) -> dict[str, Any]:
        # Current runpod SDK versions may print raw GraphQL responses to stdout.
        # Suppress that noise so operational logs remain readable.
        with contextlib.redirect_stdout(io.StringIO()):
            return self._sdk.create_pod(**kwargs)

    def terminate_pod(self, pod_id: str) -> Any:
        return self._sdk.terminate_pod(pod_id)

    def stop_pod(self, pod_id: str) -> Any:
        return self._sdk.stop_pod(pod_id)

    def resume_pod(self, pod_id: str, gpu_count: int = 1) -> Any:
        # RunPod SDK exposes resume_pod for starting stopped pods.
        return self._sdk.resume_pod(pod_id, gpu_count)


class RunPodService:
    """Resilient RunPod API facade with retries and idempotent helpers."""

    def __init__(
        self,
        *,
        client: RunPodClientProtocol,
        logger: logging.Logger,
        max_retries: int,
        retry_delay_seconds: float,
        rate_limit_seconds: float,
    ) -> None:
        self.client = client
        self.logger = logger
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.rate_limit_seconds = rate_limit_seconds

    @classmethod
    def from_api_key(
        cls,
        *,
        api_key: str,
        logger: logging.Logger,
        max_retries: int,
        retry_delay_seconds: float,
        rate_limit_seconds: float,
    ) -> "RunPodService":
        try:
            import runpod  # type: ignore
        except ImportError as exc:
            raise RuntimeError("runpod package is not installed. Install requirements first.") from exc

        runpod.api_key = api_key
        client = RunPodSDKAdapter(runpod)
        return cls(
            client=client,
            logger=logger,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            rate_limit_seconds=rate_limit_seconds,
        )

    def list_gpu_types(self) -> list[str]:
        gpus = self._retry_call(lambda: self.client.get_gpus(), "get_gpus")
        result: list[str] = []
        for gpu in gpus:
            display = gpu.get("id") or gpu.get("gpuTypeId") or gpu.get("displayName") or gpu.get("name")
            if display:
                result.append(str(display))
        return sorted(set(result))

    def list_gpu_types_with_memory(self, *, min_memory_gb: float | None = None) -> list[tuple[str, float]]:
        """Return GPU types with memory in GB, optionally filtered by minimum memory."""
        gpus = self._retry_call(lambda: self.client.get_gpus(), "get_gpus")
        by_name: dict[str, float] = {}

        for gpu in gpus:
            display = gpu.get("id") or gpu.get("gpuTypeId") or gpu.get("displayName") or gpu.get("name")
            if not display:
                continue

            memory_gb = self._extract_memory_gb(gpu)
            if memory_gb is None:
                continue
            if min_memory_gb is not None and memory_gb < min_memory_gb:
                continue

            name = str(display)
            # Keep the largest memory value when duplicate names appear.
            if name not in by_name or memory_gb > by_name[name]:
                by_name[name] = memory_gb

        return sorted(by_name.items(), key=lambda item: (-item[1], item[0].lower()))

    def list_gpu_types_with_memory_and_secure_price(
        self,
        *,
        min_memory_gb: float | None = None,
    ) -> list[tuple[str, float, float | None]]:
        """Return GPU type, memory (GB), and securePrice for matching GPU types."""
        items = self.list_gpu_types_with_memory(min_memory_gb=min_memory_gb)
        result: list[tuple[str, float, float | None]] = []

        for gpu_type, memory_gb in items:
            detail = self._retry_call(lambda: self.client.get_gpu(gpu_type), f"get_gpu:{gpu_type}")
            secure_price = self._extract_secure_price(detail)
            result.append((gpu_type, memory_gb, secure_price))

        return result

    @staticmethod
    def _extract_memory_gb(gpu: dict[str, Any]) -> float | None:
        for key in ("memoryInGb", "memoryGB", "memoryGb"):
            value = gpu.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue

        for key in ("memoryInMb", "memoryMB", "memoryMb"):
            value = gpu.get(key)
            if value is None:
                continue
            try:
                return float(value) / 1024.0
            except (TypeError, ValueError):
                continue

        return None

    @staticmethod
    def _extract_secure_price(detail: Any) -> float | None:
        if isinstance(detail, dict):
            value = detail.get("securePrice")
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        if isinstance(detail, list):
            for item in detail:
                if not isinstance(item, dict):
                    continue
                value = item.get("securePrice")
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return None

    def get_existing_pods_map(self) -> dict[str, dict[str, Any]]:
        pods = self._retry_call(lambda: self.client.get_pods(), "get_pods")
        by_name: dict[str, dict[str, Any]] = {}
        for pod in pods:
            name = str(pod.get("name", "")).strip().lower()
            if not name:
                continue
            by_name[name] = pod
        return by_name

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        return self._retry_call(lambda: self.client.get_pod(pod_id), f"get_pod:{pod_id}")

    def terminate_pod(self, pod_id: str, *, dry_run: bool) -> None:
        if dry_run:
            self.logger.info("[dry-run] terminate_pod(%s)", pod_id)
            return
        self._retry_call(lambda: self.client.terminate_pod(pod_id), f"terminate_pod:{pod_id}")

    def stop_pod(self, pod_id: str, *, dry_run: bool) -> None:
        if dry_run:
            self.logger.info("[dry-run] stop_pod(%s)", pod_id)
            return
        self._retry_call(lambda: self.client.stop_pod(pod_id), f"stop_pod:{pod_id}")

    def resume_pod(self, pod_id: str, *, dry_run: bool, gpu_count: int = 1) -> None:
        if dry_run:
            self.logger.info("[dry-run] resume_pod(%s)", pod_id)
            return
        self._retry_call(lambda: self.client.resume_pod(pod_id, gpu_count), f"resume_pod:{pod_id}")

    def start_pod(self, pod_id: str, *, dry_run: bool, gpu_count: int = 1) -> None:
        # start maps to resume in RunPod API semantics.
        self.resume_pod(pod_id, dry_run=dry_run, gpu_count=gpu_count)

    def create_pod(self, spec: PodCreateSpec, *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            self.logger.info("[dry-run] create_pod(name=%s)", spec.name)
            return {
                "id": f"dryrun-{spec.name}",
                "name": spec.name,
                "runtime": {
                    "host": "dry-run.local",
                    "port": spec.jupyter_port,
                    "token": spec.jupyter_token,
                },
            }

        kwargs: dict[str, Any] = {
            "name": spec.name,
            "image_name": spec.image_name,
            "gpu_type_id": spec.gpu_type_id,
            "volume_in_gb": spec.volume_in_gb,
            "container_disk_in_gb": spec.container_disk_in_gb,
            "ports": spec.ports,
            "docker_args": spec.docker_args,
        }
        if spec.template_id:
            kwargs["template_id"] = spec.template_id

        created = self._retry_call(lambda: self.client.create_pod(**kwargs), f"create_pod:{spec.name}")
        if self.rate_limit_seconds > 0:
            time.sleep(self.rate_limit_seconds)
        return created

    def create_or_get_pod(
        self,
        *,
        spec: PodCreateSpec,
        existing_pod: dict[str, Any] | None,
        force_recreate: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        if existing_pod and force_recreate:
            pod_id = str(existing_pod.get("id", "")).strip()
            if pod_id:
                self.logger.info("Recreating pod '%s' (id=%s)", spec.name, pod_id)
                self.terminate_pod(pod_id, dry_run=dry_run)
            return self.create_pod(spec, dry_run=dry_run)

        if existing_pod:
            self.logger.info("Reusing existing pod '%s'", spec.name)
            return existing_pod

        self.logger.info("Creating new pod '%s'", spec.name)
        return self.create_pod(spec, dry_run=dry_run)

    def wait_for_runtime(self, pod_id: str, *, timeout_seconds: int, poll_seconds: int = 5) -> dict[str, Any]:
        started = time.time()
        last_seen: dict[str, Any] | None = None

        while time.time() - started <= timeout_seconds:
            pod = self.get_pod(pod_id)
            last_seen = pod
            runtime = pod.get("runtime") or {}
            ports = runtime.get("ports") or []
            if runtime.get("host") and runtime.get("port"):
                return pod
            if isinstance(ports, list) and len(ports) > 0:
                return pod
            time.sleep(poll_seconds)

        if last_seen is not None:
            return last_seen
        raise TimeoutError(f"Timed out waiting for pod runtime: {pod_id}")

    def _retry_call(self, func: Any, operation_name: str) -> Any:
        return call_with_retry(
            func,
            retries=self.max_retries,
            delay_seconds=self.retry_delay_seconds,
            operation_name=operation_name,
            logger=self.logger,
        )
