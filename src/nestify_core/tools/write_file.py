import os
from typing import Optional, Dict, Any
from datetime import datetime

TOOL_NAME = "write_file"
TOOL_DESCRIPTION = """Write text content to a file in the workspace.
Requires approval. Creates missing directories optionally and can backup existing files.

Usage:
```tool
{
  "name": "write_file",
  "args": {"path": "src/nestify_core/core.py", "content": "...new file content..."}
}
```
Optional args: `create_dirs` (bool, default true), `backup` (bool, default true), `encoding` (default "utf-8").
"""

TOOL_REQUIRES_APPROVAL = True


def _safe_resolve(path: str) -> Optional[str]:
    try:
        cwd = os.getcwd()
        abs_path = os.path.abspath(os.path.join(cwd, path))
        common = os.path.commonpath([cwd, abs_path])
        if common != cwd:
            return None
        return abs_path
    except Exception:
        return None


def write_file_tool(path: str, content: str, create_dirs: bool = True, backup: bool = True, encoding: str = "utf-8") -> Dict[str, Any]:
    safe_path = _safe_resolve(path)
    if not safe_path:
        return {"status": "error", "error": "Path outside workspace", "path": path}

    try:
        dir_path = os.path.dirname(safe_path)
        if dir_path and not os.path.exists(dir_path):
            if create_dirs:
                os.makedirs(dir_path, exist_ok=True)
            else:
                return {"status": "error", "error": "Directory does not exist", "path": path}

        bytes_before = None
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            try:
                bytes_before = os.path.getsize(safe_path)
            except Exception:
                bytes_before = None
            if backup:
                stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                bak_path = f"{safe_path}.{stamp}.bak"
                try:
                    with open(safe_path, "rb") as src, open(bak_path, "wb") as dst:
                        dst.write(src.read())
                    backup_path = bak_path
                except Exception:
                    backup_path = None
            else:
                backup_path = None
        else:
            backup_path = None

        with open(safe_path, "w", encoding=encoding, errors="replace") as f:
            f.write(content)

        bytes_after = os.path.getsize(safe_path)
        return {
            "status": "ok",
            "path": path,
            "bytes_before": bytes_before,
            "bytes_after": bytes_after,
            "backup": backup_path,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "path": path}
