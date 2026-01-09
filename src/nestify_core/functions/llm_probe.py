from __future__ import annotations
import socket
from urllib.parse import urlparse


class ProbeResult:
    def __init__(self, ok: bool, reason: str | None = None):
        self.ok = ok
        self.reason = reason


def probe(provider: str, base_url: str | None, timeout_seconds: int) -> ProbeResult:
    if provider == "echo":
        return ProbeResult(True)
    if not base_url:
        return ProbeResult(False, "Missing base_url for provider")
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return ProbeResult(False, "Invalid base_url")
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return ProbeResult(True)
    except Exception as e:
        return ProbeResult(False, f"Network error: {e}")
