from __future__ import annotations

import re
import unicodedata


def normalize_segment(value: str, fallback: str = "unknown") -> str:
    """Normalize text to lowercase alnum-hyphen form for resource names."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or fallback


def build_pod_name(number: int, user_id: str, prefix: str = "class") -> str:
    """Build a deterministic pod name from row number and user ID."""
    if number < 0:
        raise ValueError("number must be >= 0")

    normalized_prefix = normalize_segment(prefix, fallback="class")
    normalized_user_id = normalize_segment(user_id, fallback="user")
    return f"{normalized_prefix}-{number:02d}-{normalized_user_id}"
