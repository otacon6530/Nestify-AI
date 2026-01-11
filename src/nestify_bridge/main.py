import sys
import json
import uuid
from nestify_core.core import Core


_PENDING_MESSAGES = []


def _write(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _read_next_message():
    if _PENDING_MESSAGES:
        return _PENDING_MESSAGES.pop(0)
    while True:
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except Exception:
            _write({"type": "error", "message": "invalid json"})


def _wait_for_shell_approval(command, reason=None):
    request_id = f"shell-{uuid.uuid4().hex}"
    _write({
        "type": "shell_approval_request",
        "command": command,
        "reason": reason,
        "id": request_id,
    })
    while True:
        line = sys.stdin.readline()
        if not line:
            return {"approved": False, "approve_all": False}
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            _write({"type": "error", "message": "invalid json"})
            continue
        if msg.get("type") == "shell_approval_response" and msg.get("id") == request_id:
            return {
                "approved": bool(msg.get("approved")),
                "approve_all": bool(msg.get("approve_all")),
            }
        _PENDING_MESSAGES.append(msg)


def main():
    try:
        core = Core()
        # Signal ready to the caller
        _write({"type": "ready"})

        while True:
            msg = _read_next_message()
            if msg is None:
                break
            try:
                if msg.get("type") == "exec":
                    text = msg.get("text", "")

                    def approval_callback(tool_name=None, tool_args=None, pending=None):
                        pending = pending or {}
                        tool_args = tool_args or {}
                        command = pending.get("command") or tool_args.get("command") or ""
                        reason = pending.get("message") or pending.get("status")
                        return _wait_for_shell_approval(command, reason)

                    try:
                        events = core.generate(text, stream=True, approval_callback=approval_callback)
                        for ev in events:
                            if isinstance(ev, dict) and ev.get("type") == "thinking":
                                _write({"type": "thinking", "value": ev.get("value", "")})
                            elif isinstance(ev, dict) and ev.get("type") == "token":
                                _write({"type": "token", "value": ev.get("value", "")})
                            elif isinstance(ev, dict) and ev.get("type") == "final":
                                _write({"type": "final", "result": ev.get("result", {})})
                    except Exception as e:
                        _write({"type": "error", "message": f"Exec error: {e}"})
                        sys.exit(1)
                elif msg.get("type") == "probe":
                    _write({"type": "ok"})
                elif msg.get("type") == "shell_approval_response":
                    # Late responses after callback consumption; ignore.
                    continue
                else:
                    _write({"type": "error", "message": "unknown command"})
            except Exception as e:
                _write({"type": "error", "message": f"Bridge loop error: {e}"})
                sys.exit(1)
    except Exception as e:
        _write({"type": "error", "message": f"Core init failed: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
