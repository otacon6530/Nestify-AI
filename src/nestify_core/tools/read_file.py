import os
from typing import Optional, Dict, Any

TOOL_NAME = "read_file"
TOOL_DESCRIPTION = """Read a text file from the current workspace. Supports optional line ranges.
Usage examples:

`	ool
{
  "name": "read_file",
  "args": {"path": "src/nestify_core/core.py"}
}
`

With line range:

`	ool
{
  "name": "read_file",
  "args": {"path": "src/nestify_core/core.py", "start": 1, "end": 200}
}
`
"""

# Reading files is safe and does not execute anything
TOOL_REQUIRES_APPROVAL = False

MAX_BYTES_DEFAULT = 200_000  # 200 KB cap to avoid flooding


def _safe_resolve(path: str) -> Optional[str]:
    """Resolve path relative to workspace cwd and ensure it's within it."""
    try:
        cwd = os.getcwd()
        abs_path = os.path.abspath(os.path.join(cwd, path))
        common = os.path.commonpath([cwd, abs_path])
        if common != cwd:
            return None
        return abs_path
    except Exception:
        return None


def read_file_tool(path: str, start: Optional[int] = None, end: Optional[int] = None, max_bytes: Optional[int] = None) -> Dict[str, Any]:
    safe_path = _safe_resolve(path)
    if not safe_path:
        return {"status": "error", "error": "Path outside workspace", "path": path}
    if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
        return {"status": "error", "error": "File not found", "path": path}

    try:
        max_cap = int(max_bytes) if max_bytes is not None else MAX_BYTES_DEFAULT
        content: str
        if start is not None or end is not None:
            # Read by lines
            start_idx = max(1, int(start) if start is not None else 1)
            end_idx = int(end) if end is not None else start_idx + 499  # default up to 500 lines
            lines = []
            with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, start=1):
                    if i < start_idx:
                        continue
                    if i > end_idx:
                        break
                    lines.append(line)
            content = "".join(lines)
        else:
            # Read whole file (capped)
            with open(safe_path, "rb") as f:
                data = f.read(max_cap)
            content = data.decode("utf-8", errors="replace")
            # Indicate truncation if file larger
            try:
                size = os.path.getsize(safe_path)
                if size > len(content.encode("utf-8", errors="ignore")):
                    content += "\n\n[...truncated...]"
            except Exception:
                pass
        return {
            "status": "ok",
            "path": path,
            "start": start,
            "end": end,
            "content": content,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "path": path}
