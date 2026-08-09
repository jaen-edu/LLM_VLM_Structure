from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


UNHEALTHY_STATUSES = {"stopped", "crashed", "failed", "terminated", "error"}


@dataclass(slots=True)
class RecoveryDecision:
    recreate: bool
    reason: str | None = None


@dataclass(slots=True)
class RecoveryService:
    """Determine whether an existing pod should be recreated."""

    recreate_numbers: set[int] = field(default_factory=set)
    recreate_ids: set[str] = field(default_factory=set)
    recreate_if_unhealthy: bool = False

    def should_recreate(self, *, number: int, user_id: str, pod: dict[str, Any] | None) -> RecoveryDecision:
        if number in self.recreate_numbers:
            return RecoveryDecision(recreate=True, reason="number")

        if user_id.strip().lower() in self.recreate_ids:
            return RecoveryDecision(recreate=True, reason="id")

        if self.recreate_if_unhealthy and pod and self.is_unhealthy(pod):
            return RecoveryDecision(recreate=True, reason="unhealthy")

        return RecoveryDecision(recreate=False)

    @staticmethod
    def is_unhealthy(pod: dict[str, Any]) -> bool:
        candidates = [
            pod.get("status"),
            pod.get("desiredStatus"),
            pod.get("currentStatus"),
            (pod.get("machine") or {}).get("podHostStatus"),
        ]
        for status in candidates:
            if status is None:
                continue
            if str(status).strip().lower() in UNHEALTHY_STATUSES:
                return True
        return False
