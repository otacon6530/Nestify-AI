import os
from pathlib import Path


def get_log_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        base = Path(local) / "Nestify" / "logs"
    else:
        base = Path.home() / ".nestify" / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base
