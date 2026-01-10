import subprocess
from typing import Optional, Dict, Any

_APPROVE_ALL = False



def shell_tool(command: str, approve: Optional[str] = None) -> Dict[str, Any]:
    """
    Run a shell command on the local system. Requires user approval unless previously approved for the session.
    Args:
        command: The shell command to execute.
        approve: Approval flag (None, 'yes', 'no', or 'all').
    Returns:
        Dict with status, command, and output or approval request.
    """
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


# Tool metadata for registration
TOOL_NAME = "shell"
TOOL_DESCRIPTION = (
    "Run a Windows shell command on the local system. Requires approval unless previously approved.\n"
    "\n"
    "Tool call examples:\n"
    "```tool\n"
    "{\n"
    "  \"name\": \"shell\",\n"
    "  \"args\": {\"command\": \"dir\"}\n"
    "}\n"
    "```\n"
    "\n"
    "or with approval:\n"
    "```tool\n"
    "{\n"
    "  \"name\": \"shell\",\n"
    "  \"args\": {\"command\": \"echo hello\", \"approve\": \"yes\"}\n"
    "}\n"
    "```\n"
)


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
