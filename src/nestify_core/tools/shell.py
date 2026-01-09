import subprocess
from typing import Optional, Dict, Any

_APPROVE_ALL = False


def shell_tool(command: str, approve: Optional[str] = None) -> Dict[str, Any]:
    global _APPROVE_ALL
    cmd = command.strip()
    if _APPROVE_ALL or approve == "all":
        _APPROVE_ALL = True
        return _run(cmd)

    if approve == "yes":
        return _run(cmd)
    if approve == "no":
        return {"status": "denied", "message": "Command denied by user", "command": cmd}

    return {"status": "needs_approval", "command": cmd}


def _run(cmd: str) -> Dict[str, Any]:
    try:
        completed = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {
            "status": "ok",
            "command": cmd,
            "exit_code": completed.returncode,
            "stdout": completed.stdout[:20000],
            "stderr": completed.stderr[:20000],
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "command": cmd}
    except Exception as e:
        return {"status": "error", "command": cmd, "error": str(e)}
