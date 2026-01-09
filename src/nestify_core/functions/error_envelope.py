import sys
import json
import traceback
from datetime import datetime, timezone

EXIT_CODES = {
    "OK": 0,
    "UNKNOWN": 1,
    "INVALID_ARGUMENT": 2,
    "CONFIG_ERROR": 3,
    "NETWORK_ERROR": 4,
    "PROVIDER_ERROR": 5,
    "PERMISSION_DENIED": 6,
    "TIMEOUT": 7,
}


def build_error_envelope(code: str, message: str, component: str, correlation_id: str, suggestion: str | None = None, exc: BaseException | None = None):
    stack = []
    if exc is not None:
        stack = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return {
        "code": code,
        "message": message,
        "component": component,
        "stack": stack,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "suggestion": suggestion,
    }


def emit_error(envelope: dict) -> int:
    try:
        sys.stderr.write(json.dumps(envelope) + "\n")
        sys.stderr.flush()
    except Exception:
        pass
    return EXIT_CODES.get(envelope.get("code", "UNKNOWN"), 1)
