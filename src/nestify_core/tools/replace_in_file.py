import os
from typing import Optional, Dict, Any

TOOL_NAME = "replace_in_file"
TOOL_DESCRIPTION = """Safely perform find/replace edits in a file.
Requires approval. Can scope by line range.

Usage:
```tool
{
  "name": "replace_in_file",
  "args": {
    "path": "src/nestify_core/core.py",
    "find": "self.logger = Logger(self.config)",
    "replace": "self.logger = logger or Logger(self.config)"
  }
}
```
Optional args: `count` (int, default -1 for all), `start`/`end` (line range).
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


def replace_in_file_tool(path: str, find: str, replace: str, count: int = -1, start: Optional[int] = None, end: Optional[int] = None, encoding: str = "utf-8") -> Dict[str, Any]:
    safe_path = _safe_resolve(path)
    if not safe_path:
        return {"status": "error", "error": "Path outside workspace", "path": path}
    if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
        return {"status": "error", "error": "File not found", "path": path}

    try:
        with open(safe_path, "r", encoding=encoding, errors="replace") as f:
            lines = f.readlines()
        start_idx = max(1, int(start) if start is not None else 1)
        end_idx = int(end) if end is not None else len(lines)
        before = "".join(lines)

        # Apply within line range
        head = lines[: start_idx - 1]
        body = lines[start_idx - 1 : end_idx]
        tail = lines[end_idx :]
        body_text = "".join(body)
        new_body_text = body_text.replace(find, replace, count if count is not None else -1)

        changed = new_body_text != body_text
        new_text = "".join(head) + new_body_text + "".join(tail)

        if changed:
            with open(safe_path, "w", encoding=encoding, errors="replace") as f:
                f.write(new_text)

        return {
            "status": "ok",
            "path": path,
            "changed": changed,
            "replacements": 0 if not changed else (new_body_text.count(replace)),
            "scoped": start is not None or end is not None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "path": path}
