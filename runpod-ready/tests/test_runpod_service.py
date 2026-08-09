from __future__ import annotations

import logging
from typing import Any

from services.runpod_service import PodCreateSpec, RunPodService


class FakeRunPodClient:
    def __init__(self) -> None:
        self.pods: list[dict[str, Any]] = []
        self.created_payloads: list[dict[str, Any]] = []
        self.terminated_ids: list[str] = []
        self.stopped_ids: list[str] = []
        self.resumed_ids: list[str] = []
        self.fail_create_count = 0

    def get_gpus(self) -> list[dict[str, Any]]:
        return [
            {"id": "NVIDIA A100 80GB PCIe", "memoryInGb": 80},
            {"displayName": "NVIDIA RTX 4090", "memoryInGb": 24},
            {"displayName": "NVIDIA H100", "memoryInGb": 80},
        ]

    def get_pods(self) -> list[dict[str, Any]]:
        return list(self.pods)

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        for pod in self.pods:
            if pod["id"] == pod_id:
                return pod
        raise KeyError(pod_id)

    def get_gpu(self, gpu_id: str) -> dict[str, Any]:
        if gpu_id == "NVIDIA A100 80GB PCIe":
            return {"id": gpu_id, "memoryInGb": 80, "securePrice": 1.39}
        if gpu_id == "NVIDIA H100":
            return {"id": gpu_id, "memoryInGb": 80, "securePrice": 2.49}
        return {"id": gpu_id, "memoryInGb": 24}

    def create_pod(self, **kwargs: Any) -> dict[str, Any]:
        if self.fail_create_count > 0:
            self.fail_create_count -= 1
            raise RuntimeError("temporary error")

        pod = {
            "id": f"pod-{len(self.pods) + 1}",
            "name": kwargs["name"],
            "runtime": {"host": "pod.example.com", "port": 8888},
        }
        self.created_payloads.append(kwargs)
        self.pods.append(pod)
        return pod

    def terminate_pod(self, pod_id: str) -> dict[str, str]:
        self.terminated_ids.append(pod_id)
        self.pods = [pod for pod in self.pods if pod["id"] != pod_id]
        return {"id": pod_id}

    def stop_pod(self, pod_id: str) -> dict[str, str]:
        self.stopped_ids.append(pod_id)
        return {"id": pod_id}

    def resume_pod(self, pod_id: str, gpu_count: int = 1) -> dict[str, str]:
        self.resumed_ids.append(pod_id)
        return {"id": pod_id}


def _make_service(client: FakeRunPodClient) -> RunPodService:
    return RunPodService(
        client=client,
        logger=logging.getLogger("test-runpod-service"),
        max_retries=3,
        retry_delay_seconds=0,
        rate_limit_seconds=0,
    )


def _make_spec(name: str) -> PodCreateSpec:
    return PodCreateSpec(
        name=name,
        image_name="runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04",
        gpu_type_id="NVIDIA A100 80GB PCIe",
        volume_in_gb=100,
        container_disk_in_gb=100,
        ports="8888/http",
        template_id=None,
        jupyter_port=8888,
        jupyter_token="token-123",
    )


def test_list_gpu_types() -> None:
    client = FakeRunPodClient()
    service = _make_service(client)
    result = service.list_gpu_types()
    assert "NVIDIA A100 80GB PCIe" in result


def test_list_gpu_types_with_memory_returns_all_by_default() -> None:
    client = FakeRunPodClient()
    service = _make_service(client)

    result = service.list_gpu_types_with_memory()

    assert ("NVIDIA A100 80GB PCIe", 80.0) in result
    assert ("NVIDIA H100", 80.0) in result
    assert ("NVIDIA RTX 4090", 24.0) in result


def test_list_gpu_types_with_memory_filters_min_40gb() -> None:
    client = FakeRunPodClient()
    service = _make_service(client)

    result = service.list_gpu_types_with_memory(min_memory_gb=40.0)

    assert ("NVIDIA A100 80GB PCIe", 80.0) in result
    assert ("NVIDIA H100", 80.0) in result
    assert all(name != "NVIDIA RTX 4090" for name, _ in result)


def test_list_gpu_types_with_memory_and_secure_price() -> None:
    client = FakeRunPodClient()
    service = _make_service(client)

    result = service.list_gpu_types_with_memory_and_secure_price()

    assert ("NVIDIA A100 80GB PCIe", 80.0, 1.39) in result
    assert ("NVIDIA H100", 80.0, 2.49) in result
    assert ("NVIDIA RTX 4090", 24.0, None) in result


def test_create_or_get_reuses_existing() -> None:
    client = FakeRunPodClient()
    existing = {"id": "pod-1", "name": "class-01-user01"}
    client.pods = [existing]
    service = _make_service(client)

    pod = service.create_or_get_pod(
        spec=_make_spec("class-01-user01"),
        existing_pod=existing,
        force_recreate=False,
        dry_run=False,
    )

    assert pod == existing
    assert client.created_payloads == []


def test_create_or_get_force_recreate_terminates_then_creates() -> None:
    client = FakeRunPodClient()
    existing = {"id": "pod-1", "name": "class-01-user01"}
    client.pods = [existing]
    service = _make_service(client)

    pod = service.create_or_get_pod(
        spec=_make_spec("class-01-user01"),
        existing_pod=existing,
        force_recreate=True,
        dry_run=False,
    )

    assert client.terminated_ids == ["pod-1"]
    assert pod["name"] == "class-01-user01"


def test_create_pod_retries_on_transient_failures() -> None:
    client = FakeRunPodClient()
    client.fail_create_count = 2
    service = _make_service(client)

    pod = service.create_pod(_make_spec("class-02-user02"), dry_run=False)

    assert pod["name"] == "class-02-user02"
    assert len(client.created_payloads) == 1


def test_stop_and_start_pod_actions() -> None:
    client = FakeRunPodClient()
    service = _make_service(client)

    service.stop_pod("pod-1", dry_run=False)
    service.start_pod("pod-1", dry_run=False)

    assert client.stopped_ids == ["pod-1"]
    assert client.resumed_ids == ["pod-1"]
