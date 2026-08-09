import pytest

from utils.naming import build_pod_name, normalize_segment


def test_normalize_segment_keeps_alnum_and_hyphen_only() -> None:
    assert normalize_segment("User_01!@#") == "user-01"


def test_build_pod_name_is_deterministic() -> None:
    assert build_pod_name(3, "User_01") == "class-03-user-01"


def test_build_pod_name_handles_non_ascii_id() -> None:
    assert build_pod_name(1, "사용자") == "class-01-user"


def test_build_pod_name_rejects_negative_number() -> None:
    with pytest.raises(ValueError):
        build_pod_name(-1, "user01")
