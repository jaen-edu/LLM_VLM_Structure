from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def build_runpod_url(pod: dict[str, Any], jupyter_port: int = 8888) -> str | None:
    """Build a user-facing Jupyter URL from pod runtime metadata."""
    runtime = pod.get("runtime") or {}

    direct_url = _extract_direct_url(runtime, pod)
    token = _extract_token(runtime, pod)

    if direct_url:
        return _append_token(direct_url, token)

    # Prefer the stable RunPod proxy endpoint when pod id is available.
    pod_id = pod.get("id")
    if pod_id:
        proxy_url = f"https://{pod_id}-{jupyter_port}.proxy.runpod.net"
        return _append_token(proxy_url, token)

    host_port = _extract_host_port(runtime, jupyter_port)
    if host_port is not None:
        host, port = host_port
        if host.startswith("http://") or host.startswith("https://"):
            base = host
        else:
            scheme = "https" if port in {443, 8443, jupyter_port} else "http"
            base = f"{scheme}://{host}:{port}"
        return _append_token(base, token)

    return None


def build_ssh_command(pod: dict[str, Any], identity_file: str = "~/.ssh/id_ed25519") -> str | None:
    """Build a user-facing SSH command from pod metadata."""
    runtime = pod.get("runtime") or {}

    for key in ("sshCommand", "sshProxyCommand", "basicSshCommand", "ssh"):
        value = runtime.get(key) or pod.get(key)
        if value:
            text = str(value).strip()
            if text:
                return text

    ssh_user = _extract_ssh_user(runtime, pod)
    if not ssh_user:
        return None

    ssh_host = str(runtime.get("sshHost") or pod.get("sshHost") or "ssh.runpod.io").strip() or "ssh.runpod.io"
    return f"ssh {ssh_user}@{ssh_host} -i {identity_file}"


def _extract_direct_url(runtime: dict[str, Any], pod: dict[str, Any]) -> str | None:
    for key in ("jupyterUrl", "url", "proxyUrl", "endpoint"):
        value = runtime.get(key) or pod.get(key)
        if value:
            return str(value).strip()

    ports = runtime.get("ports") or []
    if isinstance(ports, list):
        for port_info in ports:
            if not isinstance(port_info, dict):
                continue
            for key in ("url", "publicUrl", "endpoint"):
                value = port_info.get(key)
                if value:
                    return str(value).strip()
    return None


def _extract_host_port(runtime: dict[str, Any], jupyter_port: int) -> tuple[str, int] | None:
    ports = runtime.get("ports") or []
    if isinstance(ports, list):
        preferred = None
        fallback = None
        for port_info in ports:
            if not isinstance(port_info, dict):
                continue

            ip = port_info.get("ip") or port_info.get("publicIp")
            public_port = port_info.get("publicPort")
            private_port = port_info.get("privatePort")

            if ip and public_port:
                fallback = (str(ip), int(public_port))
                if int(private_port or -1) == jupyter_port:
                    preferred = fallback
                    break

        if preferred:
            return preferred
        if fallback:
            return fallback

    host = runtime.get("host") or runtime.get("domain") or runtime.get("ip")
    port = runtime.get("port") or runtime.get("httpPort") or runtime.get("jupyterPort")
    if host and port:
        return str(host), int(port)

    return None


def _extract_token(runtime: dict[str, Any], pod: dict[str, Any]) -> str | None:
    for key in ("token", "jupyterToken", "authToken"):
        value = runtime.get(key) or pod.get(key)
        if value:
            return str(value).strip()
    return None


def _append_token(url: str, token: str | None) -> str:
    if not token:
        return url

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("token", token)
    new_query = urlencode(query)
    return urlunparse(parsed._replace(query=new_query))


def _extract_ssh_user(runtime: dict[str, Any], pod: dict[str, Any]) -> str | None:
    pod_id = pod.get("id")
    if pod_id:
        base = str(pod_id).strip()
        if base:
            suffix = _extract_runtime_ipv4_hex_suffix(runtime)
            if suffix:
                return f"{base}-{suffix}"
            return base

    for key in ("sshUser", "sshUsername", "connectUser", "user"):
        value = runtime.get(key) or pod.get(key)
        if value:
            text = str(value).strip()
            if text:
                return text
    return None


def _extract_runtime_ipv4_hex_suffix(runtime: dict[str, Any]) -> str | None:
    ports = runtime.get("ports") or []
    if isinstance(ports, list):
        for port_info in ports:
            if not isinstance(port_info, dict):
                continue
            ip = port_info.get("ip") or port_info.get("publicIp")
            suffix = _ipv4_to_hex(ip)
            if suffix:
                return suffix

    return _ipv4_to_hex(runtime.get("host") or runtime.get("ip") or runtime.get("domain"))


def _ipv4_to_hex(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    parts = text.split(".")
    if len(parts) != 4:
        return None

    octets: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        num = int(part)
        if num < 0 or num > 255:
            return None
        octets.append(num)

    return "".join(f"{num:02x}" for num in octets)
