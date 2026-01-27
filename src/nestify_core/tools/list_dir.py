import os
from typing import Optional, Dict, Any, List

TOOL_NAME = "list_dir"
TOOL_DESCRIPTION = """List files and folders under a workspace path.
Safe, read-only.

Usage:
```tool
{
  "name": "list_dir",
  "args": {"path": "src/nestify_core"}
}
```
Optional args: `recursive` (bool, default false), `max_entries` (int, default 200).
"""

TOOL_REQUIRES_APPROVAL = False


def _safe_resolve(path: Optional[str]) -> Optional[str]:
    try:
        cwd = os.getcwd()
        path = path or "."
        abs_path = os.path.abspath(os.path.join(cwd, path))
        common = os.path.commonpath([cwd, abs_path])
        if common != cwd:
            return None
        return abs_path
    except Exception:
        return None


def list_dir_tool(path: Optional[str] = None, recursive: bool = False, max_entries: int = 200) -> Dict[str, Any]:
    safe_path = _safe_resolve(path)
    if not safe_path:
        return {"status": "error", "error": "Path outside workspace", "path": path}
    if not os.path.exists(safe_path) or not os.path.isdir(safe_path):
        return {"status": "error", "error": "Directory not found", "path": path}

    entries: List[Dict[str, Any]] = []
    try:
        if recursive:
            for root, dirs, files in os.walk(safe_path):
                for d in dirs:
                    rel = os.path.relpath(os.path.join(root, d), os.getcwd())
                    entries.append({"type": "dir", "path": rel})
                    if len(entries) >= max_entries:
                        break
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, os.getcwd())
                    try:
                        size = os.path.getsize(full)
                    except Exception:
                        size = None
                    entries.append({"type": "file", "path": rel, "size": size})
                    if len(entries) >= max_entries:
                        break
                if len(entries) >= max_entries:
                    break
        else:
            for name in os.listdir(safe_path):
                full = os.path.join(safe_path, name)
                rel = os.path.relpath(full, os.getcwd())
                if os.path.isdir(full):
                    entries.append({"type": "dir", "path": rel})
                else:
                    try:
                        size = os.path.getsize(full)
                    except Exception:
                        size = None
                    entries.append({"type": "file", "path": rel, "size": size})
                if len(entries) >= max_entries:
                    break
        return {"status": "ok", "path": path or ".", "entries": entries, "truncated": len(entries) >= max_entries}
    except Exception as e:
        return {"status": "error", "error": str(e), "path": path}
