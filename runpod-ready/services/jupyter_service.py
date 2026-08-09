from __future__ import annotations

from typing import Final

import requests


SUCCESS_CODES: Final[set[int]] = {200, 302, 303, 307, 308}


def check_jupyterlab_access(url: str, timeout_seconds: int = 20) -> tuple[bool, str]:
    """Return whether the provided JupyterLab URL is reachable."""
    connect_timeout = max(1, min(5, int(timeout_seconds)))
    read_timeout = max(1, int(timeout_seconds))
    try:
        response = requests.get(url, timeout=(connect_timeout, read_timeout), allow_redirects=True)
    except requests.RequestException as exc:
        return False, f"REQUEST_ERROR:{exc.__class__.__name__}"

    if response.status_code in SUCCESS_CODES:
        return True, f"HTTP_{response.status_code}"
    return False, f"HTTP_{response.status_code}"
