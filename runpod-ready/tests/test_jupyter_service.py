from __future__ import annotations

import requests

from services.jupyter_service import check_jupyterlab_access


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def test_check_jupyterlab_access_success(monkeypatch) -> None:
    def _fake_get(url: str, timeout: tuple[int, int], allow_redirects: bool):
        assert timeout == (3, 3)
        return _FakeResponse(200)

    monkeypatch.setattr(requests, "get", _fake_get)
    ok, detail = check_jupyterlab_access("https://example.com", timeout_seconds=3)
    assert ok is True
    assert detail == "HTTP_200"


def test_check_jupyterlab_access_request_error(monkeypatch) -> None:
    def _fake_get(url: str, timeout: tuple[int, int], allow_redirects: bool):
        assert timeout == (3, 3)
        raise requests.Timeout("timed out")

    monkeypatch.setattr(requests, "get", _fake_get)
    ok, detail = check_jupyterlab_access("https://example.com", timeout_seconds=3)
    assert ok is False
    assert detail.startswith("REQUEST_ERROR")
