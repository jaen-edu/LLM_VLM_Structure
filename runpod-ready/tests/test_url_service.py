from services.url_service import build_runpod_url, build_ssh_command


def test_url_from_direct_runtime_field() -> None:
    pod = {"runtime": {"jupyterUrl": "https://example.runpod.net/lab"}}
    assert build_runpod_url(pod) == "https://example.runpod.net/lab"


def test_url_from_host_port_and_token() -> None:
    pod = {"runtime": {"host": "pod.example.com", "port": 8888, "token": "abc123"}}
    assert build_runpod_url(pod) == "https://pod.example.com:8888?token=abc123"


def test_url_prefers_proxy_when_pod_id_exists() -> None:
    pod = {
        "id": "p8hrsnucv79uid",
        "runtime": {"host": "100.65.31.93", "port": 60750},
    }
    assert build_runpod_url(pod, jupyter_port=8888) == "https://p8hrsnucv79uid-8888.proxy.runpod.net"


def test_url_from_ports_public_ip() -> None:
    pod = {
        "runtime": {
            "ports": [
                {"privatePort": 8888, "publicPort": 30123, "ip": "34.1.2.3"},
            ]
        }
    }
    assert build_runpod_url(pod) == "http://34.1.2.3:30123"


def test_url_fallback_to_proxy_pattern() -> None:
    pod = {"id": "abcde"}
    assert build_runpod_url(pod, jupyter_port=8888) == "https://abcde-8888.proxy.runpod.net"


def test_ssh_command_from_direct_runtime_field() -> None:
    pod = {"runtime": {"sshCommand": "ssh custom-user@ssh.runpod.io -i ~/.ssh/id_ed25519"}}
    assert build_ssh_command(pod) == "ssh custom-user@ssh.runpod.io -i ~/.ssh/id_ed25519"


def test_ssh_command_fallback_to_pod_id() -> None:
    pod = {"id": "t5jlk6quhxubew-64411d38"}
    assert build_ssh_command(pod) == "ssh t5jlk6quhxubew-64411d38@ssh.runpod.io -i ~/.ssh/id_ed25519"


def test_ssh_command_prefers_full_pod_id_over_short_runtime_user() -> None:
    pod = {
        "id": "fuwo0xenw86i9w-6441138e",
        "runtime": {"sshUser": "fuwo0xenw86i9w"},
    }
    assert build_ssh_command(pod) == "ssh fuwo0xenw86i9w-6441138e@ssh.runpod.io -i ~/.ssh/id_ed25519"


def test_ssh_command_uses_runtime_ip_hex_suffix() -> None:
    pod = {
        "id": "rkj0f419srcy56",
        "runtime": {
            "ports": [
                {"ip": "100.65.31.93", "privatePort": 8888, "publicPort": 60062, "type": "http"},
            ]
        },
    }
    assert build_ssh_command(pod) == "ssh rkj0f419srcy56-64411f5d@ssh.runpod.io -i ~/.ssh/id_ed25519"
